"""Tests for CHAiMERA Three-Speed AI Chain System."""

import asyncio
import pytest

from grok420.chaimera.chain import CHAiMERAChain
from grok420.chaimera.speed_modes import SpeedController
from grok420.chaimera.superconductor import Superconductor
from grok420.config import CHAiMERAConfig, ChainMode, SpeedMode


# ---------------------------------------------------------------------------
# SpeedController
# ---------------------------------------------------------------------------


def test_speed_controller_default():
    ctrl = SpeedController()
    assert ctrl.current_mode == SpeedMode.BALANCED


def test_speed_controller_set_mode():
    ctrl = SpeedController()
    ctrl.set_mode(SpeedMode.LOW_LATENCY)
    assert ctrl.current_mode == SpeedMode.LOW_LATENCY
    assert ctrl.profile.max_latency_ms == 50.0


def test_speed_controller_high_fidelity():
    ctrl = SpeedController(SpeedMode.HIGH_FIDELITY)
    assert ctrl.profile.max_layers == 8
    assert ctrl.profile.min_confidence >= 0.95


def test_speed_controller_latency_check():
    ctrl = SpeedController(SpeedMode.LOW_LATENCY)
    assert ctrl.is_within_latency(49.0)
    assert not ctrl.is_within_latency(100.0)


def test_speed_controller_confidence_check():
    ctrl = SpeedController(SpeedMode.HIGH_FIDELITY)
    assert ctrl.is_sufficient_confidence(0.96)
    assert not ctrl.is_sufficient_confidence(0.5)


# ---------------------------------------------------------------------------
# Superconductor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_superconductor_basic():
    config = CHAiMERAConfig(superconductor_threads=2)
    sc = Superconductor(config)
    await sc.start()

    async def work():
        return 99

    result = await sc.execute(work)
    assert result == 99
    assert sc.metrics.tasks_completed == 1
    await sc.stop()


@pytest.mark.asyncio
async def test_superconductor_concurrency():
    config = CHAiMERAConfig(superconductor_threads=3)
    sc = Superconductor(config)
    await sc.start()

    async def make_coro(i):
        async def coro():
            return i
        return coro

    tasks = [await make_coro(i) for i in range(6)]
    results = await asyncio.gather(*[sc.execute(t) for t in tasks])
    assert sorted(results) == list(range(6))
    assert sc.metrics.tasks_completed == 6
    await sc.stop()


@pytest.mark.asyncio
async def test_superconductor_error_tracking():
    config = CHAiMERAConfig(superconductor_threads=1)
    sc = Superconductor(config)
    await sc.start()

    async def bad():
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        await sc.execute(bad)
    assert sc.metrics.tasks_failed == 1
    await sc.stop()


def test_superconductor_set_threads():
    config = CHAiMERAConfig(superconductor_threads=2)
    sc = Superconductor(config)
    sc._semaphore = asyncio.Semaphore(2)
    sc.set_thread_count(4)
    assert config.superconductor_threads == 4


def test_superconductor_set_threads_invalid():
    config = CHAiMERAConfig()
    sc = Superconductor(config)
    with pytest.raises(ValueError):
        sc.set_thread_count(0)


# ---------------------------------------------------------------------------
# CHAiMERAChain
# ---------------------------------------------------------------------------


async def _identity(data):
    return data


async def _double(data):
    if isinstance(data, (int, float)):
        return data * 2
    return data


async def _confident_layer(data):
    return {"result": data, "confidence": 0.95}


@pytest.mark.asyncio
async def test_chain_series_mode():
    config = CHAiMERAConfig(chain_mode=ChainMode.SERIES, layer_count=3)
    chain = CHAiMERAChain(config)
    chain.add_layer(_identity).add_layer(_double).add_layer(_double)

    async with chain:
        result = await chain.run(2)

    assert result.success
    # 2 → identity(2) → double(2)=4 → double(4)=8
    assert result.final_output == 8
    assert len(result.layer_results) == 3


@pytest.mark.asyncio
async def test_chain_parallel_mode():
    config = CHAiMERAConfig(chain_mode=ChainMode.PARALLEL, layer_count=3)
    chain = CHAiMERAChain(config)
    for _ in range(3):
        chain.add_layer(_confident_layer)

    async with chain:
        result = await chain.run("input")

    assert result.success
    assert result.final_output == {"result": "input", "confidence": 0.95}


@pytest.mark.asyncio
async def test_chain_hybrid_mode():
    config = CHAiMERAConfig(
        chain_mode=ChainMode.HYBRID,
        speed_mode=SpeedMode.BALANCED,
        layer_count=5,
    )
    chain = CHAiMERAChain(config)
    for _ in range(5):
        chain.add_layer(_identity)

    async with chain:
        result = await chain.run("data")

    assert result.success
    assert len(result.layer_results) == 5


@pytest.mark.asyncio
async def test_chain_layer_limit():
    config = CHAiMERAConfig(layer_count=2)
    chain = CHAiMERAChain(config)
    chain.add_layer(_identity)
    chain.add_layer(_identity)
    with pytest.raises(ValueError, match="Layer limit"):
        chain.add_layer(_identity)


@pytest.mark.asyncio
async def test_chain_not_started_raises():
    chain = CHAiMERAChain()
    chain.add_layer(_identity)
    with pytest.raises(RuntimeError, match="start"):
        await chain.run("x")


@pytest.mark.asyncio
async def test_chain_set_speed_mode():
    chain = CHAiMERAChain()
    async with chain:
        chain.set_speed_mode(SpeedMode.HIGH_FIDELITY)
        assert chain.speed_controller.current_mode == SpeedMode.HIGH_FIDELITY


@pytest.mark.asyncio
async def test_chain_set_chain_mode():
    config = CHAiMERAConfig(chain_mode=ChainMode.SERIES, layer_count=2)
    chain = CHAiMERAChain(config)
    chain.add_layer(_identity)
    async with chain:
        chain.set_chain_mode(ChainMode.PARALLEL)
        assert chain._config.chain_mode == ChainMode.PARALLEL


def test_chain_set_learning_rate_invalid():
    chain = CHAiMERAChain()
    with pytest.raises(ValueError):
        chain.set_learning_rate(2.0)


@pytest.mark.asyncio
async def test_chain_empty_parallel():
    """Empty chain parallel mode should return None final output."""
    config = CHAiMERAConfig(chain_mode=ChainMode.PARALLEL)
    chain = CHAiMERAChain(config)
    async with chain:
        result = await chain.run("x")
    assert result.final_output is None
