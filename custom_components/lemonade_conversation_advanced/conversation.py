"""Conversation support for Lemonade Conversation Advanced."""

from __future__ import annotations

from typing import Any, Literal, override

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import LemonadeBaseEntity


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

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Call the API."""
        options = self.subentry.data

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        await self._async_handle_chat_log(chat_log)

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
    ) -> None:
        """Generate an answer for the chat log with tool calling loop."""
        import json
        import aiohttp
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        options = self.subentry.data
        server_url = self.entry.data.get("server_url", "")
        api_key = self.entry.data.get("api_key", "")
        model = options.get("model_name", "")
        temperature = options.get("temperature", 0.7)
        max_tokens = options.get("max_tokens", 2048)

        # Tool calling loop - max iterations to prevent infinite loops
        max_iterations = 5
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Build messages from chat log
            messages = []
            for content in chat_log.content:
                if isinstance(content, conversation.SystemContent):
                    messages.append({"role": "system", "content": content.content})
                elif isinstance(content, conversation.UserContent):
                    messages.append({"role": "user", "content": content.content})
                elif isinstance(content, conversation.AssistantContent):
                    msg: dict[str, Any] = {"role": "assistant", "content": content.content or ""}
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

            # Get tools from chat log
            tools = None
            if chat_log.llm_api:
                tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters.schema if tool.parameters else {},
                        },
                    }
                    for tool in chat_log.llm_api.tools
                ]

            # Call Lemonade Server
            session = async_get_clientsession(self.hass)
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            try:
                async with session.post(
                    f"{server_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        raise HomeAssistantError(f"LLM error: {text}")

                    data = await resp.json()
                    message = data["choices"][0]["message"]

                # Add assistant response to chat log
                if message.get("tool_calls"):
                    # LLM wants to call tools - add AssistantContent with tool_calls
                    tool_calls_list = [
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
                            content=message.get("content", ""),
                            tool_calls=tool_calls_list,
                        )
                    )
                    # Execute the tools via ChatLog
                    for tc in message["tool_calls"]:
                        await chat_log.async_call_tool(
                            tool_name=tc["function"]["name"],
                            tool_args=json.loads(tc["function"]["arguments"]),
                            tool_call_id=tc["id"],
                            agent_id=self.entity_id,
                        )
                    # Continue loop to let LLM respond to tool results
                    continue

                # No tool calls - add final response and break
                chat_log.async_add_assistant_content_without_tools(
                    conversation.AssistantContent(
                        agent_id=self.entity_id,
                        content=message.get("content", ""),
                    )
                )
                break

            except aiohttp.ClientError as err:
                raise HomeAssistantError(f"Connection error: {err}") from err
        else:
            # Max iterations reached
            raise HomeAssistantError("Max tool calling iterations reached")