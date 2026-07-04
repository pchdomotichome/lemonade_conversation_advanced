"""Conversation agent for Lemonade Conversation Advanced."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal, override

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .backends.openai_compat import LemonadeOpenAICompatBackend
from .const import (
    CONF_DEFAULT_MODEL,
    CONF_MAX_TOOL_ITERATIONS,
    CONF_MAX_TOKENS,
    CONF_STREAMING,
    CONF_TEMPERATURE,
    CONF_TIMEOUT,
    CONF_TOP_K,
    CONF_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MAX_TOOL_ITERATIONS,
    DEFAULT_STREAMING,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    DOMAIN,
)
from .streaming import StreamingProcessor, StreamResult

_LOGGER = logging.getLogger(__name__)


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

        # Build messages from chat log
        messages = self._build_messages(chat_log)

        # Get tools from chat log
        tools = self._get_tools(chat_log)

        # Call the LLM
        try:
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

            # Process response
            if streaming:
                result = await self._process_streaming_response(response)
            else:
                result = self._process_non_streaming_response(response)

            # Handle tool calls
            if result.has_tool_calls:
                result = await self._handle_tool_calls(
                    result, messages, tools, model, temperature, top_p,
                    top_k, max_tokens, streaming, timeout, chat_log
                )

            # Store the response in chat log
            chat_log.async_add_assistant_content(
                conversation.AssistantContent(
                    agent_id=self.entity_id,
                    content=result.content,
                )
            )

            return conversation.async_get_result_from_chat_log(user_input, chat_log)

        except Exception as err:
            _LOGGER.error("Error generating response: %s", err)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(f"Error: {err}")
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )

    def _build_messages(
        self, chat_log: conversation.ChatLog
    ) -> list[dict[str, Any]]:
        """Build messages array from chat log."""
        messages = []

        # System prompt
        if chat_log.system_prompt:
            messages.append({
                "role": "system",
                "content": chat_log.system_prompt,
            })

        # Conversation history
        for msg in chat_log.history:
            if isinstance(msg, conversation.UserContent):
                messages.append({
                    "role": "user",
                    "content": msg.content,
                })
            elif isinstance(msg, conversation.AssistantContent):
                msg_dict: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content,
                }
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    msg_dict["tool_calls"] = msg.tool_calls
                messages.append(msg_dict)
            elif isinstance(msg, conversation.ToolResultContent):
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": str(msg.content),
                })

        return messages

    def _get_tools(
        self, chat_log: conversation.ChatLog
    ) -> list[dict[str, Any]] | None:
        """Get tools in OpenAI format from chat log."""
        if not chat_log.tools:
            return None

        tools = []
        for tool in chat_log.tools:
            tool_dict: dict[str, Any] = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                },
            }
            # Handle parameters schema
            if hasattr(tool, "parameters") and tool.parameters:
                if hasattr(tool.parameters, "schema"):
                    tool_dict["function"]["parameters"] = tool.parameters.schema
                elif isinstance(tool.parameters, dict):
                    tool_dict["function"]["parameters"] = tool.parameters
            tools.append(tool_dict)

        return tools if tools else None

    async def _handle_tool_calls(
        self,
        result: StreamResult,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        temperature: float,
        top_p: float,
        top_k: int,
        max_tokens: int,
        streaming: bool,
        timeout: int,
        chat_log: conversation.ChatLog,
    ) -> StreamResult:
        """Handle tool calls from the LLM."""
        # Add assistant message with tool calls
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": result.content or None,
            "tool_calls": result.tool_calls_list,
        }
        messages.append(assistant_msg)

        # Execute each tool call via HA
        for tc in result.tool_calls_list:
            tool_name = tc["function"]["name"]
            tool_args_str = tc["function"]["arguments"]

            try:
                tool_args = json.loads(tool_args_str) if tool_args_str else {}
            except json.JSONDecodeError:
                tool_args = {}

            # Execute via HA intent system
            tool_result = await self._execute_ha_tool(
                tool_name, tool_args, chat_log
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(tool_result),
            })

        # Call LLM again with tool results
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

        if streaming:
            return await self._process_streaming_response(response)
        return self._process_non_streaming_response(response)

    async def _execute_ha_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        chat_log: conversation.ChatLog,
    ) -> dict[str, Any]:
        """Execute a tool via Home Assistant."""
        # Find the tool in chat log tools
        if chat_log.tools:
            for tool in chat_log.tools:
                if tool.name == tool_name:
                    try:
                        from homeassistant.helpers.llm import ToolInput, LLMContext

                        tool_input = ToolInput(tool_args=tool_args)
                        llm_context = LLMContext(
                            platform=DOMAIN,
                            context=None,
                            user_prompt=None,
                            assistant_response=None,
                            tool_result=None,
                        )
                        result = await tool.async_call(
                            self.hass, tool_input, llm_context
                        )
                        return result
                    except Exception as err:
                        _LOGGER.error("Error executing tool %s: %s", tool_name, err)
                        return {"error": str(err)}

        return {"error": f"Tool {tool_name} not found"}

    def _process_non_streaming_response(
        self, response: Any
    ) -> StreamResult:
        """Process non-streaming response."""
        try:
            if not hasattr(response, "choices") or not response.choices:
                return StreamResult(content="No response from model")

            choice = response.choices[0]
            message = choice.message

            content = message.content or ""
            tool_calls = {}

            if hasattr(message, "tool_calls") and message.tool_calls:
                for i, tc in enumerate(message.tool_calls):
                    tool_calls[i] = {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }

            return StreamResult(
                content=content,
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason,
            )

        except Exception as err:
            _LOGGER.error("Error processing response: %s", err)
            return StreamResult(content=f"Error: {err}")

    async def _process_streaming_response(
        self, stream: Any
    ) -> StreamResult:
        """Process streaming response."""
        processor = StreamingProcessor()
        return await processor.process_stream(stream)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entity."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    backend = data["backend"]
    async_add_entities([LemonadeConversationEntity(config_entry, backend)])
