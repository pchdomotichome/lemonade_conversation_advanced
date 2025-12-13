"""Tools for Lemonade Conversation Advanced."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.util import dt as dt_util

from .llm import LemonadeLLM

_LOGGER = logging.getLogger(__name__)

class LemonadeTool(llm.Tool):
    """Base tool class for Lemonade tools."""

    def __init__(self, hass: HomeAssistant, name: str, description: str):
        """Initialize the tool."""
        self.hass = hass
        self.name = name
        self.description = description

class ModelManagementTool(LemonadeTool):
    """Tool to manage models in Lemonade Server."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the tool."""
        super().__init__(
            hass,
            "model_management",
            "Manage models in Lemonade Server - pull, load, unload"
        )

    async def async_call(
        self, 
        hass: HomeAssistant, 
        tool_input: llm.ToolInput, 
        llm_context: llm.LLMContext
    ) -> Dict[str, Any]:
        """Execute the model management task."""
        try:
            server_url = llm_context.config.get("server_url")
            llm_instance = LemonadeLLM(hass, server_url)
            
            action = tool_input.tool_args.get("action")
            model_name = tool_input.tool_args.get("model_name")
            
            if action == "pull":
                result = await llm_instance.pull_model(model_name)
            elif action == "load":
                result = await llm_instance.load_model(model_name)
            elif action == "unload":
                result = await llm_instance.unload_model(model_name)
            else:
                raise ValueError(f"Unknown action: {action}")
                
            return {"result": "success", "data": result}
        except Exception as err:
            _LOGGER.error(f"Error in model management tool: {err}")
            raise

class SystemInfoTool(LemonadeTool):
    """Tool to get system information."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the tool."""
        super().__init__(
            hass,
            "system_info",
            "Get system information from Lemonade Server"
        )

    async def async_call(
        self, 
        hass: HomeAssistant, 
        tool_input: llm.ToolInput, 
        llm_context: llm.LLMContext
    ) -> Dict[str, Any]:
        """Execute the system info task."""
        try:
            server_url = llm_context.config.get("server_url")
            llm_instance = LemonadeLLM(hass, server_url)
            
            result = await llm_instance.get_system_info()
            return {"result": "success", "data": result}
        except Exception as err:
            _LOGGER.error(f"Error in system info tool: {err}")
            raise

class StatsTool(LemonadeTool):
    """Tool to get performance statistics."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the tool."""
        super().__init__(
            hass,
            "performance_stats",
            "Get performance statistics from Lemonade Server"
        )

    async def async_call(
        self, 
        hass: HomeAssistant, 
        tool_input: llm.ToolInput, 
        llm_context: llm.LLMContext
    ) -> Dict[str, Any]:
        """Execute the stats task."""
        try:
            server_url = llm_context.config.get("server_url")
            llm_instance = LemonadeLLM(hass, server_url)
            
            result = await llm_instance.get_stats()
            return {"result": "success", "data": result}
        except Exception as err:
            _LOGGER.error(f"Error in stats tool: {err}")
            raise