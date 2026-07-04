"""Conversation agent for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.helpers import intent

from .backends.openai_compat import LemonadeOpenAICompatBackend
from .const import CONF_DEFAULT_MODEL, CONF_MAX_TOKENS, CONF_STREAMING, CONF_TEMPERATURE, DOMAIN
from .utils import strip_thinking_blocks

_LOGGER = logging.getLogger(__name__)


class LemonadeConversationAgent(conversation.ConversationEntity):
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
    def supported_languages(self):
        """Return supported languages."""
        return MATCH_ALL

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
        try:
            config = self.entry.data
            options = self.entry.options
            model = options.get(CONF_DEFAULT_MODEL, config.get(CONF_DEFAULT_MODEL))
            temperature = options.get(CONF_TEMPERATURE, 0.7)
            max_tokens = options.get(CONF_MAX_TOKENS, 512)
            streaming = options.get(CONF_STREAMING, True)

            messages = []
            agent_info = getattr(user_input, "agent_info", None)
            if agent_info is not None:
                system_prompt = getattr(agent_info, "system_prompt", None)
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_input.text})

            response = await self.backend.chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=streaming,
            )
            if streaming:
                return await self._process_streaming_response(response, user_input.conversation_id, user_input.language)
            return self._process_response(response, user_input.conversation_id, user_input.language)
        except Exception as err:
            _LOGGER.error("Error processing conversation: %s", err)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(f"Error processing request: {err}")
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )

    def _process_response(self, response: Any, conversation_id: str | None, language: str) -> conversation.ConversationResult:
        """Process non-streaming response."""
        try:
            if hasattr(response, "choices") and response.choices:
                content = response.choices[0].message.content or ""
                content = strip_thinking_blocks(content)
                intent_response = intent.IntentResponse(language=language)
                intent_response.async_set_speech(content)
                return conversation.ConversationResult(
                    response=intent_response,
                    conversation_id=conversation_id,
                )
        except Exception as err:
            _LOGGER.error("Error parsing response: %s", err)
        intent_response = intent.IntentResponse(language=language)
        intent_response.async_set_speech("Failed to parse response")
        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=conversation_id,
        )

    async def _process_streaming_response(self, stream: Any, conversation_id: str | None, language: str) -> conversation.ConversationResult:
        """Process streaming response."""
        try:
            full_content = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_content += chunk.choices[0].delta.content
            full_content = strip_thinking_blocks(full_content)
            intent_response = intent.IntentResponse(language=language)
            intent_response.async_set_speech(full_content)
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=conversation_id,
            )
        except Exception as err:
            _LOGGER.error("Error processing streaming response: %s", err)
            intent_response = intent.IntentResponse(language=language)
            intent_response.async_set_speech(f"Streaming error: {err}")
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=conversation_id,
            )


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up conversation entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    agent = LemonadeConversationAgent(entry, data["backend"])
    async_add_entities([agent])
