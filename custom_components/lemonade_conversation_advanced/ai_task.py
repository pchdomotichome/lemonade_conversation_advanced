"""AI Task support for Lemonade Conversation Advanced."""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    CONF_SERVER_URL,
    CONF_API_KEY,
    CONF_MODEL_NAME,
    CONF_SYSTEM_PROMPT,
    CONF_TEMPERATURE,
    CONF_MAX_TOKENS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry_id, subentry in config_entry.subentries.items():
        if subentry.subentry_type != "ai_task":
            continue

        async_add_entities(
            [LemonadeAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry_id,
        )


class LemonadeAITaskEntity(ai_task.AITaskEntity):
    """Lemonade AI Task entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = ai_task.AITaskEntityFeature.GENERATE_DATA

    def __init__(
        self,
        entry: ConfigEntry,
        subentry: Any,
    ) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        import aiohttp
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        options = self.subentry.data
        server_url = self.entry.data.get(CONF_SERVER_URL, "")
        api_key = self.entry.data.get(CONF_API_KEY, "")
        model = options.get(CONF_MODEL_NAME, "")
        system_prompt = options.get(CONF_SYSTEM_PROMPT, "You are a helpful assistant.")
        temperature = options.get(CONF_TEMPERATURE, 0.7)
        max_tokens = options.get(CONF_MAX_TOKENS, 2048)

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task.instructions},
        ]

        # Call Lemonade Server
        session = async_get_clientsession(self.hass)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with session.post(
                f"{server_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise HomeAssistantError(f"LLM error: {text}")

                data = await resp.json()
                content = data["choices"][0]["message"]["content"]

                return ai_task.GenDataTaskResult(
                    conversation_id=chat_log.conversation_id,
                    data=content,
                )

        except aiohttp.ClientError as err:
            raise HomeAssistantError(f"Connection error: {err}") from err
