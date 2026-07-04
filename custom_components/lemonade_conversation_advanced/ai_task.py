"""AI Task support for Lemonade Conversation Advanced."""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Any,
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
    _attr_supported_features = (
        ai_task.AITaskEntityFeature.GENERATE_DATA
    )

    def __init__(
        self,
        entry: Any,
        subentry: ConfigSubentry,
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
        options = self.subentry.data
        model = options.get(CONF_MODEL, "")

        # Provide LLM data
        try:
            await chat_log.async_provide_llm_data(
                llm.LLMContext(
                    platform=DOMAIN,
                    context=None,
                    user_prompt=task.instructions,
                    assistant_response=None,
                    tool_result=None,
                ),
                None,
                None,
                None,
            )
        except Exception as err:
            raise HomeAssistantError(f"Error providing LLM data: {err}") from err

        # Build messages
        messages = [
            {"role": "user", "content": task.instructions}
        ]

        # Get the backend client
        backend = self.entry.runtime_data.backend

        # Call the LLM
        try:
            response = await backend.chat_completion(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                stream=False,
                timeout=30,
            )

            if not hasattr(response, "choices") or not response.choices:
                raise HomeAssistantError("No response from model")

            text = response.choices[0].message.content or ""

            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=text,
            )

        except Exception as err:
            raise HomeAssistantError(f"Error generating data: {err}") from err
