"""
Tests for TWINBRAIN Algorithm.
"""
import pytest
from ai_engine.twinbrain import (
    BrainDecision,
    ConsensusStrategy,
    TwinBrainAlgorithm,
)


@pytest.fixture
def twinbrain():
    return TwinBrainAlgorithm(strategy=ConsensusStrategy.WEIGHTED)


def test_initialization(twinbrain):
    assert twinbrain.strategy == ConsensusStrategy.WEIGHTED
    assert twinbrain.agreement_threshold == 0.7


@pytest.mark.asyncio
async def test_evaluate_agreement(twinbrain):
    async def brain_a(ctx):
        return {"action": "scan", "confidence": 0.9, "reasoning": "test A"}

    async def brain_b(ctx):
        return {"action": "scan", "confidence": 0.85, "reasoning": "test B"}

    result = await twinbrain.evaluate({}, brain_a, brain_b)
    assert result.agreed is True
    assert result.final_action == "scan"
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_evaluate_disagreement(twinbrain):
    async def brain_a(ctx):
        return {"action": "attack", "confidence": 0.9, "reasoning": "A"}

    async def brain_b(ctx):
        return {"action": "defend", "confidence": 0.6, "reasoning": "B"}

    result = await twinbrain.evaluate({}, brain_a, brain_b)
    assert result.agreed is False
    assert result.final_action in ("attack", "defend")


@pytest.mark.asyncio
async def test_consensus_strategies():
    for strategy in ConsensusStrategy:
        tb = TwinBrainAlgorithm(strategy=strategy)

        async def brain_a(ctx):
            return {"action": "act", "confidence": 0.8, "reasoning": ""}

        async def brain_b(ctx):
            return {"action": "wait", "confidence": 0.6, "reasoning": ""}

        result = await tb.evaluate({}, brain_a, brain_b)
        assert result.final_action in ("act", "wait")
        assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_sync_brain_function(twinbrain):
    def sync_brain_a(ctx):
        return {"action": "noop", "confidence": 0.5, "reasoning": "sync"}

    async def async_brain_b(ctx):
        return {"action": "noop", "confidence": 0.7, "reasoning": "async"}

    result = await twinbrain.evaluate({}, sync_brain_a, async_brain_b)
    assert result.agreed is True


def test_get_divergence_rate_empty(twinbrain):
    rate = twinbrain.get_divergence_rate()
    assert rate == 0.0


@pytest.mark.asyncio
async def test_stats(twinbrain):
    async def ba(ctx):
        return {"action": "go", "confidence": 0.8, "reasoning": ""}

    async def bb(ctx):
        return {"action": "go", "confidence": 0.9, "reasoning": ""}

    await twinbrain.evaluate({}, ba, bb)
    stats = twinbrain.get_stats()
    assert stats["total_evaluations"] == 1
    assert 0 <= stats["agreement_rate"] <= 1


def test_compute_state_hash_empty():
    tb = TwinBrainAlgorithm()
    h = tb.compute_state_hash()
    assert len(h) == 64


@pytest.mark.asyncio
async def test_compute_state_hash_after_eval():
    tb = TwinBrainAlgorithm()

    async def ba(ctx):
        return {"action": "run", "confidence": 0.9, "reasoning": ""}

    async def bb(ctx):
        return {"action": "run", "confidence": 0.8, "reasoning": ""}

    await tb.evaluate({}, ba, bb)
    h = tb.compute_state_hash()
    assert len(h) == 64


def test_brain_decision_to_dict():
    bd = BrainDecision(
        branch_id="A",
        action="scan",
        confidence=0.9,
        reasoning="test",
    )
    d = bd.to_dict()
    assert d["branch_id"] == "A"
    assert d["action"] == "scan"
    assert d["confidence"] == 0.9
