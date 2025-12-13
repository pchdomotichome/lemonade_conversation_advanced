"""Agent implementation for Lemonade Conversation Advanced."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent, llm
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .llm import LemonadeLLM

_LOGGER = logging.getLogger(__name__)

class LemonadeAgent(ConversationEntity):
    """Lemonade Conversation Agent."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._attr_name = "Lemonade Assistant"
        self._attr_unique_id = f"{DOMAIN}_agent"

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a conversation request."""
        config = self.entry.data
        
        server_url = config.get("server_url")
        default_model = config.get("default_model")
        
        llm_instance = LemonadeLLM(self.hass, server_url)
        
        # Construir mensaje para el LLM
        messages = []
        
        if user_input.agent_info.system_prompt:
            messages.append({
                "role": "system",
                "content": user_input.agent_info.system_prompt
            })
        
        # Agregar historial de conversación limitado
        conversation_history = user_input.conversation_history or []
        max_history = 10
        
        for msg in conversation_history[-max_history:]:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Agregar mensaje actual
        messages.append({
            "role": "user",
            "content": user_input.text
        })
        
        try:
            # Llamar al servidor Lemonade
            response = await llm_instance.chat_completion(
                model=default_model,
                messages=messages,
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 512),
                stream=config.get("streaming", True)
            )
            
            if "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]
                
                return ConversationResult(
                    response=content,
                    conversation_id=user_input.conversation_id
                )
            else:
                _LOGGER.error("No choices returned from Lemonade Server")
                return ConversationResult(
                    response="Lo siento, no pude procesar tu solicitud.",
                    conversation_id=user_input.conversation_id
                )
                
        except Exception as err:
            _LOGGER.error(f"Error processing conversation: {err}")
            return ConversationResult(
                response="Ha ocurrido un error al procesar tu solicitud.",
                conversation_id=user_input.conversation_id
            )

    @property
    def supported_features(self) -> int:
        """Return the features supported by this agent."""
        return 0

    async def async_get_tools(self) -> List[llm.Tool]:
        """Return a list of tools for the agent."""
        # Implementar herramientas personalizadas aquí
        return []