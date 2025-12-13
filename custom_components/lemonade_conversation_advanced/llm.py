"""LLM handling for Lemonade Assistant Advanced."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class LemonadeLLM:
    """Handle communication with Lemonade Server."""

    def __init__(self, hass: HomeAssistant, server_url: str):
        """Initialize the LLM handler."""
        self.hass = hass
        self.server_url = server_url.rstrip('/')

    async def pull_model(self, model_name: str) -> dict:
        """Pull a model from the registry."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/api/v1/pull",
                    json={"model_name": model_name}
                ) as resp:
                    result = await resp.json()
                    _LOGGER.debug(f"Model pull result: {result}")
                    return result
        except Exception as err:
            _LOGGER.error(f"Error pulling model {model_name}: {err}")
            raise

    async def load_model(self, model_name: str, **kwargs) -> dict:
        """Load a model into memory."""
        try:
            payload = {"model_name": model_name}
            payload.update(kwargs)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/api/v1/load",
                    json=payload
                ) as resp:
                    result = await resp.json()
                    _LOGGER.debug(f"Model load result: {result}")
                    return result
        except Exception as err:
            _LOGGER.error(f"Error loading model {model_name}: {err}")
            raise

    async def unload_model(self, model_name: str) -> dict:
        """Unload a model from memory."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/api/v1/unload",
                    json={"model_name": model_name}
                ) as resp:
                    result = await resp.json()
                    _LOGGER.debug(f"Model unload result: {result}")
                    return result
        except Exception as err:
            _LOGGER.error(f"Error unloading model {model_name}: {err}")
            raise

    async def health_check(self) -> dict:
        """Check server health."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/api/v1/health") as resp:
                    result = await resp.json()
                    _LOGGER.debug(f"Health check result: {result}")
                    return result
        except Exception as err:
            _LOGGER.error(f"Error during health check: {err}")
            raise

    async def list_models(self, show_all: bool = False) -> dict:
        """List available models."""
        try:
            url = f"{self.server_url}/api/v1/models"
            if show_all:
                url += "?show_all=true"
                
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    result = await resp.json()
                    _LOGGER.debug(f"Models list result: {result}")
                    return result
        except Exception as err:
            _LOGGER.error(f"Error listing models: {err}")
            raise

    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        stream: bool = False,
        **kwargs
    ) -> dict:
        """Get chat completion from Lemonade Server."""
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
                **kwargs
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/api/v1/chat/completions",
                    json=payload
                ) as resp:
                    result = await resp.json()
                    _LOGGER.debug(f"Chat completion result: {result}")
                    return result
        except Exception as err:
            _LOGGER.error(f"Error getting chat completion: {err}")
            raise