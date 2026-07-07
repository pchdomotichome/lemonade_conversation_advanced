"""RAG mode for Lemonade Conversation Advanced.

Local keyword-based entity retrieval — no embedding API calls needed.
Entity index is cached to disk for fast startup.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as async_get_entity_reg
from homeassistant.helpers.area_registry import async_get as async_get_area_reg

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

RAG_TOP_K = 12
RAG_SCORE_THRESHOLD = 1
RAG_CACHE_DIR_NAME = "lemonade_rag_cache"

_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "de", "del", "en", "con", "y",
    "que", "es", "por", "para", "se", "no", "a", "e", "o", "u", "lo",
    "como", "más", "pero", "sus", "le", "ya", "este", "entre", "porque",
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "is",
    "are", "it", "its", "my", "your",
}


class RAGIndex:
    """Local keyword-based entity index — no embedding API calls."""

    def __init__(self, cache_dir: str, api_key: str = "") -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict[str, Any]] = []

    async def load(self) -> None:
        cache_file = self._cache_dir / "index.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text())
            self._entries = data.get("entries", [])
            _LOGGER.info("RAG index loaded: %d entities", len(self._entries))
        else:
            self._entries = []

    async def save(self) -> None:
        cache_file = self._cache_dir / "index.json"
        cache_file.write_text(json.dumps({"entries": self._entries}, ensure_ascii=False))

    async def refresh(self, hass: HomeAssistant) -> int:
        self._entries.clear()
        entity_reg = async_get_entity_reg(hass)
        area_reg = async_get_area_reg(hass)

        for entry in entity_reg.entities.values():
            area_name = ""
            if entry.area_id:
                area_obj = area_reg.async_get(entry.area_id)
                area_name = area_obj.name if area_obj else ""
            tokens = self._tokenize(self._build_entity_text(entry, area_name))
            self._entries.append({
                "entity_id": entry.entity_id,
                "name": entry.name or entry.original_name or "",
                "domain": entry.domain,
                "area": area_name,
                "tokens": list(tokens),
            })

        await self.save()
        _LOGGER.info("RAG index refreshed: %d entities", len(self._entries))
        return len(self._entries)

    async def query(
        self, prompt: str, top_k: int = RAG_TOP_K
    ) -> list[dict[str, Any]]:
        if not self._entries:
            return []

        prompt_tokens = self._tokenize(prompt)
        if not prompt_tokens:
            return self._entries[:top_k]

        results: list[tuple[int, dict]] = []
        for e in self._entries:
            entity_tokens = set(e["tokens"])
            score = len(prompt_tokens & entity_tokens)
            if score >= RAG_SCORE_THRESHOLD:
                results.append((score, e))

        results.sort(key=lambda t: t[0], reverse=True)
        return [e for _, e in results[:top_k]]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        text = text.lower()
        text = re.sub(r"[^a-záéíóúüñ0-9\s]", " ", text)
        tokens = {t for t in text.split() if t not in _STOPWORDS and len(t) > 1}
        return tokens

    @staticmethod
    def _build_entity_text(entry: Any, area_name: str) -> str:
        parts = [entry.entity_id.replace("_", " ")]
        if entry.name:
            parts.append(entry.name)
        if entry.domain:
            parts.append(entry.domain)
        if area_name:
            parts.append(f"area {area_name}")
        if entry.device_class:
            parts.append(f"device class {entry.device_class}")
        return " ".join(parts)


async def build_rag_instructions(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> str | None:
    cache_dir = os.path.join(hass.config.config_dir, RAG_CACHE_DIR_NAME)
    api_key = config_entry.data.get("api_key", "")
    index = RAGIndex(cache_dir, api_key)
    await index.load()

    if not index._entries:
        entity_reg = async_get_entity_reg(hass)
        if not entity_reg.entities:
            return None
        index = RAGIndex(cache_dir, api_key)
        await index.refresh(hass)

    entity_list = []
    area_reg = async_get_area_reg(hass)
    for e in index._entries:
        entity_list.append(f"{e['entity_id']} ({e['domain']}) in {e['area'] or 'unassigned'}")

    return "Entities: " + "\n".join(entity_list)
