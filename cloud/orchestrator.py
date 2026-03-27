"""
orchestrator.py – Server-side cloud orchestration engine.

Receives packet uploads from NetHunterZ devices, performs RF analysis,
and pushes back frequency recommendations in real-time.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeviceSession:
    device_id: str
    connected_at: float
    last_seen: float
    packet_count: int = 0
    current_channel: int = 76
    recommendations_sent: int = 0


class Orchestrator:
    """
    Server-side orchestration hub for all connected NetHunterZ devices.

    * Aggregates packet streams from multiple devices.
    * Runs the FrequencyEngine to detect congestion and generate recommendations.
    * Pushes recommendations back via WebSocket or polling endpoint.
    * Maintains per-device sessions and telemetry.
    """

    RECOMMENDATION_INTERVAL_S = 30

    def __init__(
        self,
        frequency_engine=None,
        *,
        recommendation_callback: Optional[Callable] = None,
    ):
        self._freq_engine = frequency_engine
        self._rec_callback = recommendation_callback
        self._sessions: Dict[str, DeviceSession] = {}
        self._packet_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recommendation_queue: Dict[str, List[dict]] = defaultdict(list)
        self._task: Optional[asyncio.Task] = None
        self._running = False

    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._analysis_loop())
        logger.info("Cloud Orchestrator started.")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Device session management
    # ------------------------------------------------------------------
    def register_device(self, device_id: str) -> DeviceSession:
        session = DeviceSession(
            device_id=device_id,
            connected_at=time.time(),
            last_seen=time.time(),
        )
        self._sessions[device_id] = session
        logger.info("Device registered: %s", device_id)
        return session

    def update_device(self, device_id: str) -> None:
        if device_id in self._sessions:
            self._sessions[device_id].last_seen = time.time()

    # ------------------------------------------------------------------
    # Packet ingestion
    # ------------------------------------------------------------------
    async def ingest_packets(self, device_id: str, packets: List[dict]) -> dict:
        """Accept a batch of NRF packets from a device and enqueue for analysis."""
        if device_id not in self._sessions:
            self.register_device(device_id)
        session = self._sessions[device_id]
        session.packet_count += len(packets)
        session.last_seen = time.time()
        buf = self._packet_buffer[device_id]
        for pkt in packets:
            buf.append(pkt)
        logger.debug("Ingested %d packets from %s", len(packets), device_id)
        # Return any pending recommendations immediately
        recs = self._recommendation_queue.pop(device_id, [])
        return {"status": "ok", "recommendations": recs}

    # ------------------------------------------------------------------
    # Analysis loop
    # ------------------------------------------------------------------
    async def _analysis_loop(self) -> None:
        while self._running:
            for device_id, buf in list(self._packet_buffer.items()):
                if not buf:
                    continue
                packets = list(buf)
                buf.clear()
                if self._freq_engine:
                    recommendations = await self._freq_engine.analyse(
                        device_id, packets
                    )
                    if recommendations:
                        self._recommendation_queue[device_id].extend(recommendations)
                        session = self._sessions.get(device_id)
                        if session:
                            session.recommendations_sent += len(recommendations)
                        if self._rec_callback:
                            for rec in recommendations:
                                await self._rec_callback(device_id, rec)
            await asyncio.sleep(self.RECOMMENDATION_INTERVAL_S)

    # ------------------------------------------------------------------
    def get_sessions(self) -> List[dict]:
        return [asdict(s) for s in self._sessions.values()]

    def get_pending_recommendations(self, device_id: str) -> List[dict]:
        return list(self._recommendation_queue.get(device_id, []))

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "devices": len(self._sessions),
            "total_packets": sum(s.packet_count for s in self._sessions.values()),
        }
