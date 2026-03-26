"""BlackArch Suite — adapters for extended BlackArch repository tools.

Mirrors the same interface as :mod:`jessica.suites.kali` so both suites
can be used interchangeably inside CHAiMERA chains.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jessica.suites.blackarch")


@dataclass
class ToolDescriptor:
    name: str
    binary: str
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    available: bool = False


class BlackArchSuite:
    """Manages and invokes tools from the BlackArch extended suite."""

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
                    available=shutil.which(entry["binary"]) is not None,
                )
                self._tools[td.name] = td
        available = sum(1 for t in self._tools.values() if t.available)
        logger.info("BlackArchSuite loaded: %d tools (%d available)", len(self._tools), available)

    def list_tools(self) -> list[ToolDescriptor]:
        return list(self._tools.values())

    def available_tools(self) -> list[ToolDescriptor]:
        return [t for t in self._tools.values() if t.available]

    def get_tool(self, name: str) -> ToolDescriptor | None:
        return self._tools.get(name)

    def has_capability(self, capability: str) -> list[ToolDescriptor]:
        return [t for t in self._tools.values() if capability in t.capabilities and t.available]

    async def run(self, tool_name: str, target: str, extra_args: list[str] | None = None) -> str:
        td = self._tools.get(tool_name)
        if td is None:
            raise KeyError(f"Unknown BlackArch tool: {tool_name}")
        if not td.available:
            raise RuntimeError(f"Tool {tool_name} ({td.binary}) is not installed")

        cmd = [td.binary]
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
