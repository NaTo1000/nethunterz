"""Frequency hopping manager for NRF modules."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger("nethunterz.nrf.frequency_manager")


@dataclass
class HopConfig:
    channels: list[int]
    dwell_time_s: float = 1.0


class FrequencyManager:
    """Manages frequency hopping across NRF channels."""

    def __init__(self) -> None:
        self._running = False
        self._current_channel: int = 76
        self._hop_config: HopConfig | None = None

    async def start_hopping(self, config: HopConfig) -> None:
        self._hop_config = config
        self._running = True
        asyncio.create_task(self._hop_loop())
        logger.info("Frequency hopping started: channels=%s", config.channels)

    async def stop_hopping(self) -> None:
        self._running = False
        logger.info("Frequency hopping stopped")

    async def _hop_loop(self) -> None:
        if not self._hop_config or not self._hop_config.channels:
            return
        idx = 0
        while self._running:
            self._current_channel = self._hop_config.channels[idx % len(self._hop_config.channels)]
            idx += 1
            await asyncio.sleep(self._hop_config.dwell_time_s)

    async def apply_cloud_recommendation(self, rec: dict) -> None:
        channel = rec.get("channel")
        if channel is not None:
            self._current_channel = int(channel)
            logger.info("Applied cloud channel recommendation: %d", self._current_channel)

    def get_current_channel(self) -> int:
        return self._current_channel
