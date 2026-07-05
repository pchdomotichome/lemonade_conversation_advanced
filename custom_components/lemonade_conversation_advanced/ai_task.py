"""AI Task support for Lemonade Conversation Advanced."""

from __future__ import annotations

import json
import logging
from typing import Any, override

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import LemonadeBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task":
            continue

        async_add_entities(
            [LemonadeAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LemonadeAITaskEntity(
    ai_task.AITaskEntity,
    LemonadeBaseEntity,
):
    """Lemonade AI Task entity."""

    def __init__(self, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_supported_features = ai_task.AITaskEntityFeature.GENERATE_DATA

    @override
    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        import aiohttp
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        options = self.subentry.data
        server_url = self.entry.data.get("server_url", "")
        api_key = self.entry.data.get("api_key", "")
        model = options.get("model_name", "")
        system_prompt = options.get("system_prompt", "You are a helpful assistant.")
        temperature = options.get("temperature", 0.7)
        max_tokens = options.get("max_tokens", 2048)

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
