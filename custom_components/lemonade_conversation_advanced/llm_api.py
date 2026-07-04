"""LLM API for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant.helpers.llm import API, APIInstance, LLMContext, Tool, ToolInput
from homeassistant.core import HomeAssistant

from .backends.openai_compat import LemonadeOpenAICompatBackend
from .const import (
    DOMAIN,
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


class _LemonadeTool(Tool):
    """Tool that delegates async_call to a bound method."""

    def __init__(self, name: str, description: str, parameters: vol.Schema, func) -> None:
        super().__init__()
        self.name = name
        self.description = description
        self.parameters = parameters
        self._func = func

    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> Dict[str, Any]:
        return await self._func(hass, tool_input, llm_context)


def _make_tool(name: str, description: str, parameters: vol.Schema, func) -> Tool:
    """Create an llm Tool instance."""
    return _LemonadeTool(name=name, description=description, parameters=parameters, func=func)


class LemonadeLLMAPI(API):
    """Custom LLM API for Lemonade Server management tools."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, backend: LemonadeOpenAICompatBackend) -> None:
        """Initialize the API."""
        super().__init__(hass=hass, id=f"{DOMAIN}-{entry.entry_id}", name=LLM_API_NAME)
        self.entry = entry
        self.backend = backend
        self._description = LLM_API_DESCRIPTION

    async def async_get_api_instance(self, llm_context: LLMContext) -> APIInstance:
        """Return the API instance with tools."""
        tools = [
            _make_tool(TOOL_PULL_MODEL, "Download/pull a model from Lemonade registry or Hugging Face", vol.Schema({vol.Required("model_name"): str, vol.Optional("checkpoint"): str, vol.Optional("recipe"): str}), self._pull_model),
            _make_tool(TOOL_LOAD_MODEL, "Load a model into memory for inference", vol.Schema({vol.Required("model_name"): str, vol.Optional("ctx_size"): vol.Coerce(int), vol.Optional("gpu_layers"): vol.Coerce(int), vol.Optional("backend"): str}), self._load_model),
            _make_tool(TOOL_UNLOAD_MODEL, "Unload a model from memory", vol.Schema({vol.Required("model_name"): str}), self._unload_model),
            _make_tool(TOOL_LIST_MODELS, "List available models on Lemonade Server", vol.Schema({vol.Optional("show_all"): bool}), self._list_models),
            _make_tool(TOOL_SYSTEM_INFO, "Get system information: hardware, backends, loaded models", vol.Schema({}), self._system_info),
            _make_tool(TOOL_GET_STATS, "Get performance statistics from last inference", vol.Schema({}), self._get_stats),
        ]
        return APIInstance(api=self, api_prompt=self._description, llm_context=llm_context, tools=tools)

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
