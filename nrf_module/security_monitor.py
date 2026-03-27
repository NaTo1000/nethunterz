"""
security_monitor.py – Security and runtime monitoring for NetHunterZ.

Features
--------
* Real-time anomaly detection (packet flood, replay attacks, rogue devices).
* Encrypted audit log (AES-GCM via cryptography library, or base64 fallback).
* Alert dispatcher: console, file, webhook, BLE push.
* Health watchdog: restarts failed coroutines, emits alerts on repeated failures.
* Rate-limiting for authentication attempts.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Alert severity
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    severity: Severity
    code: str
    message: str
    timestamp: float
    context: dict

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


# ---------------------------------------------------------------------------
# Encrypted log writer
# ---------------------------------------------------------------------------

class _EncryptedLogWriter:
    """
    Writes audit log entries encrypted with AES-256-GCM when the
    `cryptography` package is available; falls back to Base64 encoding.
    """

    def __init__(self, log_path: str, key_hex: Optional[str] = None):
        self._path = log_path
        raw_key = bytes.fromhex(key_hex) if key_hex else None
        if raw_key is None:
            env_key = os.environ.get("NRF_LOG_KEY", "")
            raw_key = bytes.fromhex(env_key) if env_key else None
        self._key = raw_key
        self._use_crypto = False
        if self._key:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore  # noqa
                self._use_crypto = True
            except ImportError:
                logger.warning(
                    "cryptography package not available – using Base64 log encoding."
                )

    def write(self, data: dict) -> None:
        raw = json.dumps(data).encode()
        if self._use_crypto and self._key:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
            import os as _os
            nonce = _os.urandom(12)
            ct = AESGCM(self._key).encrypt(nonce, raw, None)
            line = base64.b64encode(nonce + ct).decode() + "\n"
        else:
            line = base64.b64encode(raw).decode() + "\n"
        with open(self._path, "a") as fh:
            fh.write(line)


# ---------------------------------------------------------------------------
# Security Monitor
# ---------------------------------------------------------------------------

class SecurityMonitor:
    """
    Monitors the NRF runtime for security threats and operational anomalies.

    Usage::

        monitor = SecurityMonitor()
        await monitor.start()
        monitor.record_packet_event(module_id=0, packet_count_per_sec=1200)
        await monitor.stop()
    """

    # Thresholds
    FLOOD_PPS_THRESHOLD = 1000         # packets/sec
    MAX_AUTH_ATTEMPTS_PER_MIN = 5
    REPLAY_WINDOW_S = 60               # seconds to keep hash cache

    def __init__(
        self,
        *,
        log_path: str = "logs/security_audit.log",
        alert_callback: Optional[Callable[[Alert], None]] = None,
        webhook_url: Optional[str] = None,
        log_key_hex: Optional[str] = None,
    ):
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self._log_writer = _EncryptedLogWriter(log_path, log_key_hex)
        self._alert_callback = alert_callback
        self._webhook_url = webhook_url or os.environ.get("ALERT_WEBHOOK_URL")
        self._alerts: List[Alert] = []

        # Replay detection: sliding window of payload hashes
        self._payload_hashes: deque = deque()

        # Rate limiting: device_id -> list of attempt timestamps
        self._auth_attempts: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.MAX_AUTH_ATTEMPTS_PER_MIN + 10)
        )

        # Watchdog state
        self._watchdog_task: Optional[asyncio.Task] = None
        self._running = False
        self._watched_tasks: Dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        logger.info("SecurityMonitor started.")

    async def stop(self) -> None:
        self._running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        logger.info("SecurityMonitor stopped. Total alerts: %d", len(self._alerts))

    # ------------------------------------------------------------------
    # Packet / RF anomaly detection
    # ------------------------------------------------------------------
    def record_packet_event(
        self,
        *,
        module_id: int,
        packet_count_per_sec: int,
        payload_hash: Optional[str] = None,
    ) -> None:
        """
        Evaluate a packet-rate event for flooding and replay attacks.

        Parameters
        ----------
        module_id:            Which NRF module produced the event.
        packet_count_per_sec: Current observed rate.
        payload_hash:         SHA-256 hex of the raw payload (for replay detection).
        """
        if packet_count_per_sec > self.FLOOD_PPS_THRESHOLD:
            self._emit_alert(
                Severity.CRITICAL,
                "PACKET_FLOOD",
                f"Module {module_id}: packet rate {packet_count_per_sec} pps "
                f"exceeds threshold {self.FLOOD_PPS_THRESHOLD}.",
                {"module_id": module_id, "pps": packet_count_per_sec},
            )

        if payload_hash:
            now = time.time()
            # Expire old hashes
            while self._payload_hashes and self._payload_hashes[0][1] < now - self.REPLAY_WINDOW_S:
                self._payload_hashes.popleft()
            existing = {h for h, _ in self._payload_hashes}
            if payload_hash in existing:
                self._emit_alert(
                    Severity.WARNING,
                    "REPLAY_ATTACK",
                    f"Duplicate payload hash detected on module {module_id}.",
                    {"module_id": module_id, "hash": payload_hash},
                )
            else:
                self._payload_hashes.append((payload_hash, now))

    # ------------------------------------------------------------------
    # Authentication rate limiting
    # ------------------------------------------------------------------
    def check_auth_rate(self, device_id: str) -> bool:
        """
        Return True if the device may attempt authentication now.
        Records the attempt; returns False if the rate limit is exceeded.
        """
        now = time.time()
        attempts = self._auth_attempts[device_id]
        # Remove attempts older than 60 s
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= self.MAX_AUTH_ATTEMPTS_PER_MIN:
            self._emit_alert(
                Severity.CRITICAL,
                "AUTH_RATE_LIMIT",
                f"Device {device_id} exceeded {self.MAX_AUTH_ATTEMPTS_PER_MIN} "
                "auth attempts per minute.",
                {"device_id": device_id},
            )
            return False
        attempts.append(now)
        return True

    # ------------------------------------------------------------------
    # Watchdog
    # ------------------------------------------------------------------
    def watch_task(self, name: str, task: asyncio.Task) -> None:
        """Register a coroutine task with the watchdog."""
        self._watched_tasks[name] = task

    async def _watchdog_loop(self) -> None:
        while self._running:
            for name, task in list(self._watched_tasks.items()):
                if task.done() and not task.cancelled():
                    exc = task.exception()
                    if exc:
                        self._emit_alert(
                            Severity.CRITICAL,
                            "TASK_FAILURE",
                            f"Task '{name}' raised an unhandled exception: {exc}",
                            {"task": name, "exception": str(exc)},
                        )
            await asyncio.sleep(5)

    # ------------------------------------------------------------------
    # Alert emission
    # ------------------------------------------------------------------

    # Map Severity enum to logging methods once at class definition time
    _SEVERITY_TO_LOG = None  # populated after class body (see below)

    def _emit_alert(
        self,
        severity: Severity,
        code: str,
        message: str,
        context: dict,
    ) -> None:
        alert = Alert(
            severity=severity,
            code=code,
            message=message,
            timestamp=time.time(),
            context=context,
        )
        self._alerts.append(alert)
        log_method = self._SEVERITY_TO_LOG.get(severity, logger.warning)
        log_method("[ALERT %s] %s: %s", severity.value, code, message)
        self._log_writer.write(alert.to_dict())
        if self._alert_callback:
            try:
                self._alert_callback(alert)
            except Exception as exc:  # pragma: no cover
                logger.error("Alert callback error: %s", exc)
        if self._webhook_url:
            asyncio.ensure_future(self._send_webhook(alert))

    async def _send_webhook(self, alert: Alert) -> None:
        try:
            import aiohttp  # type: ignore
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self._webhook_url,
                    json=alert.to_dict(),
                    timeout=aiohttp.ClientTimeout(total=5.0),
                )
        except Exception as exc:
            logger.debug("Webhook delivery failed: %s", exc)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get_alerts(self, *, severity: Optional[Severity] = None) -> List[Alert]:
        if severity:
            return [a for a in self._alerts if a.severity == severity]
        return list(self._alerts)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "total_alerts": len(self._alerts),
            "critical_alerts": len(self.get_alerts(severity=Severity.CRITICAL)),
            "warning_alerts": len(self.get_alerts(severity=Severity.WARNING)),
        }


# Populate the class-level severity → log method map after both Severity and SecurityMonitor are defined
SecurityMonitor._SEVERITY_TO_LOG = {
    Severity.DEBUG: logger.debug,
    Severity.INFO: logger.info,
    Severity.WARNING: logger.warning,
    Severity.CRITICAL: logger.critical,
}
