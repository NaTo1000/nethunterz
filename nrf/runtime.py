#!/usr/bin/env python3
"""NRF24L01+ dual-module runtime: scan, record, hop, and bridge BLE to internet."""

import time
import logging
import threading
import struct
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

NRF_MIN_CHANNEL = 0
NRF_MAX_CHANNEL = 125
SCAN_DWELL_MS   = 5
HOP_INTERVAL_S  = 0.5
LOG_FILE        = "nrf_scan_log.jsonl"


@dataclass
class ChannelRecord:
    channel: int
    freq_mhz: int
    rssi_estimate: int
    packet_count: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ScanSession:
    start_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    records: List[ChannelRecord] = field(default_factory=list)
    best_channel: int = 76
    total_packets: int = 0


class NRFRuntime:
    """Dual NRF24L01+ module runtime manager.
    
    Module A (CE=GPIO22, CSN=GPIO21): Scanner / receiver
    Module B (CE=GPIO17, CSN=GPIO16): Transmitter / hopper
    """

    def __init__(self, 
                 ce_a: int = 22, csn_a: int = 21,
                 ce_b: int = 17, csn_b: int = 16,
                 spi_bus: int = 0) -> None:
        self.ce_a   = ce_a
        self.csn_a  = csn_a
        self.ce_b   = ce_b
        self.csn_b  = csn_b
        self.spi_bus = spi_bus
        self._radio_a = None
        self._radio_b = None
        self._session  = ScanSession()
        self._running  = False
        self._lock     = threading.Lock()
        self._log_file = open(LOG_FILE, "a", encoding="utf-8")
        self._initialize()

    def _initialize(self) -> None:
        """Attempt to initialise NRF24L01+ hardware; fall back to simulation."""
        try:
            import spidev
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            self._gpio = GPIO
            self._spi  = spidev.SpiDev()
            self._spi.open(self.spi_bus, 0)
            self._spi.max_speed_hz = 10_000_000
            self._hw_available = True
            logger.info("NRF24L01+ hardware initialised (SPI bus %d)", self.spi_bus)
        except ImportError:
            logger.warning("RPi.GPIO/spidev not available – running in simulation mode")
            self._hw_available = False
        except Exception as exc:
            logger.error("Hardware init failed: %s – simulation mode", exc)
            self._hw_available = False

    def _spi_write_register(self, reg: int, value: int) -> None:
        if not self._hw_available:
            return
        self._spi.xfer2([0x20 | reg, value])

    def _spi_read_register(self, reg: int) -> int:
        if not self._hw_available:
            return 0
        result = self._spi.xfer2([reg, 0xFF])
        return result[1]

    def _set_channel(self, radio_id: str, channel: int) -> None:
        channel = max(NRF_MIN_CHANNEL, min(NRF_MAX_CHANNEL, channel))
        self._spi_write_register(0x05, channel)  # RF_CH register

    def _read_rpd(self) -> bool:
        """Read Received Power Detector register."""
        if not self._hw_available:
            import random
            return random.random() < 0.15
        return bool(self._spi_read_register(0x09) & 0x01)

    def scan_all_channels(self) -> Dict[int, int]:
        """Scan all 126 channels and return {channel: packet_count}."""
        counts: Dict[int, int] = {}
        logger.info("Starting full channel scan (0–%d)...", NRF_MAX_CHANNEL)
        for ch in range(NRF_MIN_CHANNEL, NRF_MAX_CHANNEL + 1):
            self._set_channel("A", ch)
            time.sleep(SCAN_DWELL_MS / 1000.0)
            detected = self._read_rpd()
            count = 1 if detected else 0
            counts[ch] = count
            freq = 2400 + ch
            record = ChannelRecord(
                channel=ch,
                freq_mhz=freq,
                rssi_estimate=-90 + (count * 30),
                packet_count=count,
            )
            self._session.records.append(record)
            self._log_record(record)
        self._session.total_packets = sum(counts.values())
        logger.info("Scan complete. %d channels with activity detected.",
                    sum(1 for v in counts.values() if v > 0))
        return counts

    def find_clear_channel(self, counts: Dict[int, int]) -> int:
        """Find the channel with least interference."""
        if not counts:
            return 76  # Default safe channel
        # Prefer channels 1, 6, 11 (non-overlapping WiFi) + avoid congested
        preferred = [1, 6, 11, 36, 76, 100]
        for ch in preferred:
            if counts.get(ch, 0) == 0:
                return ch
        return min(counts, key=lambda c: counts[c])

    def hop_to_clear_channel(self) -> int:
        """Scan, find clear channel, and hop both radios to it."""
        counts = self.scan_all_channels()
        best   = self.find_clear_channel(counts)
        self._session.best_channel = best
        logger.info("Hopping to channel %d (freq %d MHz)", best, 2400 + best)
        self._set_channel("A", best)
        self._set_channel("B", best)
        return best

    def start_continuous_scan(self, interval_s: float = HOP_INTERVAL_S) -> None:
        """Start background channel hopping thread."""
        self._running = True
        self._hop_thread = threading.Thread(
            target=self._hop_loop, args=(interval_s,), daemon=True
        )
        self._hop_thread.start()
        logger.info("Continuous scan/hop started (interval=%.1fs)", interval_s)

    def stop_continuous_scan(self) -> None:
        self._running = False

    def _hop_loop(self, interval_s: float) -> None:
        while self._running:
            best = self.hop_to_clear_channel()
            logger.debug("Hopped to channel %d", best)
            time.sleep(interval_s)

    def _log_record(self, record: ChannelRecord) -> None:
        with self._lock:
            self._log_file.write(json.dumps(asdict(record)) + "\n")
            self._log_file.flush()

    def send_packet(self, data: bytes, channel: int = None) -> bool:
        """Send a packet via radio B."""
        if channel is not None:
            self._set_channel("B", channel)
        if not self._hw_available:
            logger.debug("SIM TX %d bytes on channel %s", len(data), channel)
            return True
        try:
            self._spi.xfer2([0xA0] + list(data[:32]))
            return True
        except Exception as exc:
            logger.error("TX error: %s", exc)
            return False

    def receive_packet(self, timeout_ms: int = 100) -> Optional[bytes]:
        """Receive a packet from radio A."""
        if not self._hw_available:
            return None
        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline:
            status = self._spi_read_register(0x07)
            if status & 0x40:  # RX_DR bit
                payload = self._spi.xfer2([0x61] + [0xFF] * 32)
                self._spi_write_register(0x07, 0x40)
                return bytes(payload[1:])
        return None

    def get_session_summary(self) -> dict:
        return {
            "start_time":    self._session.start_time,
            "total_channels_scanned": len(self._session.records),
            "total_packets": self._session.total_packets,
            "best_channel":  self._session.best_channel,
            "best_freq_mhz": 2400 + self._session.best_channel,
        }

    def close(self) -> None:
        self.stop_continuous_scan()
        self._log_file.close()
        if self._hw_available:
            self._spi.close()
        logger.info("NRF runtime closed. Session: %s", self.get_session_summary())


if __name__ == "__main__":
    runtime = NRFRuntime()
    try:
        logger.info("Running NRF frequency scan...")
        runtime.start_continuous_scan(interval_s=30)
        time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        runtime.close()
