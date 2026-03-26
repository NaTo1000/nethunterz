"""CHAiMERA Chain Engine — the core chained workflow execution engine.

Manages workflow chains that flow through the 3×3×3 stack overlay.
Chains can be sequential, parallel, conditional, looping, or fan‑out/fan‑in.
Supports hot‑swapping between parallel and series execution at runtime.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

from jessica.chimera.stack_overlay import StackCell, StackOverlay

logger = logging.getLogger("jessica.chimera.chain")


class ChainType(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    FAN_OUT_FAN_IN = "fan_out_fan_in"


class ChainStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ChainStep:
    """A single executable step inside a workflow chain."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    tool: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    target_cell: StackCell | None = None
    status: ChainStatus = ChainStatus.PENDING
    result: Any = None
    error: str | None = None


@dataclass
class WorkflowChain:
    """A complete workflow chain — an ordered collection of steps with an
    execution strategy."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    chain_type: ChainType = ChainType.SEQUENTIAL
    steps: list[ChainStep] = field(default_factory=list)
    status: ChainStatus = ChainStatus.PENDING
    condition: Callable[[Any], bool] | None = None  # for CONDITIONAL chains
    max_iterations: int = 10  # for LOOP chains


class ChimeraChainEngine:
    """Executes workflow chains through the 3×3×3 stack overlay.

    Supports parallel/series switching, hot‑swap, and dynamic chain creation
    driven by ConductorX or by autonomous AI decisions.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._cfg = config
        overlay_cfg = config.get("stack_overlay", {})
        self._overlay = StackOverlay(
            depth=overlay_cfg.get("depth", 3),
            width=overlay_cfg.get("width", 3),
            height=overlay_cfg.get("height", 3),
        )
        workflow_cfg = config.get("workflow", {})
        self._max_concurrent = workflow_cfg.get("max_concurrent_chains", 27)
        self._parallel_series_switching = workflow_cfg.get("parallel_series_switching", True)
        self._hot_swap = workflow_cfg.get("hot_swap_enabled", True)
        self._running = False
        self._chains: dict[str, WorkflowChain] = {}
        self._semaphore: asyncio.Semaphore | None = None
        # Pluggable step executor (provided by ConductorX or tool adapter)
        self._step_executor: Callable[[ChainStep], Awaitable[Any]] | None = None

    # ── lifecycle ─────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        logger.info(
            "CHAiMERA chain engine started — stack=%dx%dx%d  max_concurrent=%d",
            self._overlay.depth,
            self._overlay.width,
            self._overlay.height,
            self._max_concurrent,
        )

    async def stop(self) -> None:
        self._running = False
        logger.info("CHAiMERA chain engine stopped.")

    def set_step_executor(self, executor: Callable[[ChainStep], Awaitable[Any]]) -> None:
        """Inject the function that actually runs a step (tool invocation)."""
        self._step_executor = executor

    # ── chain management ──────────────────────────────────

    def create_chain(
        self,
        name: str,
        chain_type: ChainType = ChainType.SEQUENTIAL,
        steps: list[ChainStep] | None = None,
    ) -> WorkflowChain:
        chain = WorkflowChain(name=name, chain_type=chain_type, steps=steps or [])
        self._chains[chain.id] = chain
        logger.info("Created chain %s (%s) with %d steps", chain.id, chain_type.value, len(chain.steps))
        return chain

    def get_chain(self, chain_id: str) -> WorkflowChain | None:
        return self._chains.get(chain_id)

    def list_chains(self) -> list[WorkflowChain]:
        return list(self._chains.values())

    # ── execution ─────────────────────────────────────────

    async def execute_chain(self, chain_id: str) -> WorkflowChain:
        """Execute a chain using its configured strategy."""
        chain = self._chains.get(chain_id)
        if chain is None:
            raise KeyError(f"Chain {chain_id} not found")
        if self._semaphore is None:
            raise RuntimeError("Engine not started")

        async with self._semaphore:
            chain.status = ChainStatus.RUNNING
            try:
                if chain.chain_type == ChainType.SEQUENTIAL:
                    await self._run_sequential(chain)
                elif chain.chain_type == ChainType.PARALLEL:
                    await self._run_parallel(chain)
                elif chain.chain_type == ChainType.CONDITIONAL:
                    await self._run_conditional(chain)
                elif chain.chain_type == ChainType.LOOP:
                    await self._run_loop(chain)
                elif chain.chain_type == ChainType.FAN_OUT_FAN_IN:
                    await self._run_fan_out_fan_in(chain)
                chain.status = ChainStatus.COMPLETED
            except Exception as exc:
                chain.status = ChainStatus.FAILED
                logger.exception("Chain %s failed: %s", chain_id, exc)
            return chain

    async def swap_execution_mode(self, chain_id: str, new_type: ChainType) -> None:
        """Hot‑swap a chain's execution mode (parallel ↔ series)."""
        if not self._hot_swap:
            raise RuntimeError("Hot-swap is disabled in configuration")
        chain = self._chains.get(chain_id)
        if chain is None:
            raise KeyError(f"Chain {chain_id} not found")
        old_type = chain.chain_type
        chain.chain_type = new_type
        logger.info("Hot-swapped chain %s: %s → %s", chain_id, old_type.value, new_type.value)

    # ── overlay access ────────────────────────────────────

    @property
    def overlay(self) -> StackOverlay:
        return self._overlay

    # ── private executors ─────────────────────────────────

    async def _exec_step(self, step: ChainStep) -> Any:
        step.status = ChainStatus.RUNNING
        try:
            if self._step_executor:
                step.result = await self._step_executor(step)
            else:
                logger.warning("No step executor set — step %s skipped", step.id)
                step.result = None
            step.status = ChainStatus.COMPLETED
        except Exception as exc:
            step.status = ChainStatus.FAILED
            step.error = str(exc)
            raise
        return step.result

    async def _run_sequential(self, chain: WorkflowChain) -> None:
        for step in chain.steps:
            await self._exec_step(step)

    async def _run_parallel(self, chain: WorkflowChain) -> None:
        await asyncio.gather(*(self._exec_step(s) for s in chain.steps))

    async def _run_conditional(self, chain: WorkflowChain) -> None:
        if len(chain.steps) < 2:
            raise ValueError("Conditional chain requires at least 2 steps")
        condition_step = chain.steps[0]
        result = await self._exec_step(condition_step)
        if chain.condition and chain.condition(result):
            await self._exec_step(chain.steps[1])
        elif len(chain.steps) > 2:
            await self._exec_step(chain.steps[2])

    async def _run_loop(self, chain: WorkflowChain) -> None:
        for iteration in range(chain.max_iterations):
            for step in chain.steps:
                result = await self._exec_step(step)
                if chain.condition and not chain.condition(result):
                    logger.info("Loop chain %s exiting at iteration %d", chain.id, iteration)
                    return

    async def _run_fan_out_fan_in(self, chain: WorkflowChain) -> None:
        """First step produces input, middle steps run in parallel, last step merges."""
        if len(chain.steps) < 3:
            raise ValueError("Fan-out/fan-in requires at least 3 steps")
        # Fan-out
        await self._exec_step(chain.steps[0])
        # Parallel middle
        middle = chain.steps[1:-1]
        await asyncio.gather(*(self._exec_step(s) for s in middle))
        # Fan-in
        await self._exec_step(chain.steps[-1])
