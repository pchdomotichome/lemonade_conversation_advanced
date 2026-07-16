"""Telemetry coordinator for Lemonade Server."""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import LemonadeAPIClient

_LOGGER = logging.getLogger(__name__)

# ponytail: fixed-size ring buffers; cheap and bounded, no numpy.
_TTFT_WINDOW = 20
_TPS_WINDOW = 20


class LemonadeTelemetryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll Lemonade Server health/stats/system-stats and keep rolling averages.

    ``_async_update_data`` returns the latest raw payloads merged with the
    computed rolling averages. ``available`` reflects server reachability.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: LemonadeAPIClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="lemonade_telemetry",
            update_interval=scan_interval,
        )
        self._client = client
        self._ttft: deque[float] = deque(maxlen=_TTFT_WINDOW)
        self._tps: deque[float] = deque(maxlen=_TPS_WINDOW)

    @property
    def client(self) -> LemonadeAPIClient:
        """The underlying API client (closed on unload)."""
        return self._client

    async def _async_update_data(self) -> dict[str, Any]:
        health, system_stats, stats = await self._fetch()
        merged: dict[str, Any] = {
            "available": health is not None,
            "health": health or {},
            "system_stats": system_stats or {},
            "stats": stats or {},
            "ttft_avg": None,
            "tps_avg": None,
        }

        if stats:
            ttft = stats.get("time_to_first_token")
            tps = stats.get("tokens_per_second")
            if isinstance(ttft, (int, float)):
                self._ttft.append(float(ttft))
            if isinstance(tps, (int, float)):
                self._tps.append(float(tps))

        if self._ttft:
            merged["ttft_avg"] = sum(self._ttft) / len(self._ttft)
        if self._tps:
            merged["tps_avg"] = sum(self._tps) / len(self._tps)

        return merged

    async def _fetch(self):
        return await self.hass.async_gather(
            self._client.get_health(),
            self._client.get_system_stats(),
            self._client.get_stats(),
        )
