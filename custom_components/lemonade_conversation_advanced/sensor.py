"""Sensor platform for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .backends.openai_compat import LemonadeOpenAICompatBackend
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class LemonadeSensorData:
    """Data for Lemonade sensors."""

    health: Optional[Dict[str, Any]] = None
    system_info: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    models: Optional[list] = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = LemonadeDataCoordinator(hass, data["backend"])
    await coordinator.async_config_entry_first_refresh()
    async_add_entities([
        LemonadeSimpleSensor(coordinator, entry, SensorEntityDescription(key="health", name="Health", icon="mdi:heart-pulse"), "health"),
        LemonadeSimpleSensor(coordinator, entry, SensorEntityDescription(key="loaded_model", name="Loaded Model", icon="mdi:brain"), "loaded_model"),
        LemonadeSimpleSensor(coordinator, entry, SensorEntityDescription(key="vram_usage", name="VRAM Usage", native_unit_of_measurement=UnitOfInformation.MEGABYTES, state_class=SensorStateClass.MEASUREMENT, icon="mdi:memory"), "vram_usage"),
        LemonadeSimpleSensor(coordinator, entry, SensorEntityDescription(key="npu_usage", name="NPU Usage", icon="mdi:cpu-64-bit"), "npu_usage"),
        LemonadeSimpleSensor(coordinator, entry, SensorEntityDescription(key="model_count", name="Model Count", state_class=SensorStateClass.MEASUREMENT, icon="mdi:counter"), "model_count"),
        LemonadeSimpleSensor(coordinator, entry, SensorEntityDescription(key="inference_speed", name="Inference Speed", native_unit_of_measurement="tokens/s", state_class=SensorStateClass.MEASUREMENT, icon="mdi:speedometer"), "inference_speed"),
    ])


class LemonadeDataCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from Lemonade Server."""

    def __init__(self, hass: HomeAssistant, backend: LemonadeOpenAICompatBackend) -> None:
        """Initialize coordinator."""
        super().__init__(hass, _LOGGER, name="Lemonade Server Data", update_interval=30)
        self.backend = backend

    async def _async_update_data(self) -> LemonadeSensorData:
        """Fetch data from Lemonade Server."""
        try:
            return LemonadeSensorData(
                health=await self.backend.health_check(),
                system_info=await self.backend.get_system_info(),
                stats=await self.backend.get_stats(),
                models=await self.backend.list_models(show_all=False),
            )
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err


class LemonadeSimpleSensor(CoordinatorEntity[LemonadeDataCoordinator], SensorEntity):
    """Simple Lemonade sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LemonadeDataCoordinator, entry: ConfigEntry, description: SensorEntityDescription, key: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self.entity_description = description
        self._key = key
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="Lemonade Server", manufacturer="AMD", model="Lemonade Server")

    @property
    def native_value(self):
        """Return sensor state."""
        data = self.coordinator.data
        if not data:
            return None
        if self._key == "health":
            return (data.health or {}).get("status", "unknown")
        if self._key == "loaded_model":
            loaded = (data.system_info or {}).get("loaded_models", [])
            return loaded[0].get("model_name", "none") if loaded else "none"
        if self._key == "vram_usage":
            loaded = (data.system_info or {}).get("loaded_models", [])
            return loaded[0].get("memory_usage_mb") if loaded else None
        if self._key == "npu_usage":
            loaded = (data.system_info or {}).get("loaded_models", [])
            if any(model.get("device", "").lower() in ["npu", "ryzenai", "xdnn"] for model in loaded):
                return "Active"
            return "Inactive"
        if self._key == "model_count":
            return len(data.models or [])
        if self._key == "inference_speed":
            return (data.stats or {}).get("eval_rate")
        return None

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        data = self.coordinator.data
        if not data:
            return None
        if self._key == "health":
            return data.health
        if self._key in ["loaded_model", "vram_usage", "npu_usage"]:
            return data.system_info
        if self._key == "inference_speed":
            return data.stats
        return None
