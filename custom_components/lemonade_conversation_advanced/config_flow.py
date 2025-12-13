"""Config flow for Lemonade Conversation Advanced integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import aiohttp  # Importar aiohttp aquí

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_SERVER_URL, CONF_DEFAULT_MODEL, CONF_TEMPERATURE, CONF_MAX_TOKENS, CONF_STREAMING

_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lemonade Conversation Advanced."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                # Validar conexión con Lemonade Server
                await self._test_connection(user_input)
                return self.async_create_entry(
                    title="Lemonade Conversation Advanced", 
                    data=user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_SERVER_URL): str,
                vol.Optional(CONF_DEFAULT_MODEL): str,
                vol.Optional(CONF_TEMPERATURE, default=0.7): vol.Coerce(float),
                vol.Optional(CONF_MAX_TOKENS, default=512): int,
                vol.Optional(CONF_STREAMING, default=True): bool,
            }),
            errors=errors
        )

    async def _test_connection(self, config: dict[str, Any]) -> None:
        """Test connection to Lemonade Server."""
        from aiohttp import ClientError
        
        server_url = config[CONF_SERVER_URL].rstrip('/')
        
        try:
            # Hacer una llamada de prueba a la salud del servidor
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{server_url}/api/v1/health") as resp:
                    if resp.status != 200:
                        raise CannotConnect()
        except ClientError as err:
            raise CannotConnect() from err

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
    
class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""