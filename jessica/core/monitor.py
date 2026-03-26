"""Autonomous Monitor — continuously watches every entry point:
ports, localhost services, USB devices, WiFi interfaces, and loaded drivers.

Runs as an async loop that periodically scans and emits events to ConductorX
for reactive orchestration.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jessica.core.monitor")


@dataclass
class MonitorEvent:
    """An observation produced by one of the monitoring sub‑systems."""

    subsystem: str
    event_type: str  # "new" | "changed" | "removed" | "alert"
    detail: dict[str, Any] = field(default_factory=dict)


class AutonomousMonitor:
    """Watches all entry points (ports, USB, WiFi, drivers, localhost) and
    feeds events into the ConductorX event bus.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._cfg = config
        self._running = False
        self._events: asyncio.Queue[MonitorEvent] = asyncio.Queue()
        self._tasks: list[asyncio.Task[None]] = []

    # ── lifecycle ─────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        targets = self._cfg.get("targets", {})

        if targets.get("ports", {}).get("watch_all", False):
            self._tasks.append(asyncio.create_task(self._watch_ports(targets["ports"])))

        if targets.get("localhost", {}).get("monitor", False):
            self._tasks.append(asyncio.create_task(self._watch_localhost(targets["localhost"])))

        if targets.get("usb", {}).get("monitor_all", False):
            self._tasks.append(asyncio.create_task(self._watch_usb(targets["usb"])))

        if targets.get("wifi", {}).get("monitor_all_interfaces", False):
            self._tasks.append(asyncio.create_task(self._watch_wifi(targets["wifi"])))

        if targets.get("drivers", {}).get("watch_loaded_modules", False):
            self._tasks.append(asyncio.create_task(self._watch_drivers(targets["drivers"])))

        if targets.get("network_interfaces", {}).get("watch_all", False):
            self._tasks.append(asyncio.create_task(self._watch_network_interfaces()))

        logger.info("AutonomousMonitor started — %d watchers active", len(self._tasks))

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        logger.info("AutonomousMonitor stopped.")

    async def next_event(self) -> MonitorEvent:
        """Await the next monitor event."""
        return await self._events.get()

    # ── watchers ──────────────────────────────────────────

    async def _watch_ports(self, cfg: dict[str, Any]) -> None:
        """Periodic TCP/UDP port scan of localhost."""
        interval = cfg.get("scan_interval_seconds", 30)
        known_ports: set[str] = set()
        while self._running:
            current = self._scan_open_ports()
            new_ports = current - known_ports
            closed_ports = known_ports - current
            for port in new_ports:
                await self._events.put(MonitorEvent("ports", "new", {"port": port}))
            for port in closed_ports:
                await self._events.put(MonitorEvent("ports", "removed", {"port": port}))
            known_ports = current
            await asyncio.sleep(interval)

    async def _watch_localhost(self, cfg: dict[str, Any]) -> None:
        interval = cfg.get("scan_interval_seconds", 10)
        while self._running:
            # Simple connectivity + service check
            services = self._check_localhost_services()
            for svc in services:
                await self._events.put(MonitorEvent("localhost", "alert", svc))
            await asyncio.sleep(interval)

    async def _watch_usb(self, cfg: dict[str, Any]) -> None:
        """Detect USB device insertion / removal (USB‑A and USB‑C)."""
        known_devices: set[str] = set()
        while self._running:
            current = self._list_usb_devices()
            for dev in current - known_devices:
                await self._events.put(MonitorEvent("usb", "new", {"device": dev}))
            for dev in known_devices - current:
                await self._events.put(MonitorEvent("usb", "removed", {"device": dev}))
            known_devices = current
            await asyncio.sleep(2)

    async def _watch_wifi(self, cfg: dict[str, Any]) -> None:
        known_networks: set[str] = set()
        while self._running:
            current = self._scan_wifi()
            for net in current - known_networks:
                await self._events.put(MonitorEvent("wifi", "new", {"network": net}))
            known_networks = current
            await asyncio.sleep(5)

    async def _watch_drivers(self, cfg: dict[str, Any]) -> None:
        known_modules: set[str] = set()
        while self._running:
            current = self._list_loaded_modules()
            for mod in current - known_modules:
                await self._events.put(MonitorEvent("drivers", "new", {"module": mod}))
            known_modules = current
            await asyncio.sleep(10)

    async def _watch_network_interfaces(self) -> None:
        known_ifaces: set[str] = set()
        while self._running:
            current = self._list_network_interfaces()
            for iface in current - known_ifaces:
                await self._events.put(MonitorEvent("network_interfaces", "new", {"iface": iface}))
            known_ifaces = current
            await asyncio.sleep(5)

    # ── platform helpers ──────────────────────────────────

    @staticmethod
    def _scan_open_ports() -> set[str]:
        """Return set of open TCP ports on localhost via /proc/net/tcp."""
        ports: set[str] = set()
        proc_tcp = Path("/proc/net/tcp")
        if proc_tcp.exists():
            for line in proc_tcp.read_text().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    local = parts[1]
                    port_hex = local.split(":")[1]
                    ports.add(str(int(port_hex, 16)))
        return ports

    @staticmethod
    def _check_localhost_services() -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        try:
            result = subprocess.run(  # noqa: S603
                ["ss", "-tlnp"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines()[1:]:
                if "127.0.0.1" in line or "0.0.0.0" in line:
                    alerts.append({"raw": line.strip()})
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return alerts

    @staticmethod
    def _list_usb_devices() -> set[str]:
        devices: set[str] = set()
        usb_path = Path("/sys/bus/usb/devices")
        if usb_path.is_dir():
            for entry in usb_path.iterdir():
                product_file = entry / "product"
                if product_file.exists():
                    devices.add(product_file.read_text().strip())
        return devices

    @staticmethod
    def _list_loaded_modules() -> set[str]:
        modules: set[str] = set()
        proc_modules = Path("/proc/modules")
        if proc_modules.exists():
            for line in proc_modules.read_text().splitlines():
                parts = line.split()
                if parts:
                    modules.add(parts[0])
        return modules

    @staticmethod
    def _scan_wifi() -> set[str]:
        networks: set[str] = set()
        try:
            result = subprocess.run(  # noqa: S603
                ["iwlist", "scanning"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.splitlines():
                if "ESSID:" in line:
                    essid = line.split("ESSID:")[1].strip().strip('"')
                    if essid:
                        networks.add(essid)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return networks

    @staticmethod
    def _list_network_interfaces() -> set[str]:
        ifaces: set[str] = set()
        net_path = Path("/sys/class/net")
        if net_path.is_dir():
            for entry in net_path.iterdir():
                ifaces.add(entry.name)
        return ifaces
