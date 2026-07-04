"""Conversation platform for Lemonade Conversation Advanced."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .agent import LemonadeConversationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lemonade Conversation Advanced conversation entity."""
    async_add_entities([LemonadeConversationEntity(hass, entry)])
