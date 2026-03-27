"""Autonomous AI decision engine for LoRa mesh network management."""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from .firmware import LoRaFirmware
from .mesh_scanner import MeshScanner
from .frequency_ai import FrequencyAI
from .geofence import GeofenceManager
from .attack_mirror import AttackMirrorDefense

logger = logging.getLogger("nethunterz.lora.autonomy")


@dataclass
class AutonomyDecision:
    decision_type: str
    rationale: str
    timestamp: float = field(default_factory=time.time)
    executed: bool = False

    def to_dict(self) -> dict:
        return {
            "decision_type": self.decision_type,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
            "executed": self.executed,
        }


class AutonomyEngine:
    """Monitors the network and makes autonomous defensive and maintenance decisions."""

    CHECK_INTERVAL_S = 15.0
    INACTIVE_NODE_SEEK_THRESHOLD = 2

    def __init__(
        self,
        firmware: LoRaFirmware,
        scanner: MeshScanner,
        frequency_ai: FrequencyAI,
        geofence: GeofenceManager,
        defense: AttackMirrorDefense,
    ):
        self.firmware = firmware
        self.scanner = scanner
        self.frequency_ai = frequency_ai
        self.geofence = geofence
        self.defense = defense
        self._running = False
        self._decisions: list[AutonomyDecision] = []

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._autonomy_loop())
        logger.info("AutonomyEngine started")

    async def stop(self) -> None:
        self._running = False

    async def _autonomy_loop(self) -> None:
        while self._running:
            await self._check_network_health()
            await self._check_geofence_status()
            await self._check_defense_status()
            await asyncio.sleep(self.CHECK_INTERVAL_S)

    async def _check_network_health(self) -> None:
        scanner_status = self.scanner.get_status()
        inactive = scanner_status.get("inactive_nodes", 0)

        if inactive >= self.INACTIVE_NODE_SEEK_THRESHOLD:
            inactive_nodes = self.scanner.get_inactive_nodes()
            for node in inactive_nodes[:3]:
                self.scanner.seek(node.node_id)
            dec = AutonomyDecision(
                decision_type="seek_inactive_nodes",
                rationale=f"Found {inactive} inactive nodes, initiating seek",
                executed=True,
            )
            self._decisions.append(dec)
            logger.info("Autonomy: %s", dec.rationale)

    async def _check_geofence_status(self) -> None:
        events = self.geofence.get_events()
        recent_breaches = [e for e in events if time.time() - e.timestamp < 60.0]

        if recent_breaches:
            dec = AutonomyDecision(
                decision_type="geofence_breach_response",
                rationale=f"{len(recent_breaches)} geofence breach(es) in last 60s",
                executed=True,
            )
            self._decisions.append(dec)
            logger.warning("Autonomy: %s", dec.rationale)

    async def _check_defense_status(self) -> None:
        defense_status = self.defense.get_status()
        isolated = defense_status.get("isolated_nodes", [])

        if isolated:
            dec = AutonomyDecision(
                decision_type="defense_active",
                rationale=f"Nodes isolated due to threats: {isolated}",
                executed=True,
            )
            self._decisions.append(dec)
            logger.warning("Autonomy: %s", dec.rationale)

    def get_decisions(self) -> list[AutonomyDecision]:
        return list(self._decisions)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "total_decisions": len(self._decisions),
            "recent_decisions": [d.to_dict() for d in self._decisions[-5:]],
        }
