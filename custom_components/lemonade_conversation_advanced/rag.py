"""RAG mode for Lemonade Conversation Advanced.

Uses Lemonade Server embeddings endpoint for semantic entity retrieval.
Simple cosine-similarity retrieval — no vector DB dependency.
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as async_get_entity_reg
from homeassistant.helpers.area_registry import async_get as async_get_area_reg

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

EMBED_MODEL = "Qwen3-Embedding-0.6B-GGUF"
RAG_TOP_K = 12
RAG_SCORE_THRESHOLD = 0.15
RAG_CACHE_DIR_NAME = "lemonade_rag_cache"


class RAGIndex:
    """Simple embedding index for Home Assistant entities."""

    def __init__(self, cache_dir: str) -> None:
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

    async def _embed(self, session: aiohttp.ClientSession, text: str, server_url: str) -> list[float]:
        # Lemonade Server embeddings endpoint (OpenAI-compatible)
        # Try both /v1/embeddings and /embeddings paths
        for path in ["/v1/embeddings", "/embeddings"]:
            url = f"{server_url.rstrip('/')}{path}"
            _LOGGER.debug("Trying embedding URL: %s", url)
            try:
                resp = await session.post(
                    url,
                    json={"model": EMBED_MODEL, "input": text},
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                )
                if resp.status != 200:
                    continue
                body = await resp.json()
                embedding = body["data"][0]["embedding"]
                _LOGGER.debug("Got embedding with %d dims", len(embedding))
                return embedding
            except Exception:
                continue
        raise RuntimeError("All embedding endpoints failed")

    async def refresh(
        self, hass: HomeAssistant, session: aiohttp.ClientSession, server_url: str
    ) -> int:
        await self.load()
        self._entries.clear()

        entity_reg = async_get_entity_reg(hass)
        area_reg = async_get_area_reg(hass)

        for entry in entity_reg.entities.values():
            area_name = ""
            if entry.area_id:
                area_obj = area_reg.async_get(entry.area_id)
                area_name = area_obj.name if area_obj else ""

            text = self._build_entity_text(entry, area_name)
            try:
                emb = await self._embed(session, text, server_url)
                self._entries.append(
                    {
                        "entity_id": entry.entity_id,
                        "name": entry.name or entry.original_name or "",
                        "domain": entry.domain,
                        "area": area_name,
                        "text": text,
                        "embedding": emb,
                    }
                )
            except Exception as err:
                _LOGGER.warning("Skipping %s: %s", entry.entity_id, err)
                continue

        await self.save()
        _LOGGER.info("RAG index refreshed: %d entities", len(self._entries))
        return len(self._entries)

    async def query(
        self, session: aiohttp.ClientSession, prompt: str, server_url: str, top_k: int = RAG_TOP_K
    ) -> list[dict[str, Any]]:
        if not self._entries:
            return []

        emb = await self._embed(session, prompt, server_url)
        results: list[tuple[float, dict]] = []

        for e in self._entries:
            score = cosine(emb, e["embedding"])
            if score >= RAG_SCORE_THRESHOLD:
                results.append((score, e))

        results.sort(key=lambda t: t[0], reverse=True)
        return [e for _, e in results[:top_k]]

    @staticmethod
    def _build_entity_text(entry: Any, area_name: str) -> str:
        parts = [entry.entity_id.replace("_", " ")]
        if entry.name:
            parts.append(entry.name)
        if entry.domain:
            parts.append(entry.domain)
        if area_name:
            parts.append(f"area {area_name}")
        if entry.unit_of_measurement:
            parts.append(f"unit {entry.unit_of_measurement}")
        if entry.device_class:
            parts.append(f"device class {entry.device_class}")
        return " ".join(parts)


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


async def build_rag_instructions(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> str | None:
    """Build RAG-enhanced instructions string, or plain entity list if no RAG.

    Returns None when RAG is disabled, caller uses default instructions.
    """
    server_url = config_entry.data.get("server_url", "")
    if not server_url:
        return None

    cache_dir = os.path.join(hass.config.config_dir, RAG_CACHE_DIR_NAME)
    index = RAGIndex(cache_dir)
    await index.load()

    if not index._entries:
        _LOGGER.debug("RAG index empty — using plain entity list")
        return None

    # If entity list changed, rebuild
    entity_reg = async_get_entity_reg(hass)
    current_ids = set(entity_reg.entities.keys())
    cached_ids = {e["entity_id"] for e in index._entries}
    if current_ids != cached_ids:
        async with aiohttp.ClientSession() as session:
            await index.refresh(hass, session, server_url)

    # Semantic search against the prompt (passed in as context)
    # For now return entity list; full semantic search per-query done in conversation.py
    entity_list = []
    for entry in entity_reg.entities.values():
        area_name = ""
        if entry.area_id:
            ao = async_get_area_reg(hass).async_get(entry.area_id)
            area_name = ao.name if ao else ""
        entity_list.append(f"{entry.entity_id} ({entry.domain}) in {area_name or 'unassigned'}")

    return "Entities: " + "\n".join(entity_list)
