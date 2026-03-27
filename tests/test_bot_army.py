"""Tests for Bot Army Infrastructure."""

import asyncio
import pytest

from grok420.bot_army.army import BotArmy
from grok420.bot_army.bot import Bot, BotConfig, BotStatus
from grok420.config import ConductorConfig


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bot_start_stop():
    bot = Bot()
    await bot.start()
    assert bot._running
    assert bot.status == BotStatus.IDLE
    await bot.stop()
    assert not bot._running


@pytest.mark.asyncio
async def test_bot_submit_task():
    bot = Bot()
    await bot.start()

    async def work():
        return "result"

    result = await bot.submit(work)
    assert result == "result"
    assert bot.tasks_completed == 1
    await bot.stop()


@pytest.mark.asyncio
async def test_bot_submit_with_retry():
    attempts = [0]

    async def flaky():
        attempts[0] += 1
        if attempts[0] < 3:
            raise RuntimeError("not yet")
        return "success"

    config = BotConfig(max_retries=3)
    bot = Bot(config)
    await bot.start()
    result = await bot.submit(flaky)
    assert result == "success"
    assert attempts[0] == 3
    await bot.stop()


@pytest.mark.asyncio
async def test_bot_submit_max_retries_exceeded():
    async def always_fail():
        raise RuntimeError("always fails")

    config = BotConfig(max_retries=2)
    bot = Bot(config)
    await bot.start()
    with pytest.raises(RuntimeError, match="always fails"):
        await bot.submit(always_fail)
    assert bot.tasks_failed == 1
    await bot.stop()


@pytest.mark.asyncio
async def test_bot_is_healthy():
    bot = Bot()
    await bot.start()
    assert bot.is_healthy
    await bot.stop()


def test_bot_to_dict():
    bot = Bot()
    d = bot.to_dict()
    assert "bot_id" in d
    assert "status" in d
    assert "hardware_class" in d


# ---------------------------------------------------------------------------
# BotArmy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bot_army_start_stop():
    army = BotArmy(initial_size=3)
    await army.start()
    assert army.bot_count == 3
    assert army.healthy_bot_count == 3
    await army.stop()
    assert army.bot_count == 0


@pytest.mark.asyncio
async def test_bot_army_dispatch():
    async with BotArmy(initial_size=2) as army:
        async def work():
            return 42

        result = await army.dispatch(work)
        assert result == 42


@pytest.mark.asyncio
async def test_bot_army_dispatch_all():
    async with BotArmy(initial_size=4) as army:
        async def make_coro(i):
            async def coro():
                return i
            return coro

        factories = [await make_coro(i) for i in range(8)]
        results = await army.dispatch_all(factories)
        assert sorted(r for r in results if not isinstance(r, Exception)) == list(range(8))


@pytest.mark.asyncio
async def test_bot_army_scale_up():
    config = ConductorConfig(max_bots=20)
    async with BotArmy(conductor_config=config, initial_size=2) as army:
        await army.scale_to(8)
        assert army.bot_count == 8


@pytest.mark.asyncio
async def test_bot_army_scale_down():
    async with BotArmy(initial_size=6) as army:
        await army.scale_to(2)
        assert army.bot_count == 2


@pytest.mark.asyncio
async def test_bot_army_max_bots_limit():
    config = ConductorConfig(max_bots=5)
    async with BotArmy(conductor_config=config, initial_size=2) as army:
        await army.scale_to(100)
        # Should cap at max_bots
        assert army.bot_count <= 5


@pytest.mark.asyncio
async def test_bot_army_no_healthy_bots():
    army = BotArmy(initial_size=0)
    await army.start()

    async def noop():
        return None

    with pytest.raises(RuntimeError, match="No healthy bots"):
        await army.dispatch(noop)
    await army.stop()


@pytest.mark.asyncio
async def test_bot_army_status():
    async with BotArmy(initial_size=2) as army:
        status = army.get_army_status()
        assert len(status) == 2
        assert all("bot_id" in s for s in status)


def test_bot_army_set_max_bots():
    army = BotArmy()
    army.set_max_bots(500)
    assert army._config.max_bots == 500


def test_bot_army_set_max_bots_invalid():
    army = BotArmy()
    with pytest.raises(ValueError):
        army.set_max_bots(0)
