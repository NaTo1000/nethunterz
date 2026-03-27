"""BrainSynchronizer — real-time state sharing between brain instances."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SyncPacket:
    """A synchronization packet exchanged between brain instances."""

    brain_id: str
    sequence: int
    state_hash: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.monotonic)

    def to_bytes(self) -> bytes:
        return json.dumps(
            {
                "brain_id": self.brain_id,
                "sequence": self.sequence,
                "state_hash": self.state_hash,
                "payload": self.payload,
                "timestamp": self.timestamp,
            }
        ).encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> "SyncPacket":
        d = json.loads(data.decode())
        return cls(**d)


class BrainSynchronizer:
    """Manages bi-directional state synchronisation between two brains.

    Uses an asyncio.Queue as the shared memory bus.  Each brain pushes
    :class:`SyncPacket` objects; the counterpart reads and applies them.
    """

    def __init__(self, sync_interval_ms: int = 100) -> None:
        self._interval_ms = sync_interval_ms
        self._outbox: asyncio.Queue[SyncPacket] = asyncio.Queue()
        self._inbox: asyncio.Queue[SyncPacket] = asyncio.Queue()
        self._sequence = 0
        self._last_remote_seq: int = -1
        self._running = False
        self._sync_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.debug("BrainSynchronizer started (interval=%dms)", self._interval_ms)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Packet I/O
    # ------------------------------------------------------------------

    async def send(self, brain_id: str, state: dict[str, Any]) -> SyncPacket:
        """Create and enqueue a sync packet for the given state."""
        self._sequence += 1
        packet = SyncPacket(
            brain_id=brain_id,
            sequence=self._sequence,
            state_hash=self._hash_state(state),
            payload=state,
        )
        await self._outbox.put(packet)
        return packet

    async def receive(self, timeout_s: float = 1.0) -> SyncPacket | None:
        """Dequeue the next incoming sync packet, or None on timeout."""
        try:
            return await asyncio.wait_for(self._inbox.get(), timeout=timeout_s)
        except asyncio.TimeoutError:
            return None

    def connect_to(self, other: "BrainSynchronizer") -> None:
        """Wire this sync's outbox to *other*'s inbox (in-process bus)."""
        # Patch the other's inbox queue to receive from our outbox
        # Real deployments use network transport here
        self._peer = other

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _sync_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._interval_ms / 1000.0)
            # Drain outbox and forward to peer inbox if connected
            while not self._outbox.empty():
                pkt = await self._outbox.get()
                if hasattr(self, "_peer"):
                    await self._peer._inbox.put(pkt)

    @staticmethod
    def _hash_state(state: dict[str, Any]) -> str:
        raw = json.dumps(state, sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()
