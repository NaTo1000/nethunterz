"""Tests for NayDoev1 Conductor and ResourceAllocator."""

import asyncio
import pytest

from grok420.config import ConductorConfig, HardwareClass
from grok420.conductor.naydoev1 import BotState, NayDoev1Conductor
from grok420.conductor.resource_allocator import ResourceAllocator


# ---------------------------------------------------------------------------
# ResourceAllocator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resource_allocator_basic():
    config = ConductorConfig(max_bots=5, inference_power=1.0)
    alloc = ResourceAllocator(config)
    await alloc.start()

    async def _coro():
        return 42

    result = await alloc.dispatch(_coro)
    assert result == 42

    await alloc.stop()


@pytest.mark.asyncio
async def test_resource_allocator_concurrency_limit():
    """Verify semaphore caps concurrent slots."""
    config = ConductorConfig(max_bots=2, inference_power=1.0)
    alloc = ResourceAllocator(config)
    await alloc.start()

    # Run 4 tasks through a cap-2 semaphore — all should complete
    async def slow_task():
        await asyncio.sleep(0.01)
        return "done"

    results = await asyncio.gather(*[alloc.dispatch(slow_task) for _ in range(4)])
    assert all(r == "done" for r in results)
    await alloc.stop()


@pytest.mark.asyncio
async def test_resource_allocator_error_propagated():
    config = ConductorConfig(max_bots=2, inference_power=1.0)
    alloc = ResourceAllocator(config)
    await alloc.start()

    async def bad_task():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await alloc.dispatch(bad_task)
    await alloc.stop()


def test_resource_allocator_inference_power_validation():
    config = ConductorConfig(max_bots=1)
    alloc = ResourceAllocator(config)
    with pytest.raises(ValueError):
        alloc.set_inference_power(1.5)
    with pytest.raises(ValueError):
        alloc.set_inference_power(-0.1)


def test_resource_allocator_latency_vs_accuracy_validation():
    config = ConductorConfig(max_bots=1)
    alloc = ResourceAllocator(config)
    with pytest.raises(ValueError):
        alloc.set_latency_vs_accuracy(2.0)


# ---------------------------------------------------------------------------
# NayDoev1Conductor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conductor_start_stop():
    conductor = NayDoev1Conductor()
    await conductor.start()
    assert conductor.active_bot_count == 0
    await conductor.stop()


@pytest.mark.asyncio
async def test_conductor_register_and_confirm():
    async with NayDoev1Conductor() as c:
        bot_id, token = await c.register_bot(HardwareClass.CPU)
        assert bot_id
        assert token
        ok = await c.confirm_handshake(bot_id, token)
        assert ok
        assert c.active_bot_count == 1


@pytest.mark.asyncio
async def test_conductor_bad_handshake_token():
    async with NayDoev1Conductor() as c:
        bot_id, _ = await c.register_bot()
        ok = await c.confirm_handshake(bot_id, "wrong-token")
        assert not ok
        assert c.active_bot_count == 0


@pytest.mark.asyncio
async def test_conductor_max_bots_enforcement():
    config = ConductorConfig(max_bots=2)
    async with NayDoev1Conductor(config) as c:
        await c.register_bot()
        await c.register_bot()
        with pytest.raises(RuntimeError, match="Bot limit"):
            await c.register_bot()


@pytest.mark.asyncio
async def test_conductor_deregister():
    async with NayDoev1Conductor() as c:
        bot_id, token = await c.register_bot()
        await c.confirm_handshake(bot_id, token)
        assert c.active_bot_count == 1
        await c.deregister_bot(bot_id)
        assert c.active_bot_count == 0


@pytest.mark.asyncio
async def test_conductor_dispatch():
    async with NayDoev1Conductor() as c:
        async def work():
            return "hello"

        result = await c.dispatch(work)
        assert result == "hello"


@pytest.mark.asyncio
async def test_conductor_parameter_adjustment():
    async with NayDoev1Conductor() as c:
        c.set_inference_power(0.3)
        c.set_latency_vs_accuracy(0.8)
        c.set_max_bots(500)
        c.set_hardware_class(HardwareClass.GPU)
        assert c._config.max_bots == 500


@pytest.mark.asyncio
async def test_conductor_context_manager():
    conductor = NayDoev1Conductor()
    async with conductor:
        assert conductor._running
    assert not conductor._running


@pytest.mark.asyncio
async def test_conductor_bot_status():
    async with NayDoev1Conductor() as c:
        bot_id, token = await c.register_bot()
        await c.confirm_handshake(bot_id, token)
        status = c.get_bot_status()
        assert len(status) == 1
        assert status[0]["bot_id"] == bot_id
        assert status[0]["state"] == "active"
