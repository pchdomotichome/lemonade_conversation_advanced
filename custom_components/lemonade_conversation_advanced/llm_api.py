"""LLM API for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant.helpers.llm import API, APIInstance, LLMContext, Tool, ToolInput
from homeassistant.core import HomeAssistant

from .backends.openai_compat import LemonadeOpenAICompatBackend
from .const import (
    LLM_API_DESCRIPTION,
    LLM_API_NAME,
    TOOL_GET_STATS,
    TOOL_LIST_MODELS,
    TOOL_LOAD_MODEL,
    TOOL_PULL_MODEL,
    TOOL_SYSTEM_INFO,
    TOOL_UNLOAD_MODEL,
)

_LOGGER = logging.getLogger(__name__)


class LemonadeLLMAPI(API):
    """Custom LLM API for Lemonade Server management tools."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, backend: LemonadeOpenAICompatBackend) -> None:
        """Initialize the API."""
        self.hass = hass
        self.entry = entry
        self.backend = backend

    @property
    def name(self) -> str:
        """Return API name."""
        return LLM_API_NAME

    @property
    def description(self) -> str:
        """Return API description."""
        return LLM_API_DESCRIPTION

    async def async_get_api_instance(self, llm_context: LLMContext) -> APIInstance:
        """Return the API instance with tools."""
        tools = [
            Tool(
                name=TOOL_PULL_MODEL,
                description="Download/pull a model from Lemonade registry or Hugging Face",
                parameters=vol.Schema({vol.Required("model_name"): str, vol.Optional("checkpoint"): str, vol.Optional("recipe"): str}),
                func=self._pull_model,
            ),
            Tool(
                name=TOOL_LOAD_MODEL,
                description="Load a model into memory for inference",
                parameters=vol.Schema({vol.Required("model_name"): str, vol.Optional("ctx_size"): vol.Coerce(int), vol.Optional("gpu_layers"): vol.Coerce(int), vol.Optional("backend"): str}),
                func=self._load_model,
            ),
            Tool(
                name=TOOL_UNLOAD_MODEL,
                description="Unload a model from memory",
                parameters=vol.Schema({vol.Required("model_name"): str}),
                func=self._unload_model,
            ),
            Tool(
                name=TOOL_LIST_MODELS,
                description="List available models on Lemonade Server",
                parameters=vol.Schema({vol.Optional("show_all"): bool}),
                func=self._list_models,
            ),
            Tool(
                name=TOOL_SYSTEM_INFO,
                description="Get system information: hardware, backends, loaded models",
                parameters=vol.Schema({}),
                func=self._system_info,
            ),
            Tool(
                name=TOOL_GET_STATS,
                description="Get performance statistics from last inference",
                parameters=vol.Schema({}),
                func=self._get_stats,
            ),
        ]
        return APIInstance(tools=tools)

    async def _pull_model(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> Dict[str, Any]:
        """Pull/download a model."""
        try:
            result = await self.backend.pull_model(
                model_name=tool_input.tool_args["model_name"],
                checkpoint=tool_input.tool_args.get("checkpoint"),
                recipe=tool_input.tool_args.get("recipe"),
            )
            return {"result": "success", "data": result}
        except Exception as err:
            _LOGGER.error("Error pulling model: %s", err)
            return {"result": "error", "error": str(err)}

    async def _load_model(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> Dict[str, Any]:
        """Load a model into memory."""
        try:
            result = await self.backend.load_model(
                model_name=tool_input.tool_args["model_name"],
                ctx_size=tool_input.tool_args.get("ctx_size"),
                gpu_layers=tool_input.tool_args.get("gpu_layers"),
                backend=tool_input.tool_args.get("backend"),
            )
            return {"result": "success", "data": result}
        except Exception as err:
            _LOGGER.error("Error loading model: %s", err)
            return {"result": "error", "error": str(err)}

    async def _unload_model(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> Dict[str, Any]:
        """Unload a model from memory."""
        try:
            result = await self.backend.unload_model(tool_input.tool_args["model_name"])
            return {"result": "success", "data": result}
        except Exception as err:
            _LOGGER.error("Error unloading model: %s", err)
            return {"result": "error", "error": str(err)}

    async def _list_models(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> Dict[str, Any]:
        """List available models."""
        try:
            models = await self.backend.list_models(show_all=tool_input.tool_args.get("show_all", False))
            return {"result": "success", "data": {"models": models}}
        except Exception as err:
            _LOGGER.error("Error listing models: %s", err)
            return {"result": "error", "error": str(err)}

    async def _system_info(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> Dict[str, Any]:
        """Get system information."""
        try:
            return {"result": "success", "data": await self.backend.get_system_info()}
        except Exception as err:
            _LOGGER.error("Error getting system info: %s", err)
            return {"result": "error", "error": str(err)}

    async def _get_stats(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> Dict[str, Any]:
        """Get performance statistics."""
        try:
            return {"result": "success", "data": await self.backend.get_stats()}
        except Exception as err:
            _LOGGER.error("Error getting stats: %s", err)
            return {"result": "error", "error": str(err)}
