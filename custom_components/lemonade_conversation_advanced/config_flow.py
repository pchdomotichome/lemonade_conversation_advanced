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
    DEFAULT_TECHNICAL_PROMPT,
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
    CONF_TECHNICAL_PROMPT: DEFAULT_TECHNICAL_PROMPT,
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


def _as_bool(val: Any, default: bool = False) -> bool:
    """Coerce a stored value into a real bool for checkbox defaults."""
    if val is None:
        return default
    if isinstance(val, str):
        return val in ("1", "true", "yes", "on", "True")
    return bool(val)


class LemonadeSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Handle subentry flow for Lemonade.

    Creation (source == "user") uses a single minimal step (name + model,
    plus personality for conversation agents); everything else is seeded with
    defaults. Reconfiguration presents a menu: each settings section is its
    own sub-step that saves and returns to the menu. Entity aliases and
    context templates are managed via dedicated add/remove sub-steps.
    """

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    # ------------------------------------------------------------------
    # Creation (minimal, linear)
    # ------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create a new subentry with the essentials; the rest uses defaults."""
        entry = self._get_entry()
        is_ai = self._subentry_type == "ai_task"

        if user_input is not None:
            flat: dict[str, Any] = {}
            for value in user_input.values():
                if isinstance(value, dict):
                    flat.update(value)
            flat = flat or user_input

            model = flat.get(CONF_MODEL_NAME)
            name = (flat.get(CONF_NAME) or "").strip()
            defaults = (
                DEFAULT_AI_TASK_DATA if is_ai else DEFAULT_CONVERSATION_DATA
            ).copy()
            data = {**defaults, CONF_MODEL_NAME: model}
            if not is_ai and flat.get(CONF_PERSONALITY):
                data[CONF_PERSONALITY] = flat[CONF_PERSONALITY]
            title = name or (
                f"Lemonade AI Task ({model})"
                if is_ai
                else f"Lemonade Assistant ({model})"
            )
            return self.async_create_entry(title=title, data=data)

        models = await self._fetch_models(entry)
        model_options = models or ["No models found"]
        default_name = "AI Task" if is_ai else "Conversation Agent"

        fields: dict[Any, Any] = {
            vol.Required(CONF_NAME, default=default_name): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_MODEL_NAME): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=m, label=m) for m in model_options
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    sort=True,
                )
            ),
        }
        if not is_ai:
            personalities = await build_personalities(self.hass)
            fields[
                vol.Optional(CONF_PERSONALITY, default=DEFAULT_PERSONALITY)
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=k, label=v["name"])
                        for k, v in personalities.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    sort=True,
                )
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(fields),
        )

    # ------------------------------------------------------------------
    # Reconfigure: menu
    # ------------------------------------------------------------------
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Entry point for reconfiguration -> show the section menu."""
        return await self.async_step_menu()

    async def async_step_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show a menu of configuration sections."""
        entry = self._get_entry()
        if entry.state is not config_entries.ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if self._subentry_type == "ai_task":
            menu_options = ["profile", "structured", "advanced"]
        else:
            menu_options = [
                "profile",
                "personalidad",
                "entities",
                "aliases",
                "templates",
                "behaviour",
                "web_search",
                "rag",
                "follow_up",
                "advanced",
            ]
        return self.async_show_menu(step_id="menu", menu_options=menu_options)

    # ------------------------------------------------------------------
    # Section step wrappers
    # ------------------------------------------------------------------
    async def async_step_profile(self, user_input=None) -> FlowResult:
        return await self._section_step("profile", user_input)

    async def async_step_personalidad(self, user_input=None) -> FlowResult:
        return await self._section_step("personalidad", user_input)

    async def async_step_entities(self, user_input=None) -> FlowResult:
        return await self._section_step("entities", user_input)

    async def async_step_behaviour(self, user_input=None) -> FlowResult:
        return await self._section_step("behaviour", user_input)

    async def async_step_web_search(self, user_input=None) -> FlowResult:
        return await self._section_step("web_search", user_input)

    async def async_step_rag(self, user_input=None) -> FlowResult:
        return await self._section_step("rag", user_input)

    async def async_step_follow_up(self, user_input=None) -> FlowResult:
        return await self._section_step("follow_up", user_input)

    async def async_step_advanced(self, user_input=None) -> FlowResult:
        return await self._section_step("advanced", user_input)

    async def async_step_structured(self, user_input=None) -> FlowResult:
        return await self._section_step("structured", user_input)

    # ------------------------------------------------------------------
    # Generic section handler
    # ------------------------------------------------------------------
    async def _section_step(
        self, section_id: str, user_input: dict[str, Any] | None
    ) -> FlowResult:
        """Render or save a single settings section, returning to the menu."""
        entry = self._get_entry()
        if entry.state is not config_entries.ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        subentry = self._get_reconfigure_subentry()
        options = dict(subentry.data)
        personalities = await build_personalities(self.hass)

        if user_input is not None:
            flat: dict[str, Any] = {}
            for value in user_input.values():
                if isinstance(value, dict):
                    flat.update(value)
            flat = flat or dict(user_input)

            title = None
            if CONF_NAME in flat:
                title = flat.pop(CONF_NAME).strip() or subentry.title

            normalized = self._normalize(flat, options, personalities)
            options.update(normalized)
            self._commit(options, title)
            return await self.async_step_menu()

        schema = await self._build_section_schema(
            section_id, options, personalities, entry
        )
        return self.async_show_form(step_id=section_id, data_schema=schema)

    def _commit(self, data: dict[str, Any], title: str | None = None) -> None:
        """Persist the subentry data (and optional title) without aborting."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        kwargs: dict[str, Any] = {"data": data}
        if title:
            kwargs["title"] = title
        self.hass.config_entries.async_update_subentry(entry, subentry, **kwargs)

    def _normalize(
        self,
        user_input: dict[str, Any],
        old_options: dict[str, Any],
        personalities: dict[str, Any],
    ) -> dict[str, Any]:
        """Coerce raw form values into stored types (partial-dict safe)."""
        data = dict(user_input)

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
            if key in data:
                data[key] = data[key] in ("1", True, "true")

        if CONF_AI_TASK_RETRIES in data:
            try:
                data[CONF_AI_TASK_RETRIES] = int(data[CONF_AI_TASK_RETRIES])
            except (ValueError, TypeError):
                data[CONF_AI_TASK_RETRIES] = DEFAULT_AI_TASK_RETRIES

        # Personality prompt: store per-personality. The form cannot refresh the
        # prompt textbox live when the persona dropdown changes, so on submit the
        # box may still hold the previously-shown text. Reset the target
        # persona's override when the persona changed; only persist an edit when
        # the persona is unchanged and the text differs from its built-in.
        if CONF_PERSONALITY_PROMPT in data:
            old_personality = old_options.get(CONF_PERSONALITY, DEFAULT_PERSONALITY)
            new_personality = data.get(CONF_PERSONALITY, DEFAULT_PERSONALITY)
            sub_prompt = data.pop(CONF_PERSONALITY_PROMPT)
            prompts = dict(old_options.get(CONF_PERSONALITY_PROMPTS, {}) or {})
            if new_personality != old_personality:
                prompts.pop(new_personality, None)
            else:
                builtin = (personalities.get(new_personality, {}) or {}).get(
                    "prompt", ""
                )
                if sub_prompt and sub_prompt != builtin:
                    prompts[new_personality] = sub_prompt
                else:
                    prompts.pop(new_personality, None)
            data[CONF_PERSONALITY_PROMPTS] = prompts

        if CONF_MAX_ENTITIES_PER_DISCOVERY in data:
            try:
                data[CONF_MAX_ENTITIES_PER_DISCOVERY] = int(
                    data[CONF_MAX_ENTITIES_PER_DISCOVERY]
                )
            except (ValueError, TypeError):
                data[CONF_MAX_ENTITIES_PER_DISCOVERY] = (
                    DEFAULT_MAX_ENTITIES_PER_DISCOVERY
                )
        if CONF_SEARXNG_MAX_RESULTS in data:
            try:
                data[CONF_SEARXNG_MAX_RESULTS] = int(data[CONF_SEARXNG_MAX_RESULTS])
            except (ValueError, TypeError):
                data[CONF_SEARXNG_MAX_RESULTS] = DEFAULT_SEARXNG_MAX_RESULTS

        return data

    # ------------------------------------------------------------------
    # Aliases sub-step (add/remove entity aliases)
    # ------------------------------------------------------------------
    async def async_step_aliases(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage entity aliases (add one, or remove one), then return to menu."""
        entry = self._get_entry()
        if entry.state is not config_entries.ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        subentry = self._get_reconfigure_subentry()
        options = dict(subentry.data)
        aliases: dict[str, str] = dict(
            options.get(CONF_ENTITY_ALIASES, DEFAULT_ENTITY_ALIASES) or {}
        )

        if user_input is not None:
            new_entity = (user_input.get("entity_id") or "").strip()
            new_alias = (user_input.get("alias") or "").strip()
            remove = user_input.get("remove_alias")

            if new_entity and new_alias:
                aliases[new_entity] = new_alias
            if remove and remove in aliases:
                del aliases[remove]

            options[CONF_ENTITY_ALIASES] = aliases
            self._commit(options)
            return await self.async_step_menu()

        fields: dict[Any, Any] = {
            vol.Optional("entity_id"): EntitySelector(EntitySelectorConfig()),
            vol.Optional("alias"): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }
        if aliases:
            remove_options = []
            for ent, alias in aliases.items():
                state = self.hass.states.get(ent)
                original = (
                    state.attributes.get("friendly_name", ent) if state else ent
                )
                remove_options.append(
                    SelectOptionDict(value=ent, label=f"{original} → '{alias}'")
                )
            fields[vol.Optional("remove_alias")] = SelectSelector(
                SelectSelectorConfig(
                    options=remove_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

        current = "\n".join(f"• {k} → {v}" for k, v in aliases.items()) or "—"
        return self.async_show_form(
            step_id="aliases",
            data_schema=vol.Schema(fields),
            description_placeholders={"current": current},
        )

    # ------------------------------------------------------------------
    # Templates sub-step (add/remove context templates)
    # ------------------------------------------------------------------
    async def async_step_templates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage context (Jinja2) templates, then return to the menu."""
        entry = self._get_entry()
        if entry.state is not config_entries.ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        subentry = self._get_reconfigure_subentry()
        options = dict(subentry.data)
        templates: list[str] = list(
            options.get(CONF_CONTEXT_TEMPLATES, DEFAULT_CONTEXT_TEMPLATES) or []
        )

        if user_input is not None:
            new_template = (user_input.get("new_template") or "").strip()
            remove = user_input.get("remove_template")

            if new_template and new_template not in templates:
                templates.append(new_template)
            if remove and remove in templates:
                templates.remove(remove)

            options[CONF_CONTEXT_TEMPLATES] = templates
            self._commit(options)
            return await self.async_step_menu()

        fields: dict[Any, Any] = {
            vol.Optional("new_template"): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
            ),
        }
        if templates:
            remove_options = [
                SelectOptionDict(
                    value=t,
                    label=(t if len(t) <= 60 else f"{t[:57]}..."),
                )
                for t in templates
            ]
            fields[vol.Optional("remove_template")] = SelectSelector(
                SelectSelectorConfig(
                    options=remove_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

        current = "\n".join(f"• {t}" for t in templates) or "—"
        return self.async_show_form(
            step_id="templates",
            data_schema=vol.Schema(fields),
            description_placeholders={"current": current},
        )

    # ------------------------------------------------------------------
    # Section schema builders (flat, one form per section)
    # ------------------------------------------------------------------
    async def _build_section_schema(
        self,
        section_id: str,
        options: dict[str, Any],
        personalities: dict[str, Any],
        entry: config_entries.ConfigEntry,
    ) -> vol.Schema:
        """Return the flat vol.Schema for a given section id."""
        if section_id == "profile":
            models = await self._fetch_models(entry)
            model_options = models or ["No models found"]
            if self._subentry_type == "ai_task":
                return self._schema_ai_profile(options, model_options)
            return self._schema_profile(options, model_options)
        if section_id == "personalidad":
            return self._schema_personalidad(options, personalities)
        if section_id == "entities":
            return self._schema_entities(options)
        if section_id == "behaviour":
            return self._schema_behaviour(options)
        if section_id == "web_search":
            return self._schema_web_search(options)
        if section_id == "rag":
            return self._schema_rag(options)
        if section_id == "follow_up":
            return self._schema_follow_up(options)
        if section_id == "structured":
            return self._schema_structured(options)
        if section_id == "advanced":
            if self._subentry_type == "ai_task":
                return self._schema_ai_advanced(options)
            return self._schema_advanced(options)
        return vol.Schema({})

    def _schema_profile(
        self, options: dict[str, Any], model_options: list[str]
    ) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    default=self._get_reconfigure_subentry().title,
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_MODEL_NAME, default=options.get(CONF_MODEL_NAME)
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
                    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                ),
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
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
                    CONF_MAX_HISTORY,
                    default=options.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY),
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
                    default=options.get(CONF_RESPONSE_MODE, DEFAULT_RESPONSE_MODE),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value="none", label="None (pass-through)"
                            ),
                            SelectOptionDict(value="default", label="Default"),
                            SelectOptionDict(
                                value="always", label="Always respond"
                            ),
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_CLEAN_RESPONSES,
                    default=_as_bool(
                        options.get(CONF_CLEAN_RESPONSES), DEFAULT_CLEAN_RESPONSES
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_ENABLE_STREAMING,
                    default=_as_bool(
                        options.get(CONF_ENABLE_STREAMING),
                        DEFAULT_ENABLE_STREAMING,
                    ),
                ): BooleanSelector(),
            }
        )

    def _schema_personalidad(
        self, options: dict[str, Any], personalities: dict[str, Any]
    ) -> vol.Schema:
        _personality = options.get(CONF_PERSONALITY, DEFAULT_PERSONALITY)
        fields: dict[Any, Any] = {
            vol.Optional(CONF_PERSONALITY, default=_personality): SelectSelector(
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
                TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
            ),
            vol.Optional(
                CONF_SARCASM_ENTITY,
                default=options.get(CONF_SARCASM_ENTITY, DEFAULT_SARCASM_ENTITY),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Optional(
                CONF_INCLUDE_EXAMPLES,
                default=_as_bool(
                    options.get(CONF_INCLUDE_EXAMPLES), DEFAULT_INCLUDE_EXAMPLES
                ),
            ): BooleanSelector(),
        }
        if _as_bool(
            options.get(CONF_INCLUDE_EXAMPLES), DEFAULT_INCLUDE_EXAMPLES
        ):
            fields[
                vol.Optional(
                    CONF_PERSONALITY_EXAMPLES,
                    default=personalities.get(_personality, {}).get("examples", ""),
                )
            ] = TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
            )
        return vol.Schema(fields)

    def _schema_entities(self, options: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(
                    CONF_ENABLED_DOMAINS,
                    default=options.get(
                        CONF_ENABLED_DOMAINS, DEFAULT_ENABLED_DOMAINS
                    ),
                ): cv.multi_select(SUPPORTED_DOMAINS),
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
                    default=_as_bool(
                        options.get(CONF_RESPECT_EXPOSURE),
                        DEFAULT_RESPECT_EXPOSURE,
                    ),
                ): BooleanSelector(),
            }
        )

    def _schema_behaviour(self, options: dict[str, Any]) -> vol.Schema:
        llm_apis = llm.async_get_apis(self.hass)
        llm_api_options = [
            {"value": api.id, "label": api.name} for api in llm_apis
        ]
        if not llm_api_options:
            llm_api_options = [
                {"value": "none", "label": "No LLM APIs available"}
            ]
        return vol.Schema(
            {
                vol.Optional(
                    CONF_CONTROL_HA,
                    default=_as_bool(
                        options.get(CONF_CONTROL_HA), DEFAULT_CONTROL_HA
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
                    default=_as_bool(
                        options.get(CONF_CONFIRMATION_REQUIRED),
                        DEFAULT_CONFIRMATION_REQUIRED,
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_EXPOSE_SCRIPTS,
                    default=_as_bool(
                        options.get(CONF_EXPOSE_SCRIPTS), DEFAULT_EXPOSE_SCRIPTS
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_EXPOSE_SCENES,
                    default=_as_bool(
                        options.get(CONF_EXPOSE_SCENES), DEFAULT_EXPOSE_SCENES
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_MAX_ITERATIONS,
                    default=options.get(
                        CONF_MAX_ITERATIONS, DEFAULT_MAX_ITERATIONS
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
        )

    def _schema_web_search(self, options: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(
                    CONF_ENABLE_WEB_SEARCH,
                    default=_as_bool(
                        options.get(CONF_ENABLE_WEB_SEARCH),
                        DEFAULT_ENABLE_WEB_SEARCH,
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_SEARXNG_URL,
                    default=options.get(CONF_SEARXNG_URL, DEFAULT_SEARXNG_URL),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                vol.Optional(
                    CONF_SEARXNG_ENGINES,
                    default=options.get(
                        CONF_SEARXNG_ENGINES, DEFAULT_SEARXNG_ENGINES
                    ),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_SEARXNG_MAX_RESULTS,
                    default=options.get(
                        CONF_SEARXNG_MAX_RESULTS, DEFAULT_SEARXNG_MAX_RESULTS
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
        )

    def _schema_rag(self, options: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(
                    CONF_ENABLE_RAG,
                    default=_as_bool(
                        options.get(CONF_ENABLE_RAG), DEFAULT_ENABLE_RAG
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_RAG_TOP_K,
                    default=options.get(CONF_RAG_TOP_K, DEFAULT_RAG_TOP_K),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_RAG_TOP_K,
                        max=MAX_RAG_TOP_K,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    def _schema_follow_up(self, options: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(
                    CONF_FOLLOW_UP_PHRASES,
                    default=options.get(
                        CONF_FOLLOW_UP_PHRASES, DEFAULT_FOLLOW_UP_PHRASES
                    ),
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                ),
                vol.Optional(
                    CONF_END_WORDS,
                    default=options.get(CONF_END_WORDS, DEFAULT_END_WORDS),
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                ),
            }
        )

    def _schema_advanced(self, options: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(
                    CONF_DEBUG_MODE,
                    default=_as_bool(
                        options.get(CONF_DEBUG_MODE), DEFAULT_DEBUG_MODE
                    ),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_REQUEST_TIMEOUT,
                    default=options.get(
                        CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT
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
                        CONF_CONNECT_TIMEOUT, DEFAULT_CONNECT_TIMEOUT
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
                        CONF_FIRST_DELTA_TIMEOUT, DEFAULT_FIRST_DELTA_TIMEOUT
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
                    default=options.get(CONF_MAX_RETRIES, DEFAULT_MAX_RETRIES),
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
                    default=options.get(CONF_RETRY_BACKOFF, DEFAULT_RETRY_BACKOFF),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_RETRY_BACKOFF,
                        max=MAX_RETRY_BACKOFF,
                        step=0.5,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    # ---- AI Task section schemas ----
    def _schema_ai_profile(
        self, options: dict[str, Any], model_options: list[str]
    ) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=self._get_reconfigure_subentry().title
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Required(
                    CONF_MODEL_NAME, default=options.get(CONF_MODEL_NAME)
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
                        CONF_SYSTEM_PROMPT, DEFAULT_AI_TASK_SYSTEM_PROMPT
                    ),
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                ),
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
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
                    default=options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_MAX_TOKENS,
                        max=MAX_MAX_TOKENS,
                        step=256,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    def _schema_structured(self, options: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
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
                                value=AI_TASK_EXTRACTION_TOOL, label="Tool call"
                            ),
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_AI_TASK_RETRIES,
                    default=options.get(
                        CONF_AI_TASK_RETRIES, DEFAULT_AI_TASK_RETRIES
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
                    default=_as_bool(
                        options.get(CONF_AI_TASK_ENABLE_VISION), False
                    ),
                ): BooleanSelector(),
            }
        )

    def _schema_ai_advanced(self, options: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(
                    CONF_REQUEST_TIMEOUT,
                    default=options.get(
                        CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT
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
