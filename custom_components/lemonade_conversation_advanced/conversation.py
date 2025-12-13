"""Conversation integration for Lemonade Conversation Advanced."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.conversation import (
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_DEFAULT_MODEL, CONF_TEMPERATURE, CONF_MAX_TOKENS, CONF_STREAMING
from .llm import LemonadeLLM

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Registrar el componente de conversación personalizado
    hass.data[DOMAIN]["config_entry"] = entry
    
    return True

async def async_process(
    hass: HomeAssistant,
    config: Dict[str, Any],
    conversation_input: ConversationInput,
) -> ConversationResult:
    """Process a conversation."""
    
    server_url = config.get("server_url")
    default_model = config.get(CONF_DEFAULT_MODEL)
    temperature = config.get(CONF_TEMPERATURE, 0.7)
    max_tokens = config.get(CONF_MAX_TOKENS, 512)
    streaming = config.get(CONF_STREAMING, True)
    
    llm = LemonadeLLM(hass, server_url)
    
    # Construir mensajes para la conversación
    messages = []
    
    # Agregar sistema de contexto si está disponible
    if conversation_input.agent_info.system_prompt:
        messages.append({
            "role": "system",
            "content": conversation_input.agent_info.system_prompt
        })
    
    # Agregar historial de conversación limitado
    conversation_history = conversation_input.conversation_history or []
    max_history = 10  # Limitar a 10 mensajes para evitar overflow
    
    for msg in conversation_history[-max_history:]:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })
    
    # Agregar mensaje actual
    messages.append({
        "role": "user",
        "content": conversation_input.text
    })
    
    try:
        # Llamar al servidor Lemonade
        response = await llm.chat_completion(
            model=default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=streaming
        )
        
        # Procesar respuesta
        if "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            
            return ConversationResult(
                response=content,
                conversation_id=conversation_input.conversation_id
            )
        else:
            _LOGGER.error("No choices returned from Lemonade Server")
            return ConversationResult(
                response="Lo siento, no pude procesar tu solicitud.",
                conversation_id=conversation_input.conversation_id
            )
            
    except Exception as err:
        _LOGGER.error(f"Error processing conversation: {err}")
        return ConversationResult(
            response="Ha ocurrido un error al procesar tu solicitud.",
            conversation_id=conversation_input.conversation_id
        )