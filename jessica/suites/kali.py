"""Kali Suite — adapters for every tool category in the Kali Linux arsenal.

Each adapter wraps a tool binary, validates its availability, and exposes
a uniform async ``run(target, **kwargs)`` interface consumed by the
OrchestratorWorker.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jessica.suites.kali")


@dataclass
class ToolDescriptor:
    """Metadata for a single security tool."""

    name: str
    binary: str
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    default_args: list[str] = field(default_factory=list)
    available: bool = False


class KaliSuite:
    """Manages and invokes tools from the Kali Linux suite.

    On initialisation it probes the system to determine which tools are
    actually installed, so workflows can adapt at runtime.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._cfg = config
        self._tools: dict[str, ToolDescriptor] = {}
        self._load_tools()

    def _load_tools(self) -> None:
        for category, tools in self._cfg.items():
            if not isinstance(tools, list):
                continue
            for entry in tools:
                td = ToolDescriptor(
                    name=entry["name"],
                    binary=entry["binary"],
                    description=entry.get("description", ""),
                    capabilities=entry.get("capabilities", []),
                    default_args=entry.get("default_args", []),
                    available=shutil.which(entry["binary"]) is not None,
                )
                self._tools[td.name] = td
        available = sum(1 for t in self._tools.values() if t.available)
        logger.info("KaliSuite loaded: %d tools (%d available on this system)", len(self._tools), available)

    # ── queries ───────────────────────────────────────────

    def list_tools(self) -> list[ToolDescriptor]:
        return list(self._tools.values())

    def available_tools(self) -> list[ToolDescriptor]:
        return [t for t in self._tools.values() if t.available]

    def get_tool(self, name: str) -> ToolDescriptor | None:
        return self._tools.get(name)

    def has_capability(self, capability: str) -> list[ToolDescriptor]:
        return [t for t in self._tools.values() if capability in t.capabilities and t.available]

    # ── execution ─────────────────────────────────────────

    async def run(self, tool_name: str, target: str, extra_args: list[str] | None = None) -> str:
        """Run a Kali tool against a target and return its stdout."""
        td = self._tools.get(tool_name)
        if td is None:
            raise KeyError(f"Unknown Kali tool: {tool_name}")
        if not td.available:
            raise RuntimeError(f"Tool {tool_name} ({td.binary}) is not installed")

        cmd = [td.binary, *td.default_args]
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(target)

        logger.info("Running %s: %s", tool_name, " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode(errors="replace")
        if proc.returncode != 0:
            err = stderr.decode(errors="replace")
            logger.warning("%s exited %d: %s", tool_name, proc.returncode, err[:200])
        return output
