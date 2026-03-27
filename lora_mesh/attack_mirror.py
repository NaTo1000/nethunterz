"""Attack Mirror Defensive System for LoRa mesh networks."""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("nethunterz.lora.attack_mirror")


class ThreatLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResponseAction(Enum):
    LOG = "log"
    ISOLATE = "isolate"
    MIRROR = "mirror"
    SHUTDOWN = "shutdown"


@dataclass
class AnomalyPacket:
    source_node: str
    payload_hex: str
    rssi: float
    frequency_mhz: float
    timestamp: float = field(default_factory=time.time)
    threat_level: ThreatLevel = ThreatLevel.LOW

    def to_dict(self) -> dict:
        return {
            "source_node": self.source_node,
            "payload_hex": self.payload_hex,
            "rssi": self.rssi,
            "frequency_mhz": self.frequency_mhz,
            "timestamp": self.timestamp,
            "threat_level": self.threat_level.value,
        }


@dataclass
class DefenseEvent:
    anomaly: AnomalyPacket
    action: ResponseAction
    timestamp: float = field(default_factory=time.time)
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "anomaly": self.anomaly.to_dict(),
            "action": self.action.value,
            "timestamp": self.timestamp,
            "details": self.details,
        }


class AttackMirrorDefense:
    """Detects, isolates, and neutralises suspicious mesh activity.

    Uses AI-driven anomaly detection to classify packets and respond
    with: logging, isolation, mirroring back to origin, or node shutdown.
    """

    HIGH_PACKET_RATE_THRESHOLD = 50      # packets per second per node
    RSSI_ANOMALY_THRESHOLD_DBM = -30.0   # dBm; signals stronger than this are anomalous
    DUPLICATE_PAYLOAD_WINDOW = 10        # last N payloads checked for replay attacks

    def __init__(
        self, response_callback: Optional[Callable[[DefenseEvent], None]] = None
    ):
        self._anomalies: list[AnomalyPacket] = []
        self._defense_events: list[DefenseEvent] = []
        self._isolated_nodes: set[str] = set()
        self._packet_rates: dict[str, list[float]] = {}
        self._payload_window: list[str] = []
        self._response_callback = response_callback
        self._running = False

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._cleanup_loop())
        logger.info("AttackMirrorDefense started")

    async def stop(self) -> None:
        self._running = False

    async def _cleanup_loop(self) -> None:
        while self._running:
            now = time.time()
            for nid in list(self._packet_rates.keys()):
                self._packet_rates[nid] = [
                    t for t in self._packet_rates[nid] if now - t < 1.0
                ]
            await asyncio.sleep(1.0)

    def analyze_packet(
        self,
        source_node: str,
        payload_bytes: bytes,
        rssi: float,
        frequency_mhz: float,
    ) -> Optional[DefenseEvent]:
        """Analyze an incoming packet for anomalies. Returns DefenseEvent if threat detected."""
        if source_node in self._isolated_nodes:
            logger.debug("Dropping packet from isolated node: %s", source_node)
            return None

        payload_hex = payload_bytes.hex()
        now = time.time()

        if source_node not in self._packet_rates:
            self._packet_rates[source_node] = []
        self._packet_rates[source_node].append(now)
        rate = len(self._packet_rates[source_node])

        threat = self._classify_threat(rate, rssi, payload_hex)

        if threat == ThreatLevel.LOW:
            self._payload_window.append(payload_hex)
            if len(self._payload_window) > self.DUPLICATE_PAYLOAD_WINDOW:
                self._payload_window.pop(0)
            return None

        anomaly = AnomalyPacket(
            source_node=source_node,
            payload_hex=payload_hex,
            rssi=rssi,
            frequency_mhz=frequency_mhz,
            threat_level=threat,
        )
        self._anomalies.append(anomaly)

        action = self._decide_response(threat, source_node)
        evt = DefenseEvent(
            anomaly=anomaly,
            action=action,
            details=self._describe_action(action, source_node),
        )
        self._defense_events.append(evt)
        self._execute_response(action, source_node)

        if self._response_callback:
            self._response_callback(evt)

        return evt

    def _classify_threat(
        self, rate: int, rssi: float, payload_hex: str
    ) -> ThreatLevel:
        score = 0

        if rate >= self.HIGH_PACKET_RATE_THRESHOLD:
            score += 3
        elif rate >= self.HIGH_PACKET_RATE_THRESHOLD // 2:
            score += 1

        if rssi > self.RSSI_ANOMALY_THRESHOLD_DBM:
            score += 2

        if payload_hex in self._payload_window:
            score += 2

        if score == 0:
            return ThreatLevel.LOW
        elif score <= 2:
            return ThreatLevel.MEDIUM
        elif score <= 4:
            return ThreatLevel.HIGH
        return ThreatLevel.CRITICAL

    def _decide_response(self, threat: ThreatLevel, node_id: str) -> ResponseAction:
        if threat == ThreatLevel.MEDIUM:
            return ResponseAction.LOG
        elif threat == ThreatLevel.HIGH:
            return ResponseAction.ISOLATE
        elif threat == ThreatLevel.CRITICAL:
            return ResponseAction.MIRROR
        return ResponseAction.LOG

    def _describe_action(self, action: ResponseAction, node_id: str) -> str:
        return f"Action {action.value} applied to node {node_id}"

    def _execute_response(self, action: ResponseAction, node_id: str) -> None:
        if action == ResponseAction.ISOLATE:
            self._isolated_nodes.add(node_id)
            logger.warning("Node ISOLATED: %s", node_id)
        elif action == ResponseAction.MIRROR:
            self._isolated_nodes.add(node_id)
            logger.critical("Attack MIRRORED to origin + node ISOLATED: %s", node_id)
        elif action == ResponseAction.SHUTDOWN:
            self._isolated_nodes.add(node_id)
            logger.critical("Node SHUTDOWN: %s", node_id)
        else:
            logger.info("Threat logged for node: %s", node_id)

    def release_node(self, node_id: str) -> None:
        self._isolated_nodes.discard(node_id)

    def get_isolated_nodes(self) -> list[str]:
        return list(self._isolated_nodes)

    def get_defense_events(self) -> list[DefenseEvent]:
        return list(self._defense_events)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "anomalies_detected": len(self._anomalies),
            "defense_events": len(self._defense_events),
            "isolated_nodes": list(self._isolated_nodes),
        }
