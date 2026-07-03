"""Config flow for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .client import LemonadeClient
from .const import (
    CONF_API_KEY,
    CONF_DEFAULT_MODEL,
    CONF_MAX_TOKENS,
    CONF_SERVER_URL,
    CONF_STREAMING,
    CONF_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_STREAMING,
    DEFAULT_TEMPERATURE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONNECTION_SCHEMA = vol.Schema({
    vol.Required(CONF_SERVER_URL): str,
    vol.Optional(CONF_API_KEY): str,
})

PARAMETERS_SCHEMA = vol.Schema({
    vol.Optional(CONF_TEMPERATURE, default=DEFAULT_TEMPERATURE): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
    vol.Optional(CONF_MAX_TOKENS, default=DEFAULT_MAX_TOKENS): vol.All(vol.Coerce(int), vol.Range(min=1, max=32768)),
    vol.Optional(CONF_STREAMING, default=DEFAULT_STREAMING): bool,
})


class LemonadeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lemonade Conversation Advanced."""

    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._server_url: str = ""
        self._api_key: Optional[str] = None
        self._model_options: List[str] = []
        self._selected_model: str = ""

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                client = LemonadeClient(
                    base_url=user_input[CONF_SERVER_URL],
                    api_key=user_input.get(CONF_API_KEY),
                )
                await client.health_check()
                models = await client.list_models(show_all=True)
                await client.close()
                self._server_url = user_input[CONF_SERVER_URL]
                self._api_key = user_input.get(CONF_API_KEY)
                self._model_options = [model.id for model in models] if models else []
                return await self.async_step_model()
            except Exception as err:
                _LOGGER.error("Connection test failed: %s", err)
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=CONNECTION_SCHEMA,
            errors=errors,
            description_placeholders={"server_url_example": "http://10.0.98.218:13305"},
        )

    async def async_step_model(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Handle model selection step."""
        errors = {}
        no_models = "No models found - pull a model first"
        if user_input is not None:
            if user_input[CONF_DEFAULT_MODEL] == no_models:
                errors[CONF_DEFAULT_MODEL] = "no_models"
            else:
                self._selected_model = user_input[CONF_DEFAULT_MODEL]
                return await self.async_step_parameters()
        schema = vol.Schema({
            vol.Required(CONF_DEFAULT_MODEL): vol.In(self._model_options or [no_models]),
        })
        return self.async_show_form(step_id="model", data_schema=schema, errors=errors)

    async def async_step_parameters(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Handle parameters step."""
        if user_input is not None:
            data = {
                CONF_SERVER_URL: self._server_url,
                CONF_API_KEY: self._api_key or "",
            }
            options = {
                CONF_DEFAULT_MODEL: self._selected_model,
                CONF_TEMPERATURE: user_input[CONF_TEMPERATURE],
                CONF_MAX_TOKENS: user_input[CONF_MAX_TOKENS],
                CONF_STREAMING: user_input[CONF_STREAMING],
            }
            return self.async_create_entry(
                title="Lemonade Conversation Advanced",
                data=data,
                options=options,
            )
        return self.async_show_form(step_id="parameters", data_schema=PARAMETERS_SCHEMA)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return LemonadeOptionsFlow(config_entry)


class LemonadeOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Lemonade Conversation Advanced."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry

    async def async_step_init(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema({
            vol.Optional(CONF_TEMPERATURE, default=self.entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(CONF_MAX_TOKENS, default=self.entry.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)): vol.All(vol.Coerce(int), vol.Range(min=1, max=32768)),
            vol.Optional(CONF_STREAMING, default=self.entry.options.get(CONF_STREAMING, DEFAULT_STREAMING)): bool,
            vol.Optional(CONF_DEFAULT_MODEL, default=self.entry.options.get(CONF_DEFAULT_MODEL, "")): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid auth."""
