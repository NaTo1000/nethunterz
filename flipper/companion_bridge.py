"""BLE companion app bridge: Flipper Zero ↔ companion mobile/desktop."""
from __future__ import annotations

import asyncio
import logging
import secrets
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("nethunterz.flipper.companion_bridge")


class BridgeState(Enum):
    DISCONNECTED = "disconnected"
    ADVERTISING = "advertising"
    PAIRED = "paired"
    AUTHENTICATED = "authenticated"
    TRANSFERRING = "transferring"


@dataclass
class BLEPacket:
    """A BLE packet exchanged between Flipper and companion app."""

    packet_type: str
    payload: bytes
    sequence: int = 0
    encrypted: bool = True

    def to_dict(self) -> dict:
        return {
            "packet_type": self.packet_type,
            "payload_len": len(self.payload),
            "sequence": self.sequence,
            "encrypted": self.encrypted,
        }


@dataclass
class TransferSession:
    """Tracks an ongoing firmware/model/scene transfer session."""

    session_id: str = field(default_factory=lambda: secrets.token_hex(8))
    transfer_type: str = "firmware"
    total_bytes: int = 0
    received_bytes: int = 0
    chunks: list[bytes] = field(default_factory=list)
    complete: bool = False

    @property
    def percent(self) -> float:
        return (self.received_bytes / self.total_bytes * 100.0) if self.total_bytes > 0 else 0.0

    def append_chunk(self, data: bytes) -> None:
        self.chunks.append(data)
        self.received_bytes += len(data)
        if self.received_bytes >= self.total_bytes:
            self.complete = True

    def assemble(self) -> bytes:
        return b"".join(self.chunks)


