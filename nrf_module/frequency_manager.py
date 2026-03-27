"""
frequency_manager.py – Dynamic frequency management for Pingequa Dual NRF.

Provides automated frequency hopping, spectrum scanning, interference
detection, and cloud-driven frequency recommendation integration.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .pingequa_dual_nrf import PingequaDualNRF

logger = logging.getLogger(__name__)

# 2.4 GHz ISM band: channels 0–125 → 2400–2525 MHz
MIN_CHANNEL = 0
MAX_CHANNEL = 125


@dataclass
class ChannelStats:
    """Observed statistics for one RF channel."""
    channel: int
    sample_count: int = 0
    rssi_sum: int = 0
    packet_count: int = 0
    last_seen: float = 0.0

    @property
    def avg_rssi(self) -> Optional[float]:
        if self.sample_count == 0:
            return None
        return self.rssi_sum / self.sample_count

    @property
    def frequency_mhz(self) -> float:
        return 2400.0 + self.channel


@dataclass
class HopConfig:
    """Parameters for a frequency-hop sequence."""
    channels: List[int] = field(default_factory=lambda: list(range(0, 126, 5)))
    dwell_time_s: float = 0.5   # time to stay on each channel
    module_id: int = 0          # which NRF module hops


class FrequencyManager:
    """
    Manages RF channel allocation and dynamic frequency upgrades.

    Features
    --------
    * Spectrum scan – briefly visit each channel and record RSSI.
    * Frequency hopping – cycle through channels automatically.
    * Best-channel selection – pick the cleanest (lowest RSSI) channel.
    * Cloud recommendations – accept externally derived channel list.
    * Upgrade log – full history of all frequency changes.
    """

    def __init__(self, nrf: PingequaDualNRF):
        self._nrf = nrf
        self._stats: Dict[int, ChannelStats] = {
            ch: ChannelStats(channel=ch) for ch in range(MIN_CHANNEL, MAX_CHANNEL + 1)
        }
        self._hop_task: Optional[asyncio.Task] = None
        self._hopping = False
        self._upgrade_log: List[dict] = []

    # ------------------------------------------------------------------
    # Spectrum scan
    # ------------------------------------------------------------------
    async def scan_spectrum(
        self,
        *,
        module_id: int = 0,
        channels: Optional[List[int]] = None,
        dwell_time_s: float = 0.1,
    ) -> Dict[int, ChannelStats]:
        """
        Scan the specified channels (default: all) and return stats.

        The scan upgrades the module's frequency for each channel,
        waits `dwell_time_s`, then returns it to the original channel.
        """
        status = self._nrf.get_status()
        original_channel = status["modules"][module_id]["channel"]

        channels_to_scan = channels or list(range(MIN_CHANNEL, MAX_CHANNEL + 1))
        logger.info(
            "Starting spectrum scan on %d channels (module %d).",
            len(channels_to_scan), module_id
        )

        for ch in channels_to_scan:
            await self._nrf.upgrade_frequency(
                module_id=module_id,
                new_channel=ch,
                transition_delay_s=0.005,
            )
            await asyncio.sleep(dwell_time_s)
            # Aggregate RSSI from recently captured packets on this channel
            captured = await self._nrf.get_captured_packets()
            recent = [
                p for p in captured
                if p.module_id == module_id
                and p.channel == ch
                and (time.time() - p.timestamp) < dwell_time_s * 2
            ]
            stats = self._stats[ch]
            for pkt in recent:
                stats.sample_count += 1
                stats.rssi_sum += pkt.rssi
                stats.packet_count += 1
                stats.last_seen = pkt.timestamp

        # Restore original channel
        await self._nrf.upgrade_frequency(
            module_id=module_id,
            new_channel=original_channel,
            transition_delay_s=0.02,
        )
        logger.info("Spectrum scan complete.")
        return {ch: self._stats[ch] for ch in channels_to_scan}

    # ------------------------------------------------------------------
    # Best channel selection
    # ------------------------------------------------------------------
    def select_best_channel(
        self,
        candidates: Optional[List[int]] = None,
    ) -> int:
        """
        Return the channel with the lowest average RSSI (least congested).

        Falls back to channel 76 (2.476 GHz) if no data is available.
        """
        pool = candidates or list(range(MIN_CHANNEL, MAX_CHANNEL + 1))
        scored = [
            (ch, self._stats[ch].avg_rssi)
            for ch in pool
            if self._stats[ch].avg_rssi is not None
        ]
        if not scored:
            logger.warning("No scan data – defaulting to channel 76.")
            return 76
        best = min(scored, key=lambda x: x[1])
        logger.info("Best channel: %d (avg RSSI %.1f dBm)", best[0], best[1])
        return best[0]

    # ------------------------------------------------------------------
    # Frequency hopping
    # ------------------------------------------------------------------
    async def start_hopping(self, hop_config: Optional[HopConfig] = None) -> None:
        """Start automatic frequency hopping on the configured module."""
        if self._hopping:
            logger.warning("Hopping already active.")
            return
        cfg = hop_config or HopConfig()
        self._hopping = True
        self._hop_task = asyncio.create_task(self._hop_loop(cfg))
        logger.info(
            "Frequency hopping started on module %d (%d channels).",
            cfg.module_id, len(cfg.channels),
        )

    async def stop_hopping(self) -> None:
        """Stop automatic frequency hopping."""
        self._hopping = False
        if self._hop_task:
            self._hop_task.cancel()
            try:
                await self._hop_task
            except asyncio.CancelledError:
                pass
            self._hop_task = None
        logger.info("Frequency hopping stopped.")

    async def _hop_loop(self, cfg: HopConfig) -> None:
        idx = 0
        while self._hopping:
            ch = cfg.channels[idx % len(cfg.channels)]
            new_freq = await self._nrf.upgrade_frequency(
                module_id=cfg.module_id,
                new_channel=ch,
                transition_delay_s=0.01,
            )
            self._upgrade_log.append({
                "timestamp": time.time(),
                "module_id": cfg.module_id,
                "channel": ch,
                "frequency_mhz": new_freq,
                "source": "hopping",
            })
            await asyncio.sleep(cfg.dwell_time_s)
            idx += 1

    # ------------------------------------------------------------------
    # Cloud-driven upgrade
    # ------------------------------------------------------------------
    async def apply_cloud_recommendation(
        self,
        recommendation: dict,
    ) -> None:
        """
        Apply a frequency recommendation received from the cloud.

        Expected format::

            {
                "module_id": 0,
                "channel": 110,
                "reason": "interference detected on current channel"
            }
        """
        module_id = int(recommendation.get("module_id", 0))
        channel = int(recommendation.get("channel", 76))
        reason = recommendation.get("reason", "cloud recommendation")
        new_freq = await self._nrf.upgrade_frequency(
            module_id=module_id,
            new_channel=channel,
        )
        entry = {
            "timestamp": time.time(),
            "module_id": module_id,
            "channel": channel,
            "frequency_mhz": new_freq,
            "source": "cloud",
            "reason": reason,
        }
        self._upgrade_log.append(entry)
        logger.info("Applied cloud frequency recommendation: %s", entry)

    # ------------------------------------------------------------------
    # Upgrade log
    # ------------------------------------------------------------------
    def get_upgrade_log(self) -> List[dict]:
        """Return the full history of frequency changes."""
        return list(self._upgrade_log)

    def get_channel_stats(self) -> Dict[int, dict]:
        """Return per-channel statistics as plain dicts."""
        return {
            ch: {
                "channel": s.channel,
                "frequency_mhz": s.frequency_mhz,
                "sample_count": s.sample_count,
                "avg_rssi": s.avg_rssi,
                "packet_count": s.packet_count,
            }
            for ch, s in self._stats.items()
        }
