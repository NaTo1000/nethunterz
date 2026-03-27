"""AI-controlled dynamic frequency management for LoRa mesh."""
from __future__ import annotations
import asyncio
import logging
import statistics
import time
from dataclasses import dataclass
from typing import Optional
from .firmware import LoRaFirmware

logger = logging.getLogger("nethunterz.lora.frequency_ai")


@dataclass
class FrequencyDecision:
    recommended_mhz: float
    reason: str
    confidence: float  # 0.0 - 1.0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class FrequencyAI:
    """AI-driven frequency management.

    Monitors node activity, traffic, and power constraints to select
    the optimal LoRa frequency band. Supports manual override.
    """

    CANDIDATE_FREQS_MHZ = [433.175, 868.0, 915.0, 923.0]

    def __init__(self, firmware: LoRaFirmware, scan_interval_s: float = 10.0):
        self.firmware = firmware
        self.scan_interval_s = scan_interval_s
        self._running = False
        self._manual_override_mhz: Optional[float] = None
        self._history: list[FrequencyDecision] = []

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._ai_loop())
        logger.info("FrequencyAI started")

    async def stop(self) -> None:
        self._running = False

    def set_manual_override(self, freq_mhz: float) -> None:
        """GUI / API manual override for frequency band."""
        self._manual_override_mhz = freq_mhz
        self.firmware.set_frequency(freq_mhz)
        logger.info("Manual frequency override: %.3f MHz", freq_mhz)

    def clear_manual_override(self) -> None:
        self._manual_override_mhz = None
        logger.info("Manual frequency override cleared")

    async def _ai_loop(self) -> None:
        while self._running:
            if self._manual_override_mhz is None:
                decision = self._decide_frequency()
                self._history.append(decision)
                self.firmware.set_frequency(decision.recommended_mhz)
                logger.info(
                    "AI frequency decision: %.3f MHz (%s, conf=%.2f)",
                    decision.recommended_mhz,
                    decision.reason,
                    decision.confidence,
                )
            await asyncio.sleep(self.scan_interval_s)

    def _decide_frequency(self) -> FrequencyDecision:
        """Simple heuristic AI: pick frequency with best average RSSI."""
        nodes = self.firmware.get_nodes()
        if not nodes:
            return FrequencyDecision(
                recommended_mhz=915.0,
                reason="no_nodes_default",
                confidence=0.5,
            )

        rssi_values = [n.rssi for n in nodes.values()]
        avg_rssi = statistics.mean(rssi_values)

        if avg_rssi < -90:
            freq = 433.175
            reason = "weak_signal_low_freq"
            conf = 0.8
        elif avg_rssi < -70:
            freq = 868.0
            reason = "moderate_signal_mid_freq"
            conf = 0.75
        else:
            freq = 915.0
            reason = "strong_signal_high_freq"
            conf = 0.9

        return FrequencyDecision(recommended_mhz=freq, reason=reason, confidence=conf)

    def get_last_decision(self) -> Optional[FrequencyDecision]:
        return self._history[-1] if self._history else None

    def get_status(self) -> dict:
        last = self.get_last_decision()
        return {
            "running": self._running,
            "manual_override_mhz": self._manual_override_mhz,
            "last_decision": last.__dict__ if last else None,
            "decision_count": len(self._history),
        }
