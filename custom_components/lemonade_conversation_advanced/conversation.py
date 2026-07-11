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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.llm import ToolInput
from voluptuous_openapi import convert

from .api import (
    LemonadeAPIClient,
    LemonadeAPIError,
    LemonadeAuthError,
    LemonadeConnectionError,
)
from .const import (
    CONF_CLEAN_RESPONSES,
    CONF_CONNECT_TIMEOUT,
    CONF_CONTROL_HA,
    CONF_DEBUG_MODE,
    CONF_ENABLE_RAG,
    CONF_ENABLE_STREAMING,
    CONF_END_WORDS,
    CONF_FIRST_DELTA_TIMEOUT,
    CONF_FOLLOW_UP_PHRASES,
    CONF_MAX_HISTORY,
    CONF_MAX_ITERATIONS,
    CONF_MAX_RETRIES,
    CONF_MAX_TOKENS,
    CONF_MODEL_NAME,
    CONF_RAG_TOP_K,
    CONF_REQUEST_TIMEOUT,
    CONF_RESPONSE_MODE,
    CONF_RETRY_BACKOFF,
    CONF_SYSTEM_PROMPT,
    CONF_TECHNICAL_PROMPT,
    CONF_TEMPERATURE,
    DEFAULT_CLEAN_RESPONSES,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_CONTROL_HA,
    DEFAULT_DEBUG_MODE,
    DEFAULT_ENABLE_RAG,
    DEFAULT_ENABLE_STREAMING,
    DEFAULT_FIRST_DELTA_TIMEOUT,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_RAG_TOP_K,
    DEFAULT_REQUEST_TIMEOUT,
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

        # Append technical prompt as system content
        technical_prompt = options.get(CONF_TECHNICAL_PROMPT, "")
        if technical_prompt:
            chat_log.content.append(
                conversation.SystemContent(content=technical_prompt)
            )

        # Append response mode instructions
        response_mode = options.get(CONF_RESPONSE_MODE, DEFAULT_RESPONSE_MODE)
        rm_instructions = RESPONSE_MODE_INSTRUCTIONS.get(response_mode)
        if rm_instructions:
            chat_log.content.append(
                conversation.SystemContent(content=rm_instructions)
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

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

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
            return

        for area_entry in matched_areas:
            # Collect entities matching this area + optional domain filter
            area_entities = []
            seen_ids = set()
            area_lower = area_entry.name.lower()

            for e in entity_registry.entities.values():
                if not async_should_expose(self.hass, "conversation", e.entity_id):
                    continue
                if domain_hint and e.domain != domain_hint:
                    continue
                if e.area_id == area_entry.id:
                    area_entities.append(e)
                    seen_ids.add(e.entity_id)

            for e in entity_registry.entities.values():
                if e.entity_id in seen_ids:
                    continue
                if not async_should_expose(self.hass, "conversation", e.entity_id):
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
                friendly = (
                    entity_entry.name
                    or entity_entry.original_name
                    or entity_entry.entity_id
                )
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
            return f"- {entity_id} ({friendly}): unknown\n"

        extras: list[str] = []
        for key, val in state_obj.attributes.items():
            if key in LemonadeConversationEntity._STATE_METADATA_KEYS:
                continue
            if isinstance(val, (list, dict)):
                continue
            extras.append(f"{key}={val}")
        # Keep the most relevant attributes to avoid bloating the prompt.
        extras = extras[:8]

        if extras:
            return f"- {entity_id} ({friendly}): {state_obj.state} ({', '.join(extras)})\n"
        return f"- {entity_id} ({friendly}): {state_obj.state}\n"

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

        # Bookend: insert a reminder after the injected context so the LLM
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

        enable_streaming = options.get(CONF_ENABLE_STREAMING, DEFAULT_ENABLE_STREAMING)
        if isinstance(enable_streaming, str):
            enable_streaming = enable_streaming in ("1", "true", "yes", "on")

        for iteration in range(max_iterations):
            _LOGGER.debug("Chat iteration %d", iteration)
            messages = self._build_messages(chat_log)
            payload = self._build_payload(messages, tools, stream=enable_streaming)

            # --- streaming path (skipped if disabled or after a failure) --- #
            if enable_streaming:
                try:
                    captured_tool_calls: list[ToolInput] = []
                    captured_thinking: str | None = None

                    async def _content_iter(
                        raw: AsyncGenerator[dict[str, Any], None],
                    ) -> AsyncGenerator[dict[str, Any], None]:
                        """Filter dict stream for HA's ``async_add_delta_content_stream``.

                        ``async_add_delta_content_stream`` expects
                        ``AsyncIterable[dict]`` (it calls ``.get("content")`` on
                        each item).  This adapter:
                          - passes through content-only dicts
                          - captures ``tool_calls`` and ``thinking_content`` for
                            post-stream processing
                        """
                        nonlocal captured_tool_calls, captured_thinking
                        async for delta in raw:
                            _LOGGER.debug("Stream delta: %s", delta)
                            # Capture tool calls for post-stream processing
                            tc = delta.get("tool_calls")
                            if tc:
                                captured_tool_calls.extend(tc)
                            # Capture thinking/reasoning content
                            think = (
                                delta.get("thinking_content")
                                or delta.get("reasoning_content")
                                or ""
                            )
                            if think:
                                captured_thinking = (
                                    captured_thinking or ""
                                ) + think
                            # Pass through content-only deltas to HA's streaming
                            if "content" in delta and delta["content"] is not None:
                                yield {"content": delta["content"]}

                    async for _ in chat_log.async_add_delta_content_stream(
                        self.entity_id,
                        _content_iter(
                            self._client.chat_completions_stream(payload)
                        ),
                    ):
                        pass

                    # If the stream produced tool_calls, add them to the log
                    # so HA can execute them and the loop can continue.
                    if captured_tool_calls:
                        async for _ in chat_log.async_add_assistant_content(
                            conversation.AssistantContent(
                                agent_id=self.entity_id,
                                content=None,
                                thinking_content=captured_thinking,
                                tool_calls=captured_tool_calls,
                            ),
                        ):
                            pass
                        continue

                    # Text-only response — done
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