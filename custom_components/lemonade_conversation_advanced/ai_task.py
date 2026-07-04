"""AI Task entities for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.ai_task import (
    AITaskEntity,
    AITaskEntityFeature,
    GenDataTask,
    GenDataTaskResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LemonadeSummarizeTask(AITaskEntity):
    """AI Task entity for summarization."""

    _attr_name = "Lemonade Summarize"
    _attr_supported_features = AITaskEntityFeature.GENERATE_DATA

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the task."""
        self.entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_summarize"

    @property
    def device_info(self) -> dict[str, Any] | None:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Lemonade Server",
            "manufacturer": "AMD",
            "model": "Lemonade Server",
        }

    async def _async_generate_data(
        self, task: GenDataTask, chat_log: Any
    ) -> GenDataTaskResult:
        """Generate data."""
        return GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=f"Summary of: {task.instructions[:100]}...",
        )


class LemonadeExtractEntitiesTask(AITaskEntity):
    """AI Task entity for entity extraction."""

    _attr_name = "Lemonade Extract Entities"
    _attr_supported_features = AITaskEntityFeature.GENERATE_DATA

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the task."""
        self.entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_extract_entities"

    @property
    def device_info(self) -> dict[str, Any] | None:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Lemonade Server",
            "manufacturer": "AMD",
            "model": "Lemonade Server",
        }

    async def _async_generate_data(
        self, task: GenDataTask, chat_log: Any
    ) -> GenDataTaskResult:
        """Generate data."""
        return GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=f"Entities extracted from: {task.instructions[:100]}...",
        )


class LemonadeIntentClassifierTask(AITaskEntity):
    """AI Task entity for intent classification."""

    _attr_name = "Lemonade Intent Classifier"
    _attr_supported_features = AITaskEntityFeature.GENERATE_DATA

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the task."""
        self.entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_intent_classifier"

    @property
    def device_info(self) -> dict[str, Any] | None:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Lemonade Server",
            "manufacturer": "AMD",
            "model": "Lemonade Server",
        }

    async def _async_generate_data(
        self, task: GenDataTask, chat_log: Any
    ) -> GenDataTaskResult:
        """Generate data."""
        return GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=f"Intent classified for: {task.instructions[:100]}...",
        )


class LemonadeThemeGeneratorTask(AITaskEntity):
    """AI Task entity for theme generation."""

    _attr_name = "Lemonade Theme Generator"
    _attr_supported_features = AITaskEntityFeature.GENERATE_DATA

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the task."""
        self.entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_theme_generator"

    @property
    def device_info(self) -> dict[str, Any] | None:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Lemonade Server",
            "manufacturer": "AMD",
            "model": "Lemonade Server",
        }

    async def _async_generate_data(
        self, task: GenDataTask, chat_log: Any
    ) -> GenDataTaskResult:
        """Generate data."""
        return GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=f"Theme generated for: {task.instructions[:100]}...",
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    entities = [
        LemonadeSummarizeTask(entry),
        LemonadeExtractEntitiesTask(entry),
        LemonadeIntentClassifierTask(entry),
        LemonadeThemeGeneratorTask(entry),
    ]
    async_add_entities(entities)
