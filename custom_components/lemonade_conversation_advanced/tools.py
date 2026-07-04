"""HA bridge tools for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.homeassistant import async_shouldExposeEntity
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    template,
)
from homeassistant.helpers.llm import Tool, ToolInput, LLMContext

_LOGGER = logging.getLogger(__name__)


class ExecuteServiceTool(Tool):
    """Tool to execute Home Assistant services."""

    name = "execute_service"
    description = (
        "Call a Home Assistant service. Use this to control devices, "
        "run scripts, trigger automations, etc."
    )
    parameters = vol.Schema(
        {
            vol.Required("domain"): cv.string,
            vol.Required("service"): cv.string,
            vol.Optional("service_data", default={}): vol.Schema(
                vol.All(dict, vol.Schema({}, extra=vol.ALLOW_EXTRA))
            ),
            vol.Optional("target", default={}): vol.Schema(
                {
                    vol.Optional("entity_id"): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional("device_id"): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional("area_id"): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                }
            ),
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> dict[str, Any]:
        """Execute the service."""
        domain = tool_input.tool_args["domain"]
        service = tool_input.tool_args["service"]
        service_data = tool_input.tool_args.get("service_data", {})
        target = tool_input.tool_args.get("target", {})

        try:
            # Check if service exists
            if not hass.services.has_service(domain, service):
                return {
                    "success": False,
                    "error": f"Service {domain}.{service} not found",
                }

            # Call the service
            response = await hass.services.async_call(
                domain,
                service,
                service_data,
                target=target,
                blocking=True,
                response=None,
            )

            return {
                "success": True,
                "service": f"{domain}.{service}",
                "target": target,
                "response": response,
            }

        except Exception as err:
            _LOGGER.error("Error calling service %s.%s: %s", domain, service, err)
            return {
                "success": False,
                "error": str(err),
            }


class GetStateTool(Tool):
    """Tool to get entity states."""

    name = "get_state"
    description = (
        "Get the current state of one or more Home Assistant entities. "
        "Returns state value, attributes, and last changed time."
    )
    parameters = vol.Schema(
        {
            vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> dict[str, Any]:
        """Get entity state."""
        entity_ids = tool_input.tool_args["entity_id"]
        results = {}

        entity_registry = er.async_get(hass)

        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            if state is None:
                results[entity_id] = {
                    "found": False,
                    "error": f"Entity {entity_id} not found",
                }
                continue

            # Get entity registry entry for friendly name
            registry_entry = entity_registry.async_get(entity_id)
            friendly_name = state.attributes.get("friendly_name", entity_id)

            results[entity_id] = {
                "found": True,
                "state": state.state,
                "friendly_name": friendly_name,
                "attributes": dict(state.attributes),
                "last_changed": str(state.last_changed),
                "last_updated": str(state.last_updated),
            }

        return {"entities": results}


class RenderTemplateTool(Tool):
    """Tool to render Jinja2 templates."""

    name = "render_template"
    description = (
        "Render a Home Assistant Jinja2 template. "
        "Useful for computing values based on entity states."
    )
    parameters = vol.Schema(
        {
            vol.Required("template"): cv.string,
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> dict[str, Any]:
        """Render template."""
        template_str = tool_input.tool_args["template"]

        try:
            template_rendered = template.Template(template_str, hass)
            result = template_rendered.async_render(parse_result=True)

            return {
                "success": True,
                "result": str(result),
                "template": template_str,
            }

        except Exception as err:
            _LOGGER.error("Error rendering template: %s", err)
            return {
                "success": False,
                "error": str(err),
                "template": template_str,
            }


def get_ha_bridge_tools(hass: HomeAssistant) -> list[Tool]:
    """Get all HA bridge tools."""
    return [
        ExecuteServiceTool(),
        GetStateTool(),
        RenderTemplateTool(),
    ]
