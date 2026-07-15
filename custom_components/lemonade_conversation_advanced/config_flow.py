"""Config flow for Lemonade Conversation Advanced."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv, llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
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
    AI_TASK_EXTRACTION_NONE,
    AI_TASK_EXTRACTION_STRUCTURE,
    AI_TASK_EXTRACTION_TOOL,
    CONF_AI_TASK_ENABLE_VISION,
    CONF_INCLUDE_EXAMPLES,
    CONF_PERSONALITY,
    CONF_PERSONALITY_EXAMPLES,
    CONF_PERSONALITY_PROMPT,
    CONF_PERSONALITY_PROMPTS,
    build_personalities,
    resolve_persona_prompt,
    CONF_SARCASM_ENTITY,
    DEFAULT_INCLUDE_EXAMPLES,
    DEFAULT_PERSONALITY,
    DEFAULT_SARCASM_ENTITY,
    PERSONALITY_BUTLER,
    PERSONALITY_CUSTOM,
    PERSONALITY_DEFAULT,
    PERSONALITY_EXAMPLES,
    PERSONALITY_PIRATE,
    PERSONALITY_ROBOT,
    PERSONALITY_SARCASTIC_AR,
    CONF_AI_TASK_EXTRACTION_METHOD,
    CONF_AI_TASK_RETRIES,
    CONF_API_KEY,
    CONF_CLEAN_RESPONSES,
    CONF_CONFIRMATION_REQUIRED,
    CONF_CONNECT_TIMEOUT,
    CONF_CONTROL_HA,
    CONF_CONTEXT_TEMPLATES,
    CONF_DEBUG_MODE,
    CONF_EXPOSE_SCENES,
    CONF_EXPOSE_SCRIPTS,
    CONF_END_WORDS,
    CONF_ENABLE_RAG,
    CONF_ENABLE_STREAMING,
    CONF_ENABLED_DOMAINS,
    CONF_ENABLE_WEB_SEARCH,
    CONF_ENTITY_ALIASES,
    CONF_RESPECT_EXPOSURE,
    CONF_SEARXNG_ENGINES,
    CONF_SEARXNG_MAX_RESULTS,
    CONF_SEARXNG_URL,
    CONF_FIRST_DELTA_TIMEOUT,
    CONF_FOLLOW_UP_PHRASES,
    CONF_LLM_HASS_API,
    CONF_MAX_HISTORY,
    CONF_MAX_ITERATIONS,
    CONF_MAX_RETRIES,
    CONF_MAX_TOKENS,
    CONF_MAX_ENTITIES_PER_DISCOVERY,
    CONF_MODEL_NAME,
    CONF_RAG_TOP_K,
    CONF_REQUEST_TIMEOUT,
    CONF_RESPONSE_MODE,
    CONF_RETRY_BACKOFF,
    CONF_SERVER_URL,
    CONF_SYSTEM_PROMPT,
    CONF_TECHNICAL_PROMPT,
    CONF_TEMPERATURE,
    DEFAULT_AI_TASK_EXTRACTION_METHOD,
    DEFAULT_AI_TASK_RETRIES,
    DEFAULT_AI_TASK_SYSTEM_PROMPT,
    DEFAULT_CLEAN_RESPONSES,
    DEFAULT_CONFIRMATION_REQUIRED,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_CONTEXT_TEMPLATES,
    DEFAULT_CONTROL_HA,
    DEFAULT_DEBUG_MODE,
    DEFAULT_EXPOSE_SCENES,
    DEFAULT_EXPOSE_SCRIPTS,
    DEFAULT_END_WORDS,
    DEFAULT_ENABLE_RAG,
    DEFAULT_ENABLED_DOMAINS,
    DEFAULT_ENABLE_WEB_SEARCH,
    DEFAULT_ENTITY_ALIASES,
    DEFAULT_ENABLE_STREAMING,
    DEFAULT_SEARXNG_ENGINES,
    DEFAULT_SEARXNG_MAX_RESULTS,
    DEFAULT_SEARXNG_URL,
    DEFAULT_FIRST_DELTA_TIMEOUT,
    DEFAULT_FOLLOW_UP_PHRASES,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MAX_ENTITIES_PER_DISCOVERY,
    DEFAULT_MODEL_NAME,
    DEFAULT_RAG_TOP_K,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RESPECT_EXPOSURE,
    DEFAULT_RESPONSE_MODE,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_SERVER_URL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    MAX_MAX_ENTITIES_PER_DISCOVERY,
    MIN_MAX_ENTITIES_PER_DISCOVERY,
    MAX_SEARXNG_MAX_RESULTS,
    MIN_SEARXNG_MAX_RESULTS,
    SUPPORTED_DOMAINS,
    MAX_AI_TASK_RETRIES,
    MIN_AI_TASK_RETRIES,
    MAX_CONNECT_TIMEOUT,
    MAX_FIRST_DELTA_TIMEOUT,
    MAX_MAX_HISTORY,
    MAX_MAX_ITERATIONS,
    MAX_MAX_RETRIES,
    MAX_MAX_TOKENS,
    MAX_RAG_TOP_K,
    MAX_REQUEST_TIMEOUT,
    MAX_RETRY_BACKOFF,
    MAX_TEMPERATURE,
    MIN_CONNECT_TIMEOUT,
    MIN_FIRST_DELTA_TIMEOUT,
    MIN_MAX_HISTORY,
    MIN_MAX_ITERATIONS,
    MIN_MAX_RETRIES,
    MIN_MAX_TOKENS,
    MIN_RAG_TOP_K,
    MIN_REQUEST_TIMEOUT,
    MIN_RETRY_BACKOFF,
    MIN_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)

# Default subentry data
DEFAULT_CONVERSATION_DATA = {
    CONF_SYSTEM_PROMPT: "You are a helpful Home Assistant voice assistant.",
    CONF_PERSONALITY: DEFAULT_PERSONALITY,
    CONF_SARCASM_ENTITY: DEFAULT_SARCASM_ENTITY,
    CONF_INCLUDE_EXAMPLES: DEFAULT_INCLUDE_EXAMPLES,
    CONF_PERSONALITY_EXAMPLES: "",
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
    CONF_ENABLE_STREAMING: DEFAULT_ENABLE_STREAMING,
    CONF_RESPECT_EXPOSURE: DEFAULT_RESPECT_EXPOSURE,
    CONF_ENABLE_WEB_SEARCH: DEFAULT_ENABLE_WEB_SEARCH,
    CONF_SEARXNG_URL: DEFAULT_SEARXNG_URL,
    CONF_SEARXNG_ENGINES: DEFAULT_SEARXNG_ENGINES,
    CONF_SEARXNG_MAX_RESULTS: DEFAULT_SEARXNG_MAX_RESULTS,
    CONF_CONFIRMATION_REQUIRED: DEFAULT_CONFIRMATION_REQUIRED,
    CONF_EXPOSE_SCRIPTS: DEFAULT_EXPOSE_SCRIPTS,
    CONF_EXPOSE_SCENES: DEFAULT_EXPOSE_SCENES,
}

DEFAULT_AI_TASK_DATA = {
    CONF_SYSTEM_PROMPT: DEFAULT_AI_TASK_SYSTEM_PROMPT,
    CONF_TEMPERATURE: 0.7,
    CONF_MAX_TOKENS: 2048,
    CONF_AI_TASK_EXTRACTION_METHOD: DEFAULT_AI_TASK_EXTRACTION_METHOD,
    CONF_AI_TASK_RETRIES: DEFAULT_AI_TASK_RETRIES,
    CONF_AI_TASK_ENABLE_VISION: False,
    CONF_REQUEST_TIMEOUT: DEFAULT_REQUEST_TIMEOUT,
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

        # Personalities (built-in + shipped + user override) — needed both for
        # rendering defaults and for normalizing the saved prompt per-personality.
        personalities = build_personalities(self.hass)

        if user_input is not None:
            # Sections nest their fields; flatten back into a single dict so
            # storage stays flat (backward compatible with conversation.py).
            flat: dict[str, Any] = {}
            for value in user_input.values():
                if isinstance(value, dict):
                    flat.update(value)
            user_input = flat or user_input

            # Normalize boolean fields from string "1"/"0" to proper bools
            for key in (
                CONF_ENABLE_RAG,
                CONF_CONTROL_HA,
                CONF_DEBUG_MODE,
                CONF_CLEAN_RESPONSES,
                CONF_ENABLE_STREAMING,
                CONF_RESPECT_EXPOSURE,
                CONF_ENABLE_WEB_SEARCH,
                CONF_CONFIRMATION_REQUIRED,
                CONF_EXPOSE_SCRIPTS,
                CONF_EXPOSE_SCENES,
                CONF_AI_TASK_ENABLE_VISION,
                CONF_INCLUDE_EXAMPLES,
            ):
                if key in user_input:
                    user_input[key] = user_input[key] in ("1", True, "true")

            if CONF_AI_TASK_RETRIES in user_input:
                try:
                    user_input[CONF_AI_TASK_RETRIES] = int(
                        user_input[CONF_AI_TASK_RETRIES]
                    )
                except (ValueError, TypeError):
                    user_input[CONF_AI_TASK_RETRIES] = DEFAULT_AI_TASK_RETRIES

            # Normalize context_templates: text -> list (one template per line)
            if CONF_CONTEXT_TEMPLATES in user_input:
                user_input[CONF_CONTEXT_TEMPLATES] = [
                    line.strip()
                    for line in user_input[CONF_CONTEXT_TEMPLATES].splitlines()
                    if line.strip()
                ]

            # Normalize personality prompt: store it per-personality. Config
            # flow cannot refresh the prompt textbox live when the persona
            # dropdown changes, so on submit the box may still hold the
            # previously-shown text. To avoid leaking that stale text across
            # personas, we reset the target persona's override whenever the
            # persona actually changed, and only persist an edit when the
            # persona is unchanged and the text differs from its built-in.
            if CONF_PERSONALITY_PROMPT in user_input:
                old_data = (
                    {} if self._is_new else self._get_reconfigure_subentry().data
                )
                old_personality = old_data.get(CONF_PERSONALITY, DEFAULT_PERSONALITY)
                new_personality = user_input.get(CONF_PERSONALITY, DEFAULT_PERSONALITY)
                sub_prompt = user_input.pop(CONF_PERSONALITY_PROMPT)
                prompts = dict(user_input.get(CONF_PERSONALITY_PROMPTS, {}) or {})
                if new_personality != old_personality:
                    # Persona switched: discard the stale box content and
                    # reset the target persona to its built-in prompt.
                    prompts.pop(new_personality, None)
                else:
                    builtin = (personalities.get(new_personality, {}) or {}).get(
                        "prompt", ""
                    )
                    if sub_prompt and sub_prompt != builtin:
                        prompts[new_personality] = sub_prompt
                    else:
                        prompts.pop(new_personality, None)
                user_input[CONF_PERSONALITY_PROMPTS] = prompts

            # Normalize entity_aliases: "entity_id: alias" lines -> dict
            if CONF_ENTITY_ALIASES in user_input:
                aliases: dict[str, str] = {}
                for line in user_input[CONF_ENTITY_ALIASES].splitlines():
                    line = line.strip()
                    if not line or ":" not in line:
                        continue
                    ent, alias = line.split(":", 1)
                    ent = ent.strip()
                    alias = alias.strip()
                    if ent and alias:
                        aliases[ent] = alias
                user_input[CONF_ENTITY_ALIASES] = aliases

            # Normalize numeric fields
            if CONF_MAX_ENTITIES_PER_DISCOVERY in user_input:
                try:
                    user_input[CONF_MAX_ENTITIES_PER_DISCOVERY] = int(
                        user_input[CONF_MAX_ENTITIES_PER_DISCOVERY]
                    )
                except (ValueError, TypeError):
                    user_input[CONF_MAX_ENTITIES_PER_DISCOVERY] = (
                        DEFAULT_MAX_ENTITIES_PER_DISCOVERY
                    )
            if CONF_SEARXNG_MAX_RESULTS in user_input:
                try:
                    user_input[CONF_SEARXNG_MAX_RESULTS] = int(
                        user_input[CONF_SEARXNG_MAX_RESULTS]
                    )
                except (ValueError, TypeError):
                    user_input[CONF_SEARXNG_MAX_RESULTS] = (
                        DEFAULT_SEARXNG_MAX_RESULTS
                    )
            title = user_input.pop(CONF_NAME, "").strip() or (
                f"Lemonade ({user_input.get(CONF_MODEL_NAME, 'Lemonade')})"
            )
            if self._is_new:
                return self.async_create_entry(
                    title=title,
                    data=user_input,
                )
            return self.async_update_and_abort(
                entry,
                self._get_reconfigure_subentry(),
                data=user_input,
                title=title,
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

        # Helper returning an actual bool for BooleanSelector (checkbox) defaults
        def _bool(key: str, default: bool = False) -> bool:
            val = options.get(key, default)
            if isinstance(val, str):
                return val in ("1", "true", "yes", "on", "True")
            return bool(val)

        # Default display name shown/edited by the user
        if self._is_new:
            default_name = (
                "AI Task" if self._subentry_type == "ai_task" else "Conversation Agent"
            )
        else:
            default_name = self._get_reconfigure_subentry().title

        # ── AI Task: dedicated reduced schema ───────────────────
        if self._subentry_type == "ai_task":
            return self.async_show_form(
                step_id="set_options",
                data_schema=vol.Schema(
                    {
                        vol.Required("profile"): section(
                            vol.Schema(
                                {
                                    vol.Required(
                                        CONF_NAME, default=default_name
                                    ): TextSelector(
                                        TextSelectorConfig(
                                            type=TextSelectorType.TEXT
                                        )
                                    ),
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
                                        default=options.get(
                                            CONF_SYSTEM_PROMPT,
                                            DEFAULT_AI_TASK_SYSTEM_PROMPT,
                                        ),
                                    ): TextSelector(
                                        TextSelectorConfig(
                                            type=TextSelectorType.TEXT,
                                            multiline=True,
                                        )
                                    ),
                                    vol.Optional(
                                        CONF_TEMPERATURE,
                                        default=options.get(
                                            CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                                        ),
                                    ): NumberSelector(
                                        NumberSelectorConfig(
                                            min=MIN_TEMPERATURE,
                                            max=MAX_TEMPERATURE,
                                            step=0.1,
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
                                            min=MIN_MAX_TOKENS,
                                            max=MAX_MAX_TOKENS,
                                            step=256,
                                            mode=NumberSelectorMode.BOX,
                                        )
                                    ),
                                }
                            ),
                            {"collapsed": False},
                        ),
                        # ── 🧩 Structured output ────────────────────
                        vol.Required("structured"): section(
                            vol.Schema(
                                {
                                    vol.Optional(
                                        CONF_AI_TASK_EXTRACTION_METHOD,
                                        default=options.get(
                                            CONF_AI_TASK_EXTRACTION_METHOD,
                                            DEFAULT_AI_TASK_EXTRACTION_METHOD,
                                        ),
                                    ): SelectSelector(
                                        SelectSelectorConfig(
                                            options=[
                                                SelectOptionDict(
                                                    value=AI_TASK_EXTRACTION_NONE,
                                                    label="None (raw text)",
                                                ),
                                                SelectOptionDict(
                                                    value=AI_TASK_EXTRACTION_STRUCTURE,
                                                    label="Structured output (JSON)",
                                                ),
                                                SelectOptionDict(
                                                    value=AI_TASK_EXTRACTION_TOOL,
                                                    label="Tool call",
                                                ),
                                            ],
                                            mode=SelectSelectorMode.DROPDOWN,
                                        )
                                    ),
                                    vol.Optional(
                                        CONF_AI_TASK_RETRIES,
                                        default=options.get(
                                            CONF_AI_TASK_RETRIES,
                                            DEFAULT_AI_TASK_RETRIES,
                                        ),
                                    ): NumberSelector(
                                        NumberSelectorConfig(
                                            min=MIN_AI_TASK_RETRIES,
                                            max=MAX_AI_TASK_RETRIES,
                                            step=1,
                                            mode=NumberSelectorMode.BOX,
                                        )
                                    ),
                                    vol.Optional(
                                        CONF_AI_TASK_ENABLE_VISION,
                                        default=_bool(
                                            CONF_AI_TASK_ENABLE_VISION, False
                                        ),
                                    ): BooleanSelector(),
                                }
                            ),
                            {"collapsed": False},
                        ),
                        # ── ⚙️ Advanced ─────────────────────────────
                        vol.Required("advanced"): section(
                            vol.Schema(
                                {
                                    vol.Optional(
                                        CONF_REQUEST_TIMEOUT,
                                        default=options.get(
                                            CONF_REQUEST_TIMEOUT,
                                            DEFAULT_REQUEST_TIMEOUT,
                                        ),
                                    ): NumberSelector(
                                        NumberSelectorConfig(
                                            min=MIN_REQUEST_TIMEOUT,
                                            max=MAX_REQUEST_TIMEOUT,
                                            step=5,
                                            mode=NumberSelectorMode.BOX,
                                        )
                                    ),
                                }
                            ),
                            {"collapsed": True},
                        ),
                    }
                ),
            )

        # Build the Personality section schema (examples shown only when enabled)
        _personality = options.get(CONF_PERSONALITY, DEFAULT_PERSONALITY)
        persona_fields = {
            vol.Optional(
                CONF_PERSONALITY,
                default=_personality,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=k, label=v["name"])
                        for k, v in personalities.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    sort=True,
                )
            ),
            vol.Optional(
                CONF_PERSONALITY_PROMPT,
                default=resolve_persona_prompt(
                    options, personalities, _personality
                ),
            ): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.TEXT, multiline=True
                )
            ),
            vol.Optional(
                CONF_SARCASM_ENTITY,
                default=options.get(CONF_SARCASM_ENTITY, DEFAULT_SARCASM_ENTITY),
            ): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Optional(
                CONF_INCLUDE_EXAMPLES,
                default=_bool(CONF_INCLUDE_EXAMPLES, DEFAULT_INCLUDE_EXAMPLES),
            ): BooleanSelector(),
        }
        if _bool(CONF_INCLUDE_EXAMPLES, DEFAULT_INCLUDE_EXAMPLES):
            persona_fields[
                vol.Optional(
                    CONF_PERSONALITY_EXAMPLES,
                    default=personalities.get(_personality, {}).get("examples", ""),
                )
            ] = TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.TEXT, multiline=True
                )
            )

        return self.async_show_form(
            step_id="set_options",
            data_schema=vol.Schema(
                {
                    # ── 👤 Profile & Model ──────────────────────────
                    vol.Required("profile"): section(
                        vol.Schema(
                            {
                                vol.Required(
                                    CONF_NAME, default=default_name
                                ): TextSelector(
                                    TextSelectorConfig(type=TextSelectorType.TEXT)
                                ),
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
                                    CONF_TECHNICAL_PROMPT,
                                    default=options.get(CONF_TECHNICAL_PROMPT, ""),
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
                                        min=MIN_TEMPERATURE,
                                        max=MAX_TEMPERATURE,
                                        step=0.1,
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
                                        min=MIN_MAX_TOKENS,
                                        max=MAX_MAX_TOKENS,
                                        step=256,
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
                                        min=MIN_MAX_HISTORY,
                                        max=MAX_MAX_HISTORY,
                                        step=1,
                                        mode=NumberSelectorMode.BOX,
                                    )
                                ),
                                vol.Optional(
                                    CONF_RESPONSE_MODE,
                                    default=options.get(
                                        CONF_RESPONSE_MODE, DEFAULT_RESPONSE_MODE
                                    ),
                                ): SelectSelector(
                                    SelectSelectorConfig(
                                        options=[
                                            SelectOptionDict(
                                                value="none",
                                                label="None (pass-through)",
                                            ),
                                            SelectOptionDict(
                                                value="default", label="Default"
                                            ),
                                            SelectOptionDict(
                                                value="always",
                                                label="Always respond",
                                            ),
                                        ],
                                        mode=SelectSelectorMode.DROPDOWN,
                                    )
                                ),
                                vol.Optional(
                                    CONF_CLEAN_RESPONSES,
                                    default=_bool(
                                        CONF_CLEAN_RESPONSES,
                                        DEFAULT_CLEAN_RESPONSES,
                                    ),
                                ): BooleanSelector(),
                                vol.Optional(
                                    CONF_ENABLE_STREAMING,
                                    default=_bool(
                                        CONF_ENABLE_STREAMING,
                                        DEFAULT_ENABLE_STREAMING,
                                    ),
                                ): BooleanSelector(),
                            }
                        ),
                        {"collapsed": False},
                    ),
                    # ── 🎭 Personalidad ──────────────────────────
                    vol.Required("personalidad"): section(
                        vol.Schema(persona_fields),
                        {"collapsed": False},
                    ),
                    # ── 🧠 Context ──────────────────────────────────
                    vol.Required("context"): section(
                        vol.Schema(
                            {
                                vol.Optional(
                                    CONF_CONTEXT_TEMPLATES,
                                    default="\n".join(
                                        options.get(
                                            CONF_CONTEXT_TEMPLATES,
                                            DEFAULT_CONTEXT_TEMPLATES,
                                        )
                                    ),
                                ): TextSelector(
                                    TextSelectorConfig(
                                        type=TextSelectorType.TEXT, multiline=True
                                    )
                                ),
                            }
                        ),
                        {"collapsed": True},
                    ),
                    # ── 🏠 Entities & Domains ───────────────────────
                    vol.Required("entities"): section(
                        vol.Schema(
                            {
                                vol.Optional(
                                    CONF_ENABLED_DOMAINS,
                                    default=options.get(
                                        CONF_ENABLED_DOMAINS,
                                        DEFAULT_ENABLED_DOMAINS,
                                    ),
                                ): cv.multi_select(SUPPORTED_DOMAINS),
                                vol.Optional(
                                    CONF_ENTITY_ALIASES,
                                    default="\n".join(
                                        f"{k}: {v}"
                                        for k, v in options.get(
                                            CONF_ENTITY_ALIASES,
                                            DEFAULT_ENTITY_ALIASES,
                                        ).items()
                                    ),
                                ): TextSelector(
                                    TextSelectorConfig(
                                        type=TextSelectorType.TEXT, multiline=True
                                    )
                                ),
                                vol.Optional(
                                    CONF_MAX_ENTITIES_PER_DISCOVERY,
                                    default=options.get(
                                        CONF_MAX_ENTITIES_PER_DISCOVERY,
                                        DEFAULT_MAX_ENTITIES_PER_DISCOVERY,
                                    ),
                                ): NumberSelector(
                                    NumberSelectorConfig(
                                        min=MIN_MAX_ENTITIES_PER_DISCOVERY,
                                        max=MAX_MAX_ENTITIES_PER_DISCOVERY,
                                        step=5,
                                        mode=NumberSelectorMode.BOX,
                                    )
                                ),
                                vol.Optional(
                                    CONF_RESPECT_EXPOSURE,
                                    default=_bool(
                                        CONF_RESPECT_EXPOSURE,
                                        DEFAULT_RESPECT_EXPOSURE,
                                    ),
                                ): BooleanSelector(),
                            }
                        ),
                        {"collapsed": True},
                    ),
                    # ── 🎛️ Control & Behaviour ─────────────────────
                    vol.Required("behaviour"): section(
                        vol.Schema(
                            {
                                vol.Optional(
                                    CONF_CONTROL_HA,
                                    default=_bool(
                                        CONF_CONTROL_HA, DEFAULT_CONTROL_HA
                                    ),
                                ): BooleanSelector(),
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
                                    CONF_CONFIRMATION_REQUIRED,
                                    default=_bool(
                                        CONF_CONFIRMATION_REQUIRED,
                                        DEFAULT_CONFIRMATION_REQUIRED,
                                    ),
                                ): BooleanSelector(),
                                vol.Optional(
                                    CONF_EXPOSE_SCRIPTS,
                                    default=_bool(
                                        CONF_EXPOSE_SCRIPTS,
                                        DEFAULT_EXPOSE_SCRIPTS,
                                    ),
                                ): BooleanSelector(),
                                vol.Optional(
                                    CONF_EXPOSE_SCENES,
                                    default=_bool(
                                        CONF_EXPOSE_SCENES,
                                        DEFAULT_EXPOSE_SCENES,
                                    ),
                                ): BooleanSelector(),
                                vol.Optional(
                                    CONF_MAX_ITERATIONS,
                                    default=options.get(
                                        CONF_MAX_ITERATIONS,
                                        DEFAULT_MAX_ITERATIONS,
                                    ),
                                ): NumberSelector(
                                    NumberSelectorConfig(
                                        min=MIN_MAX_ITERATIONS,
                                        max=MAX_MAX_ITERATIONS,
                                        step=1,
                                        mode=NumberSelectorMode.BOX,
                                    )
                                ),
                            }
                        ),
                        {"collapsed": True},
                    ),
                    # ── 🌐 Web Search (SearXNG) ─────────────────────
                    vol.Required("web_search"): section(
                        vol.Schema(
                            {
                                vol.Optional(
                                    CONF_ENABLE_WEB_SEARCH,
                                    default=_bool(
                                        CONF_ENABLE_WEB_SEARCH,
                                        DEFAULT_ENABLE_WEB_SEARCH,
                                    ),
                                ): BooleanSelector(),
                                vol.Optional(
                                    CONF_SEARXNG_URL,
                                    default=options.get(
                                        CONF_SEARXNG_URL, DEFAULT_SEARXNG_URL
                                    ),
                                ): TextSelector(
                                    TextSelectorConfig(type=TextSelectorType.URL)
                                ),
                                vol.Optional(
                                    CONF_SEARXNG_ENGINES,
                                    default=options.get(
                                        CONF_SEARXNG_ENGINES,
                                        DEFAULT_SEARXNG_ENGINES,
                                    ),
                                ): TextSelector(
                                    TextSelectorConfig(type=TextSelectorType.TEXT)
                                ),
                                vol.Optional(
                                    CONF_SEARXNG_MAX_RESULTS,
                                    default=options.get(
                                        CONF_SEARXNG_MAX_RESULTS,
                                        DEFAULT_SEARXNG_MAX_RESULTS,
                                    ),
                                ): NumberSelector(
                                    NumberSelectorConfig(
                                        min=MIN_SEARXNG_MAX_RESULTS,
                                        max=MAX_SEARXNG_MAX_RESULTS,
                                        step=1,
                                        mode=NumberSelectorMode.BOX,
                                    )
                                ),
                            }
                        ),
                        {"collapsed": True},
                    ),
                    # ── 📚 RAG ──────────────────────────────────────
                    vol.Required("rag"): section(
                        vol.Schema(
                            {
                                vol.Optional(
                                    CONF_ENABLE_RAG,
                                    default=_bool(
                                        CONF_ENABLE_RAG, DEFAULT_ENABLE_RAG
                                    ),
                                ): BooleanSelector(),
                                vol.Optional(
                                    CONF_RAG_TOP_K,
                                    default=options.get(
                                        CONF_RAG_TOP_K, DEFAULT_RAG_TOP_K
                                    ),
                                ): NumberSelector(
                                    NumberSelectorConfig(
                                        min=MIN_RAG_TOP_K,
                                        max=MAX_RAG_TOP_K,
                                        step=1,
                                        mode=NumberSelectorMode.BOX,
                                    )
                                ),
                            }
                        ),
                        {"collapsed": True},
                    ),
                    # ── 💬 Follow-up ────────────────────────────────
                    vol.Required("follow_up"): section(
                        vol.Schema(
                            {
                                vol.Optional(
                                    CONF_FOLLOW_UP_PHRASES,
                                    default=options.get(
                                        CONF_FOLLOW_UP_PHRASES,
                                        DEFAULT_FOLLOW_UP_PHRASES,
                                    ),
                                ): TextSelector(
                                    TextSelectorConfig(
                                        type=TextSelectorType.TEXT, multiline=True
                                    )
                                ),
                                vol.Optional(
                                    CONF_END_WORDS,
                                    default=options.get(
                                        CONF_END_WORDS, DEFAULT_END_WORDS
                                    ),
                                ): TextSelector(
                                    TextSelectorConfig(
                                        type=TextSelectorType.TEXT, multiline=True
                                    )
                                ),
                            }
                        ),
                        {"collapsed": True},
                    ),
                    # ── ⚙️ Advanced ─────────────────────────────────
                    vol.Required("advanced"): section(
                        vol.Schema(
                            {
                                vol.Optional(
                                    CONF_DEBUG_MODE,
                                    default=_bool(
                                        CONF_DEBUG_MODE, DEFAULT_DEBUG_MODE
                                    ),
                                ): BooleanSelector(),
                                vol.Optional(
                                    CONF_REQUEST_TIMEOUT,
                                    default=options.get(
                                        CONF_REQUEST_TIMEOUT,
                                        DEFAULT_REQUEST_TIMEOUT,
                                    ),
                                ): NumberSelector(
                                    NumberSelectorConfig(
                                        min=MIN_REQUEST_TIMEOUT,
                                        max=MAX_REQUEST_TIMEOUT,
                                        step=5,
                                        mode=NumberSelectorMode.BOX,
                                    )
                                ),
                                vol.Optional(
                                    CONF_CONNECT_TIMEOUT,
                                    default=options.get(
                                        CONF_CONNECT_TIMEOUT,
                                        DEFAULT_CONNECT_TIMEOUT,
                                    ),
                                ): NumberSelector(
                                    NumberSelectorConfig(
                                        min=MIN_CONNECT_TIMEOUT,
                                        max=MAX_CONNECT_TIMEOUT,
                                        step=1,
                                        mode=NumberSelectorMode.BOX,
                                    )
                                ),
                                vol.Optional(
                                    CONF_FIRST_DELTA_TIMEOUT,
                                    default=options.get(
                                        CONF_FIRST_DELTA_TIMEOUT,
                                        DEFAULT_FIRST_DELTA_TIMEOUT,
                                    ),
                                ): NumberSelector(
                                    NumberSelectorConfig(
                                        min=MIN_FIRST_DELTA_TIMEOUT,
                                        max=MAX_FIRST_DELTA_TIMEOUT,
                                        step=1,
                                        mode=NumberSelectorMode.BOX,
                                    )
                                ),
                                vol.Optional(
                                    CONF_MAX_RETRIES,
                                    default=options.get(
                                        CONF_MAX_RETRIES, DEFAULT_MAX_RETRIES
                                    ),
                                ): NumberSelector(
                                    NumberSelectorConfig(
                                        min=MIN_MAX_RETRIES,
                                        max=MAX_MAX_RETRIES,
                                        step=1,
                                        mode=NumberSelectorMode.BOX,
                                    )
                                ),
                                vol.Optional(
                                    CONF_RETRY_BACKOFF,
                                    default=options.get(
                                        CONF_RETRY_BACKOFF, DEFAULT_RETRY_BACKOFF
                                    ),
                                ): NumberSelector(
                                    NumberSelectorConfig(
                                        min=MIN_RETRY_BACKOFF,
                                        max=MAX_RETRY_BACKOFF,
                                        step=0.5,
                                        mode=NumberSelectorMode.BOX,
                                    )
                                ),
                            }
                        ),
                        {"collapsed": True},
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
