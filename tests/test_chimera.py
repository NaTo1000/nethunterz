"""Tests for the CHAiMERA chain engine and 3×3×3 stack overlay."""

from __future__ import annotations

import pytest

from jessica.chimera.chain import (
    ChainStatus,
    ChainStep,
    ChainType,
    ChimeraChainEngine,
)
from jessica.chimera.stack_overlay import CellState, StackOverlay

# ── Stack Overlay ─────────────────────────────────────────


class TestStackOverlay:
    def test_dimensions(self) -> None:
        overlay = StackOverlay(depth=3, width=3, height=3)
        assert overlay.depth == 3
        assert overlay.width == 3
        assert overlay.height == 3
        assert overlay.total_cells == 27

    def test_custom_dimensions(self) -> None:
        overlay = StackOverlay(depth=2, width=4, height=5)
        assert overlay.total_cells == 40

    def test_get_cell(self) -> None:
        overlay = StackOverlay()
        cell = overlay.get_cell(0, 0, 0)
        assert cell.layer == 0
        assert cell.lane == 0
        assert cell.stage == 0
        assert cell.state == CellState.IDLE

    def test_reserve_and_release(self) -> None:
        overlay = StackOverlay()
        cell = overlay.reserve_cell(1, 2, 0, "nmap")
        assert cell.state == CellState.RESERVED
        assert cell.assigned_tool == "nmap"

        overlay.release_cell(1, 2, 0)
        cell = overlay.get_cell(1, 2, 0)
        assert cell.state == CellState.IDLE
        assert cell.assigned_tool is None

    def test_activate_and_complete(self) -> None:
        overlay = StackOverlay()
        overlay.reserve_cell(0, 0, 0, "nikto")
        overlay.activate_cell(0, 0, 0)
        assert overlay.get_cell(0, 0, 0).state == CellState.ACTIVE

        overlay.complete_cell(0, 0, 0, {"ports": [80, 443]})
        cell = overlay.get_cell(0, 0, 0)
        assert cell.state == CellState.COMPLETED
        assert cell.metadata["ports"] == [80, 443]

    def test_error_cell(self) -> None:
        overlay = StackOverlay()
        overlay.reserve_cell(2, 1, 1, "metasploit")
        overlay.error_cell(2, 1, 1, "timeout")
        cell = overlay.get_cell(2, 1, 1)
        assert cell.state == CellState.ERROR
        assert cell.metadata["error"] == "timeout"

    def test_utilisation(self) -> None:
        overlay = StackOverlay(depth=1, width=1, height=2)
        assert overlay.utilisation() == 0.0
        overlay.reserve_cell(0, 0, 0, "nmap")
        assert overlay.utilisation() == 0.5
        overlay.activate_cell(0, 0, 0)
        assert overlay.utilisation() == 0.5  # still busy
        overlay.reserve_cell(0, 0, 1, "nikto")
        assert overlay.utilisation() == 1.0

    def test_idle_cells(self) -> None:
        overlay = StackOverlay(depth=1, width=1, height=3)
        assert len(overlay.idle_cells()) == 3
        overlay.reserve_cell(0, 0, 1, "nmap")
        assert len(overlay.idle_cells()) == 2

    def test_double_reserve_raises(self) -> None:
        overlay = StackOverlay()
        overlay.reserve_cell(0, 0, 0, "nmap")
        with pytest.raises(RuntimeError):
            overlay.reserve_cell(0, 0, 0, "nikto")

    def test_get_layer(self) -> None:
        overlay = StackOverlay()
        layer = overlay.get_layer(0)
        assert len(layer) == 3  # 3 lanes
        assert len(layer[0]) == 3  # 3 stages per lane

    def test_find_idle_in_layer(self) -> None:
        overlay = StackOverlay()
        idle = overlay.find_idle_in_layer(0)
        assert len(idle) == 9  # 3×3


# ── Chain Engine ──────────────────────────────────────────


class TestChimeraChainEngine:
    @pytest.fixture
    def engine(self) -> ChimeraChainEngine:
        return ChimeraChainEngine({
            "stack_overlay": {"depth": 3, "width": 3, "height": 3},
            "workflow": {"max_concurrent_chains": 5, "parallel_series_switching": True, "hot_swap_enabled": True},
        })

    @pytest.mark.asyncio
    async def test_start_stop(self, engine: ChimeraChainEngine) -> None:
        await engine.start()
        await engine.stop()

    @pytest.mark.asyncio
    async def test_create_chain(self, engine: ChimeraChainEngine) -> None:
        await engine.start()
        chain = engine.create_chain("test_chain", ChainType.SEQUENTIAL, [
            ChainStep(name="step1", tool="nmap"),
            ChainStep(name="step2", tool="nikto"),
        ])
        assert chain.name == "test_chain"
        assert len(chain.steps) == 2
        assert chain.status == ChainStatus.PENDING
        await engine.stop()

    @pytest.mark.asyncio
    async def test_execute_sequential(self, engine: ChimeraChainEngine) -> None:
        results: list[str] = []

        async def executor(step: ChainStep) -> str:
            results.append(step.name)
            return f"done:{step.name}"

        await engine.start()
        engine.set_step_executor(executor)
        chain = engine.create_chain("seq", ChainType.SEQUENTIAL, [
            ChainStep(name="a"),
            ChainStep(name="b"),
            ChainStep(name="c"),
        ])
        result = await engine.execute_chain(chain.id)
        assert result.status == ChainStatus.COMPLETED
        assert results == ["a", "b", "c"]
        await engine.stop()

    @pytest.mark.asyncio
    async def test_execute_parallel(self, engine: ChimeraChainEngine) -> None:
        executed = set()

        async def executor(step: ChainStep) -> str:
            executed.add(step.name)
            return "ok"

        await engine.start()
        engine.set_step_executor(executor)
        chain = engine.create_chain("par", ChainType.PARALLEL, [
            ChainStep(name="x"),
            ChainStep(name="y"),
            ChainStep(name="z"),
        ])
        result = await engine.execute_chain(chain.id)
        assert result.status == ChainStatus.COMPLETED
        assert executed == {"x", "y", "z"}
        await engine.stop()

    @pytest.mark.asyncio
    async def test_hot_swap(self, engine: ChimeraChainEngine) -> None:
        await engine.start()
        chain = engine.create_chain("swap_test", ChainType.SEQUENTIAL)
        assert chain.chain_type == ChainType.SEQUENTIAL
        await engine.swap_execution_mode(chain.id, ChainType.PARALLEL)
        assert chain.chain_type == ChainType.PARALLEL
        await engine.stop()

    @pytest.mark.asyncio
    async def test_fan_out_fan_in(self, engine: ChimeraChainEngine) -> None:
        order: list[str] = []

        async def executor(step: ChainStep) -> str:
            order.append(step.name)
            return "ok"

        await engine.start()
        engine.set_step_executor(executor)
        chain = engine.create_chain("fofi", ChainType.FAN_OUT_FAN_IN, [
            ChainStep(name="fan_out"),
            ChainStep(name="worker_a"),
            ChainStep(name="worker_b"),
            ChainStep(name="fan_in"),
        ])
        result = await engine.execute_chain(chain.id)
        assert result.status == ChainStatus.COMPLETED
        assert order[0] == "fan_out"
        assert order[-1] == "fan_in"
        assert set(order[1:-1]) == {"worker_a", "worker_b"}
        await engine.stop()

    def test_overlay_accessible(self, engine: ChimeraChainEngine) -> None:
        assert engine.overlay.total_cells == 27
