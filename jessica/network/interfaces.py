"""Network Interfaces — manages wired, wireless, and USB network interfaces.

Provides detection, monitor mode toggling, MAC spoofing, and driver tracking.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("jessica.network.interfaces")


@dataclass
class NetworkInterface:
    """Represents a single network interface on the system."""

    name: str
    type: str  # "wired" | "wireless" | "virtual" | "usb"
    mac: str = ""
    driver: str = ""
    state: str = "down"  # "up" | "down" | "monitor"
    ipv4: str = ""
    channel: int | None = None
    chipset: str = ""

    @property
    def is_wireless(self) -> bool:
        return self.type in ("wireless", "usb") or self.name.startswith("wlan")


class InterfaceManager:
    """Detect, configure, and control all network interfaces including USB
    WiFi adapters."""

    def __init__(self) -> None:
        self._interfaces: dict[str, NetworkInterface] = {}

    def scan(self) -> list[NetworkInterface]:
        """Detect all network interfaces on the system."""
        self._interfaces.clear()
        net_dir = Path("/sys/class/net")
        if not net_dir.is_dir():
            return []

        for entry in net_dir.iterdir():
            iface = self._probe_interface(entry.name)
            self._interfaces[iface.name] = iface

        logger.info("Detected %d network interfaces", len(self._interfaces))
        return list(self._interfaces.values())

    def get(self, name: str) -> NetworkInterface | None:
        return self._interfaces.get(name)

    def wireless_interfaces(self) -> list[NetworkInterface]:
        return [i for i in self._interfaces.values() if i.is_wireless]

    # ── operations ────────────────────────────────────────

    def set_monitor_mode(self, iface_name: str) -> None:
        """Enable monitor mode on a wireless interface."""
        self._exec(["ip", "link", "set", iface_name, "down"])
        self._exec(["iw", "dev", iface_name, "set", "type", "monitor"])
        self._exec(["ip", "link", "set", iface_name, "up"])
        iface = self._interfaces.get(iface_name)
        if iface:
            iface.state = "monitor"
        logger.info("Monitor mode enabled on %s", iface_name)

    def set_managed_mode(self, iface_name: str) -> None:
        """Return a wireless interface to managed mode."""
        self._exec(["ip", "link", "set", iface_name, "down"])
        self._exec(["iw", "dev", iface_name, "set", "type", "managed"])
        self._exec(["ip", "link", "set", iface_name, "up"])
        iface = self._interfaces.get(iface_name)
        if iface:
            iface.state = "up"
        logger.info("Managed mode restored on %s", iface_name)

    def change_mac(self, iface_name: str, new_mac: str | None = None) -> str:
        """Change the MAC address (random if *new_mac* is None)."""
        self._exec(["ip", "link", "set", iface_name, "down"])
        if new_mac:
            self._exec(["macchanger", "-m", new_mac, iface_name])
        else:
            self._exec(["macchanger", "-r", iface_name])
        self._exec(["ip", "link", "set", iface_name, "up"])
        # Re-read new MAC
        iface = self._probe_interface(iface_name)
        self._interfaces[iface_name] = iface
        logger.info("MAC changed on %s → %s", iface_name, iface.mac)
        return iface.mac

    def bring_up(self, iface_name: str) -> None:
        self._exec(["ip", "link", "set", iface_name, "up"])

    def bring_down(self, iface_name: str) -> None:
        self._exec(["ip", "link", "set", iface_name, "down"])

    # ── USB device detection ──────────────────────────────

    @staticmethod
    def list_usb_wifi_adapters() -> list[dict[str, str]]:
        """List USB WiFi adapters via lsusb."""
        adapters: list[dict[str, str]] = []
        try:
            result = subprocess.run(  # noqa: S603, S607
                ["lsusb"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                lower = line.lower()
                if any(kw in lower for kw in ["wireless", "wlan", "wifi", "802.11", "atheros", "realtek", "ralink"]):
                    adapters.append({"raw": line.strip()})
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return adapters

    # ── helpers ───────────────────────────────────────────

    @staticmethod
    def _probe_interface(name: str) -> NetworkInterface:
        iface = NetworkInterface(name=name, type="wired")
        sys_path = Path(f"/sys/class/net/{name}")

        # Determine type
        wireless_path = sys_path / "wireless"
        if wireless_path.exists():
            iface.type = "wireless"
        elif name.startswith(("usb", "wlan")):
            iface.type = "wireless"
        elif name in ("lo", "docker0") or name.startswith(("veth", "br-", "virbr")):
            iface.type = "virtual"

        # Read MAC
        addr_file = sys_path / "address"
        if addr_file.exists():
            iface.mac = addr_file.read_text().strip()

        # Read driver
        driver_link = sys_path / "device" / "driver"
        if driver_link.is_symlink():
            iface.driver = driver_link.resolve().name

        # Read state
        operstate = sys_path / "operstate"
        if operstate.exists():
            iface.state = operstate.read_text().strip()

        return iface

    @staticmethod
    def _exec(cmd: list[str]) -> None:
        try:
            subprocess.run(cmd, capture_output=True, timeout=10)  # noqa: S603
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
