"""Config flow for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_LLM_HASS_API, CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers import llm
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
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_SERVER_URL,
    CONF_STREAMING,
    CONF_TEMPERATURE,
    CONF_TIMEOUT,
    CONF_TOP_K,
    CONF_TOP_P,
    DEFAULT_MAX_TOKENS,
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


class LemonadeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lemonade Conversation Advanced."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._server_url: str = ""
        self._api_key: str | None = None
        self._model_options: list[str] = []

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {
            "conversation": ConversationFlowHandler,
            "ai_task": AITaskFlowHandler,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

                return self.async_create_entry(
                    title="Lemonade Conversation Advanced",
                    data=user_input,
                )

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


class LemonadeSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for Lemonade."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self._model_options: list[str] = []

    async def _get_models(self) -> None:
        """Fetch models from Lemonade Server."""
        entry = self._get_entry()
        client = LemonadeClient(
            base_url=entry.data[CONF_SERVER_URL],
            api_key=entry.data.get(CONF_API_KEY),
        )
        try:
            models = await client.list_models(show_all=True)
            self._model_options = [m.id for m in models] if models else []
        finally:
            await client.close()


class ConversationFlowHandler(LemonadeSubentryFlowHandler):
    """Handle conversation subentry flow."""

    _subentry_type = "conversation"
    _title = "Lemonade Assistant"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create a conversation agent."""
        return await self.async_step_init(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a conversation agent."""
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage conversation agent configuration."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            # Store LLM API as list
            llm_api = user_input.get(CONF_LLM_HASS_API)
            if isinstance(llm_api, str):
                user_input[CONF_LLM_HASS_API] = [llm_api]
            elif not llm_api:
                user_input.pop(CONF_LLM_HASS_API, None)

            return self.async_create_entry(
                title=user_input.get(CONF_MODEL, "Lemonade Assistant"),
                data=user_input,
            )

        # Fetch available models
        try:
            await self._get_models()
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="cannot_connect")

        model_options = self._model_options or ["No models found"]

        # Get available LLM APIs
        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
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
                        CONF_LLM_HASS_API,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=hass_apis, multiple=True
                        )
                    ),
                    vol.Optional(
                        CONF_PROMPT, default=DEFAULT_PROMPT
                    ): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT, multiline=True
                        )
                    ),
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
                        CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_TIMEOUT,
                            max=MAX_TIMEOUT,
                            step=5,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )


class AITaskFlowHandler(LemonadeSubentryFlowHandler):
    """Handle AI task subentry flow."""

    _subentry_type = "ai_task"
    _title = "Lemonade AI Task"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create an AI task."""
        return await self.async_step_init(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of an AI task."""
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage AI task configuration."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_MODEL, "Lemonade AI Task"),
                data=user_input,
            )

        # Fetch available models
        try:
            await self._get_models()
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="cannot_connect")

        model_options = self._model_options or ["No models found"]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
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
                        CONF_PROMPT, default=DEFAULT_PROMPT
                    ): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT, multiline=True
                        )
                    ),
                }
            ),
        )
