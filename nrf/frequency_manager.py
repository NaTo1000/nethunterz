"""Dynamic frequency upgrade manager for NRF24L01+."""

import time
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

WIFI_CONGESTED_CHANNELS = list(range(1, 14))  # 2401-2413 MHz
BLUETOOTH_CHANNELS      = list(range(0, 80, 2))  # BT uses even channels

class FrequencyManager:
    """Manages dynamic frequency selection to avoid interference."""

    def __init__(self, preferred_channels: Optional[List[int]] = None) -> None:
        self.preferred = preferred_channels or [76, 100, 110, 120, 125]
        self._channel_scores: Dict[int, float] = {}
        self._current_channel: int = 76
        self._history: List[Tuple[float, int, float]] = []  # (time, channel, score)

    def score_channel(self, channel: int, packet_count: int,
                       interference_level: float = 0.0) -> float:
        """Score a channel (higher = better/clearer)."""
        score = 100.0
        # Penalise WiFi congestion zones
        if channel in WIFI_CONGESTED_CHANNELS:
            score -= 30.0
        # Penalise BT channels
        if channel in BLUETOOTH_CHANNELS:
            score -= 20.0
        # Penalise activity
        score -= packet_count * 5.0
        # Penalise interference
        score -= interference_level * 10.0
        # Bonus for preferred channels
        if channel in self.preferred:
            score += 20.0
        return max(0.0, score)

    def update_channel_scores(self, scan_counts: Dict[int, int]) -> None:
        """Update internal scores from a scan result."""
        for ch, count in scan_counts.items():
            self._channel_scores[ch] = self.score_channel(ch, count)

    def select_best_channel(self) -> int:
        """Return the highest-scoring available channel."""
        if not self._channel_scores:
            return self._current_channel
        best = max(self._channel_scores, key=self._channel_scores.get)
        self._current_channel = best
        score = self._channel_scores[best]
        self._history.append((time.time(), best, score))
        logger.info("Selected channel %d (freq %d MHz, score %.1f)",
                    best, 2400 + best, score)
        return best

    def should_hop(self, current_score_threshold: float = 30.0) -> bool:
        """Decide if we should hop based on current channel score."""
        current_score = self._channel_scores.get(self._current_channel, 100.0)
        return current_score < current_score_threshold

    def get_channel_report(self) -> List[dict]:
        """Return sorted channel report."""
        return sorted(
            [{"channel": ch, "freq_mhz": 2400 + ch, "score": sc}
             for ch, sc in self._channel_scores.items()],
            key=lambda x: x["score"],
            reverse=True,
        )

    @property
    def current_channel(self) -> int:
        return self._current_channel
