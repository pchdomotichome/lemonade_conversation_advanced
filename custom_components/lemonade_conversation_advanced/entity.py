"""Base entity for Lemonade Conversation Advanced."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, CONF_MODEL_NAME


class LemonadeBaseEntity:
    """Base class for Lemonade entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_name = subentry.title
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="AMD",
            model=subentry.data.get(CONF_MODEL_NAME, "Lemonade"),
            entry_type=dr.DeviceEntryType.SERVICE,
        )
