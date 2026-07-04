"""Conversation agent for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any, Literal, override

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent, llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .backends.openai_compat import LemonadeOpenAICompatBackend
from .const import (
    CONF_DEFAULT_MODEL,
    CONF_MAX_TOKENS,
    CONF_STREAMING,
    CONF_TEMPERATURE,
    CONF_TIMEOUT,
    CONF_TOP_K,
    CONF_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_STREAMING,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    DOMAIN,
)
from .streaming import StreamingProcessor, StreamResult

_LOGGER = logging.getLogger(__name__)


def _format_tool(tool: llm.Tool) -> dict[str, Any]:
    """Format an llm.Tool for OpenAI API."""
    tool_dict: dict[str, Any] = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
        },
    }
    if tool.parameters:
        tool_dict["function"]["parameters"] = tool.parameters.schema
    return tool_dict


def _convert_content(
    content: conversation.Content,
) -> list[dict[str, Any]]:
    """Convert chat log content to OpenAI messages."""
    if isinstance(content, conversation.SystemContent):
        return [{"role": "system", "content": content.content}]
    if isinstance(content, conversation.UserContent):
        return [{"role": "user", "content": content.content}]
    if isinstance(content, conversation.AssistantContent):
        msg: dict[str, Any] = {
            "role": "assistant",
            "content": content.content or "",
        }
        if content.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.tool_name,
                        "arguments": __import__("json").dumps(tc.tool_args),
                    },
                }
                for tc in content.tool_calls
            ]
        return [msg]
    if isinstance(content, conversation.ToolResultContent):
        return [
            {
                "role": "tool",
                "tool_call_id": content.tool_call_id,
                "content": __import__("json").dumps(content.tool_result),
            }
        ]
    return []


class LemonadeConversationEntity(conversation.ConversationEntity):
    """Lemonade Conversation Agent with streaming."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        entry: ConfigEntry,
        backend: LemonadeOpenAICompatBackend,
    ) -> None:
        """Initialize the agent."""
        self.entry = entry
        self.backend = backend
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_agent"
        self._attr_supported_features = (
            conversation.ConversationEntityFeature.CONTROL
        )

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process the user input and call the API."""
        options = self.entry.data

        # Provide LLM data (entities, tools, system prompt)
        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get("llm_hass_api"),
                options.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        # Get configuration
        model = options.get(CONF_DEFAULT_MODEL, "")
        temperature = options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
        top_p = options.get(CONF_TOP_P, DEFAULT_TOP_P)
        top_k = options.get(CONF_TOP_K, DEFAULT_TOP_K)
        max_tokens = options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        streaming = options.get(CONF_STREAMING, DEFAULT_STREAMING)
        timeout = options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        # Format tools for OpenAI API
        tools: list[dict[str, Any]] | None = None
        if chat_log.llm_api:
            tools = [_format_tool(tool) for tool in chat_log.llm_api.tools]

        # Build messages from chat log
        messages = [
            m
            for content in chat_log.content
            for m in _convert_content(content)
        ]

        # Tool calling loop
        for _iteration in range(10):
            # Call the LLM
            response = await self.backend.chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                max_tokens=max_tokens,
                stream=streaming,
                timeout=timeout,
                tools=tools,
                tool_choice="auto" if tools else None,
            )

            # Process response and add to chat log
            if streaming:
                stream_result = self._transform_stream(response)
            else:
                stream_result = self._transform_non_stream(response)

            async for content in chat_log.async_add_delta_content_stream(
                user_input.agent_id, stream_result
            ):
                messages.extend(_convert_content(content))

            if not chat_log.unresponded_tool_results:
                break

        # Return final response
        last_content = chat_log.content[-1]
        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(last_content.content or "")
        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=chat_log.conversation_id,
            continue_conversation=chat_log.continue_conversation,
        )

    def _transform_stream(self, stream: Any):
        """Transform streaming response to delta format."""
        async def _generator():
            processor = StreamingProcessor()
            result = await processor.process_stream(stream)

            # Yield content delta
            if result.content:
                yield {"content": result.content}

            # Yield thinking content if present
            if result.thinking:
                yield {"thinking_content": result.thinking}

            # Yield tool calls if present
            if result.tool_calls_list:
                yield {"tool_calls": result.tool_calls_list}

        return _generator()

    def _transform_non_stream(self, response: Any):
        """Transform non-streaming response to delta format."""
        async def _generator():
            try:
                if not hasattr(response, "choices") or not response.choices:
                    yield {"content": "No response from model"}
                    return

                choice = response.choices[0]
                message = choice.message

                # Yield content
                if message.content:
                    yield {"content": message.content}

                # Yield tool calls
                if hasattr(message, "tool_calls") and message.tool_calls:
                    tool_inputs = []
                    for tc in message.tool_calls:
                        tool_inputs.append(
                            llm.ToolInput(
                                id=tc.id,
                                tool_name=tc.function.name,
                                tool_args=__import__("json").loads(
                                    tc.function.arguments
                                )
                                if tc.function.arguments
                                else {},
                            )
                        )
                    yield {"tool_calls": tool_inputs}

            except Exception as err:
                _LOGGER.error("Error processing response: %s", err)
                yield {"content": f"Error: {err}"}

        return _generator()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entity."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    backend = data["backend"]
    async_add_entities([LemonadeConversationEntity(config_entry, backend)])
