"""Config flow for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import LemonadeClient
from .const import (
    CONF_API_KEY,
    CONF_DEFAULT_MODEL,
    CONF_LLM_HASS_API,
    CONF_MAX_TOKENS,
    CONF_MAX_TOOL_ITERATIONS,
    CONF_PROMPT,
    CONF_SERVER_URL,
    CONF_STREAMING,
    CONF_TEMPERATURE,
    CONF_TIMEOUT,
    CONF_TOP_K,
    CONF_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MAX_TOOL_ITERATIONS,
    DEFAULT_PROMPT,
    DEFAULT_STREAMING,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    DOMAIN,
    MAX_MAX_TOKENS,
    MAX_TEMPERATURE,
    MAX_TIMEOUT,
    MAX_TOP_K,
    MAX_TOP_P,
    MIN_MAX_TOKENS,
    MIN_TEMPERATURE,
    MIN_TIMEOUT,
    MIN_TOP_K,
    MIN_TOP_P,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lemonade Conversation Advanced."""

    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._server_url: str = ""
        self._api_key: str | None = None
        self._model_options: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

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
                self._model_options = [m.id for m in models] if models else []

                # Set unique ID to prevent duplicates
                await self.async_set_unique_id(self._server_url)
                self._abort_if_unique_id_configured()

                return await self.async_step_config()

            except Exception as err:
                _LOGGER.error("Connection test failed: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVER_URL): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.URL)
                    ),
                    vol.Optional(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "server_url_example": "http://10.0.98.218:13305"
            },
        )

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle model and parameters step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                CONF_SERVER_URL: self._server_url,
                CONF_API_KEY: self._api_key or "",
                CONF_DEFAULT_MODEL: user_input[CONF_DEFAULT_MODEL],
            }
            options = {
                CONF_TEMPERATURE: user_input[CONF_TEMPERATURE],
                CONF_TOP_P: user_input[CONF_TOP_P],
                CONF_TOP_K: user_input[CONF_TOP_K],
                CONF_MAX_TOKENS: user_input[CONF_MAX_TOKENS],
                CONF_STREAMING: user_input[CONF_STREAMING],
                CONF_PROMPT: user_input.get(CONF_PROMPT, DEFAULT_PROMPT),
                CONF_TIMEOUT: user_input[CONF_TIMEOUT],
                CONF_MAX_TOOL_ITERATIONS: user_input[CONF_MAX_TOOL_ITERATIONS],
            }
            return self.async_create_entry(
                title="Lemonade Conversation Advanced",
                data=data,
                options=options,
            )

        no_models = "No models found - pull a model first"
        model_options = self._model_options or [no_models]

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEFAULT_MODEL): vol.In(model_options),
                vol.Optional(
                    CONF_TEMPERATURE, default=DEFAULT_TEMPERATURE
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_TEMPERATURE,
                        max=MAX_TEMPERATURE,
                        step=0.05,
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_TOP_P, default=DEFAULT_TOP_P
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_TOP_P,
                        max=MAX_TOP_P,
                        step=0.05,
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_TOP_K, default=DEFAULT_TOP_K
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_TOP_K,
                        max=MAX_TOP_K,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_MAX_TOKENS, default=DEFAULT_MAX_TOKENS
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_MAX_TOKENS,
                        max=MAX_MAX_TOKENS,
                        step=256,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_STREAMING, default=DEFAULT_STREAMING
                ): bool,
                vol.Optional(
                    CONF_PROMPT, default=DEFAULT_PROMPT
                ): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT, multiline=True
                    )
                ),
                vol.Optional(
                    CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_TIMEOUT,
                        max=MAX_TIMEOUT,
                        step=5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_MAX_TOOL_ITERATIONS,
                    default=DEFAULT_MAX_TOOL_ITERATIONS,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=20,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="config", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return LemonadeOptionsFlow(config_entry)


class LemonadeOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Lemonade Conversation Advanced."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.entry.options
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_TEMPERATURE,
                        max=MAX_TEMPERATURE,
                        step=0.05,
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_TOP_P,
                    default=options.get(CONF_TOP_P, DEFAULT_TOP_P),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_TOP_P,
                        max=MAX_TOP_P,
                        step=0.05,
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_TOP_K,
                    default=options.get(CONF_TOP_K, DEFAULT_TOP_K),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_TOP_K,
                        max=MAX_TOP_K,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_MAX_TOKENS,
                    default=options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_MAX_TOKENS,
                        max=MAX_MAX_TOKENS,
                        step=256,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_STREAMING,
                    default=options.get(CONF_STREAMING, DEFAULT_STREAMING),
                ): bool,
                vol.Optional(
                    CONF_PROMPT,
                    default=options.get(CONF_PROMPT, DEFAULT_PROMPT),
                ): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.TEXT, multiline=True
                    )
                ),
                vol.Optional(
                    CONF_TIMEOUT,
                    default=options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_TIMEOUT,
                        max=MAX_TIMEOUT,
                        step=5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_MAX_TOOL_ITERATIONS,
                    default=options.get(
                        CONF_MAX_TOOL_ITERATIONS,
                        DEFAULT_MAX_TOOL_ITERATIONS,
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=20,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid auth."""
