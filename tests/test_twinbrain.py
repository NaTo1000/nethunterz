"""Tests for TWINBRAIN Algorithm."""

import asyncio
import pytest

from grok420.config import TwinBrainConfig
from grok420.twinbrain.algorithm import BrainInstance, BrainOutput, ConsensusResult, TwinBrain
from grok420.twinbrain.synchronizer import BrainSynchronizer, SyncPacket


# ---------------------------------------------------------------------------
# BrainSynchronizer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synchronizer_send_receive():
    sync_a = BrainSynchronizer(sync_interval_ms=50)
    sync_b = BrainSynchronizer(sync_interval_ms=50)
    sync_a.connect_to(sync_b)

    await sync_a.start()
    await sync_b.start()

    pkt = await sync_a.send("brain_a", {"key": "value"})
    assert pkt.brain_id == "brain_a"
    assert pkt.state_hash  # non-empty hash

    # Wait for sync loop to forward packet to b
    await asyncio.sleep(0.15)
    received = await sync_b.receive(timeout_s=0.2)
    assert received is not None
    assert received.payload == {"key": "value"}

    await sync_a.stop()
    await sync_b.stop()


@pytest.mark.asyncio
async def test_synchronizer_receive_timeout():
    sync = BrainSynchronizer()
    await sync.start()
    result = await sync.receive(timeout_s=0.05)
    assert result is None
    await sync.stop()


def test_sync_packet_roundtrip():
    pkt = SyncPacket(brain_id="x", sequence=1, state_hash="abc", payload={"k": "v"})
    raw = pkt.to_bytes()
    restored = SyncPacket.from_bytes(raw)
    assert restored.brain_id == pkt.brain_id
    assert restored.payload == pkt.payload


# ---------------------------------------------------------------------------
# BrainInstance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brain_instance_evaluate():
    async def simple_eval(data):
        return {"result": data, "confidence": 0.9}

    brain = BrainInstance("test_brain", simple_eval)
    await brain.start()
    output = await brain.evaluate("hello")
    assert output.brain_id == "test_brain"
    assert output.confidence == 0.9
    assert output.result["result"] == "hello"
    await brain.stop()


@pytest.mark.asyncio
async def test_brain_instance_fallback_confidence():
    async def plain_eval(data):
        return "plain_result"

    brain = BrainInstance("plain", plain_eval)
    await brain.start()
    output = await brain.evaluate("x")
    assert output.confidence == 1.0
    await brain.stop()


# ---------------------------------------------------------------------------
# TwinBrain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_twinbrain_consensus_agree():
    async def eval_fn(data):
        return {"value": data, "confidence": 0.85}

    async with TwinBrain(eval_fn) as tb:
        result = await tb.evaluate("test_input")
    assert isinstance(result, ConsensusResult)
    assert result.agreed
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_twinbrain_consensus_low_confidence():
    """With threshold=0.95 and confidence=0.6, brains should not agree."""

    async def low_conf_eval(data):
        return {"confidence": 0.6}

    config = TwinBrainConfig(consensus_threshold=0.95, max_divergence_retries=1)
    async with TwinBrain(low_conf_eval, config=config) as tb:
        result = await tb.evaluate("x")
    assert not result.agreed


@pytest.mark.asyncio
async def test_twinbrain_two_different_fns():
    async def eval_a(data):
        return {"confidence": 0.9, "source": "a"}

    async def eval_b(data):
        return {"confidence": 0.8, "source": "b"}

    config = TwinBrainConfig(consensus_threshold=0.7)
    async with TwinBrain(eval_a, eval_b, config=config) as tb:
        result = await tb.evaluate("data")
    assert result.brain_a.brain_id == "brain_a"
    assert result.brain_b.brain_id == "brain_b"


@pytest.mark.asyncio
async def test_twinbrain_not_started_raises():
    async def f(x):
        return x

    tb = TwinBrain(f)
    with pytest.raises(RuntimeError, match="start"):
        await tb.evaluate("x")


def test_twinbrain_set_consensus_threshold():
    async def f(x):
        return x

    tb = TwinBrain(f)
    tb.set_consensus_threshold(0.75)
    assert tb._config.consensus_threshold == 0.75


def test_twinbrain_invalid_threshold():
    async def f(x):
        return x

    tb = TwinBrain(f)
    with pytest.raises(ValueError):
        tb.set_consensus_threshold(0.3)


def test_twinbrain_invalid_sync_interval():
    async def f(x):
        return x

    tb = TwinBrain(f)
    with pytest.raises(ValueError):
        tb.set_sync_interval(5)
