"""HA bridge tools for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


async def execute_service(
    hass: Any,
    domain: str,
    service: str,
    service_data: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a Home Assistant service."""
    try:
        if not hass.services.has_service(domain, service):
            return {"success": False, "error": f"Service {domain}.{service} not found"}

        await hass.services.async_call(
            domain,
            service,
            service_data or {},
            target=target or {},
            blocking=True,
        )
        return {"success": True, "service": f"{domain}.{service}"}
    except Exception as err:
        _LOGGER.error("Error calling service %s.%s: %s", domain, service, err)
        return {"success": False, "error": str(err)}


async def get_state(
    hass: Any,
    entity_id: str,
) -> dict[str, Any]:
    """Get entity state."""
    state = hass.states.get(entity_id)
    if state is None:
        return {"found": False, "error": f"Entity {entity_id} not found"}

    return {
        "found": True,
        "state": state.state,
        "attributes": dict(state.attributes),
        "last_changed": str(state.last_changed),
    }
