"""Tests for Grok 420x1000 Orchestration Engine."""

import asyncio
import pytest

from grok420.config import DecisionMode, OrchestrationConfig
from grok420.orchestration.cluster_manager import ClusterManager, ClusterNode, NodeStatus
from grok420.orchestration.decision_engine import DecisionContext, DecisionEngine, DecisionStatus
from grok420.orchestration.engine import Grok420Engine


# ---------------------------------------------------------------------------
# ClusterManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cluster_manager_auto_discovery():
    config = OrchestrationConfig(cluster_count=3, auto_discovery=True)
    mgr = ClusterManager(config)
    await mgr.start()
    assert mgr.node_count == 3
    await mgr.stop()


@pytest.mark.asyncio
async def test_cluster_manager_add_remove_node():
    config = OrchestrationConfig(auto_discovery=False)
    mgr = ClusterManager(config)
    await mgr.start()

    node = ClusterNode(address="test-host", port=9000)
    await mgr.add_node(node)
    assert mgr.node_count == 1

    await mgr.remove_node(node.node_id)
    assert mgr.node_count == 0
    await mgr.stop()


@pytest.mark.asyncio
async def test_cluster_manager_pick_node_round_robin():
    config = OrchestrationConfig(cluster_count=2, auto_discovery=True)
    mgr = ClusterManager(config)
    await mgr.start()

    n1 = await mgr.pick_node()
    n2 = await mgr.pick_node()
    n3 = await mgr.pick_node()
    assert n1 is not None
    assert n3 is not None
    await mgr.stop()


@pytest.mark.asyncio
async def test_cluster_manager_no_healthy_nodes():
    config = OrchestrationConfig(auto_discovery=False)
    mgr = ClusterManager(config)
    await mgr.start()
    assert await mgr.pick_node() is None
    await mgr.stop()


@pytest.mark.asyncio
async def test_cluster_manager_least_loaded():
    config = OrchestrationConfig(cluster_count=2, auto_discovery=True)
    mgr = ClusterManager(config)
    await mgr.start()

    healthy = await mgr.get_healthy_nodes()
    healthy[0].task_count = 10

    node = await mgr.pick_node(strategy="least_loaded")
    assert node is not None
    assert node.task_count == 0
    await mgr.stop()


# ---------------------------------------------------------------------------
# DecisionEngine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decision_engine_precision():
    engine = DecisionEngine(mode=DecisionMode.PRECISION)
    ctx = DecisionContext(payload={"x": 1}, mode=DecisionMode.PRECISION)
    result = await engine.decide(ctx)
    assert result.status == DecisionStatus.COMPLETED
    assert result.pipeline == "precision"
    assert result.confidence >= 0.0


@pytest.mark.asyncio
async def test_decision_engine_fusion():
    engine = DecisionEngine(mode=DecisionMode.FUSION)
    ctx = DecisionContext(payload={"x": 1, "y": 2}, mode=DecisionMode.FUSION)
    result = await engine.decide(ctx)
    assert result.status == DecisionStatus.COMPLETED
    assert result.pipeline == "fusion"
    assert "fused_score" in result.output


@pytest.mark.asyncio
async def test_decision_engine_adaptive_small_payload():
    engine = DecisionEngine(mode=DecisionMode.ADAPTIVE)
    ctx = DecisionContext(payload={"x": 1}, mode=DecisionMode.ADAPTIVE)
    result = await engine.decide(ctx)
    assert result.status == DecisionStatus.COMPLETED
    assert result.pipeline == "precision"


@pytest.mark.asyncio
async def test_decision_engine_adaptive_large_payload():
    engine = DecisionEngine(mode=DecisionMode.ADAPTIVE)
    payload = {str(i): i for i in range(15)}
    ctx = DecisionContext(payload=payload, mode=DecisionMode.ADAPTIVE)
    result = await engine.decide(ctx)
    assert result.status == DecisionStatus.COMPLETED
    assert result.pipeline == "fusion"


@pytest.mark.asyncio
async def test_decision_engine_history():
    engine = DecisionEngine()
    ctx = DecisionContext(payload={})
    await engine.decide(ctx)
    assert len(engine.decision_history) == 1


# ---------------------------------------------------------------------------
# Grok420Engine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_start_stop():
    engine = Grok420Engine()
    await engine.start()
    assert engine._running
    await engine.stop()
    assert not engine._running


@pytest.mark.asyncio
async def test_engine_run_parallel():
    async with Grok420Engine() as engine:
        async def make_coro(i):
            async def coro():
                return i
            return coro

        tasks = [await make_coro(i) for i in range(5)]
        results = await engine.run_parallel(tasks)
        assert sorted(results) == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_engine_run_parallel_error_resilient():
    """Failed tasks are returned as exceptions, not propagated."""

    async def good():
        return "ok"

    async def bad():
        raise RuntimeError("nope")

    async with Grok420Engine() as engine:
        results = await engine.run_parallel([good, bad, good])
        assert results[0] == "ok"
        assert isinstance(results[1], RuntimeError)
        assert results[2] == "ok"


@pytest.mark.asyncio
async def test_engine_run_serial():
    async def step1(_: None) -> int:
        return 1

    async def step2(x: int) -> int:
        return x + 1

    async def step3(x: int) -> int:
        return x * 3

    async with Grok420Engine() as engine:
        result = await engine.run_serial([step1, step2, step3])
        assert result == 6  # (0+1+1)*3


@pytest.mark.asyncio
async def test_engine_make_decision():
    async with Grok420Engine() as engine:
        result = await engine.make_decision({"query": "test"})
        assert result.status == DecisionStatus.COMPLETED


@pytest.mark.asyncio
async def test_engine_context_manager():
    engine = Grok420Engine()
    async with engine:
        assert engine._running
    assert not engine._running
