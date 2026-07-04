"""Conversation agent for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any, Literal, override

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.llm import LLMTool

from .backends.openai_compat import LemonadeOpenAICompatBackend
from .const import (
    CONF_DEFAULT_MODEL,
    CONF_LLM_HASS_API,
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
from .entity import LemonadeBaseEntity
from .streaming import StreamingProcessor, StreamResult
from .tools import get_ha_bridge_tools

_LOGGER = logging.getLogger(__name__)


class LemonadeConversationEntity(
    LemonadeBaseEntity, conversation.ConversationEntity
):
    """Lemonade Conversation Agent with tool calling and streaming."""

    _attr_name = None

    def __init__(
        self,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        backend: LemonadeOpenAICompatBackend,
    ) -> None:
        """Initialize the agent."""
        super().__init__(entry, subentry)
        self.backend = backend
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{subentry.entry_id}"

        # Enable CONTROL feature if LLM API is configured
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
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process the user input and call the API."""
        options = self.subentry.data

        # Provide LLM data (entities, tools, system prompt)
        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
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
        max_tool_iterations = options.get(
            CONF_MAX_TOOL_ITERATIONS, DEFAULT_MAX_TOOL_ITERATIONS
        )

        # Build messages from chat log
        messages = self._build_messages(chat_log)

        # Get tools from chat log
        tools = self._get_tools(chat_log)

        # Execute conversation with tool calling loop
        result = await self._async_generate_with_tools(
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_tokens=max_tokens,
            streaming=streaming,
            timeout=timeout,
            max_iterations=max_tool_iterations,
            chat_log=chat_log,
        )

        # Store the response in chat log
        chat_log.async_add_assistant_content(
            conversation.AssistantContent(
                agent_id=self.entity_id,
                content=result.content,
                tool_calls=result.tool_calls_list if result.tool_calls else None,
                tool_results=self._get_tool_results(result, chat_log),
            )
        )

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

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
                if msg.tool_calls:
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
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters.schema
                    if hasattr(tool.parameters, "schema")
                    else tool.parameters,
                },
            })

        # Add HA bridge tools
        ha_tools = get_ha_bridge_tools(self.hass)
        for tool in ha_tools:
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters.schema
                    if hasattr(tool.parameters, "schema")
                    else tool.parameters,
                },
            })

        return tools if tools else None

    def _get_tool_results(
        self, result: StreamResult, chat_log: conversation.ChatLog
    ) -> list[conversation.ToolResultContent] | None:
        """Get tool results from the last iteration."""
        # Tool results are stored in the chat log history
        return None

    async def _async_generate_with_tools(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        top_p: float,
        top_k: int,
        max_tokens: int,
        streaming: bool,
        timeout: int,
        max_iterations: int,
        chat_log: conversation.ChatLog,
    ) -> StreamResult:
        """Generate response with tool calling loop."""
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            _LOGGER.debug("Tool calling iteration %d/%d", iteration, max_iterations)

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

            # Process response
            if streaming:
                result = await self._process_streaming_response(response)
            else:
                result = self._process_non_streaming_response(response)

            # If no tool calls, we're done
            if not result.has_tool_calls:
                return result

            # Execute tool calls
            _LOGGER.debug(
                "Executing %d tool calls", len(result.tool_calls_list)
            )

            # Add assistant message with tool calls to messages
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": result.content or None,
                "tool_calls": result.tool_calls_list,
            }
            messages.append(assistant_msg)

            # Execute each tool call
            for tc in result.tool_calls_list:
                tool_result = await self._execute_tool_call(tc, chat_log)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(tool_result),
                })

        # If we hit max iterations, return last result
        _LOGGER.warning(
            "Hit max tool iterations (%d)", max_iterations
        )
        return result

    async def _execute_tool_call(
        self,
        tool_call: dict[str, Any],
        chat_log: conversation.ChatLog,
    ) -> Any:
        """Execute a single tool call."""
        tool_name = tool_call["function"]["name"]
        tool_args_str = tool_call["function"]["arguments"]

        # Parse arguments
        import json

        try:
            tool_args = json.loads(tool_args_str) if tool_args_str else {}
        except json.JSONDecodeError:
            _LOGGER.error("Failed to parse tool arguments: %s", tool_args_str)
            return {"error": f"Invalid tool arguments: {tool_args_str}"}

        # Find the tool in chat log tools
        tool = None
        if chat_log.tools:
            for t in chat_log.tools:
                if t.name == tool_name:
                    tool = t
                    break

        # Check HA bridge tools
        if tool is None:
            ha_tools = get_ha_bridge_tools(self.hass)
            for t in ha_tools:
                if t.name == tool_name:
                    tool = t
                    break

        if tool is None:
            return {"error": f"Tool {tool_name} not found"}

        # Execute the tool
        try:
            from homeassistant.helpers.llm import ToolInput, LLMContext

            tool_input = ToolInput(tool_args=tool_args)
            llm_context = LLMContext(
                platform=DOMAIN,
                context=user_input.context if hasattr(self, "_current_user_input") else None,
                user_prompt=None,
                assistant_response=None,
                tool_result=None,
            )
            result = await tool.async_call(self.hass, tool_input, llm_context)
            return result
        except Exception as err:
            _LOGGER.error("Error executing tool %s: %s", tool_name, err)
            return {"error": str(err)}

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

            if message.tool_calls:
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
        """Process streaming response with true incremental delivery."""
        processor = StreamingProcessor()
        return await processor.process_stream(stream)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities from config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    backend = data["backend"]

    for subentry_id, subentry in config_entry.subentries.items():
        if subentry.subentry_type != "conversation":
            continue
        async_add_entities(
            [LemonadeConversationEntity(config_entry, subentry, backend)],
            config_subentry_id=subentry_id,
        )
