"""Orchestrator Worker — a scalable worker process that receives tasks from
ConductorX, executes them via the appropriate security tool, and reports
results back.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jessica.conductor.orchestrator")


@dataclass
class WorkerIdentity:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    capabilities: list[str] = field(default_factory=list)


class OrchestratorWorker:
    """A single worker that polls ConductorX and executes dispatched tasks.

    In container mode each worker runs as a separate process/pod; in autonomous
    mode they run as async tasks inside the same process.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._cfg = config
        self._identity = WorkerIdentity()
        self._running = False
        self._current_task: dict[str, Any] | None = None

    @property
    def worker_id(self) -> str:
        return self._identity.id

    # ── lifecycle ─────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        logger.info("OrchestratorWorker %s started", self.worker_id)

    async def stop(self) -> None:
        self._running = False
        logger.info("OrchestratorWorker %s stopped", self.worker_id)

    # ── task execution ────────────────────────────────────

    async def execute(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """Run a security tool with the given arguments and return structured results."""
        self._current_task = {"tool": tool, "args": args}
        logger.info("Worker %s executing tool=%s", self.worker_id, tool)

        try:
            result = await self._invoke_tool(tool, args)
            return {"status": "completed", "tool": tool, "output": result}
        except Exception as exc:
            logger.exception("Worker %s tool %s failed: %s", self.worker_id, tool, exc)
            return {"status": "failed", "tool": tool, "error": str(exc)}
        finally:
            self._current_task = None

    async def _invoke_tool(self, tool: str, args: dict[str, Any]) -> str:
        """Invoke a tool binary as a subprocess."""
        cmd = self._build_command(tool, args)
        logger.debug("Worker %s running: %s", self.worker_id, " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode(errors="replace")
        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace")
            raise RuntimeError(f"{tool} exited with code {proc.returncode}: {err_msg}")
        return output

    @staticmethod
    def _build_command(tool: str, args: dict[str, Any]) -> list[str]:
        """Translate a tool name + args dict into a CLI command list."""
        cmd = [tool]
        target = args.pop("target", None)
        flags = args.pop("flags", None)
        if flags:
            cmd.extend(flags.split())
        for key, value in args.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])
        if target:
            cmd.append(target)
        return cmd
