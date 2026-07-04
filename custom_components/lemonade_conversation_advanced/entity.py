"""Base entity for Lemonade Conversation Advanced."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


class LemonadeBaseEntity:
    """Base class for Lemonade entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        subentry: ConfigSubentry | None = None,
    ) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry

    @property
    def base_unique_id(self) -> str:
        """Return the base unique ID."""
        return f"{DOMAIN}_{self.entry.entry_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name="Lemonade Server",
            manufacturer="AMD",
            model="Lemonade Server",
            sw_version=self.entry.data.get("version", "unknown"),
        )
