"""
frequency_engine.py – Cloud-side RF frequency analysis and recommendation engine.

Analyses captured packet telemetry from devices and recommends optimal
frequency channels in real time. Uses statistical signal analysis and
(optionally) ML-based interference prediction.
"""

from __future__ import annotations

import logging
import math
import statistics
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 2.4 GHz ISM band: channels 0–125 → 2400–2525 MHz
MAX_CHANNEL = 125
CLEAN_CHANNEL_RSSI = -85.0   # dBm threshold for "clean" channel
CONGESTED_RSSI = -60.0       # dBm threshold for "congested" channel


class FrequencyEngine:
    """
    Server-side frequency analysis and recommendation engine.

    Algorithm
    ---------
    1. Aggregate per-channel RSSI observations from the packet stream.
    2. Compute a congestion score per channel.
    3. Recommend the least congested channel(s) that differ from current.
    4. Apply hysteresis to avoid oscillation.
    """

    HYSTERESIS_IMPROVEMENT = 5.0   # dBm improvement required to recommend a switch
    MIN_SAMPLES_TO_RECOMMEND = 3   # minimum channel observations before recommending

    def __init__(self):
        # Per-device, per-channel RSSI history
        self._channel_rssi: Dict[str, Dict[int, List[float]]] = {}
        self._last_recommendation: Dict[str, int] = {}  # device_id -> last recommended channel

    async def analyse(
        self,
        device_id: str,
        packets: List[dict],
    ) -> List[dict]:
        """
        Analyse a packet batch and return frequency recommendations.

        Returns a list of recommendation dicts, possibly empty.
        """
        if not packets:
            return []

        # Aggregate RSSI by channel
        if device_id not in self._channel_rssi:
            self._channel_rssi[device_id] = {}
        ch_rssi = self._channel_rssi[device_id]

        for pkt in packets:
            ch = int(pkt.get("channel", 76))
            rssi = float(pkt.get("rssi", -80))
            if ch not in ch_rssi:
                ch_rssi[ch] = []
            ch_rssi[ch].append(rssi)
            # Keep a rolling window of 100 samples per channel
            if len(ch_rssi[ch]) > 100:
                ch_rssi[ch] = ch_rssi[ch][-100:]

        # Determine current channel (most-seen in this batch)
        from collections import Counter
        channel_counts = Counter(int(p.get("channel", 76)) for p in packets)
        current_channel = channel_counts.most_common(1)[0][0]
        current_avg_rssi = self._avg_rssi(ch_rssi, current_channel)

        # Find best alternative
        scored: List[tuple] = []
        for ch, rssi_list in ch_rssi.items():
            if len(rssi_list) < self.MIN_SAMPLES_TO_RECOMMEND:
                continue
            avg = statistics.mean(rssi_list)
            scored.append((ch, avg))

        if not scored:
            return []

        # Sort by RSSI ascending (lower = less busy)
        scored.sort(key=lambda x: x[1])
        best_ch, best_rssi = scored[0]

        if best_ch == current_channel:
            if len(scored) > 1:
                best_ch, best_rssi = scored[1]
            else:
                return []

        # Hysteresis: only recommend if improvement is significant
        improvement = current_avg_rssi - best_rssi
        if improvement < self.HYSTERESIS_IMPROVEMENT:
            return []

        # Avoid same recommendation as last time (prevent oscillation)
        if self._last_recommendation.get(device_id) == best_ch:
            # Try to find a different candidate that is not the current channel
            found_alternative = False
            for ch, rssi in scored:
                if ch != current_channel and ch != best_ch:
                    best_ch, best_rssi = ch, rssi
                    found_alternative = True
                    break
            if not found_alternative:
                return []

        self._last_recommendation[device_id] = best_ch
        recommendation = {
            "device_id": device_id,
            "module_id": int(packets[0].get("module_id", 0)),
            "channel": best_ch,
            "frequency_mhz": 2400.0 + best_ch,
            "reason": (
                f"Channel {current_channel} (avg RSSI {current_avg_rssi:.1f} dBm) "
                f"congested. Recommended ch{best_ch} "
                f"(avg RSSI {best_rssi:.1f} dBm, "
                f"+{improvement:.1f} dBm improvement)."
            ),
            "timestamp": time.time(),
        }
        logger.info(
            "Frequency recommendation for %s: ch%d → ch%d",
            device_id, current_channel, best_ch
        )
        return [recommendation]

    @staticmethod
    def _avg_rssi(ch_rssi: Dict[int, List[float]], channel: int) -> float:
        rssi_list = ch_rssi.get(channel, [])
        if not rssi_list:
            return 0.0
        return statistics.mean(rssi_list)

    def get_channel_summary(self, device_id: str) -> List[dict]:
        ch_rssi = self._channel_rssi.get(device_id, {})
        results = []
        for ch, rssi_list in sorted(ch_rssi.items()):
            results.append({
                "channel": ch,
                "frequency_mhz": 2400.0 + ch,
                "sample_count": len(rssi_list),
                "avg_rssi": statistics.mean(rssi_list) if rssi_list else None,
                "min_rssi": min(rssi_list) if rssi_list else None,
                "max_rssi": max(rssi_list) if rssi_list else None,
            })
        return results
