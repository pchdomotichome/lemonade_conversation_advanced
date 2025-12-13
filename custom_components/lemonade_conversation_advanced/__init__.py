"""Integration for Lemonade Conversation Advanced."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .llm import LemonadeLLM

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lemonade Conversation Advanced from a config entry."""
    
    # Guardar datos de configuración
    hass.data.setdefault(DOMAIN, {})
    
    server_url = entry.data.get("server_url")
    
    # Validar conexión con Lemonade Server
    try:
        llm = LemonadeLLM(hass, server_url)
        await llm.health_check()
    except Exception as err:
        _LOGGER.error(f"Failed to connect to Lemonade Server: {err}")
        raise ConfigEntryNotReady from err
    
    # Registrar componentes secundarios
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok

async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up the Lemonade Conversation Advanced integration."""
    return True