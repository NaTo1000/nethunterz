"""Frequency engine for cloud-side analysis."""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass

logger = logging.getLogger("nethunterz.cloud.frequency_engine")

CANDIDATE_CHANNELS = [2, 10, 20, 40, 60, 76, 80]


@dataclass
class ChannelRecommendation:
    channel: int
    reason: str
    confidence: float


class FrequencyEngine:
    """Analyzes packet telemetry and recommends optimal frequency channels."""

    def __init__(self) -> None:
        self._history: list[dict] = []

    def ingest_telemetry(self, packets: list[dict]) -> None:
        self._history.extend(packets)

    def recommend(self) -> ChannelRecommendation:
        if not self._history:
            return ChannelRecommendation(channel=76, reason="default", confidence=0.5)

        rssi_values = [p.get("rssi", -70.0) for p in self._history[-50:]]
        avg_rssi = statistics.mean(rssi_values)

        if avg_rssi < -80:
            return ChannelRecommendation(
                channel=2, reason="weak_signal_low_channel", confidence=0.7
            )
        return ChannelRecommendation(channel=76, reason="normal_signal", confidence=0.8)

    def get_status(self) -> dict:
        return {"history_size": len(self._history)}
