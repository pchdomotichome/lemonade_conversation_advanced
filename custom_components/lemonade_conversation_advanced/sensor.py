"""Sensors exposing Lemonade Server telemetry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LemonadeTelemetryCoordinator

ATTR_LOADED_MODELS = "loaded_models"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lemonade telemetry sensors from a config entry."""
    coordinator: LemonadeTelemetryCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]["coordinator"]

    async_add_entities(
        [
            LemonadeVersionSensor(coordinator),
            LemonadeModelLoadedSensor(coordinator),
            LemonadeCpuSensor(coordinator),
            LemonadeMemorySensor(coordinator),
            LemonadeGpuSensor(coordinator),
            LemonadeVramSensor(coordinator),
            LemonadeNpuSensor(coordinator),
            LemonadeTtftAvgSensor(coordinator),
            LemonadeTpsAvgSensor(coordinator),
            LemonadeLastInputTokensSensor(coordinator),
            LemonadeLastOutputTokensSensor(coordinator),
        ]
    )


class _LemonadeSensor(CoordinatorEntity[LemonadeTelemetryCoordinator], SensorEntity):
    """Base telemetry sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LemonadeTelemetryCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._key}"

    @property
    def _key(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    @property
    def available(self) -> bool:
        return self.coordinator.data.get("available", False)


class LemonadeVersionSensor(_LemonadeSensor):
    _attr_icon = "mdi:lemon"
    _attr_translation_key = "server_version"

    @property
    def _key(self) -> str:
        return "server_version"

    @property
    def native_value(self):
        return self.coordinator.data.get("health", {}).get("version")


class LemonadeModelLoadedSensor(_LemonadeSensor):
    _attr_icon = "mdi:brain"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "model_loaded"

    @property
    def _key(self) -> str:
        return "model_loaded"

    @property
    def native_value(self):
        return len(
            self.coordinator.data.get("health", {}).get("all_models_loaded", [])
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        models = self.coordinator.data.get("health", {}).get("all_models_loaded", [])
        return {
            ATTR_LOADED_MODELS: [
                {
                    "model_name": m.get("model_name"),
                    "type": m.get("type"),
                    "device": m.get("device"),
                    "recipe": m.get("recipe"),
                    "pinned": m.get("pinned"),
                }
                for m in models
            ]
        }


class LemonadeCpuSensor(_LemonadeSensor):
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_translation_key = "cpu_percent"

    @property
    def _key(self) -> str:
        return "cpu_percent"

    @property
    def native_value(self):
        return self.coordinator.data.get("system_stats", {}).get("cpu_percent")


class LemonadeMemorySensor(_LemonadeSensor):
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "GiB"
    _attr_translation_key = "memory_gb"

    @property
    def _key(self) -> str:
        return "memory_gb"

    @property
    def native_value(self):
        return self.coordinator.data.get("system_stats", {}).get("memory_gb")


class LemonadeGpuSensor(_LemonadeSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_translation_key = "gpu_percent"

    @property
    def _key(self) -> str:
        return "gpu_percent"

    @property
    def native_value(self):
        return self.coordinator.data.get("system_stats", {}).get("gpu_percent")


class LemonadeVramSensor(_LemonadeSensor):
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "GiB"
    _attr_translation_key = "vram_gb"

    @property
    def _key(self) -> str:
        return "vram_gb"

    @property
    def native_value(self):
        return self.coordinator.data.get("system_stats", {}).get("vram_gb")


class LemonadeNpuSensor(_LemonadeSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_translation_key = "npu_percent"

    @property
    def _key(self) -> str:
        return "npu_percent"

    @property
    def native_value(self):
        return self.coordinator.data.get("system_stats", {}).get("npu_percent")


class LemonadeTtftAvgSensor(_LemonadeSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "s"
    _attr_translation_key = "ttft_avg"

    @property
    def _key(self) -> str:
        return "ttft_avg"

    @property
    def native_value(self):
        return _round(self.coordinator.data.get("ttft_avg"), 2)


class LemonadeTpsAvgSensor(_LemonadeSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "tok/s"
    _attr_translation_key = "tps_avg"

    @property
    def _key(self) -> str:
        return "tps_avg"

    @property
    def native_value(self):
        return _round(self.coordinator.data.get("tps_avg"), 2)


class LemonadeLastInputTokensSensor(_LemonadeSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "last_input_tokens"

    @property
    def _key(self) -> str:
        return "last_input_tokens"

    @property
    def native_value(self):
        return self.coordinator.data.get("stats", {}).get("input_tokens")


class LemonadeLastOutputTokensSensor(_LemonadeSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "last_output_tokens"

    @property
    def _key(self) -> str:
        return "last_output_tokens"

    @property
    def native_value(self):
        return self.coordinator.data.get("stats", {}).get("output_tokens")


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)
