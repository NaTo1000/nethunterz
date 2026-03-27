"""Security audit monitor for NRF module."""
from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from pathlib import Path

logger = logging.getLogger("nethunterz.nrf.security_monitor")


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SecurityMonitor:
    """Records security events and monitors tasks for anomalies."""

    def __init__(self, log_path: str = "logs/security_audit.log") -> None:
        self.log_path = log_path
        self._running = False
        self._events: list[dict] = []
        self._watched_tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        self._running = True
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info("SecurityMonitor started, log=%s", self.log_path)

    async def stop(self) -> None:
        self._running = False
        logger.info("SecurityMonitor stopped")

    def record_packet_event(
        self,
        module_id: int,
        packet_count_per_sec: float,
        payload_hash: str,
    ) -> None:
        severity = Severity.INFO
        if packet_count_per_sec > 100:
            severity = Severity.CRITICAL
        elif packet_count_per_sec > 50:
            severity = Severity.WARNING

        event = {
            "timestamp": time.time(),
            "module_id": module_id,
            "packet_count_per_sec": packet_count_per_sec,
            "payload_hash": payload_hash,
            "severity": severity.value,
        }
        self._events.append(event)

        if severity != Severity.INFO:
            logger.warning("Security event: %s", event)

    def watch_task(self, name: str, task: asyncio.Task) -> None:
        self._watched_tasks[name] = task
        logger.info("Watching task: %s", name)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "event_count": len(self._events),
            "watched_tasks": list(self._watched_tasks.keys()),
        }
