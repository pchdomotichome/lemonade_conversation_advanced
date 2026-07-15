"""Select entity exposing the Sarcastic-Argentine tone level.

This entity is created automatically by the integration so users can change the
assistant's sarcasm intensity from a dashboard card, an automation or a service
without manually creating an input_select. The conversation agent reads its
state (Normal/Bajo/Medio/Alto) to pick the matching tone block.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

SARCASM_LEVEL_OPTIONS = ["Normal", "Bajo", "Medio", "Alto"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sarcasm-level select entity."""
    async_add_entities([LemonadeSarcasmSelect(entry)])


class LemonadeSarcasmSelect(SelectEntity):
    """Sarcasm intensity level for the Sarcastic Argentine persona."""

    _attr_has_entity_name = True
    _attr_name = "Nivel de Sarcasmo"
    _attr_options = SARCASM_LEVEL_OPTIONS
    _attr_current_option = "Normal"
    _attr_should_poll = False
    _attr_suggested_object_id = "lemonade_sarcasm_level"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_sarcasm_level"
        self._entry = entry

    async def async_added_to_hass(self) -> None:
        """Restore the last selected option after a restart."""
        await super().async_added_to_hass()
        state = self.hass.states.get(self.entity_id)
        if state is not None and state.state in self._attr_options:
            self._attr_current_option = state.state

    async def async_select_option(self, option: str) -> None:
        """Change the sarcasm level."""
        self._attr_current_option = option
        self.async_write_ha_state()
