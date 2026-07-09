"""LLM API for Lemonade Conversation Advanced."""

from __future__ import annotations

from typing import Literal

import voluptuous as vol

from homeassistant.helpers import llm
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN


# Tool implementations as llm.Tool subclasses
class GetEntityStateTool(llm.Tool):
    """Get the current state of an entity."""

    name = "get_entity_state"
    description = "Get the current state of an entity by its entity_id."
    parameters = vol.Schema(
        {
            vol.Required("entity_id"): str,
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> JsonObjectType:
        entity_id = tool_input.tool_args["entity_id"]
        state = hass.states.get(entity_id)
        if state is None:
            return {"error": f"Entity {entity_id} not found"}

        return {
            "entity_id": entity_id,
            "state": state.state,
            "attributes": dict(state.attributes),
            "last_updated": state.last_updated.isoformat() if state.last_updated else None,
            "last_changed": state.last_changed.isoformat() if state.last_changed else None,
        }


class TurnOnEntityTool(llm.Tool):
    """Turn on an entity."""

    name = "turn_on_entity"
    description = "Turn on an entity (light, switch, climate, fan, etc.)."
    parameters = vol.Schema(
        {
            vol.Required("entity_id"): str,
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> JsonObjectType:
        entity_id = tool_input.tool_args["entity_id"]
        await hass.services.async_call(
            "homeassistant",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        return {
            "entity_id": entity_id,
            "state": state.state if state else "unknown",
            "success": True,
        }


class TurnOffEntityTool(llm.Tool):
    """Turn off an entity."""

    name = "turn_off_entity"
    description = "Turn off an entity (light, switch, climate, fan, etc.)."
    parameters = vol.Schema(
        {
            vol.Required("entity_id"): str,
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> JsonObjectType:
        entity_id = tool_input.tool_args["entity_id"]
        await hass.services.async_call(
            "homeassistant",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        return {
            "entity_id": entity_id,
            "state": state.state if state else "unknown",
            "success": True,
        }


class ToggleEntityTool(llm.Tool):
    """Toggle an entity."""

    name = "toggle_entity"
    description = "Toggle an entity (light, switch, fan, etc.)."
    parameters = vol.Schema(
        {
            vol.Required("entity_id"): str,
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> JsonObjectType:
        entity_id = tool_input.tool_args["entity_id"]
        await hass.services.async_call(
            "homeassistant",
            "toggle",
            {"entity_id": entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        return {
            "entity_id": entity_id,
            "state": state.state if state else "unknown",
            "success": True,
        }


class SetEntityValueTool(llm.Tool):
    """Set a numeric value on an entity."""

    name = "set_entity_value"
    description = "Set a numeric value on an entity (brightness, temperature, position, volume, etc.)."
    parameters = vol.Schema(
        {
            vol.Required("entity_id"): str,
            vol.Required("value"): vol.Coerce(float),
            vol.Required("attribute"): vol.In(["brightness", "temperature", "position", "volume_level", "humidity"]),
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> JsonObjectType:
        entity_id = tool_input.tool_args["entity_id"]
        value = tool_input.tool_args["value"]
        attribute: Literal["brightness", "temperature", "position", "volume_level", "humidity"] = tool_input.tool_args["attribute"]

        domain = entity_id.split(".", 1)[0]

        service_data = {"entity_id": entity_id}

        if attribute == "brightness":
            if domain == "light":
                service_data["brightness_pct"] = value
                service = "turn_on"
            else:
                return {"error": f"Brightness only supported for lights, got {domain}"}
        elif attribute == "temperature":
            if domain == "climate":
                service_data["temperature"] = value
                service = "set_temperature"
            elif domain == "water_heater":
                service_data["temperature"] = value
                service = "set_temperature"
            else:
                return {"error": f"Temperature only supported for climate/water_heater, got {domain}"}
        elif attribute == "position":
            if domain == "cover":
                service_data["position"] = value
                service = "set_cover_position"
            else:
                return {"error": f"Position only supported for covers, got {domain}"}
        elif attribute == "volume_level":
            if domain == "media_player":
                service_data["volume_level"] = value / 100.0
                service = "volume_set"
            else:
                return {"error": f"Volume only supported for media_player, got {domain}"}
        elif attribute == "humidity":
            if domain == "humidifier":
                service_data["humidity"] = value
                service = "set_humidity"
            else:
                return {"error": f"Humidity only supported for humidifier, got {domain}"}
        else:
            return {"error": f"Unknown attribute: {attribute}"}

        await hass.services.async_call(domain, service, service_data, blocking=True)
        state = hass.states.get(entity_id)
        return {
            "entity_id": entity_id,
            "state": state.state if state else "unknown",
            "success": True,
        }


class GetEntitiesInAreaTool(llm.Tool):
    """Get all entities in a specific area."""

    name = "get_entities_in_area"
    description = "Get all entities in a specific area."
    parameters = vol.Schema(
        {
            vol.Required("area"): str,
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> JsonObjectType:
        area = tool_input.tool_args["area"]
        from homeassistant.helpers.area_registry import async_get as async_get_area_reg
        from homeassistant.helpers.entity_registry import async_get as async_get_entity_reg

        area_registry = async_get_area_reg(hass)
        area_entry = None
        for a in area_registry.areas.values():
            if a.id == area or a.name.lower() == area.lower():
                area_entry = a
                break

        if not area_entry:
            return {"error": f"Area '{area}' not found"}

        entity_registry = async_get_entity_reg(hass)
        entities = [
            {"entity_id": e.entity_id, "name": e.name or e.original_name, "domain": e.domain}
            for e in entity_registry.entities.values()
            if e.area_id == area_entry.id
        ]

        return {
            "area": area_entry.name,
            "area_id": area_entry.id,
            "entities": entities,
            "count": len(entities),
        }


async def async_get_tools(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    api_id: str,
) -> list[llm.Tool] | None:
    """Return the tools for the LLM."""
    # Only provide tools if the API is enabled for this integration
    # The api_id will be the integration domain
    if api_id != DOMAIN:
        return None

    return [
        GetEntityStateTool(),
        TurnOnEntityTool(),
        TurnOffEntityTool(),
        ToggleEntityTool(),
        SetEntityValueTool(),
        GetEntitiesInAreaTool(),
    ]
