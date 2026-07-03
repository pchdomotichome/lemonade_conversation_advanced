"""AI Task platform for Lemonade Conversation Advanced.

This file intentionally keeps the initial AI Task implementation conservative.
Advanced task entities will be added after validating the base integration against
Home Assistant's current ai_task API version.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AI Task platform.

    Placeholder for Phase 2. Keeping this platform loadable allows the integration
    to declare ai_task as a dependency without creating entities until the exact
    HA ai_task entity API is validated in the target HA version.
    """
    _LOGGER.debug("AI Task platform setup for Lemonade Conversation Advanced")
