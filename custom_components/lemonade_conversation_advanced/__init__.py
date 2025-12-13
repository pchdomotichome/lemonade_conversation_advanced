"""Integration for Lemonade Assistant Advanced."""
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
    """Set up Lemonade Assistant Advanced from a config entry."""
    
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
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    
    # Registrar servicios personalizados
    async def load_model_service(call):
        """Servicio para cargar un modelo."""
        model_name = call.data.get("model_name")
        if not model_name:
            _LOGGER.error("No model name provided for load_model service")
            return
            
        try:
            await llm.load_model(model_name)
            _LOGGER.info(f"Model {model_name} loaded successfully")
        except Exception as err:
            _LOGGER.error(f"Failed to load model {model_name}: {err}")
    
    hass.services.async_register(
        DOMAIN, 
        "load_model", 
        load_model_service
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok