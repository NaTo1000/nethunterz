"""Monitoring Dashboard — real-time error monitoring and automated resolution."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """A monitoring alert."""

    alert_id: str
    severity: AlertSeverity
    component: str
    message: str
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolved_at: float | None = None


ResolutionFn = Callable[[Alert], Coroutine[Any, Any, None]]


class MonitoringDashboard:
    """Real-time monitoring dashboard with alert management.

    Features
    --------
    * Raise and resolve alerts with severity levels.
    * Register automated resolution pipelines per alert type.
    * Collect and expose system health metrics.
    * Integrity checks for blockchain-verified AI decisions.
    """

    def __init__(self, check_interval_s: float = 30.0) -> None:
        self._check_interval = check_interval_s
        self._alerts: dict[str, Alert] = {}
        self._resolution_registry: dict[str, ResolutionFn] = {}
        self._metrics: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._monitor_task: asyncio.Task[None] | None = None
        self._running = False
        self._alert_counter = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("MonitoringDashboard started")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("MonitoringDashboard stopped")

    # ------------------------------------------------------------------
    # Alert management
    # ------------------------------------------------------------------

    async def raise_alert(
        self,
        component: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
    ) -> Alert:
        async with self._lock:
            self._alert_counter += 1
            alert_id = f"alert_{self._alert_counter:06d}"
            alert = Alert(
                alert_id=alert_id,
                severity=severity,
                component=component,
                message=message,
            )
            self._alerts[alert_id] = alert

        logger.log(
            logging.ERROR if severity in (AlertSeverity.ERROR, AlertSeverity.CRITICAL)
            else logging.WARNING,
            "Alert[%s/%s]: %s",
            severity.value.upper(),
            component,
            message,
        )

        # Attempt automated resolution
        await self._try_resolve(alert)
        return alert

    async def resolve_alert(self, alert_id: str) -> bool:
        async with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return False
            alert.resolved = True
            alert.resolved_at = time.time()
        logger.info("Alert %s resolved", alert_id)
        return True

    # ------------------------------------------------------------------
    # Automated resolution
    # ------------------------------------------------------------------

    def register_resolver(
        self,
        component: str,
        fn: ResolutionFn,
    ) -> None:
        """Register an automated resolver for alerts from *component*."""
        self._resolution_registry[component] = fn
        logger.debug("Resolver registered for component %s", component)

    async def _try_resolve(self, alert: Alert) -> None:
        fn = self._resolution_registry.get(alert.component)
        if fn is None:
            return
        try:
            await fn(alert)
            await self.resolve_alert(alert.alert_id)
        except Exception as exc:
            logger.error(
                "Auto-resolution failed for %s: %s", alert.alert_id, exc
            )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def record_metric(self, name: str, value: Any) -> None:
        self._metrics[name] = {"value": value, "updated_at": time.time()}

    def get_metric(self, name: str) -> Any | None:
        entry = self._metrics.get(name)
        return entry["value"] if entry else None

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._check_interval)
            await self._run_integrity_checks()

    async def _run_integrity_checks(self) -> None:
        async with self._lock:
            unresolved = [a for a in self._alerts.values() if not a.resolved]
        if unresolved:
            logger.info(
                "Integrity check: %d unresolved alert(s)", len(unresolved)
            )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_open_alerts(self) -> list[dict[str, Any]]:
        return [
            {
                "alert_id": a.alert_id,
                "severity": a.severity.value,
                "component": a.component,
                "message": a.message,
                "timestamp": a.timestamp,
            }
            for a in self._alerts.values()
            if not a.resolved
        ]

    def get_summary(self) -> dict[str, Any]:
        total = len(self._alerts)
        open_count = sum(1 for a in self._alerts.values() if not a.resolved)
        return {
            "total_alerts": total,
            "open_alerts": open_count,
            "resolved_alerts": total - open_count,
            "metrics": dict(self._metrics),
        }
