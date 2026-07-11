"""Config flow for Lemonade Conversation Advanced."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
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
    CONF_API_KEY,
    CONF_CLEAN_RESPONSES,
    CONF_CONNECT_TIMEOUT,
    CONF_CONTROL_HA,
    CONF_DEBUG_MODE,
    CONF_END_WORDS,
    CONF_ENABLE_RAG,
    CONF_FIRST_DELTA_TIMEOUT,
    CONF_FOLLOW_UP_PHRASES,
    CONF_LLM_HASS_API,
    CONF_MAX_HISTORY,
    CONF_MAX_ITERATIONS,
    CONF_MAX_RETRIES,
    CONF_MAX_TOKENS,
    CONF_MODEL_NAME,
    CONF_RAG_TOP_K,
    CONF_REQUEST_TIMEOUT,
    CONF_RESPONSE_MODE,
    CONF_RETRY_BACKOFF,
    CONF_SERVER_URL,
    CONF_SYSTEM_PROMPT,
    CONF_TECHNICAL_PROMPT,
    CONF_TEMPERATURE,
    DEFAULT_CLEAN_RESPONSES,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_CONTROL_HA,
    DEFAULT_DEBUG_MODE,
    DEFAULT_END_WORDS,
    DEFAULT_ENABLE_RAG,
    DEFAULT_FIRST_DELTA_TIMEOUT,
    DEFAULT_FOLLOW_UP_PHRASES,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL_NAME,
    DEFAULT_RAG_TOP_K,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RESPONSE_MODE,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_SERVER_URL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Default subentry data
DEFAULT_CONVERSATION_DATA = {
    CONF_SYSTEM_PROMPT: "You are a helpful Home Assistant voice assistant.",
    CONF_TECHNICAL_PROMPT: "",
    CONF_TEMPERATURE: 0.7,
    CONF_MAX_TOKENS: 2048,
    CONF_MAX_HISTORY: DEFAULT_MAX_HISTORY,
    CONF_RESPONSE_MODE: DEFAULT_RESPONSE_MODE,
    CONF_CLEAN_RESPONSES: DEFAULT_CLEAN_RESPONSES,
    CONF_CONTROL_HA: DEFAULT_CONTROL_HA,
    CONF_MAX_ITERATIONS: DEFAULT_MAX_ITERATIONS,
    CONF_DEBUG_MODE: DEFAULT_DEBUG_MODE,
    CONF_LLM_HASS_API: None,
    CONF_ENABLE_RAG: DEFAULT_ENABLE_RAG,
    CONF_RAG_TOP_K: DEFAULT_RAG_TOP_K,
    CONF_FOLLOW_UP_PHRASES: DEFAULT_FOLLOW_UP_PHRASES,
    CONF_END_WORDS: DEFAULT_END_WORDS,
    CONF_REQUEST_TIMEOUT: DEFAULT_REQUEST_TIMEOUT,
    CONF_CONNECT_TIMEOUT: DEFAULT_CONNECT_TIMEOUT,
    CONF_FIRST_DELTA_TIMEOUT: DEFAULT_FIRST_DELTA_TIMEOUT,
    CONF_MAX_RETRIES: DEFAULT_MAX_RETRIES,
    CONF_RETRY_BACKOFF: DEFAULT_RETRY_BACKOFF,
}

DEFAULT_AI_TASK_DATA = {
    CONF_SYSTEM_PROMPT: "You are a helpful assistant.",
    CONF_TEMPERATURE: 0.7,
    CONF_MAX_TOKENS: 2048,
}


class LemonadeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lemonade Conversation Advanced."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._server_url: str = ""
        self._api_key: str | None = None
        self._model_options: list[str] = []

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {
            "conversation": LemonadeSubentryFlowHandler,
            "ai_task": LemonadeSubentryFlowHandler,
        }

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
        """Handle model selection and create entry with subentries."""
        errors: dict[str, str] = {}

        if user_input is not None:
            model_name = user_input[CONF_MODEL_NAME]

            # Store server config in data
            data = {
                CONF_SERVER_URL: self._server_url,
                CONF_API_KEY: self._api_key or "",
            }

            # Create entry with subentries
            return self.async_create_entry(
                title="Lemonade Conversation Advanced",
                data=data,
                subentries=[
                    {
                        "subentry_type": "conversation",
                        "data": {
                            CONF_MODEL_NAME: model_name,
                            **DEFAULT_CONVERSATION_DATA,
                        },
                        "title": f"Lemonade Assistant ({model_name})",
                        "unique_id": None,
                    },
                    {
                        "subentry_type": "ai_task",
                        "data": {
                            CONF_MODEL_NAME: model_name,
                            **DEFAULT_AI_TASK_DATA,
                        },
                        "title": f"Lemonade AI Task ({model_name})",
                        "unique_id": None,
                    },
                ],
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
                }
            ),
            errors=errors,
        )

    async def _test_connection(
        self, server_url: str, api_key: str | None
    ) -> None:
        """Test connection to Lemonade Server."""
        import aiohttp

        # Ensure URL has protocol
        if not server_url.startswith(("http://", "https://")):
            server_url = f"http://{server_url}"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        session = async_get_clientsession(self.hass)
        url = f"{server_url}/v1/health"

        try:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {text}")
                await resp.json()
        except asyncio.TimeoutError:
            raise Exception(f"Timeout connecting to {url}")
        except aiohttp.ClientError as err:
            raise Exception(f"Cannot connect to {url}: {err}") from err

    async def _fetch_models(self) -> list[dict[str, Any]]:
        """Fetch available models from Lemonade Server."""
        import aiohttp

        server_url = self._server_url
        if not server_url.startswith(("http://", "https://")):
            server_url = f"http://{server_url}"

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{server_url}/v1/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    return []
                data = await resp.json()
                return data.get("data", [])
        except Exception:
            return []


class LemonadeSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Handle subentry flow for Lemonade."""

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """User flow to create a subentry."""
        return await self.async_step_set_options(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration."""
        return await self.async_step_set_options(user_input)

    async def async_step_set_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set subentry options."""
        entry = self._get_entry()
        if entry.state is not config_entries.ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            # Normalize boolean fields from string "1"/"0" to proper bools
            for key in (CONF_ENABLE_RAG, CONF_CONTROL_HA, CONF_DEBUG_MODE, CONF_CLEAN_RESPONSES):
                if key in user_input:
                    user_input[key] = user_input[key] in ("1", True, "true")
            title = user_input.get(CONF_MODEL_NAME, "Lemonade")
            if self._is_new:
                return self.async_create_entry(
                    title=f"Lemonade ({title})",
                    data=user_input,
                )
            return self.async_update_and_abort(
                entry,
                self._get_reconfigure_subentry(),
                data=user_input,
            )

        # Get current options
        if self._is_new:
            options = DEFAULT_CONVERSATION_DATA.copy()
            if self._subentry_type == "ai_task":
                options = DEFAULT_AI_TASK_DATA.copy()
        else:
            options = self._get_reconfigure_subentry().data.copy()

        # Fetch models
        models = await self._fetch_models(entry)
        model_options = models or ["No models found"]

        # Fetch available LLM APIs for HA control
        llm_apis = llm.async_get_apis(self.hass)
        llm_api_options = [{"value": api.id, "label": api.name} for api in llm_apis]
        if not llm_api_options:
            llm_api_options = [{"value": "none", "label": "No LLM APIs available"}]

        # Helper to convert stored bool to selector value string
        def _bool_val(key: str, default: bool = False) -> str:
            val = options.get(key, default)
            return "1" if val else "0"

        return self.async_show_form(
            step_id="set_options",
            data_schema=vol.Schema(
                {
                    # ── Model & Prompts ─────────────────────────────
                    vol.Required(
                        CONF_MODEL_NAME,
                        default=options.get(CONF_MODEL_NAME),
                    ): SelectSelector(
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
                        CONF_SYSTEM_PROMPT,
                        default=options.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT),
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                    ),
                    vol.Optional(
                        CONF_TECHNICAL_PROMPT,
                        default=options.get(CONF_TECHNICAL_PROMPT, ""),
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                    ),
                    # ── Response Settings ───────────────────────────
                    vol.Optional(
                        CONF_TEMPERATURE,
                        default=options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0.0, max=2.0, step=0.05, mode=NumberSelectorMode.SLIDER)
                    ),
                    vol.Optional(
                        CONF_MAX_TOKENS,
                        default=options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                    ): NumberSelector(
                        NumberSelectorConfig(min=256, max=32768, step=256, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        CONF_MAX_HISTORY,
                        default=options.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY),
                    ): NumberSelector(
                        NumberSelectorConfig(min=2, max=50, step=1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        CONF_RESPONSE_MODE,
                        default=options.get(CONF_RESPONSE_MODE, DEFAULT_RESPONSE_MODE),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="none", label="None (pass-through)"),
                                SelectOptionDict(value="default", label="Default"),
                                SelectOptionDict(value="always", label="Always respond"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_CLEAN_RESPONSES,
                        default=_bool_val(CONF_CLEAN_RESPONSES, DEFAULT_CLEAN_RESPONSES),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="1", label="On"),
                                SelectOptionDict(value="0", label="Off"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    # ── Behaviour ──────────────────────────────────
                    vol.Optional(
                        CONF_CONTROL_HA,
                        default=_bool_val(CONF_CONTROL_HA, DEFAULT_CONTROL_HA),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="1", label="On"),
                                SelectOptionDict(value="0", label="Off"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_ITERATIONS,
                        default=options.get(CONF_MAX_ITERATIONS, DEFAULT_MAX_ITERATIONS),
                    ): NumberSelector(
                        NumberSelectorConfig(min=1, max=50, step=1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        CONF_DEBUG_MODE,
                        default=_bool_val(CONF_DEBUG_MODE, DEFAULT_DEBUG_MODE),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="1", label="On"),
                                SelectOptionDict(value="0", label="Off"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    # ── Home Assistant API & RAG ───────────────────
                    vol.Optional(
                        CONF_LLM_HASS_API,
                        default=options.get(CONF_LLM_HASS_API),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=llm_api_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="llm_hass_api",
                        )
                    ),
                    vol.Optional(
                        CONF_ENABLE_RAG,
                        default=_bool_val(CONF_ENABLE_RAG, DEFAULT_ENABLE_RAG),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="1", label="On"),
                                SelectOptionDict(value="0", label="Off"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_RAG_TOP_K,
                        default=options.get(CONF_RAG_TOP_K, DEFAULT_RAG_TOP_K),
                    ): NumberSelector(
                        NumberSelectorConfig(min=1, max=50, step=1, mode=NumberSelectorMode.BOX)
                    ),
                    # ── Follow-up & End Phrases ────────────────────
                    vol.Optional(
                        CONF_FOLLOW_UP_PHRASES,
                        default=options.get(CONF_FOLLOW_UP_PHRASES, DEFAULT_FOLLOW_UP_PHRASES),
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                    ),
                    vol.Optional(
                        CONF_END_WORDS,
                        default=options.get(CONF_END_WORDS, DEFAULT_END_WORDS),
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                    ),
                    # ── Timeouts & Retries ─────────────────────────
                    vol.Optional(
                        CONF_REQUEST_TIMEOUT,
                        default=options.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=600, step=5, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        CONF_CONNECT_TIMEOUT,
                        default=options.get(CONF_CONNECT_TIMEOUT, DEFAULT_CONNECT_TIMEOUT),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=120, step=1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        CONF_FIRST_DELTA_TIMEOUT,
                        default=options.get(CONF_FIRST_DELTA_TIMEOUT, DEFAULT_FIRST_DELTA_TIMEOUT),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=120, step=1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        CONF_MAX_RETRIES,
                        default=options.get(CONF_MAX_RETRIES, DEFAULT_MAX_RETRIES),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=10, step=1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        CONF_RETRY_BACKOFF,
                        default=options.get(CONF_RETRY_BACKOFF, DEFAULT_RETRY_BACKOFF),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0.0, max=30.0, step=0.5, mode=NumberSelectorMode.BOX)
                    ),
                }
            ),
        )

    async def _fetch_models(self, entry: config_entries.ConfigEntry) -> list[str]:
        """Fetch models from Lemonade Server."""
        import aiohttp
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        server_url = entry.data.get(CONF_SERVER_URL, "")
        api_key = entry.data.get(CONF_API_KEY, "")

        if not server_url.startswith(("http://", "https://")):
            server_url = f"http://{server_url}"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{server_url}/v1/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    return []
                data = await resp.json()
                return [m.get("id", "") for m in data.get("data", [])]
        except Exception:
            return []
