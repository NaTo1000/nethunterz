"""Speed modes — three-speed operation controller for CHAiMERA."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from grok420.config import SpeedMode

logger = logging.getLogger(__name__)


@dataclass
class SpeedProfile:
    """Parameters associated with each speed mode."""

    mode: SpeedMode
    max_latency_ms: float
    min_confidence: float
    max_layers: int
    description: str


_SPEED_PROFILES: dict[SpeedMode, SpeedProfile] = {
    SpeedMode.LOW_LATENCY: SpeedProfile(
        mode=SpeedMode.LOW_LATENCY,
        max_latency_ms=50.0,
        min_confidence=0.6,
        max_layers=1,
        description="Single-pass, maximum throughput, relaxed accuracy.",
    ),
    SpeedMode.BALANCED: SpeedProfile(
        mode=SpeedMode.BALANCED,
        max_latency_ms=200.0,
        min_confidence=0.75,
        max_layers=3,
        description="Multi-pass, balanced throughput and accuracy.",
    ),
    SpeedMode.HIGH_FIDELITY: SpeedProfile(
        mode=SpeedMode.HIGH_FIDELITY,
        max_latency_ms=2000.0,
        min_confidence=0.95,
        max_layers=8,
        description="Deep multi-pass, maximum accuracy, higher latency.",
    ),
}


class SpeedController:
    """Selects and enforces speed-mode parameters at runtime."""

    def __init__(self, initial_mode: SpeedMode = SpeedMode.BALANCED) -> None:
        self._mode = initial_mode

    @property
    def current_mode(self) -> SpeedMode:
        return self._mode

    @property
    def profile(self) -> SpeedProfile:
        return _SPEED_PROFILES[self._mode]

    def set_mode(self, mode: SpeedMode) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        logger.info(
            "SpeedController mode changed to %s (%s)",
            mode.value,
            self.profile.description,
        )

    def is_within_latency(self, latency_ms: float) -> bool:
        return latency_ms <= self.profile.max_latency_ms

    def is_sufficient_confidence(self, confidence: float) -> bool:
        return confidence >= self.profile.min_confidence
