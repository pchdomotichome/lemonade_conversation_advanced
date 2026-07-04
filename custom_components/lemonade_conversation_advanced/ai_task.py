"""AI Task entities for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.ai_task import (
    AiTaskEntity,
    AiTaskEntityFeature,
    AsyncGenerateContentCallback,
    GenerateContent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LemonadeSummarizeTask(AiTaskEntity):
    """AI Task entity for summarization."""

    _attr_name = "Lemonade Summarize"
    _attr_supported_features = AiTaskEntityFeature.GENERATE

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

    async def async_generate_content(
        self,
        user_input: str,
        callback: AsyncGenerateContentCallback | None = None,
        **kwargs: Any,
    ) -> GenerateContent:
        """Generate content."""
        # TODO: Implement with backend
        return GenerateContent(
            content=f"Summary of: {user_input[:100]}...",
            response_type="application/text",
        )


class LemonadeExtractEntitiesTask(AiTaskEntity):
    """AI Task entity for entity extraction."""

    _attr_name = "Lemonade Extract Entities"
    _attr_supported_features = AiTaskEntityFeature.GENERATE

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

    async def async_generate_content(
        self,
        user_input: str,
        callback: AsyncGenerateContentCallback | None = None,
        **kwargs: Any,
    ) -> GenerateContent:
        """Generate content."""
        # TODO: Implement with backend
        return GenerateContent(
            content=f"Entities extracted from: {user_input[:100]}...",
            response_type="application/json",
        )


class LemonadeIntentClassifierTask(AiTaskEntity):
    """AI Task entity for intent classification."""

    _attr_name = "Lemonade Intent Classifier"
    _attr_supported_features = AiTaskEntityFeature.GENERATE

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

    async def async_generate_content(
        self,
        user_input: str,
        callback: AsyncGenerateContentCallback | None = None,
        **kwargs: Any,
    ) -> GenerateContent:
        """Generate content."""
        # TODO: Implement with backend
        return GenerateContent(
            content=f"Intent classified for: {user_input[:100]}...",
            response_type="application/json",
        )


class LemonadeThemeGeneratorTask(AiTaskEntity):
    """AI Task entity for theme generation."""

    _attr_name = "Lemonade Theme Generator"
    _attr_supported_features = AiTaskEntityFeature.GENERATE

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

    async def async_generate_content(
        self,
        user_input: str,
        callback: AsyncGenerateContentCallback | None = None,
        **kwargs: Any,
    ) -> GenerateContent:
        """Generate content."""
        # TODO: Implement with backend
        return GenerateContent(
            content=f"Theme generated for: {user_input[:100]}...",
            response_type="application/yaml",
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
