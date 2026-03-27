"""
Tests for CHAiMERA Orchestrator.
"""
import pytest
from ai_engine.chaimera import (
    ChaimeraOrchestrator,
    ChainSpeed,
    LayerMode,
)


@pytest.fixture
def orchestrator():
    return ChaimeraOrchestrator(default_speed=ChainSpeed.BALANCED)


def _make_handler(name: str, confidence: float = 0.9):
    async def handler(data, ctx):
        return {"layer": name, "processed": True, "confidence": confidence}
    return handler


def test_initialization(orchestrator):
    assert orchestrator.default_speed == ChainSpeed.BALANCED
    assert orchestrator.max_chain_depth == 20


def test_add_layer_chaining(orchestrator):
    result = orchestrator.add_layer("test", _make_handler("test"))
    assert result is orchestrator  # Should return self for chaining


def test_add_multiple_layers(orchestrator):
    orchestrator.add_layer("layer1", _make_handler("layer1"))
    orchestrator.add_layer("layer2", _make_handler("layer2"))
    assert len(orchestrator._layers) == 2


@pytest.mark.asyncio
async def test_execute_balanced(orchestrator):
    orchestrator.add_layer(
        "analysis", _make_handler("analysis"),
        mode=LayerMode.ANALYSIS
    )
    orchestrator.add_layer(
        "decision", _make_handler("decision"),
        mode=LayerMode.DECISION
    )
    result = await orchestrator.execute({"data": "test"})
    assert result.success is True
    assert result.successful_layers >= 0
    assert result.total_elapsed_ms > 0


@pytest.mark.asyncio
async def test_execute_rapid(orchestrator):
    orchestrator.add_layer("r1", _make_handler("r1"))
    orchestrator.add_layer("r2", _make_handler("r2"))
    result = await orchestrator.execute(
        {"test": 1}, speed=ChainSpeed.RAPID
    )
    assert result.success is True
    assert result.speed == ChainSpeed.RAPID


@pytest.mark.asyncio
async def test_execute_deep(orchestrator):
    orchestrator.add_layer("d1", _make_handler("d1"))
    orchestrator.add_layer("d2", _make_handler("d2"))
    result = await orchestrator.execute(
        {"test": 1}, speed=ChainSpeed.DEEP
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_failing_layer():
    orch = ChaimeraOrchestrator()

    async def failing_handler(data, ctx):
        raise ValueError("Layer failed")

    orch.add_layer("fail", failing_handler, required=True)
    result = await orch.execute({"test": 1})
    # Should still complete, but layer failed
    assert result.layer_results[0].success is False
    assert result.layer_results[0].error is not None


@pytest.mark.asyncio
async def test_sync_handler():
    orch = ChaimeraOrchestrator()

    def sync_handler(data, ctx):
        return {"sync": True, "confidence": 0.8}

    orch.add_layer("sync", sync_handler)
    result = await orch.execute({})
    assert result.layer_results[0].success is True


def test_get_stats_empty(orchestrator):
    stats = orchestrator.get_stats()
    assert stats["total_executions"] == 0
    assert stats["layers_registered"] == 0


@pytest.mark.asyncio
async def test_get_stats_after_execution(orchestrator):
    orchestrator.add_layer("s1", _make_handler("s1"))
    await orchestrator.execute({})
    stats = orchestrator.get_stats()
    assert stats["total_executions"] == 1
    assert stats["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_average_confidence():
    orch = ChaimeraOrchestrator()
    orch.add_layer("l1", _make_handler("l1", confidence=0.8))
    orch.add_layer("l2", _make_handler("l2", confidence=0.6))
    result = await orch.execute({}, speed=ChainSpeed.DEEP)
    assert 0.0 <= result.average_confidence <= 1.0
