"""Port Control — full control over localhost ports, firewall rules,
and traffic redirection for the JESSICA platform.

Provides programmatic iptables / nftables management and port forwarding.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger("jessica.core.port_control")


@dataclass
class PortRule:
    """Describes a single port rule (allow, deny, redirect)."""

    action: str  # "allow" | "deny" | "redirect"
    protocol: str  # "tcp" | "udp"
    port: int
    destination: str | None = None  # for redirect
    redirect_port: int | None = None


class PortController:
    """Manages firewall rules and port-level traffic control.

    Wraps iptables/nftables so the CHAiMERA workflow and ConductorX can
    dynamically open, close, and redirect ports at runtime.
    """

    def __init__(self) -> None:
        self._backend = self._detect_backend()
        self._rules: list[PortRule] = []

    # ── public API ────────────────────────────────────────

    def allow_port(self, port: int, protocol: str = "tcp") -> None:
        rule = PortRule(action="allow", protocol=protocol, port=port)
        self._apply(rule)
        self._rules.append(rule)
        logger.info("Allowed %s/%d", protocol, port)

    def deny_port(self, port: int, protocol: str = "tcp") -> None:
        rule = PortRule(action="deny", protocol=protocol, port=port)
        self._apply(rule)
        self._rules.append(rule)
        logger.info("Denied %s/%d", protocol, port)

    def redirect_port(self, src_port: int, dst_port: int, protocol: str = "tcp") -> None:
        rule = PortRule(
            action="redirect",
            protocol=protocol,
            port=src_port,
            destination="127.0.0.1",
            redirect_port=dst_port,
        )
        self._apply(rule)
        self._rules.append(rule)
        logger.info("Redirected %s/%d → %d", protocol, src_port, dst_port)

    def flush_rules(self) -> None:
        """Remove all JESSICA-managed rules."""
        self._exec(["iptables", "-F", "JESSICA"])
        self._rules.clear()
        logger.info("Flushed all JESSICA port rules")

    def list_rules(self) -> list[PortRule]:
        return list(self._rules)

    def enable_ip_forwarding(self) -> None:
        self._exec(["sysctl", "-w", "net.ipv4.ip_forward=1"])
        logger.info("IP forwarding enabled")

    def setup_nat(self, interface: str) -> None:
        self._exec([
            "iptables", "-t", "nat", "-A", "POSTROUTING",
            "-o", interface, "-j", "MASQUERADE",
        ])
        logger.info("NAT masquerade enabled on %s", interface)

    # ── internals ─────────────────────────────────────────

    @staticmethod
    def _detect_backend() -> str:
        """Prefer nftables, fall back to iptables."""
        try:
            subprocess.run(["nft", "--version"], capture_output=True, check=True, timeout=3)  # noqa: S603, S607
            return "nftables"
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return "iptables"

    def _apply(self, rule: PortRule) -> None:
        if rule.action == "allow":
            self._exec([
                "iptables", "-A", "INPUT", "-p", rule.protocol,
                "--dport", str(rule.port), "-j", "ACCEPT",
            ])
        elif rule.action == "deny":
            self._exec([
                "iptables", "-A", "INPUT", "-p", rule.protocol,
                "--dport", str(rule.port), "-j", "DROP",
            ])
        elif rule.action == "redirect" and rule.redirect_port is not None:
            self._exec([
                "iptables", "-t", "nat", "-A", "PREROUTING",
                "-p", rule.protocol, "--dport", str(rule.port),
                "-j", "REDIRECT", "--to-port", str(rule.redirect_port),
            ])

    @staticmethod
    def _exec(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        logger.debug("exec: %s", " ".join(cmd))
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10)  # noqa: S603
