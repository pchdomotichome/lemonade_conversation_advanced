"""Conversation agent for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry

from .backends.openai_compat import LemonadeOpenAICompatBackend
from .const import CONF_DEFAULT_MODEL, CONF_MAX_TOKENS, CONF_STREAMING, CONF_TEMPERATURE, DOMAIN
from .utils import strip_thinking_blocks

_LOGGER = logging.getLogger(__name__)


class LemonadeConversationAgent(conversation.ConversationEntity, conversation.AbstractConversationAgent):
    """Lemonade Conversation Agent."""

    _attr_has_entity_name = True
    _attr_name = "Lemonade Assistant"

    def __init__(self, entry: ConfigEntry, backend: LemonadeOpenAICompatBackend) -> None:
        """Initialize the agent."""
        self.entry = entry
        self.backend = backend
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_agent"
        self._attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return self._attr_supported_features

    @property
    def device_info(self) -> Dict[str, Any] | None:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "AMD",
            "model": "Lemonade Server",
        }

    async def async_process(self, user_input: conversation.ConversationInput) -> conversation.ConversationResult:
        """Process a conversation request."""
        config = self.entry.data
        options = self.entry.options
        model = options.get(CONF_DEFAULT_MODEL, config.get(CONF_DEFAULT_MODEL))
        temperature = options.get(CONF_TEMPERATURE, 0.7)
        max_tokens = options.get(CONF_MAX_TOKENS, 512)
        streaming = options.get(CONF_STREAMING, True)

        messages = []
        system_prompt = getattr(user_input.agent_info, "system_prompt", None)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_input.text})

        try:
            response = await self.backend.chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=streaming,
            )
            if streaming:
                return await self._process_streaming_response(response, user_input.conversation_id)
            return self._process_response(response, user_input.conversation_id)
        except Exception as err:
            _LOGGER.error("Error processing conversation: %s", err)
            return conversation.ConversationResult(
                response=conversation.ConversationResponse(
                    response_type=conversation.ConversationResponseType.ERROR,
                    error_code="unknown",
                    message=f"Error processing request: {err}",
                ),
                conversation_id=user_input.conversation_id,
            )

    def _process_response(self, response: Any, conversation_id: str | None) -> conversation.ConversationResult:
        """Process non-streaming response."""
        try:
            if hasattr(response, "choices") and response.choices:
                content = response.choices[0].message.content or ""
                content = strip_thinking_blocks(content)
                return conversation.ConversationResult(
                    response=conversation.ConversationResponse(
                        response_type=conversation.ConversationResponseType.ACTION_DONE,
                        speech={"plain": {"speech": content, "extra_data": None}},
                    ),
                    conversation_id=conversation_id,
                )
        except Exception as err:
            _LOGGER.error("Error parsing response: %s", err)
        return conversation.ConversationResult(
            response=conversation.ConversationResponse(
                response_type=conversation.ConversationResponseType.ERROR,
                error_code="unknown",
                message="Failed to parse response",
            ),
            conversation_id=conversation_id,
        )

    async def _process_streaming_response(self, stream: Any, conversation_id: str | None) -> conversation.ConversationResult:
        """Process streaming response."""
        try:
            full_content = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_content += chunk.choices[0].delta.content
            full_content = strip_thinking_blocks(full_content)
            return conversation.ConversationResult(
                response=conversation.ConversationResponse(
                    response_type=conversation.ConversationResponseType.ACTION_DONE,
                    speech={"plain": {"speech": full_content, "extra_data": None}},
                ),
                conversation_id=conversation_id,
            )
        except Exception as err:
            _LOGGER.error("Error processing streaming response: %s", err)
            return conversation.ConversationResult(
                response=conversation.ConversationResponse(
                    response_type=conversation.ConversationResponseType.ERROR,
                    error_code="unknown",
                    message=f"Streaming error: {err}",
                ),
                conversation_id=conversation_id,
            )


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up conversation entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LemonadeConversationAgent(entry, data["backend"])])
