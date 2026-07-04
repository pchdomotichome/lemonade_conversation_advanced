"""Lemonade Conversation Advanced integration for Home Assistant."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .backends.openai_compat import LemonadeOpenAICompatBackend
from .client import LemonadeClient
from .const import CONF_API_KEY, CONF_SERVER_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CONVERSATION, Platform.AI_TASK, Platform.SENSOR]

type LemonadeConfigEntry = ConfigEntry[LemonadeRuntimeData]


@dataclass
class LemonadeRuntimeData:
    """Runtime data for Lemonade config entry."""

    client: LemonadeClient
    backend: LemonadeOpenAICompatBackend


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Lemonade Conversation Advanced integration."""
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: LemonadeConfigEntry
) -> bool:
    """Set up Lemonade Conversation Advanced from a config entry."""
    _LOGGER.debug(
        "Setting up Lemonade Conversation Advanced entry: %s", entry.entry_id
    )

    # Get configuration
    server_url = entry.data.get(CONF_SERVER_URL)
    api_key = entry.data.get(CONF_API_KEY)

    # Create Lemonade client
    client = LemonadeClient(base_url=server_url, api_key=api_key)

    # Create backend
    backend = LemonadeOpenAICompatBackend(client)

    # Validate connection
    try:
        await backend.validate_connection()
    except Exception as err:
        _LOGGER.error("Failed to connect to Lemonade Server: %s", err)
        raise ConfigEntryNotReady from err

    # Store runtime data
    entry.runtime_data = LemonadeRuntimeData(client=client, backend=backend)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("Lemonade Conversation Advanced setup complete")
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: LemonadeConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(
    hass: HomeAssistant, entry: LemonadeConfigEntry
) -> bool:
    """Migrate old config entry."""
    _LOGGER.debug("Migrating config entry from version %s", entry.version)

    if entry.version == 2:
        # Version 2 -> 3: Restructure data for subentry pattern
        # Move model/prompt settings from options to a default subentry
        new_data = {
            "server_url": entry.data.get("server_url", ""),
            "api_key": entry.data.get("api_key", ""),
        }
        hass.config_entries.async_update_entry(
            entry, data=new_data, version=3
        )
        _LOGGER.info("Migrated config entry to version 3")

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LemonadeConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(
        "Unloading Lemonade Conversation Advanced entry: %s", entry.entry_id
    )

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Close client
        if entry.runtime_data:
            await entry.runtime_data.client.close()

    return unload_ok
