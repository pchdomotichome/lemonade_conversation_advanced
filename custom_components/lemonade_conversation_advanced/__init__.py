"""Lemonade Conversation Advanced integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.typing import ConfigType

from .backends import get_backend_class
from .backends.openai_compat import LemonadeOpenAICompatBackend
from .client import LemonadeClient
from .const import (
    CONF_API_KEY,
    CONF_DEFAULT_MODEL,
    CONF_SERVER_URL,
    DOMAIN,
    LLM_API_DESCRIPTION,
    LLM_API_NAME,
)
from .llm_api import LemonadeLLMAPI
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

# Backend registry (extensible)
BACKEND_TO_CLS = {
    "openai_compat": LemonadeOpenAICompatBackend,
}

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Lemonade Conversation Advanced integration."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lemonade Conversation Advanced from a config entry."""
    _LOGGER.debug("Setting up Lemonade Conversation Advanced entry: %s", entry.entry_id)

    # Get configuration
    server_url = entry.data.get(CONF_SERVER_URL)
    api_key = entry.data.get(CONF_API_KEY)

    # Create Lemonade client
    client = LemonadeClient(base_url=server_url, api_key=api_key)

    # Create backend
    backend_cls = BACKEND_TO_CLS.get("openai_compat")
    backend = backend_cls(client)

    # Validate connection
    try:
        await backend.validate_connection()
    except Exception as err:
        _LOGGER.error("Failed to connect to Lemonade Server: %s", err)
        raise ConfigEntryNotReady from err

    # Store in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "backend": backend,
        "entry": entry,
    }

    # Register LLM API
    llm_api = LemonadeLLMAPI(hass, entry, backend)
    hass.data[DOMAIN][entry.entry_id]["llm_api"] = llm_api

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["conversation", "sensor", "ai_task"])

    # Register services
    await async_setup_services(hass, entry)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Lemonade Conversation Advanced setup complete")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Lemonade Conversation Advanced entry: %s", entry.entry_id)

    # Unload services
    await async_unload_services(hass, entry)

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["conversation", "sensor", "ai_task"]
    )

    if unload_ok:
        # Close client
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        client = data.get("client")
        if client:
            await client.close()

    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug("Updating options for entry: %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry."""
    _LOGGER.debug("Migrating config entry from version %s", entry.version)

    # Version 1 -> 2: Add subentries support
    if entry.version == 1:
        new_data = dict(entry.data)
        new_options = dict(entry.options)
        # Migration logic here
        hass.config_entries.async_update_entry(entry, data=new_data, options=new_options, version=2)
        _LOGGER.info("Migrated config entry to version 2")

    return True