"""Conversation support for Lemonade Conversation Advanced."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, override

from homeassistant.components import conversation
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
from .const import DOMAIN
from .entity import LemonadeBaseEntity
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
        if self.subentry.data.get(CONF_LLM_HASS_API):
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
        return LemonadeAPIClient(
            hass=self.hass,
            server_url=self.entry.data.get("server_url", ""),
            api_key=self.entry.data.get("api_key", ""),
            request_timeout=self.subentry.data.get("request_timeout", 120.0),
            connect_timeout=self.subentry.data.get("connect_timeout", 15.0),
            first_delta_timeout=self.subentry.data.get("first_delta_timeout", 8.0),
            max_retries=self.subentry.data.get("max_retries", 2),
            retry_backoff=self.subentry.data.get("retry_backoff", 2.0),
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

        # Inject system structure index from IndexManager
        index_manager = self.hass.data.get(DOMAIN, {}).get("index_manager")
        if index_manager:
            index = await index_manager.get_index()
            if index:
                index_json = json.dumps(index, indent=2)
                _LOGGER.debug("IndexManager index injected (%d chars)", len(index_json))
                chat_log.content.append(
                    conversation.SystemContent(
                        content=f"## System Index\n\n{index_json}"
                    )
                )

        # Instruct LLM not to call GetLiveContext — states are already in context
        chat_log.content.append(
            conversation.SystemContent(
                content=(
                    "IMPORTANT: Do NOT call the 'GetLiveContext' tool. "
                    "The current states of all relevant entities are already provided above "
                    "in the System Index and the Current States sections. "
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

    @staticmethod
    def _build_messages(chat_log: conversation.ChatLog) -> list[dict[str, Any]]:
        """Serialise ChatLog content into OpenAI-format messages."""
        messages: list[dict[str, Any]] = []
        for content in chat_log.content:
            if isinstance(content, conversation.SystemContent):
                messages.append({"role": "system", "content": content.content})
            elif isinstance(content, conversation.UserContent):
                messages.append({"role": "user", "content": content.content})
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
                messages.append(msg)
            elif isinstance(content, conversation.ToolResultContent):
                messages.append({
                    "role": "tool",
                    "tool_call_id": content.tool_call_id,
                    "content": json.dumps(content.tool_result),
                })
        return messages

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
            "model": options.get("model_name", ""),
            "messages": messages,
            "temperature": options.get("temperature", 0.7),
            "max_tokens": options.get("max_tokens", 2048),
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

    async def _inject_area_entity_states(
        self,
        chat_log: conversation.ChatLog,
        user_prompt: str,
    ) -> None:
        """Inject entity states for areas mentioned in the user prompt.

        This gives the LLM the entity states directly in its context so it
        can answer without calling ``get_entities_in_area`` /
        ``get_entity_state`` — the same approach MCP Assist uses.
        """
        if not user_prompt:
            return

        area_registry = ar.async_get(self.hass)
        entity_registry = er.async_get(self.hass)

        prompt_lower = user_prompt.lower()

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
            # Collect entities matching this area (same logic as GetEntitiesInAreaTool)
            area_entities = []
            seen_ids = set()
            area_lower = area_entry.name.lower()

            for e in entity_registry.entities.values():
                if e.area_id == area_entry.id:
                    area_entities.append(e)
                    seen_ids.add(e.entity_id)

            for e in entity_registry.entities.values():
                if e.entity_id in seen_ids:
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

            # Build state block — limit to avoid blowing up the context
            entity_context = (
                f"## Current states for area '{area_entry.name}'"
                f"\n(These states are already provided — "
                f"do NOT call get_entity_state or get_entities_in_area"
                f" for this area)\n"
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
                entity_context += (
                    f"- {entity_entry.entity_id} ({friendly}): {state_obj.state}\n"
                )

            _LOGGER.debug(
                "Injected %d entity states for area '%s' (%d chars)",
                len(area_entities),
                area_entry.name,
                len(entity_context),
            )
            chat_log.content.append(
                conversation.SystemContent(content=entity_context)
            )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
    ) -> None:
        """Generate an answer for the chat log with streaming and tool-call loop."""
        assert self._client is not None

        tools = self._get_tools(chat_log)
        _LOGGER.debug(
            "Starting chat with server_url=%s, model=%s",
            self._client.server_url,
            self.subentry.data.get("model_name"),
        )

        # Extract the user prompt once before any injection so downstream
        # code (area-injection, RAG) operates on the original user message.
        user_prompt = ""
        if chat_log.content:
            for c in reversed(chat_log.content):
                if isinstance(c, conversation.UserContent):
                    user_prompt = c.content or ""
                    break

        # Pre-inject entity states for areas mentioned in the prompt
        await self._inject_area_entity_states(chat_log, user_prompt)

        # RAG: local keyword-based entity retrieval per user prompt
        options = self.subentry.data
        max_iterations = options.get("max_iterations", 10)
        enable_rag = options.get("enable_rag", True)
        rag_top_k = options.get("rag_top_k", 12)
        if enable_rag and user_prompt:
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
                    relevant = await rag_index.query(user_prompt, top_k=rag_top_k)
                    if relevant:
                        entity_context = "Current states of relevant entities for this request:\n"
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
                        chat_log.content.append(
                            conversation.SystemContent(content=entity_context)
                        )
                except Exception:
                    pass

        for iteration in range(max_iterations):
            _LOGGER.debug("Chat iteration %d", iteration)
            messages = self._build_messages(chat_log)
            payload = self._build_payload(messages, tools, stream=True)

            # --- try streaming first, fallback to non-streaming --------- #
            try:
                # Wrap the client stream with logging
                async def _log_stream(stream):
                    async for delta in stream:
                        _LOGGER.debug("Stream delta: %s", delta)
                        yield delta

                async for delta in chat_log.async_add_delta_content_stream(
                    self.entity_id,
                    _log_stream(self._client.chat_completions_stream(payload)),
                ):
                    pass

                # If the last entry in chat_log is a tool result (added by
                # async_add_delta_content_stream), continue the loop so the
                # LLM sees the result in the next iteration.
                if chat_log.unresponded_tool_results:
                    continue

                # No tool calls — final text response received
                break

            except (LemonadeConnectionError, LemonadeAPIError) as err:
                _LOGGER.error(
                    "Streaming failed for iteration %d: %s", iteration, err
                )
                # Fall back to non-streaming
                try:
                    messages = self._build_messages(chat_log)
                    payload = self._build_payload(messages, tools, stream=False)
                    data = await self._client.chat_completions(payload)
                    message = data["choices"][0]["message"]
                except (LemonadeConnectionError, LemonadeAPIError) as retry_err:
                    raise HomeAssistantError(
                        f"Connection error: {err} "
                        f"(non-streaming fallback failed: {retry_err})"
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