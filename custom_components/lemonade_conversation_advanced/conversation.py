"""Conversation support for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncGenerator
from typing import Any, Literal, override
import aiohttp

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from voluptuous_openapi import convert
from homeassistant.helpers.llm import ToolInput

from .const import DOMAIN
from .entity import LemonadeBaseEntity
from .llm_tools import async_get_tools as local_async_get_tools
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

    @override
    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

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
                import json
                chat_log.content.append(
                    conversation.SystemContent(
                        content=f"## System Index\n\n{json.dumps(index, indent=2)}"
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

    async def async_process(
        self,
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """Process a sentence, keeping HA's streaming path available."""
        return await super().async_process(user_input)

    # ------------------------------------------------------------------ #
    #  Helpers – build messages / payload from ChatLog                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_messages(chat_log: conversation.ChatLog) -> list[dict[str, Any]]:
        """Serialise ChatLog content into OpenAI-format messages."""
        import json

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

    def _get_headers(self) -> dict[str, str]:
        """Return HTTP headers for the API call."""
        api_key = self.entry.data.get("api_key", "")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

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
    #  Thinking-tag extraction                                             #
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
        # Remove empty thinking tags that may remain
        cleaned = re.sub(r"<nik[^>]*>|</nik>", "", cleaned, flags=re.IGNORECASE)
        return cleaned, "\n".join(thinking_parts)

    # ------------------------------------------------------------------ #
    #  SSE streaming parser - returns async generator                      #
    # ------------------------------------------------------------------ #

    async def _iter_sse_deltas(
        self,
        response: aiohttp.ClientResponse,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Parse an SSE stream into OpenAI-format deltas.

        Yields AssistantContentDeltaDict-compatible dicts.
        """
        import json as _json

        content_buf = ""
        tc_accum: dict[int, dict[str, Any]] = {}
        in_thinking = False
        thinking_tag_buffer = ""

        # Use text() to read entire response body - more reliable than iter_chunks
        # for Lemonade Server which may send non-chunked responses
        try:
            text = await response.text()
            _LOGGER.debug("Raw response text (first 500 chars): %s", text[:500])
        except Exception as e:
            _LOGGER.error("Failed to read response text: %s", e)
            # Fallback to reading in chunks if full text fails
            chunks = []
            async for chunk in response.content.iter_chunked(4096):
                chunks.append(chunk.decode("utf-8", errors="replace"))
            text = "".join(chunks)

        # Process line by line
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # OpenAI SSE format: "data: {...}" or "data: [DONE]"
            if line.startswith("data: "):
                if line == "data: [DONE]":
                    _LOGGER.debug("Got SSE [DONE]")
                    break
                try:
                    data = _json.loads(line[6:])
                except ValueError as e:
                    _LOGGER.warning("Failed to parse SSE line: %s", e)
                    continue
                choice = data.get("choices", [{}])[0]
                delta = choice.get("delta", {})
            # Ollama format: raw JSON per line (non-streaming returns single JSON)
            elif line.startswith("{"):
                try:
                    data = _json.loads(line)
                except ValueError as e:
                    _LOGGER.warning("Failed to parse JSON line: %s", e)
                    continue
                if data.get("done"):
                    _LOGGER.debug("Got Ollama done marker")
                    break
                delta = data.get("message", {})
                # Ollama uses "content" at top level when streaming
                if "content" in data and not delta:
                    delta = {"content": data["content"]}
            else:
                _LOGGER.debug("Unknown line format: %s", line[:100])
                continue

            if not delta:
                continue

            _LOGGER.debug("Parsed delta: %s", delta)

            raw_content = delta.get("content") or ""
            if raw_content:
                content_buf += raw_content

                # Handle thinking tags - stream content in real-time
                while content_buf:
                    if in_thinking:
                        end_tag = "</nik>" if thinking_tag_buffer == "<nik" else "<|/thought|>"
                        end_idx = content_buf.find(end_tag)
                        if end_idx == -1:
                            break
                        thinking_tag_buffer = ""
                        content_buf = content_buf[end_idx + len(end_tag):]
                        in_thinking = False
                        continue

                    think_idx = content_buf.find("<nik")
                    alt_idx = content_buf.find("<|thought|>")
                    candidates = [idx for idx in (think_idx, alt_idx) if idx != -1]
                    if not candidates:
                        # Stream out available content
                        if content_buf:
                            yield {"content": content_buf}
                        content_buf = ""
                        break

                    next_idx = min(candidates)
                    if next_idx > 0:
                        yield {"content": content_buf[:next_idx]}

                    if think_idx != -1 and think_idx == next_idx:
                        thinking_tag_buffer = "<nik"
                        content_buf = content_buf[next_idx + 4:]  # len("<nik") = 4
                    else:
                        thinking_tag_buffer = "<|thought|>"
                        content_buf = content_buf[next_idx + len("<|thought|>"):]
                    in_thinking = True

            # Lemonade uses 'reasoning_content' instead of 'thinking_content'
            # Map both to thinking_content for HA compatibility
            rc_field = delta.get("reasoning_content") or delta.get("thinking_content") or ""
            if rc_field:
                yield {"thinking_content": rc_field}

            for tc_delta in delta.get("tool_calls") or []:
                idx = tc_delta.get("index", 0)
                if idx not in tc_accum:
                    tc_accum[idx] = {}
                entry = tc_accum[idx]
                if "id" in tc_delta:
                    entry["id"] = tc_delta["id"]
                func = tc_delta.get("function", {})
                if "name" in func:
                    entry["name"] = func["name"]
                if "arguments" in func:
                    entry["args_str"] = entry.get("args_str", "") + func["arguments"]

        # Flush remaining content buffer
        if content_buf and not in_thinking:
            yield {"content": content_buf}

        # Yield accumulated tool calls as ToolInput objects so
        # async_add_delta_content_stream can execute them via
        # chat_log.llm_api.async_call_tool internally.
        for idx in sorted(tc_accum):
            tc = tc_accum[idx]
            if "id" in tc and "name" in tc and "args_str" in tc:
                try:
                    args = _json.loads(tc["args_str"])
                except (_json.JSONDecodeError, ValueError):
                    args = {}
                yield {
                    "tool_calls": [
                        ToolInput(
                            tool_name=tc["name"],
                            tool_args=args,
                            id=tc["id"],
                        )
                    ]
                }

    # ------------------------------------------------------------------ #
    #  Non-streaming fallback                                              #
    # ------------------------------------------------------------------ #

    async def _call_api_non_streaming(
        self,
        session: aiohttp.ClientSession,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Make a non-streaming API call and return the message dict."""
        async with session.post(
            f"{self.entry.data.get('server_url', '')}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                _LOGGER.error("Non-streaming LLM error: %s", text)
                raise HomeAssistantError(f"LLM error: {text}")
            data = await resp.json()
            _LOGGER.debug("Non-streaming response: %s", data)
            return data["choices"][0]["message"]

    # ------------------------------------------------------------------ #
    #  Main handler                                                        #
    # ------------------------------------------------------------------ #

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
    ) -> None:
        """Generate an answer for the chat log with streaming and tool-call loop."""
        import json

        session = async_get_clientsession(self.hass)
        headers = self._get_headers()
        server_url = self.entry.data.get("server_url", "")
        api_url = f"{server_url}/v1/chat/completions"
        tools = self._get_tools(chat_log)
        _LOGGER.debug("Starting chat with server_url=%s, model=%s", server_url, self.subentry.data.get("model_name"))

        # RAG: local keyword-based entity retrieval per user prompt
        options = self.subentry.data
        max_iterations = options.get("max_iterations", 10)
        enable_rag = options.get("enable_rag", True)
        rag_top_k = options.get("rag_top_k", 12)
        if enable_rag and server_url:
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
                user_prompt = chat_log.content[-1].content if chat_log.content else ""
                if user_prompt:
                    try:
                        relevant = await rag_index.query(user_prompt, top_k=rag_top_k)
                        if relevant:
                            entity_context = "Current states of relevant entities for this request:\n"
                            for e in relevant:
                                state_obj = self.hass.states.get(e["entity_id"])
                                state_str = state_obj.state if state_obj else "unknown"
                                entity_context += f"- {e['entity_id']} (domain: {e['domain']}, state: {state_str}) in {e['area'] or 'unassigned'}: {e['name']}\n"
                            chat_log.content.append(conversation.SystemContent(content=entity_context))
                    except Exception:
                        pass

        for iteration in range(max_iterations):
            _LOGGER.debug("Chat iteration %d", iteration)
            messages = self._build_messages(chat_log)
            payload = self._build_payload(messages, tools, stream=True)

            # --- try streaming first, fallback to non-streaming --------- #
            try:
                async with session.post(
                    api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status >= 400:
                        err_text = await resp.text()
                        _LOGGER.error("Streaming LLM error (status %d): %s", resp.status, err_text)
                        raise HomeAssistantError(f"LLM error: {err_text}")

                    # Stream deltas to chat_log – tool calls are yielded as ToolInput
                    # objects from _iter_sse_deltas, and async_add_delta_content_stream
                    # executes them via chat_log.llm_api.async_call_tool internally.
                    async for delta in chat_log.async_add_delta_content_stream(
                        self.entity_id,
                        self._iter_sse_deltas(resp),
                    ):
                        _LOGGER.debug("Chat log received delta: %s", delta)

                    # If the last entry in chat_log is a tool result (added by
                    # async_add_delta_content_stream), continue the loop so the LLM
                    # sees the result in the next iteration.
                    if chat_log.unresponded_tool_results:
                        continue

                    # No tool calls – final text response
                    break

            except aiohttp.ClientError as err:
                _LOGGER.error("Streaming connection error: %s", err)
                # Timeout or network error – retry once with non-streaming
                try:
                    messages = self._build_messages(chat_log)
                    payload = self._build_payload(messages, tools, stream=False)
                    message = await self._call_api_non_streaming(session, payload, headers)
                except (aiohttp.ClientError, HomeAssistantError) as retry_err:
                    raise HomeAssistantError(
                        f"Connection error: {err} (retry failed: {retry_err})"
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
                            tool_args=tc["function"]["arguments"] if isinstance(tc["function"]["arguments"], dict) else json.loads(tc["function"]["arguments"]),
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