"""Conversation support for Lemonade Conversation Advanced."""

from __future__ import annotations

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

from .const import DOMAIN
from .entity import LemonadeBaseEntity
from .llm_tools import async_get_tools as local_async_get_tools
from .rag import RAGIndex

# Regex patterns for thinking/reasoning tags embedded in content
_THINKING_PATTERNS = [
    re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE),
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

        await self._async_handle_chat_log(chat_log)

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
        return cleaned, "\n".join(thinking_parts)

    # ------------------------------------------------------------------ #
    #  SSE streaming parser                                                #
    # ------------------------------------------------------------------ #

    async def _parse_sse_stream(
        self,
        response: aiohttp.ClientResponse,
        chat_log: conversation.ChatLog,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Parse an SSE stream into accumulated deltas.

        Yields ``AssistantContentDeltaDict``-compatible dicts.  Content is
        buffered to detect ``<think>`` tags that span multiple chunks.
        """
        import json as _json

        content_buf = ""
        tc_accum: dict[int, dict[str, Any]] = {}
        in_thinking = False
        thinking_tag_buffer = ""

        async for raw_line in response.content:
            if not raw_line:
                continue
            line = raw_line.decode("utf-8").strip()

            # Ollama: complete JSON per line
            if line.startswith("{"):
                try:
                    data = _json.loads(line)
                except ValueError:
                    continue
                if data.get("done"):
                    break
                msg = data.get("message", {})
                delta: dict[str, Any] = {}
                if msg.get("content"):
                    delta["content"] = msg["content"]
                if msg.get("tool_calls"):
                    delta["tool_calls"] = msg["tool_calls"]
                if not delta:
                    continue
                line_data = delta

            # OpenAI SSE format
            elif line.startswith("data: "):
                if line == "data: [DONE]":
                    break
                try:
                    data = _json.loads(line[6:])
                except ValueError:
                    continue
                choice = data.get("choices", [{}])[0]
                line_data = choice.get("delta", {})
                if not line_data:
                    continue
            else:
                continue

            raw_content = line_data.get("content") or ""
            if raw_content:
                content_buf += raw_content

                if not in_thinking and "<think>" not in content_buf and "<|thought|>" not in content_buf:
                    yield {"content": content_buf}
                    content_buf = ""
                else:
                    while content_buf:
                        if in_thinking:
                            end_tag = "</think>" if thinking_tag_buffer == "<think>" else "<|/thought|>"
                            end_idx = content_buf.find(end_tag)
                            if end_idx == -1:
                                break
                            content_buf = content_buf[end_idx + len(end_tag):]
                            in_thinking = False
                            thinking_tag_buffer = ""
                            continue

                        think_idx = content_buf.find("<think>")
                        alt_idx = content_buf.find("<|thought|>")
                        candidates = [idx for idx in (think_idx, alt_idx) if idx != -1]
                        if not candidates:
                            if content_buf:
                                yield {"content": content_buf}
                                content_buf = ""
                            break

                        next_idx = min(candidates)
                        if next_idx > 0:
                            yield {"content": content_buf[:next_idx]}

                        if think_idx != -1 and think_idx == next_idx:
                            thinking_tag_buffer = "<think>"
                            content_buf = content_buf[next_idx + len("<think>"):]
                        else:
                            thinking_tag_buffer = "<|thought|>"
                            content_buf = content_buf[next_idx + len("<|thought|>"):]
                        in_thinking = True

            tc_field = line_data.get("thinking_content") or ""
            if tc_field:
                yield {"thinking_content": tc_field}

            for tc_delta in line_data.get("tool_calls") or []:
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

        if content_buf and not in_thinking:
            yield {"content": content_buf}

        # Flush accumulated tool calls
        for idx in sorted(tc_accum):
            tc = tc_accum[idx]
            if "id" in tc and "name" in tc and "args_str" in tc:
                try:
                    args = _json.loads(tc["args_str"])
                except (_json.JSONDecodeError, ValueError):
                    args = {}
                yield {
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": args},
                        }
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
                raise HomeAssistantError(f"LLM error: {text}")
            data = await resp.json()
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
        max_iterations = 5

        # RAG: semantic entity retrieval per user prompt
        options = self.subentry.data
        enable_rag = options.get("enable_rag", True)
        rag_top_k = options.get("rag_top_k", 12)
        if enable_rag and server_url:
            cache_dir = f"{self.hass.config.config_dir}/lemonade_rag_cache"
            rag_index = RAGIndex(cache_dir)
            await rag_index.load()
            if not rag_index._entries:
                try:
                    await rag_index.refresh(self.hass, session, server_url)
                except Exception:
                    enable_rag = False
            else:
                user_prompt = chat_log.content[-1].content if chat_log.content else ""
                if user_prompt:
                    try:
                        relevant = await rag_index.query(session, user_prompt, server_url, top_k=rag_top_k)
                        if relevant:
                            entity_context = "Relevant entities for this request:\n"
                            for e in relevant:
                                entity_context += f"- {e['entity_id']} ({e['domain']}) in {e['area'] or 'unassigned'}: {e['name']}\n"
                            chat_log.async_add_system_content(entity_context)
                    except Exception:
                        pass

        for iteration in range(max_iterations):
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
                        raise HomeAssistantError(f"LLM error: {err_text}")

                    # Feed the SSE stream into HA's delta handler
                    has_tool_result = False
                    async for content in chat_log.async_add_delta_content_stream(
                        self.entity_id,
                        self._parse_sse_stream(resp, chat_log),
                    ):
                        if isinstance(content, conversation.ToolResultContent):
                            has_tool_result = True

                    if has_tool_result:
                        continue  # tool results added – next iteration

                    # No tool calls – final text response already streamed
                    break

            except aiohttp.ClientError as err:
                # Timeout or network error – retry once with non-streaming
                try:
                    payload["stream"] = False
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
                    tc_list = [
                        conversation.ToolCall(
                            id=tc["id"],
                            name=tc["function"]["name"],
                            arguments=json.loads(tc["function"]["arguments"]),
                        )
                        for tc in message["tool_calls"]
                    ]
                    chat_log.async_add_assistant_content(
                        conversation.AssistantContent(
                            agent_id=self.entity_id,
                            content=content_text,
                            thinking_content=thinking_content,
                            tool_calls=tc_list,
                        )
                    )
                    for tc in message["tool_calls"]:
                        await chat_log.async_call_tool(
                            tool_name=tc["function"]["name"],
                            tool_args=json.loads(tc["function"]["arguments"]),
                            tool_call_id=tc["id"],
                            agent_id=self.entity_id,
                        )
                    continue

                chat_log.async_add_assistant_content_without_tools(
                    conversation.AssistantContent(
                        agent_id=self.entity_id,
                        content=content_text,
                        thinking_content=thinking_content,
                    )
                )
                break

        else:
            raise HomeAssistantError("Max tool calling iterations reached")