class CompanionBridge:
    """
    BLE bridge between the Flipper Zero and the companion mobile/desktop app.

    The companion app handles:
    - Cloud authentication and heavy API calls
    - Firmware compilation and transfer to Flipper
    - AI model management and inference offloading
    - Scene/animation downloads and transfers

    This class manages the BLE communication layer on the Flipper side.
    """

    # ATT MTU for Flipper Zero BLE (max payload per packet)
    BLE_MTU = 512

    def __init__(
        self,
        device_name: str = "NayDoeV1-Flipper",
        simulation: bool = True,
    ) -> None:
        self.device_name = device_name
        self.simulation = simulation
        self._state = BridgeState.DISCONNECTED
        self._message_handlers: dict[str, Callable] = {}
        self._transfer_sessions: dict[str, TransferSession] = {}
        self._rx_queue: asyncio.Queue = asyncio.Queue()
        self._tx_queue: asyncio.Queue = asyncio.Queue()
        self._sequence = 0
        logger.info("CompanionBridge '%s' initialised (sim=%s)", device_name, simulation)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def start_advertising(self) -> None:
        """Begin BLE advertising so the companion app can discover us."""
        self._state = BridgeState.ADVERTISING
        logger.info("[BLE] Advertising as '%s'", self.device_name)
        if self.simulation:
            await asyncio.sleep(0)

    async def pair(self, companion_key: str) -> bool:
        """Complete the BLE pairing handshake with a companion app."""
        logger.info("[BLE] Pairing with companion key hash %s…", companion_key[:8])
        self._state = BridgeState.PAIRED
        if self.simulation:
            self._state = BridgeState.AUTHENTICATED
            logger.info("[BLE] Pairing + auth complete (simulation)")
            return True
        # Real implementation would exchange challenge-response
        return False

    async def disconnect(self) -> None:
        self._state = BridgeState.DISCONNECTED
        logger.info("[BLE] Disconnected")

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    def register_handler(self, packet_type: str, handler: Callable) -> None:
        """Register a callback for a specific incoming packet type."""
        self._message_handlers[packet_type] = handler

    async def send(self, packet_type: str, payload: bytes) -> None:
        """Queue a packet for transmission to the companion app."""
        self._sequence += 1
        pkt = BLEPacket(
            packet_type=packet_type,
            payload=payload,
            sequence=self._sequence,
            encrypted=True,
        )
        await self._tx_queue.put(pkt)
        logger.debug("[BLE TX] %s seq=%d len=%d", packet_type, self._sequence, len(payload))

    async def receive(self) -> Optional[BLEPacket]:
        """Get the next received packet (non-blocking in simulation)."""
        if self.simulation and self._rx_queue.empty():
            return None
        try:
            return self._rx_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def inject_packet(self, packet_type: str, payload: bytes) -> None:
        """Inject a simulated inbound packet (for testing)."""
        pkt = BLEPacket(packet_type=packet_type, payload=payload)
        await self._rx_queue.put(pkt)

    async def process_rx(self) -> None:
        """Process all pending inbound packets."""
        while not self._rx_queue.empty():
            pkt = await self._rx_queue.get()
            handler = self._message_handlers.get(pkt.packet_type)
            if handler:
                await handler(pkt) if asyncio.iscoroutinefunction(handler) else handler(pkt)
            else:
                logger.debug("[BLE RX] Unhandled packet type: %s", pkt.packet_type)

    # ------------------------------------------------------------------
    # Transfer sessions (firmware, scenes, AI models)
    # ------------------------------------------------------------------

    def start_transfer(self, transfer_type: str, total_bytes: int) -> TransferSession:
        """Initiate a chunked transfer session."""
        session = TransferSession(transfer_type=transfer_type, total_bytes=total_bytes)
        self._transfer_sessions[session.session_id] = session
        self._state = BridgeState.TRANSFERRING
        logger.info("[BLE] Transfer started: %s %d bytes sid=%s",
                    transfer_type, total_bytes, session.session_id)
        return session

    def receive_chunk(self, session_id: str, data: bytes) -> bool:
        """Append a received chunk to the transfer session."""
        session = self._transfer_sessions.get(session_id)
        if session is None:
            logger.warning("[BLE] Unknown transfer session: %s", session_id)
            return False
        session.append_chunk(data)
        logger.debug("[BLE] Chunk received sid=%s %.1f%%", session_id, session.percent)
        if session.complete:
            self._state = BridgeState.AUTHENTICATED
            logger.info("[BLE] Transfer complete sid=%s total=%d bytes",
                        session_id, session.received_bytes)
        return True

    def get_transfer(self, session_id: str) -> Optional[TransferSession]:
        return self._transfer_sessions.get(session_id)

    # ------------------------------------------------------------------
    # Offload requests (sent to companion app)
    # ------------------------------------------------------------------

    async def request_cloud_auth(self, provider: str) -> None:
        """Ask companion app to authenticate with cloud provider."""
        payload = provider.encode()
        await self.send("cloud_auth_request", payload)
        logger.info("[BLE] Cloud auth request sent: %s", provider)

    async def request_ai_inference(self, prompt: bytes) -> None:
        """Offload an AI inference request to the companion app."""
        await self.send("ai_inference_request", prompt)

    async def request_scene_download(self, scene_name: str) -> None:
        """Request a scene animation pack from the companion app."""
        await self.send("scene_download_request", scene_name.encode())

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "device_name": self.device_name,
            "state": self._state.value,
            "active_transfers": len([s for s in self._transfer_sessions.values()
                                     if not s.complete]),
            "completed_transfers": len([s for s in self._transfer_sessions.values()
                                        if s.complete]),
            "tx_queue_size": self._tx_queue.qsize(),
            "rx_queue_size": self._rx_queue.qsize(),
            "simulation": self.simulation,
        }

    # ------------------------------------------------------------------
    # Event loop integration
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Main BLE event loop (processes TX and RX queues)."""
        logger.info("[BLE] Bridge event loop started")
        while self._state != BridgeState.DISCONNECTED:
            await self.process_rx()
            # Drain TX queue (in real implementation: send via BLE stack)
            while not self._tx_queue.empty():
                pkt = self._tx_queue.get_nowait()
                logger.debug("[BLE TX dispatched] %s", pkt.packet_type)
            await asyncio.sleep(0.05)

    async def run_once(self) -> None:
        """Process a single cycle of the BLE event loop."""
        await self.process_rx()
        while not self._tx_queue.empty():
            pkt = self._tx_queue.get_nowait()
            logger.debug("[BLE TX dispatched] %s", pkt.packet_type)
