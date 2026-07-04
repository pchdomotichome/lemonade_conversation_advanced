"""Config flow for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
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

from .const import (
    DOMAIN,
    CONF_SERVER_URL,
    CONF_API_KEY,
    CONF_MODEL_NAME,
    CONF_SYSTEM_PROMPT,
    CONF_TEMPERATURE,
    CONF_MAX_TOKENS,
    CONF_MAX_HISTORY,
    CONF_MAX_ITERATIONS,
    CONF_LEMONADE_PORT,
    CONF_CONTROL_HA,
    CONF_FOLLOW_UP_MODE,
    CONF_RESPONSE_MODE,
    CONF_DEBUG_MODE,
    CONF_TIMEOUT,
    DEFAULT_SERVER_URL,
    DEFAULT_MODEL_NAME,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_LEMONADE_PORT,
    DEFAULT_CONTROL_HA,
    DEFAULT_FOLLOW_UP_MODE,
    DEFAULT_RESPONSE_MODE,
    DEFAULT_DEBUG_MODE,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class LemonadeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lemonade Conversation Advanced."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._server_url: str = ""
        self._api_key: str | None = None
        self._model_options: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - server connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            server_url = user_input[CONF_SERVER_URL].rstrip("/")
            api_key = user_input.get(CONF_API_KEY)

            # Test connection to Lemonade Server
            try:
                await self._test_connection(server_url, api_key)
            except Exception as err:
                _LOGGER.error("Connection test failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                self._server_url = server_url
                self._api_key = api_key

                # Set unique ID to prevent duplicates
                await self.async_set_unique_id(server_url)
                self._abort_if_unique_id_configured()

                return await self.async_step_model()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SERVER_URL, default=DEFAULT_SERVER_URL
                    ): TextSelector(
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

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle model selection and basic config."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store server config in data
            data = {
                CONF_SERVER_URL: self._server_url,
                CONF_API_KEY: self._api_key or "",
            }

            # Store model config in options
            options = {
                CONF_MODEL_NAME: user_input[CONF_MODEL_NAME],
                CONF_SYSTEM_PROMPT: user_input.get(
                    CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT
                ),
                CONF_TEMPERATURE: user_input.get(
                    CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                ),
                CONF_MAX_TOKENS: user_input.get(
                    CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS
                ),
            }

            return self.async_create_entry(
                title=f"Lemonade ({user_input[CONF_MODEL_NAME]})",
                data=data,
                options=options,
            )

        # Fetch available models
        try:
            models = await self._fetch_models()
            self._model_options = [m.get("id", "") for m in models]
        except Exception as err:
            _LOGGER.warning("Could not fetch models: %s", err)
            self._model_options = []

        model_options = self._model_options or ["No models found"]

        return self.async_show_form(
            step_id="model",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL_NAME): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=m, label=m)
                                for m in model_options
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    ),
                    vol.Optional(
                        CONF_SYSTEM_PROMPT, default=DEFAULT_SYSTEM_PROMPT
                    ): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT, multiline=True
                        )
                    ),
                    vol.Optional(
                        CONF_TEMPERATURE, default=DEFAULT_TEMPERATURE
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0.0, max=2.0, step=0.05,
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_TOKENS, default=DEFAULT_MAX_TOKENS
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=256, max=32768, step=256,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle advanced settings (optional)."""
        if user_input is not None:
            # Update options with advanced settings
            return self.async_create_entry(
                title="Lemonade Conversation Advanced",
                data={
                    CONF_SERVER_URL: self._server_url,
                    CONF_API_KEY: self._api_key or "",
                },
                options=user_input,
            )

        return self.async_show_form(
            step_id="advanced",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MAX_HISTORY, default=DEFAULT_MAX_HISTORY
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=50, step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_ITERATIONS, default=DEFAULT_MAX_ITERATIONS
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=20, step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_CONTROL_HA, default=DEFAULT_CONTROL_HA
                    ): bool,
                    vol.Optional(
                        CONF_FOLLOW_UP_MODE, default=DEFAULT_FOLLOW_UP_MODE
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="none", label="None"),
                                SelectOptionDict(value="smart", label="Smart"),
                                SelectOptionDict(value="always", label="Always"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_DEBUG_MODE, default=DEFAULT_DEBUG_MODE
                    ): bool,
                    vol.Optional(
                        CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=5, max=120, step=5,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    async def _test_connection(
        self, server_url: str, api_key: str | None
    ) -> None:
        """Test connection to Lemonade Server."""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{server_url}/v1/health",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    raise Exception(f"HTTP {resp.status}")
                await resp.json()

    async def _fetch_models(self) -> list[dict[str, Any]]:
        """Fetch available models from Lemonade Server."""
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self._server_url}/v1/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    return []
                data = await resp.json()
                return data.get("data", [])

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> LemonadeOptionsFlow:
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

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MODEL_NAME,
                        default=options.get(CONF_MODEL_NAME, DEFAULT_MODEL_NAME),
                    ): str,
                    vol.Optional(
                        CONF_SYSTEM_PROMPT,
                        default=options.get(
                            CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT
                        ),
                    ): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT, multiline=True
                        )
                    ),
                    vol.Optional(
                        CONF_TEMPERATURE,
                        default=options.get(
                            CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0.0, max=2.0, step=0.05,
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_TOKENS,
                        default=options.get(
                            CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=256, max=32768, step=256,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_HISTORY,
                        default=options.get(
                            CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=50, step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_ITERATIONS,
                        default=options.get(
                            CONF_MAX_ITERATIONS, DEFAULT_MAX_ITERATIONS
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=20, step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_CONTROL_HA,
                        default=options.get(
                            CONF_CONTROL_HA, DEFAULT_CONTROL_HA
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_DEBUG_MODE,
                        default=options.get(
                            CONF_DEBUG_MODE, DEFAULT_DEBUG_MODE
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_TIMEOUT,
                        default=options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=5, max=120, step=5,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
