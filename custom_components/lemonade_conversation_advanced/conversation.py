"""Conversation support for Lemonade Conversation Advanced."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any, Literal, override

from homeassistant.components import conversation
from homeassistant.components.homeassistant import async_should_expose
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import template as template_helper
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.llm import ToolInput
from homeassistant.util import dt as dt_util
from voluptuous_openapi import convert

from .api import LemonadeAPIClient
from .exceptions import (
    LemonadeAPIError,
    LemonadeAuthError,
    LemonadeConnectionError,
)
from .const import (
    CONF_CLEAN_RESPONSES,
    CONF_CONFIRMATION_REQUIRED,
    CONF_CONNECT_TIMEOUT,
    CONF_CONTEXT_TEMPLATES,
    CONF_CONTROL_HA,
    CONF_DEBUG_MODE,
    CONF_ENABLE_RAG,
    CONF_ENABLED_DOMAINS,
    CONF_ENTITY_ALIASES,
    CONF_ENABLE_STREAMING,
    CONF_END_WORDS,
    CONF_FIRST_DELTA_TIMEOUT,
    CONF_FOLLOW_UP_PHRASES,
    CONF_MAX_ENTITIES_PER_DISCOVERY,
    CONF_MAX_HISTORY,
    CONF_MAX_ITERATIONS,
    CONF_MAX_RETRIES,
    CONF_MAX_TOKENS,
    CONF_MODEL_NAME,
    CONF_RAG_TOP_K,
    CONF_REQUEST_TIMEOUT,
    CONF_RESPECT_EXPOSURE,
    CONF_RESPONSE_MODE,
    CONF_RETRY_BACKOFF,
    CONF_SYSTEM_PROMPT,
    CONF_TECHNICAL_PROMPT,
    CONF_TEMPERATURE,
    CONF_PERSONALITY,
    CONF_INCLUDE_EXAMPLES,
    CONF_PERSONALITY_EXAMPLES,
    CONF_PERSONALITY_PROMPT,
    CONF_PERSONALITY_PROMPTS,
    build_personalities,
    resolve_persona_prompt,
    CONFIRMATION_INSTRUCTION,
    DEFAULT_CONFIRMATION_REQUIRED,
    DEFAULT_INCLUDE_EXAMPLES,
    DEFAULT_PERSONALITY,
    DEFAULT_SARCASM_ENTITY,
    PERSONALITIES,
    PERSONALITY_CUSTOM,
    PERSONALITY_DEFAULT,
    PERSONALITY_SARCASTIC_AR,
    SARCASTIC_TONE_BLOCKS,
    DEFAULT_CONTEXT_TEMPLATES,
    DEFAULT_CLEAN_RESPONSES,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_CONTROL_HA,
    DEFAULT_DEBUG_MODE,
    DEFAULT_ENABLE_RAG,
    DEFAULT_ENABLED_DOMAINS,
    DEFAULT_ENTITY_ALIASES,
    DEFAULT_ENABLE_STREAMING,
    DEFAULT_FIRST_DELTA_TIMEOUT,
    DEFAULT_MAX_ENTITIES_PER_DISCOVERY,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_RAG_TOP_K,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RESPECT_EXPOSURE,
    CONF_SARCASM_ENTITY,
    DEFAULT_RESPONSE_MODE,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    RESPONSE_MODE_INSTRUCTIONS,
)
from .entity import LemonadeBaseEntity
from .prompt_analyzer import extract_prompt_intent
from .rag import RAGIndex

_LOGGER = logging.getLogger(__name__)

# Regex patterns for thinking/reasoning tags embedded in content
_THINKING_PATTERNS = [
    re.compile(r"<nik(.*?)k>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<\|thought\|>(.*?)<\|/thought\|>", re.DOTALL | re.IGNORECASE),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue

        async_add_entities(
            [LemonadeConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LemonadeConversationEntity(
    conversation.ConversationEntity,
    LemonadeBaseEntity,
):
    """Lemonade Conversation Agent."""

    _attr_supports_streaming = True

    def __init__(self, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the agent."""
        super().__init__(entry, subentry)
        self._client: LemonadeAPIClient | None = None
        opts = self.subentry.data
        control_ha = opts.get(CONF_CONTROL_HA, DEFAULT_CONTROL_HA)
        if isinstance(control_ha, str):
            control_ha = control_ha in ("1", "true", "yes", "on")
        if opts.get(CONF_LLM_HASS_API) and control_ha:
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)
        self._client = self._build_client()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        if self._client is not None:
            await self._client.close()
            self._client = None
        await super().async_will_remove_from_hass()

    def _build_client(self) -> LemonadeAPIClient:
        """Create a LemonadeAPIClient from the current config."""
        opts = self.subentry.data
        return LemonadeAPIClient(
            hass=self.hass,
            server_url=self.entry.data.get("server_url", ""),
            api_key=self.entry.data.get("api_key", ""),
            request_timeout=opts.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT),
            connect_timeout=opts.get(CONF_CONNECT_TIMEOUT, DEFAULT_CONNECT_TIMEOUT),
            first_delta_timeout=opts.get(CONF_FIRST_DELTA_TIMEOUT, DEFAULT_FIRST_DELTA_TIMEOUT),
            max_retries=int(opts.get(CONF_MAX_RETRIES, DEFAULT_MAX_RETRIES)),
            retry_backoff=opts.get(CONF_RETRY_BACKOFF, DEFAULT_RETRY_BACKOFF),
        )

    async def _async_prepare_chat_log(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> None:
        """Prepare LLM/tool context for the chat log."""
        options = self.subentry.data
        await chat_log.async_provide_llm_data(
            user_input.as_llm_context(DOMAIN),
            options.get(CONF_LLM_HASS_API),
            options.get(CONF_PROMPT),
            user_input.extra_system_prompt,
        )

        # Inject the selected assistant personality as the base system prompt.
        # Personalities are data-driven (built-in + shipped personalities.json
        # + user personalities_override.json). The editable prompt stored in
        # CONF_PERSONALITY_PROMPT takes precedence over the built-in text, so
        # users can tweak a persona without losing future updates.
        # Backward compatible: legacy subentries fall back to CONF_SYSTEM_PROMPT.
        personas = await build_personalities(self.hass)
        personality = options.get(CONF_PERSONALITY)
        if personality is None:
            persona_text = options.get(CONF_SYSTEM_PROMPT) or ""
            personality = PERSONALITY_CUSTOM if persona_text else PERSONALITY_DEFAULT
        else:
            persona_text = resolve_persona_prompt(options, personas, personality)

        if persona_text:
            chat_log.content.append(
                conversation.SystemContent(content=persona_text)
            )

        # Sarcastic-Argentine dynamic tone: read the configured sarcasm-level
        # entity (default input_select.sarcasm_level) and append the matching
        # tone block so the model adapts its irony per the user's setting.
        if personality == PERSONALITY_SARCASTIC_AR:
            level = "Normal"
            sarcasm_entity = options.get(CONF_SARCASM_ENTITY) or DEFAULT_SARCASM_ENTITY
            state = self.hass.states.get(sarcasm_entity) if sarcasm_entity else None
            if state is not None and state.state in SARCASTIC_TONE_BLOCKS:
                level = state.state
            chat_log.content.append(
                conversation.SystemContent(
                    content=(
                        f"SARCASM LEVEL: {level}. "
                        f"{SARCASTIC_TONE_BLOCKS[level]}"
                    )
                )
            )

        # Optional per-personality examples (user opts in via "Include
        # examples"). Helpful to steer small models toward the desired tone.
        if options.get(CONF_INCLUDE_EXAMPLES, DEFAULT_INCLUDE_EXAMPLES):
            examples = options.get(CONF_PERSONALITY_EXAMPLES) or personas.get(
                personality, {}
            ).get("examples", "")
            if examples.strip():
                chat_log.content.append(
                    conversation.SystemContent(
                        content=f"EXAMPLES:\n{examples.strip()}"
                    )
                )

        # Reinforce current date/time. Small models tend to answer from
        # training-cutoff knowledge (e.g. "it's 2025") even when the base
        # prompt already states today's date, so we inject an explicit,
        # authoritative instruction.
        now_local = dt_util.now()
        chat_log.content.append(
            conversation.SystemContent(
                content=(
                    "CURRENT DATE/TIME (authoritative): it is "
                    f"{now_local.strftime('%A %d %B %Y, %H:%M')} "
                    f"({now_local.strftime('%Y-%m-%d')}). "
                    "ALWAYS use this real, current date and time for any "
                    "reasoning about 'now', 'today', 'currently', recent "
                    "events or web-search results. IGNORE any date implied "
                    "by your training data — your training cutoff is NOT the "
                    "current date."
                )
            )
        )

        # Append technical prompt as system content, rendering its
        # placeholders ({index}, {current_area}, {response_mode}, {time},
        # {date}) so it behaves like MCP Assist's instruction block. Kept
        # user-editable so behaviour tweaks don't require a code change.
        technical_prompt = options.get(CONF_TECHNICAL_PROMPT, "")
        if technical_prompt:
            rendered_technical = await self._render_technical_prompt(
                technical_prompt, options, now_local
            )
            chat_log.content.append(
                conversation.SystemContent(content=rendered_technical)
            )

        # Append response mode instructions (skipped when a technical
        # prompt is present, since it already embeds {response_mode}).
        if not technical_prompt:
            response_mode = options.get(CONF_RESPONSE_MODE, DEFAULT_RESPONSE_MODE)
            rm_instructions = RESPONSE_MODE_INSTRUCTIONS.get(response_mode)
            if rm_instructions:
                chat_log.content.append(
                    conversation.SystemContent(content=rm_instructions)
                )

        # Require confirmation before control actions if enabled
        confirmation_required = options.get(
            CONF_CONFIRMATION_REQUIRED, DEFAULT_CONFIRMATION_REQUIRED
        )
        if isinstance(confirmation_required, str):
            confirmation_required = confirmation_required in ("1", "true", "yes", "on")
        if confirmation_required:
            chat_log.content.append(
                conversation.SystemContent(content=CONFIRMATION_INSTRUCTION)
            )

        # Inject a concise home structure summary (NOT the full index —
        # the full index lists all entities without states, which prompts
        # the LLM to call get_entity_state unnecessarily).
        index_manager = self.hass.data.get(DOMAIN, {}).get("index_manager")
        if index_manager:
            index = await index_manager.get_index()
            if index:
                areas_list = index.get("areas", [])
                domains_map = index.get("domains", {})
                area_summary = "Areas: " + ", ".join(
                    f"{a['name']} ({a['entity_count']} ent.)"
                    for a in areas_list
                )
                domain_summary = "Domains: " + ", ".join(
                    f"{d} ({c})" for d, c in domains_map.items()
                )
                summary = (
                    f"## Home Structure\n{area_summary}\n{domain_summary}\n"
                    f"(Entity states are provided separately below — "
                    f"use those, do NOT call tools to discover entities)"
                )
                _LOGGER.debug(
                    "Home structure summary injected (%d chars)",
                    len(summary),
                )
                chat_log.content.append(
                    conversation.SystemContent(content=summary)
                )

        # Render user-defined Jinja2 context templates as dynamic context.
        templates = options.get(CONF_CONTEXT_TEMPLATES, DEFAULT_CONTEXT_TEMPLATES)
        if templates:
            rendered = await self._render_context_templates(templates)
            if rendered:
                chat_log.content.append(
                    conversation.SystemContent(content=rendered)
                )

        # Instruct LLM not to call GetLiveContext — states are already in context
        chat_log.content.append(
            conversation.SystemContent(
                content=(
                    "IMPORTANT: Do NOT call the 'GetLiveContext' tool. "
                    "The current states of all relevant entities are already provided below "
                    "in the Current States sections. "
                    "Answer directly using the information already in this prompt."
                )
            )
        )

    async def _render_context_templates(
        self, templates: list[str]
    ) -> str:
        """Render Jinja2 context templates and join them as a context block.

        Each template is rendered with the Home Assistant template engine and
        the result is injected as dynamic context for the LLM.
        """
        rendered_lines: list[str] = []
        for tpl_text in templates:
            tpl_text = (tpl_text or "").strip()
            if not tpl_text:
                continue
            try:
                tpl = template_helper.Template(tpl_text, self.hass)
                value = tpl.async_render()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to render context template %r: %s", tpl_text, err
                )
                continue
            if value is not None and str(value).strip():
                rendered_lines.append(f"- {tpl_text} => {value}")

        if not rendered_lines:
            return ""

        return "## Dynamic Context (from templates)\n" + "\n".join(rendered_lines)

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Handle a message and return the final conversation result."""
        try:
            await self._async_prepare_chat_log(user_input, chat_log)
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        try:
            await self._async_handle_chat_log(chat_log)
        except HomeAssistantError:
            raise
        except Exception as err:
            _LOGGER.exception("Chat handling failed")
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(
                    agent_id=self.entity_id,
                    content=f"An unexpected error occurred: {err}",
                )
            )

        result = conversation.async_get_result_from_chat_log(user_input, chat_log)
        _LOGGER.debug(
            "ConversationResult speech=%s continue=%s chat_log[-1]=%s",
            result.response.speech,
            result.continue_conversation,
            chat_log.content[-1] if chat_log.content else "EMPTY",
        )
        return result

    # ------------------------------------------------------------------ #
    #  Helpers – build messages / payload from ChatLog                     #
    # ------------------------------------------------------------------ #

    def _build_messages(
        self,
        chat_log: conversation.ChatLog,
    ) -> list[dict[str, Any]]:
        """Serialise ChatLog content into OpenAI-format messages.

        Only keeps system content from:
          1. The core prompt region (before the first non-system entry).
          2. The current turn's injection zone (after the last UserContent).
        All system content interleaved between old conversation turns is
        stale injected context and is discarded.
        """
        options = self.subentry.data
        max_history = int(options.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY))

        # Find the last UserContent index — everything after it is fresh
        last_user_idx = -1
        for i, content in enumerate(chat_log.content):
            if isinstance(content, conversation.UserContent):
                last_user_idx = i

        # Find the first non-system index — everything before is core prompt
        first_nonsys_idx = len(chat_log.content)
        for i, content in enumerate(chat_log.content):
            if not isinstance(content, conversation.SystemContent):
                first_nonsys_idx = i
                break

        system_messages: list[dict[str, Any]] = []
        non_system_messages: list[dict[str, Any]] = []

        for i, content in enumerate(chat_log.content):
            in_core_region = i < first_nonsys_idx
            in_current_turn = i > last_user_idx

            if isinstance(content, conversation.SystemContent):
                # Keep system from core prompt region OR current turn injection zone
                if in_core_region or in_current_turn:
                    system_messages.append(
                        {"role": "system", "content": content.content}
                    )
            elif isinstance(content, conversation.UserContent):
                non_system_messages.append({
                    "role": "user", "content": content.content,
                })
            elif isinstance(content, conversation.AssistantContent):
                msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": content.content or "",
                }
                if content.thinking_content:
                    msg["thinking_content"] = content.thinking_content
                if content.tool_calls:
                    msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.tool_name,
                                "arguments": json.dumps(tc.tool_args),
                            },
                        }
                        for tc in content.tool_calls
                    ]
                non_system_messages.append(msg)
            elif isinstance(content, conversation.ToolResultContent):
                non_system_messages.append({
                    "role": "tool",
                    "tool_call_id": content.tool_call_id,
                    "content": json.dumps(content.tool_result),
                })

        # Trim history to last max_history turns (each "turn" is user+assistant+tools)
        if max_history > 0 and len(non_system_messages) > max_history * 2:
            non_system_messages = non_system_messages[-(max_history * 2):]

        return system_messages + non_system_messages

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Build the API request payload."""
        options = self.subentry.data
        payload: dict[str, Any] = {
            "model": options.get(CONF_MODEL_NAME, ""),
            "messages": messages,
            "temperature": options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
            "max_tokens": options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def _get_tools(self, chat_log: conversation.ChatLog) -> list[dict[str, Any]] | None:
        """Extract tool definitions from ChatLog and convert to OpenAI format."""
        if not chat_log.llm_api:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": convert(tool.parameters),
                },
            }
            for tool in chat_log.llm_api.tools
        ]

    # ------------------------------------------------------------------ #
    #  Thinking-tag extraction (for non-streaming responses)               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_thinking(text: str) -> tuple[str, str]:
        """Strip <think> / <|thought|> tags, returning (clean_text, thinking)."""
        thinking_parts: list[str] = []
        cleaned = text
        for pat in _THINKING_PATTERNS:
            for match in pat.finditer(cleaned):
                thinking_parts.append(match.group(1))
            cleaned = pat.sub("", cleaned)
        cleaned = re.sub(r"\n\s*\n", "\n\n", cleaned).strip()
        cleaned = re.sub(r"<nik[^>]*>|</nik>", "", cleaned, flags=re.IGNORECASE)
        return cleaned, "\n".join(thinking_parts)

    @staticmethod
    def _clean_response(text: str) -> str:
        """Strip markdown formatting so TTS reads clean text.

        Removes **bold**, *italic*, `code` and heading markers; collapses
        list bullets to plain text. Keeps the words intact.
        """
        # Bold/italic: **x** or *x* or __x__ — drop the markers, keep text
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*(?!\*)", r"\1", text)
        # Inline code `x`
        text = re.sub(r"`(.+?)`", r"\1", text)
        # Markdown headings / bullets at line start
        text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
        return text.strip()

    # ------------------------------------------------------------------ #
    #  Main handler                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _find_user_content_idx(
        chat_log: conversation.ChatLog,
    ) -> int | None:
        """Return the index of the LAST UserContent entry in the chat log."""
        idx = None
        for i, c in enumerate(chat_log.content):
            if isinstance(c, conversation.UserContent):
                idx = i
        return idx

    async def _inject_area_entity_states(
        self,
        chat_log: conversation.ChatLog,
        user_prompt: str,
        intent: dict[str, Any] | None = None,
        start_idx: int | None = None,
    ) -> int:
        """Inject entity states for areas mentioned in the user prompt.

        Inserts the state block right after the last user message (the
        "current-turn zone") so ``_build_messages`` keeps it in the payload
        sent to the LLM. When *intent* contains a ``domain_hint``, only
        entities matching that domain are injected.

        Returns the insertion index to use for the next block.
        """
        if not user_prompt:
            return start_idx if start_idx is not None else 0

        if start_idx is None:
            user_idx = self._find_user_content_idx(chat_log)
            if user_idx is None:
                return 0
            start_idx = user_idx + 1

        insert_idx = start_idx

        area_registry = ar.async_get(self.hass)
        entity_registry = er.async_get(self.hass)

        prompt_lower = user_prompt.lower()
        domain_hint = (intent or {}).get("domain_hint")

        matched_areas = []
        for area_entry in area_registry.areas.values():
            if area_entry.name.lower() in prompt_lower:
                matched_areas.append(area_entry)

        if not matched_areas:
            _LOGGER.debug(
                "No area name found in prompt: %s", user_prompt[:100]
            )
            # Fallback: a domain-scoped question with no area named
            # (e.g. "how many lights are on?") still needs entity
            # states. Inject all exposed entities of the hinted domain.
            if domain_hint:
                inserted = await self._inject_domain_states(
                    chat_log, domain_hint, insert_idx
                )
                return inserted
            return insert_idx

        enabled_domains = self.subentry.data.get(
            CONF_ENABLED_DOMAINS, DEFAULT_ENABLED_DOMAINS
        )
        enabled_domains_set = (
            set(enabled_domains) if enabled_domains else set()
        )
        entity_aliases = self.subentry.data.get(
            CONF_ENTITY_ALIASES, DEFAULT_ENTITY_ALIASES
        )

        def _should_inject(e: er.RegistryEntry) -> bool:
            if enabled_domains_set and e.domain not in enabled_domains_set:
                return False
            # Read-only context: include non-exposed entities too so the
            # model can answer truthfully about real states.
            return True

        for area_entry in matched_areas:
            # Collect entities matching this area + optional domain filter
            area_entities = []
            seen_ids = set()
            area_lower = area_entry.name.lower()

            for e in entity_registry.entities.values():
                if not _should_inject(e):
                    continue
                if domain_hint and e.domain != domain_hint:
                    continue
                if e.area_id == area_entry.id:
                    area_entities.append(e)
                    seen_ids.add(e.entity_id)

            for e in entity_registry.entities.values():
                if e.entity_id in seen_ids:
                    continue
                if not _should_inject(e):
                    continue
                if domain_hint and e.domain != domain_hint:
                    continue
                name_text = (e.name or e.original_name or "").lower()
                alias_text = " ".join(
                    a for a in e.aliases if isinstance(a, str)
                ).lower()
                if (
                    area_lower in name_text
                    or area_lower in e.entity_id.lower()
                    or area_lower in alias_text
                ):
                    area_entities.append(e)
                    seen_ids.add(e.entity_id)

            if not area_entities:
                continue

            # Build state block
            label = f" ({domain_hint})" if domain_hint else ""
            entity_context = (
                f"## Current states for area '{area_entry.name}'{label}"
                f"\nUse THIS data directly. DO NOT call get_entity_state or"
                f" get_entities_in_area for these entities.\n"
            )
            for entity_entry in area_entities:
                state_obj = self.hass.states.get(entity_entry.entity_id)
                if state_obj is None:
                    continue
                friendly = self._pretty_entity_name(
                    entity_entry.entity_id,
                    entity_entry.name or entity_entry.original_name,
                    state_obj,
                )
                alias = entity_aliases.get(entity_entry.entity_id)
                if alias:
                    friendly = f"{friendly} ({alias})"
                entity_context += self._format_entity_state(
                    entity_entry.entity_id, friendly, state_obj
                )

            _LOGGER.debug(
                "Injected %d entity states for area '%s'%s (%d chars)",
                len(area_entities),
                area_entry.name,
                label,
                len(entity_context),
            )
            chat_log.content.insert(
                insert_idx,
                conversation.SystemContent(content=entity_context),
            )
            insert_idx += 1

        return insert_idx

    async def _inject_domain_states(
        self,
        chat_log: conversation.ChatLog,
        domain: str,
        start_idx: int,
    ) -> int:
        """Inject states for ALL exposed entities of a domain (no-area fallback).

        Used when the user asks a domain-scoped question without naming
        an area (e.g. "how many lights are on?"). The model then
        has the data inline and can answer without tool calls.
        """
        entity_registry = er.async_get(self.hass)
        enabled_domains = self.subentry.data.get(
            CONF_ENABLED_DOMAINS, DEFAULT_ENABLED_DOMAINS
        )
        enabled_domains_set = (
            set(enabled_domains) if enabled_domains else set()
        )
        entity_aliases = self.subentry.data.get(
            CONF_ENTITY_ALIASES, DEFAULT_ENTITY_ALIASES
        )

        # Read-only context injection: do NOT gate on conversation
        # exposure. Exposure only matters for control actions; here we
        # just surface actual states so the model can answer truthfully
        # (e.g. a light the user forgot to expose still shows as on).
        domain_entities = []
        for e in entity_registry.entities.values():
            if e.domain != domain:
                continue
            if enabled_domains_set and e.domain not in enabled_domains_set:
                continue
            domain_entities.append(e)

        if not domain_entities:
            _LOGGER.debug(
                "No entities for domain '%s' to inject", domain
            )
            return start_idx

        entity_context = (
            f"## Current states for all '{domain}' entities\n"
            f"Use THIS data directly. DO NOT call get_entity_state or"
            f" get_entities_in_area for these entities.\n"
        )
        for entity_entry in domain_entities:
            state_obj = self.hass.states.get(entity_entry.entity_id)
            if state_obj is None:
                continue
            friendly = self._pretty_entity_name(
                entity_entry.entity_id,
                entity_entry.name or entity_entry.original_name,
                state_obj,
            )
            alias = entity_aliases.get(entity_entry.entity_id)
            if alias:
                friendly = f"{friendly} ({alias})"
            entity_context += self._format_entity_state(
                entity_entry.entity_id, friendly, state_obj
            )

        _LOGGER.debug(
            "Injected %d '%s' entity states (%d chars)",
            len(domain_entities),
            domain,
            len(entity_context),
        )
        chat_log.content.insert(
            start_idx,
            conversation.SystemContent(content=entity_context),
        )
        return start_idx + 1

    # Attribute keys that are metadata, not the entity's actual state/value.
    _STATE_METADATA_KEYS = frozenset(
        {
            "friendly_name",
            "entity_id",
            "icon",
            "entity_picture",
            "device_class",
            "supported_features",
            "supported_color_modes",
            "state_class",
            "attribution",
            "assumed_state",
            "restored",
            "saved_state",
            "initial_state",
        }
    )

    async def _render_technical_prompt(
        self,
        template: str,
        options: dict[str, Any],
        now_local: Any,
    ) -> str:
        """Render the user-editable technical prompt with live placeholders.

        Supports {index} (compact home index), {current_area},
        {response_mode} (follow-up instruction block), {time}, {date}.
        Unknown placeholders are left untouched so MCP-Assist-style
        templates keep working.
        """
        index_manager = self.hass.data.get(DOMAIN, {}).get("index_manager")
        index_text = ""
        if index_manager:
            index = await index_manager.get_index()
            if index:
                area_summary = ", ".join(
                    f"{a['name']} ({a['entity_count']} ent.)"
                    for a in index.get("areas", [])
                )
                domain_summary = ", ".join(
                    f"{d} ({c})" for d, c in index.get("domains", {}).items()
                )
                index_text = f"Areas: {area_summary}\nDomains: {domain_summary}"

        response_mode = options.get(CONF_RESPONSE_MODE, DEFAULT_RESPONSE_MODE)
        rm_text = RESPONSE_MODE_INSTRUCTIONS.get(response_mode, "")

        # Safe format: only substitute known placeholders and ignore
        # KeyError for any the template doesn't use.
        values = {
            "index": index_text,
            "current_area": "",
            "response_mode": rm_text,
            "time": now_local.strftime("%H:%M"),
            "date": now_local.strftime("%d/%m/%Y"),
        }
        try:
            return template.format(**values)
        except (KeyError, IndexError, ValueError):
            return template

    @staticmethod
    def _pretty_entity_name(
        entity_id: str,
        registry_name: str | None,
        state_obj: Any,
    ) -> str:
        """Return a human-readable name, never a raw entity_id.

        Falls back to the state's friendly_name attribute, then to a
        humanized version of the entity_id (e.g. 'luz_1s_comedor' ->
        'Luz 1s Comedor') so the model cites a readable label.
        """
        name = registry_name or (
            state_obj.attributes.get("friendly_name") if state_obj else None
        )
        if name:
            return str(name)
        # Humanize the entity_id: strip domain prefix, split on _,
        # title-case, keep trailing tokens like '1s'/'2n' uppercased.
        slug = entity_id.split(".", 1)[-1]
        parts = [p.upper() if p[:1].isdigit() else p.capitalize() for p in slug.split("_")]
        return " ".join(parts)

    @staticmethod
    def _format_entity_state(
        entity_id: str,
        friendly: str,
        state_obj: Any,
    ) -> str:
        """Render an entity's state plus its useful attributes for injection.

        ``state`` alone is often insufficient (e.g. a climate entity's state
        is just the HVAC mode). Including value attributes (temperature,
        brightness, humidity, …) lets the LLM answer directly instead of
        calling ``get_entity_state``.
        """
        if state_obj is None:
            return f"- {friendly} ({entity_id}): unknown\n"

        # Climate entities have two temperature fields: "temperature" (set
        # point) and "current_temperature" (actual).  Rename the set point so
        # the LLM doesn't confuse them.
        is_climate = entity_id.startswith("climate.")
        extras: list[str] = []
        for key, val in state_obj.attributes.items():
            if key in LemonadeConversationEntity._STATE_METADATA_KEYS:
                continue
            if isinstance(val, (list, dict)):
                continue
            label = key
            if is_climate and key == "temperature":
                label = "target_temperature"
            extras.append(f"{label}={val}")
        extras = extras[:8]

        if extras:
            return f"- {friendly} ({entity_id}): {state_obj.state} ({', '.join(extras)})\n"
        return f"- {friendly} ({entity_id}): {state_obj.state}\n"

    @staticmethod
    def _cleanup_stale_system_content(chat_log: conversation.ChatLog) -> None:
        """Remove stale injected SystemContent from previous turns.

        _async_prepare_chat_log adds fresh system content (home structure,
        reminders, technical prompt) at the end of chat_log each turn.
        Area-state injections, RAG context, and CRITICAL REMINDER entries
        from previous turns accumulate and bloat the context — strip them.
        """
        stale_prefixes = (
            "## Current states for area",
            "Other relevant entities for this request",
            "CRITICAL REMINDER",
        )
        chat_log.content[:] = [
            c
            for c in chat_log.content
            if not (
                isinstance(c, conversation.SystemContent)
                and c.content.startswith(stale_prefixes)
            )
        ]

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
    ) -> None:
        """Generate an answer for the chat log with streaming and tool-call loop."""
        assert self._client is not None

        tools = self._get_tools(chat_log)
        options = self.subentry.data

        # Strip stale injected system content from previous turns
        self._cleanup_stale_system_content(chat_log)

        # Debug mode: bump logging for this handler
        debug_mode = options.get(CONF_DEBUG_MODE, DEFAULT_DEBUG_MODE)
        if isinstance(debug_mode, str):
            debug_mode = debug_mode in ("1", "true", "yes", "on")
        if debug_mode:
            _LOGGER.setLevel(logging.DEBUG)

        _LOGGER.debug(
            "Starting chat with server_url=%s, model=%s",
            self._client.server_url,
            options.get(CONF_MODEL_NAME),
        )

        # Extract the user prompt once before any injection so downstream
        # code (area-injection, RAG) operates on the original user message.
        user_prompt = ""
        if chat_log.content:
            for c in reversed(chat_log.content):
                if isinstance(c, conversation.UserContent):
                    user_prompt = c.content or ""
                    break

        # Check if user input matches an end word — short-circuit if so
        end_words_raw = options.get(CONF_END_WORDS, "")
        if end_words_raw and user_prompt:
            end_words = [w.strip().lower() for w in end_words_raw.split(",") if w.strip()]
            prompt_lower = user_prompt.strip().lower().rstrip(".!?")
            if prompt_lower in end_words or any(
                prompt_lower == ew for ew in end_words
            ):
                _LOGGER.debug("End word matched, returning brief goodbye")
                chat_log.async_add_assistant_content_without_tools(
                    conversation.AssistantContent(
                        agent_id=self.entity_id,
                        content="You're welcome! Feel free to ask if you need anything else.",
                    )
                )
                return

        # Analyse the prompt for domain / action hints
        intent = extract_prompt_intent(user_prompt)
        domain_hint = intent["domain_hint"]
        action_hint = intent["action_hint"]
        if domain_hint or action_hint:
            _LOGGER.debug(
                "Prompt intent: domain=%s action=%s",
                domain_hint,
                action_hint,
            )

        # All current-turn context is inserted right after the last user
        # message so _build_messages keeps it (the "current-turn zone").
        # A single shared index keeps the blocks in a stable order:
        #   <user> <area states> <rag context> <CRITICAL REMINDER>
        post_user_idx = self._find_user_content_idx(chat_log)
        cur_idx = (
            post_user_idx + 1
            if post_user_idx is not None
            else len(chat_log.content)
        )

        # Pre-inject entity states for areas mentioned in the prompt
        cur_idx = await self._inject_area_entity_states(
            chat_log, user_prompt, intent, cur_idx
        )

        # RAG: local keyword-based entity retrieval per user prompt
        max_iterations = int(options.get(CONF_MAX_ITERATIONS, DEFAULT_MAX_ITERATIONS))
        enable_rag = options.get(CONF_ENABLE_RAG, DEFAULT_ENABLE_RAG)
        if isinstance(enable_rag, str):
            enable_rag = enable_rag in ("1", "true", "yes", "on")
        rag_top_k = int(options.get(CONF_RAG_TOP_K, DEFAULT_RAG_TOP_K))
        if post_user_idx is not None and enable_rag and user_prompt:
            rag_index = self.hass.data[DOMAIN].get("rag_index")
            if rag_index is None:
                cache_dir = f"{self.hass.config.config_dir}/lemonade_rag_cache"
                rag_index = RAGIndex(cache_dir)
                await rag_index.load()
                self.hass.data[DOMAIN]["rag_index"] = rag_index
            if not rag_index._entries:
                try:
                    await rag_index.refresh(self.hass)
                except Exception:
                    enable_rag = False
            else:
                try:
                    relevant = await rag_index.query(
                        user_prompt,
                        top_k=rag_top_k,
                        domain_filter=domain_hint,
                        area_filter=None,
                    )
                    respect_exposure = bool(
                        options.get(CONF_RESPECT_EXPOSURE, DEFAULT_RESPECT_EXPOSURE)
                    )
                    if respect_exposure:
                        relevant = [
                            e for e in relevant
                            if async_should_expose(self.hass, "conversation", e["entity_id"])
                        ]
                    if relevant:
                        entity_context = "Other relevant entities for this request:\n"
                        for e in relevant:
                            state_obj = self.hass.states.get(e["entity_id"])
                            state_str = state_obj.state if state_obj else "unknown"
                            entity_context += (
                                f"- {e['entity_id']} (domain: {e['domain']}, "
                                f"state: {state_str}) in {e['area'] or 'unassigned'}: "
                                f"{e['name']}\n"
                            )
                        _LOGGER.debug(
                            "RAG entity context injected (%d chars): %s",
                            len(entity_context),
                            entity_context[:200],
                        )
                        chat_log.content.insert(
                            cur_idx,
                            conversation.SystemContent(content=entity_context),
                        )
                        cur_idx += 1
                except Exception:
                    pass

        # Bookend: insert reminders after the injected context so the LLM
        # re-reads the "don't call tools" instruction right after the states.
        if post_user_idx is not None:
            chat_log.content.insert(
                cur_idx,
                conversation.SystemContent(
                    content=(
                        "CRITICAL REMINDER: All necessary entity states are "
                        "provided ABOVE. Answer using those states directly. "
                        "Do NOT call get_entity_state or get_entities_in_area."
                    )
                ),
            )
            cur_idx += 1
            chat_log.content.insert(
                cur_idx,
                conversation.SystemContent(
                    content=(
                        "HONESTY RULE: NEVER make up or hallucinate data. "
                        "If there is no climate, temperature, or humidity "
                        "data for a requested area, say so honestly "
                        "(e.g. \"No tengo datos de temperatura para esa área\"). "
                        "Do NOT invent temperatures or pretend a sensor exists "
                        "when the available data does not include one."
                    )
                ),
            )

        enable_streaming = options.get(CONF_ENABLE_STREAMING, DEFAULT_ENABLE_STREAMING)
        if isinstance(enable_streaming, str):
            enable_streaming = enable_streaming in ("1", "true", "yes", "on")

        respect_exposure = bool(
            options.get(CONF_RESPECT_EXPOSURE, DEFAULT_RESPECT_EXPOSURE)
        )
        if respect_exposure and chat_log.llm_api is not None:
            original_call = chat_log.llm_api.async_call_tool

            async def _exposure_filtered_call(
                tool_input: ToolInput,
            ) -> dict[str, Any]:
                result = await original_call(tool_input)
                if tool_input.tool_name == "get_entity_state":
                    entity_id = (tool_input.tool_args or {}).get("entity_id")
                    if entity_id and not async_should_expose(
                        self.hass, "conversation", entity_id
                    ):
                        _LOGGER.debug(
                            "Blocked get_entity_state for unexposed entity: %s",
                            entity_id,
                        )
                        return {
                            "error": "not_exposed",
                            "error_text": (
                                f"Entity {entity_id} is not exposed to "
                                f"this assistant and cannot be accessed."
                            ),
                        }
                elif tool_input.tool_name == "get_entities_in_area":
                    entities = (result or {}).get("entities", [])
                    filtered = [
                        e
                        for e in entities
                        if async_should_expose(
                            self.hass, "conversation", e.get("entity_id", "")
                        )
                    ]
                    if result is not None:
                        result = {**result, "entities": filtered, "count": len(filtered)}
                return result

            chat_log.llm_api.async_call_tool = _exposure_filtered_call

        for iteration in range(max_iterations):
            _LOGGER.debug("Chat iteration %d", iteration)
            messages = self._build_messages(chat_log)
            payload = self._build_payload(messages, tools, stream=enable_streaming)

            # --- streaming path (skipped if disabled or after a failure) --- #
            if enable_streaming:
                try:
                    had_tool_calls = False

                    async def _content_iter(
                        raw: AsyncGenerator[dict[str, Any], None],
                    ) -> AsyncGenerator[dict[str, Any], None]:
                        """Pass all delta types through to ``async_add_delta_content_stream``.

                        ``async_add_delta_content_stream`` accepts dicts with
                        ``content``, ``tool_calls``, and ``thinking_content`` keys
                        and accumulates them into a single ``AssistantContent`` at
                        stream end.
                        """
                        nonlocal had_tool_calls
                        async for delta in raw:
                            _LOGGER.debug("Stream delta: %s", delta)
                            # Pass through content deltas
                            if "content" in delta and delta["content"] is not None:
                                yield {"content": delta["content"]}
                            # Pass through tool calls (already ToolInput objects)
                            tc = delta.get("tool_calls")
                            if tc:
                                had_tool_calls = True
                                yield {"tool_calls": tc}
                            # Pass through thinking/reasoning content
                            think = (
                                delta.get("thinking_content")
                                or delta.get("reasoning_content")
                                or ""
                            )
                            if think:
                                yield {"thinking_content": think}

                    async for _ in chat_log.async_add_delta_content_stream(
                        self.entity_id,
                        _content_iter(
                            self._client.chat_completions_stream(payload)
                        ),
                    ):
                        pass

                    # ``async_add_delta_content_stream`` already created a single
                    # ``AssistantContent`` with content + tool_calls (if any),
                    # added it to the chat log (via ``async_add_assistant_content``),
                    # and executed any tool calls. However,
                    # ``async_add_assistant_content`` does NOT notify frontend
                    # subscribers (``_async_notify_subscribers``), so the
                    # response never renders in the UI.  Workaround: pop the
                    # silent duplicate and re-add via
                    # ``async_add_assistant_content_without_tools`` which DOES
                    # fire the notification event.
                    if had_tool_calls:
                        continue

                    # Text-only response — notify frontend
                    last = chat_log.content[-1]
                    if (
                        isinstance(last, conversation.AssistantContent)
                        and not last.tool_calls
                    ):
                        chat_log.content.pop()
                        chat_log.async_add_assistant_content_without_tools(last)

                    # Done
                    break

                except (LemonadeConnectionError, LemonadeAPIError) as err:
                    _LOGGER.error(
                        "Streaming failed for iteration %d: %s", iteration, err
                    )
                    # Disable streaming for this and remaining iterations,
                    # then fall through to the non-streaming path below.
                    enable_streaming = False
                    payload = self._build_payload(
                        messages, tools, stream=False
                    )

            # --- non-streaming path (primary or post-streaming fallback) --- #
            try:
                data = await self._client.chat_completions(payload)
                message = data["choices"][0]["message"]
            except (LemonadeConnectionError, LemonadeAPIError) as retry_err:
                raise HomeAssistantError(
                    f"Connection error: {retry_err}"
                ) from retry_err

            # Process the non-streaming message
            thinking_content = None
            content_text = message.get("content", "")
            if content_text:
                cleaned, thinking = self._extract_thinking(content_text)
                content_text = cleaned
                thinking_content = thinking or None
                if options.get(CONF_CLEAN_RESPONSES, DEFAULT_CLEAN_RESPONSES):
                    content_text = self._clean_response(content_text)

            if message.get("tool_calls"):
                tool_inputs = [
                    ToolInput(
                        tool_name=tc["function"]["name"],
                        tool_args=tc["function"]["arguments"]
                        if isinstance(tc["function"]["arguments"], dict)
                        else json.loads(tc["function"]["arguments"]),
                        id=tc["id"],
                    )
                    for tc in message["tool_calls"]
                ]
                async for _ in chat_log.async_add_assistant_content(
                    conversation.AssistantContent(
                        agent_id=self.entity_id,
                        content=content_text or None,
                        thinking_content=thinking_content,
                        tool_calls=tool_inputs,
                    ),
                ):
                    pass
                continue

            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(
                    agent_id=self.entity_id,
                    content=content_text or None,
                    thinking_content=thinking_content,
                ),
            )
            break

        else:
            _LOGGER.error("Max tool calling iterations reached")
            raise HomeAssistantError("Max tool calling iterations reached")