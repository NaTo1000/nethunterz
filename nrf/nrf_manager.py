"""NRF manager class with read/record/rewrite logic."""

import time
import logging
import json
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class NRFPacket:
    channel: int
    freq_mhz: int
    payload: bytes
    timestamp: float = field(default_factory=time.time)
    rssi: int = -90

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "freq_mhz": self.freq_mhz,
            "payload_hex": self.payload.hex(),
            "timestamp": self.timestamp,
            "rssi": self.rssi,
        }


class NRFManager:
    """High-level NRF24L01+ management: read, record, and rewrite packets."""

    PIPE_ADDRESSES = [
        b"\xE7\xE7\xE7\xE7\xE7",
        b"\xC2\xC2\xC2\xC2\xC2",
        b"\xC3\xC3\xC3\xC3\xC3",
        b"\xC4\xC4\xC4\xC4\xC4",
        b"\xC5\xC5\xC5\xC5\xC5",
    ]

    def __init__(self, runtime=None) -> None:
        self._runtime = runtime
        self._packet_log: List[NRFPacket] = []
        self._rewrite_rules: Dict[bytes, bytes] = {}
        self._recording = False
        self._max_log_size = 10000

    def start_recording(self) -> None:
        self._recording = True
        logger.info("NRF packet recording started")

    def stop_recording(self) -> None:
        self._recording = False
        logger.info("NRF recording stopped. %d packets captured.", len(self._packet_log))

    def record_packet(self, channel: int, payload: bytes, rssi: int = -90) -> NRFPacket:
        pkt = NRFPacket(
            channel=channel,
            freq_mhz=2400 + channel,
            payload=payload,
            rssi=rssi,
        )
        if self._recording and len(self._packet_log) < self._max_log_size:
            self._packet_log.append(pkt)
        return pkt

    def add_rewrite_rule(self, match: bytes, replacement: bytes) -> None:
        self._rewrite_rules[match] = replacement
        logger.info("Rewrite rule: %s → %s", match.hex(), replacement.hex())

    def apply_rewrite(self, payload: bytes) -> bytes:
        for match, replacement in self._rewrite_rules.items():
            if match in payload:
                idx = payload.index(match)
                payload = payload[:idx] + replacement + payload[idx + len(match):]
        return payload

    def replay_packet(self, packet: NRFPacket, modify: bool = True) -> bool:
        if not self._runtime:
            return False
        data = self.apply_rewrite(packet.payload) if modify else packet.payload
        return self._runtime.send_packet(data, channel=packet.channel)

    def get_channel_statistics(self) -> Dict[int, dict]:
        stats: Dict[int, dict] = {}
        for pkt in self._packet_log:
            if pkt.channel not in stats:
                stats[pkt.channel] = {"count": 0, "avg_rssi": 0, "total_bytes": 0}
            stats[pkt.channel]["count"] += 1
            stats[pkt.channel]["avg_rssi"] += pkt.rssi
            stats[pkt.channel]["total_bytes"] += len(pkt.payload)
        for ch, s in stats.items():
            if s["count"] > 0:
                s["avg_rssi"] = s["avg_rssi"] // s["count"]
        return stats

    def export_log(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            for pkt in self._packet_log:
                f.write(json.dumps(pkt.to_dict()) + "\n")
        logger.info("Exported %d packets to %s", len(self._packet_log), filepath)

    def clear_log(self) -> None:
        self._packet_log.clear()
        logger.info("Packet log cleared")
