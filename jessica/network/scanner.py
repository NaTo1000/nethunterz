"""Network Scanner — lightweight async wrapper around nmap and masscan."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("jessica.network.scanner")


@dataclass
class ScanResult:
    target: str
    open_ports: list[int] = field(default_factory=list)
    services: dict[int, str] = field(default_factory=dict)
    os_guess: str = ""
    raw_output: str = ""


class NetworkScanner:
    """Async network scanner using nmap and masscan."""

    async def quick_scan(self, target: str, ports: str = "1-1024") -> ScanResult:
        """Fast SYN scan of the most common ports."""
        return await self._nmap(target, ["-sS", "-T4", "-p", ports, "--open"])

    async def full_scan(self, target: str) -> ScanResult:
        """Full port scan with service and OS detection."""
        return await self._nmap(target, ["-sV", "-sC", "-O", "-p-", "-T4"])

    async def udp_scan(self, target: str, ports: str = "1-1024") -> ScanResult:
        return await self._nmap(target, ["-sU", "-T4", "-p", ports])

    async def mass_scan(self, targets: str, ports: str = "0-65535", rate: int = 10000) -> str:
        """Ultra‑fast mass scan using masscan."""
        cmd = ["masscan", targets, "-p", ports, "--rate", str(rate), "-oG", "-"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode(errors="replace")

    # ── private ───────────────────────────────────────────

    async def _nmap(self, target: str, flags: list[str]) -> ScanResult:
        cmd = ["nmap", *flags, target]
        logger.info("Scanning: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode(errors="replace")
        return self._parse_nmap(target, output)

    @staticmethod
    def _parse_nmap(target: str, output: str) -> ScanResult:
        result = ScanResult(target=target, raw_output=output)
        for line in output.splitlines():
            stripped = line.strip()
            if "/tcp" in stripped or "/udp" in stripped:
                parts = stripped.split()
                if len(parts) >= 3 and parts[1] == "open":
                    port = int(parts[0].split("/")[0])
                    result.open_ports.append(port)
                    result.services[port] = parts[2]
            if "OS details:" in stripped:
                result.os_guess = stripped.split("OS details:")[1].strip()
        return result
