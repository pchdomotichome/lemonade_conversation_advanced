"""Sensor for Lemonade Assistant Advanced."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .llm import LemonadeLLM

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    server_url = entry.data.get("server_url")
    
    # Crear entidad de sensor
    async_add_entities([
        LemonadeHealthSensor(hass, server_url),
        LemonadeModelSensor(hass, server_url)
    ])

class LemonadeHealthSensor(SensorEntity):
    """Sensor for Lemonade Server health status."""

    def __init__(self, hass: HomeAssistant, server_url: str) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self.server_url = server_url
        self._attr_name = "Lemonade Server Health"
        self._attr_unique_id = f"{DOMAIN}_health"
        self._state = None

    async def async_update(self) -> None:
        """Update sensor state."""
        try:
            llm = LemonadeLLM(self.hass, self.server_url)
            health_data = await llm.health_check()
            self._state = health_data.get("status", "unknown")
        except Exception as err:
            _LOGGER.error(f"Error updating health sensor: {err}")
            self._state = "error"

class LemonadeModelSensor(SensorEntity):
    """Sensor for currently loaded model."""

    def __init__(self, hass: HomeAssistant, server_url: str) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self.server_url = server_url
        self._attr_name = "Lemonade Loaded Model"
        self._attr_unique_id = f"{DOMAIN}_model"
        self._state = None

    async def async_update(self) -> None:
        """Update sensor state."""
        try:
            llm = LemonadeLLM(self.hass, self.server_url)
            health_data = await llm.health_check()
            model_name = health_data.get("model_loaded", "none")
            self._state = model_name
        except Exception as err:
            _LOGGER.error(f"Error updating model sensor: {err}")
            self._state = "error"