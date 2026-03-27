"""
pingequa_dual_nrf.py – Core runtime driver for the Pingequa Dual NRF Module.

Responsibilities
----------------
* Open and manage two independent NRF24L01+ radio channels (primary + secondary).
* Read raw RF packets from the air on both channels simultaneously.
* Record captured packets into a time-stamped log file.
* Rewrite (replay / inject) stored packets back onto the air.
* Trigger live frequency upgrades without stopping the runtime.
* Expose a clean async API consumed by BLEBridge and CloudOrchestrator.
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class NRFPacket:
    """Represents a single captured RF packet."""
    channel: int
    frequency_mhz: float
    timestamp: float
    rssi: int
    payload: bytes
    module_id: int  # 0 = primary, 1 = secondary

    def to_dict(self) -> dict:
        d = asdict(self)
        d["payload"] = self.payload.hex()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "NRFPacket":
        data = dict(data)
        data["payload"] = bytes.fromhex(data["payload"])
        return cls(**data)


@dataclass
class ModuleConfig:
    """Runtime configuration for one NRF module."""
    module_id: int
    channel: int = 76          # default 2.476 GHz
    data_rate: str = "1MBPS"   # 250KBPS | 1MBPS | 2MBPS
    pa_level: str = "HIGH"     # MIN | LOW | HIGH | MAX
    address: bytes = field(default_factory=lambda: b"\xe7\xe7\xe7\xe7\xe7")
    payload_size: int = 32

    @property
    def frequency_mhz(self) -> float:
        return 2400.0 + self.channel


# ---------------------------------------------------------------------------
# Hardware abstraction – swappable with real spidev / RF24 library
# ---------------------------------------------------------------------------

class _NRFHardware:
    """
    Thin abstraction layer over the physical NRF24L01+ chip.

    In production this wraps the RF24 Python library (or spidev).
    In CI / unit-test mode it operates as a software stub.
    """

    def __init__(self, config: ModuleConfig, *, simulation: bool = False):
        self.config = config
        self.simulation = simulation
        self._open = False

    # ------------------------------------------------------------------
    def open(self) -> None:
        if self._open:
            return
        if not self.simulation:
            try:
                import RF24  # type: ignore
                self._radio = RF24.RF24(17, 0)  # CE=GPIO17, CSN=CE0
                self._radio.begin()
                self._radio.setChannel(self.config.channel)
                self._radio.setDataRate(
                    getattr(RF24, f"RF24_{''.join(self.config.data_rate.split('_'))}")
                )
                self._radio.setPALevel(
                    getattr(RF24, f"RF24_PA_{self.config.pa_level}")
                )
                self._radio.openReadingPipe(1, self.config.address)
                self._radio.startListening()
            except ImportError:
                logger.warning(
                    "RF24 library not available – falling back to simulation mode "
                    "for module %d", self.config.module_id
                )
                self.simulation = True
        self._open = True
        logger.info(
            "NRF module %d opened on channel %d (%.3f GHz)",
            self.config.module_id,
            self.config.channel,
            self.config.frequency_mhz / 1000,
        )

    def close(self) -> None:
        if not self.simulation and self._open:
            try:
                self._radio.stopListening()
            except Exception:  # pragma: no cover
                pass
        self._open = False

    # ------------------------------------------------------------------
    def set_channel(self, channel: int) -> None:
        self.config.channel = max(0, min(125, channel))
        if not self.simulation and self._open:
            try:
                self._radio.setChannel(self.config.channel)
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to set channel on hardware: %s", exc)

    def available(self) -> bool:
        if self.simulation:
            # Randomly produce a fake packet ~20 % of the time
            import random
            return random.random() < 0.2
        return bool(self._radio.available())

    def read(self) -> bytes:
        if self.simulation:
            import random
            size = random.randint(4, self.config.payload_size)
            return bytes(random.getrandbits(8) for _ in range(size))
        return bytes(self._radio.read(self.config.payload_size))

    def write(self, payload: bytes) -> bool:
        if self.simulation:
            logger.debug(
                "Module %d [SIM] TX %d bytes: %s",
                self.config.module_id, len(payload), payload.hex()
            )
            return True
        self._radio.stopListening()
        ok = bool(self._radio.write(payload))
        self._radio.startListening()
        return ok

    def get_rssi(self) -> int:
        if self.simulation:
            import random
            return random.randint(-90, -30)
        try:
            return self._radio.testRPD()
        except Exception:  # pragma: no cover
            return -100


# ---------------------------------------------------------------------------
# Main runtime class
# ---------------------------------------------------------------------------

class PingequaDualNRF:
    """
    High-level runtime controller for the Pingequa Dual NRF module.

    Usage::

        async with PingequaDualNRF() as nrf:
            await nrf.start_capture()
            await asyncio.sleep(30)
            packets = await nrf.get_captured_packets()
            await nrf.upgrade_frequency(module_id=0, new_channel=100)
    """

    DEFAULT_LOG_DIR = Path("logs/nrf")

    def __init__(
        self,
        primary_config: Optional[ModuleConfig] = None,
        secondary_config: Optional[ModuleConfig] = None,
        *,
        log_dir: Optional[Path] = None,
        simulation: bool = True,
        packet_callback: Optional[Callable[[NRFPacket], None]] = None,
    ):
        self._primary_config = primary_config or ModuleConfig(module_id=0, channel=76)
        self._secondary_config = secondary_config or ModuleConfig(module_id=1, channel=100)
        self._log_dir = log_dir or self.DEFAULT_LOG_DIR
        self._simulation = simulation
        self._packet_callback = packet_callback

        self._hw = [
            _NRFHardware(self._primary_config, simulation=simulation),
            _NRFHardware(self._secondary_config, simulation=simulation),
        ]
        self._capture_task: Optional[asyncio.Task] = None
        self._running = False
        self._packets: List[NRFPacket] = []
        self._log_file: Optional[Path] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------
    async def __aenter__(self) -> "PingequaDualNRF":
        self.open()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop_capture()
        self.close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def open(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        for hw in self._hw:
            hw.open()
        ts = int(time.time())
        self._log_file = self._log_dir / f"capture_{ts}.jsonl"
        logger.info("Log file: %s", self._log_file)

    def close(self) -> None:
        for hw in self._hw:
            hw.close()

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------
    async def start_capture(self) -> None:
        if self._running:
            logger.warning("Capture already running.")
            return
        self._running = True
        self._capture_task = asyncio.create_task(self._capture_loop())
        logger.info("Dual-NRF capture started.")

    async def stop_capture(self) -> None:
        self._running = False
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
            self._capture_task = None
        logger.info("Dual-NRF capture stopped. %d packets recorded.", len(self._packets))

    async def _capture_loop(self) -> None:
        """Continuously poll both NRF modules and record packets."""
        while self._running:
            for hw in self._hw:
                if hw.available():
                    raw = hw.read()
                    pkt = NRFPacket(
                        channel=hw.config.channel,
                        frequency_mhz=hw.config.frequency_mhz,
                        timestamp=time.time(),
                        rssi=hw.get_rssi(),
                        payload=raw,
                        module_id=hw.config.module_id,
                    )
                    await self._record_packet(pkt)
                    if self._packet_callback:
                        try:
                            self._packet_callback(pkt)
                        except Exception as exc:  # pragma: no cover
                            logger.error("Packet callback error: %s", exc)
            await asyncio.sleep(0.01)  # 10 ms poll cycle

    async def _record_packet(self, pkt: NRFPacket) -> None:
        """Append packet to in-memory list and persist to log file."""
        self._packets.append(pkt)
        if self._log_file:
            try:
                with self._log_file.open("a") as fh:
                    fh.write(json.dumps(pkt.to_dict()) + "\n")
            except OSError as exc:  # pragma: no cover
                logger.error("Failed to write log: %s", exc)

    # ------------------------------------------------------------------
    # Read / Rewrite
    # ------------------------------------------------------------------
    async def get_captured_packets(self) -> List[NRFPacket]:
        """Return all packets captured so far (thread-safe snapshot)."""
        return list(self._packets)

    async def load_log(self, log_path: Path) -> List[NRFPacket]:
        """Load previously recorded packets from a .jsonl log file."""
        packets: List[NRFPacket] = []
        with log_path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    packets.append(NRFPacket.from_dict(json.loads(line)))
        logger.info("Loaded %d packets from %s", len(packets), log_path)
        return packets

    async def rewrite_packets(
        self,
        packets: List[NRFPacket],
        *,
        module_id: int = 0,
        delay_s: float = 0.05,
    ) -> None:
        """
        Replay (inject) a list of packets through the chosen module.

        Parameters
        ----------
        packets:    List of NRFPacket to transmit.
        module_id:  0 = primary, 1 = secondary.
        delay_s:    Inter-packet delay in seconds.
        """
        hw = self._hw[module_id]
        ok_count = 0
        for pkt in packets:
            if hw.write(pkt.payload):
                ok_count += 1
            await asyncio.sleep(delay_s)
        logger.info(
            "Rewrite complete: %d/%d packets transmitted via module %d.",
            ok_count, len(packets), module_id,
        )

    # ------------------------------------------------------------------
    # Live frequency upgrade
    # ------------------------------------------------------------------
    async def upgrade_frequency(
        self,
        *,
        module_id: int,
        new_channel: int,
        transition_delay_s: float = 0.1,
    ) -> float:
        """
        Hot-switch a module to a new RF channel without halting capture.

        Returns the new frequency in MHz.
        """
        hw = self._hw[module_id]
        old_channel = hw.config.channel
        hw.set_channel(new_channel)
        await asyncio.sleep(transition_delay_s)  # allow PLL re-lock
        new_freq = hw.config.frequency_mhz
        logger.info(
            "Module %d frequency upgraded: ch%d (%.1f MHz) → ch%d (%.1f MHz)",
            module_id,
            old_channel, 2400.0 + old_channel,
            new_channel, new_freq,
        )
        return new_freq

    # ------------------------------------------------------------------
    # Status / diagnostics
    # ------------------------------------------------------------------
    def get_status(self) -> dict:
        return {
            "running": self._running,
            "packet_count": len(self._packets),
            "log_file": str(self._log_file) if self._log_file else None,
            "modules": [
                {
                    "id": hw.config.module_id,
                    "channel": hw.config.channel,
                    "frequency_mhz": hw.config.frequency_mhz,
                    "data_rate": hw.config.data_rate,
                    "pa_level": hw.config.pa_level,
                }
                for hw in self._hw
            ],
        }
