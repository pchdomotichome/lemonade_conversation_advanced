"""Agent implementation for Lemonade Conversation Advanced."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import DOMAIN
from .llm import LemonadeLLM
from .conversation import async_process

_LOGGER = logging.getLogger(__name__)

class LemonadeConversationAgent(ConversationEntity):
    """Lemonade Conversation Agent."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._attr_name = "Lemonade Assistant"
        self._attr_unique_id = f"{DOMAIN}_agent"

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a conversation request."""
        config = self.entry.data
        
        # Llamar al proceso de conversación
        return await async_process(
            self.hass,
            config,
            user_input
        )

    @property
    def supported_features(self) -> int:
        """Return the features supported by this agent."""
        return 0

    @property
    def device_info(self) -> Dict[str, Any] | None:
        """Return device info for this agent."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Lemonade",
            "model": "Advanced Assistant",
        }