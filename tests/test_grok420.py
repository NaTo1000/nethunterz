"""
Tests for Grok 420 Full System.
"""
import pytest
from ai_engine.grok420 import ClusterMode, Grok420
from ai_engine.naydoe_v1 import HardwareProfile
from ai_engine.chaimera import ChainSpeed


@pytest.fixture
def grok():
    return Grok420(
        hardware_profile=HardwareProfile.STANDARD,
        cluster_mode=ClusterMode.SINGLE,
        blockchain_chains=2,
        blockchain_shards=4,
    )


def test_initialization(grok):
    assert grok.system_id is not None
    assert grok.hardware_profile == HardwareProfile.STANDARD
    assert grok._started is False


def test_banner(grok):
    banner = grok.print_banner()
    assert "420" in banner or "GROK" in banner.upper()


@pytest.mark.asyncio
async def test_start_stop(grok):
    await grok.start()
    assert grok._started is True
    await grok.stop()
    assert grok._started is False


@pytest.mark.asyncio
async def test_process_operation(grok):
    await grok.start()
    result = await grok.process(
        operation="test_scan",
        data={"target": "192.168.1.0/24"},
    )
    assert result["success"] is True
    assert result["operation"] == "test_scan"
    assert "process_id" in result
    assert "elapsed_ms" in result
    await grok.stop()


@pytest.mark.asyncio
async def test_process_with_twinbrain(grok):
    await grok.start()
    result = await grok.process(
        "security_check",
        {"target": "test"},
        use_twinbrain=True,
    )
    assert result["consensus"] is not None
    assert "final_action" in result["consensus"]
    await grok.stop()


@pytest.mark.asyncio
async def test_process_without_twinbrain(grok):
    await grok.start()
    result = await grok.process(
        "fast_operation",
        {},
        use_twinbrain=False,
    )
    assert result["consensus"] is None
    await grok.stop()


@pytest.mark.asyncio
async def test_blockchain_memory_integration(grok):
    await grok.start()
    await grok.process("mem_test", {"data": "value"})
    # Should have written to memory
    reads = grok.memory.read("operation.mem_test")
    assert len(reads) >= 1
    await grok.stop()


def test_system_status_before_start(grok):
    status = grok.get_system_status()
    assert status["online"] is False
    assert status["version"] == "420.0.1000"


@pytest.mark.asyncio
async def test_system_status_after_start(grok):
    await grok.start()
    status = grok.get_system_status()
    assert status["online"] is True
    assert "conductor" in status
    assert "chaimera" in status
    assert "twinbrain" in status
    assert "memory" in status
    assert "models" in status
    assert "bot_army" in status
    await grok.stop()


@pytest.mark.asyncio
async def test_bot_army_spawned(grok):
    grok2 = Grok420(
        hardware_profile=HardwareProfile.STANDARD,
        cluster_mode=ClusterMode.SWARM,
    )
    await grok2.start()
    stats = grok2.bot_army.get_stats()
    assert stats["total_bots"] > 0
    await grok2.stop()


@pytest.mark.asyncio
async def test_different_chain_speeds():
    for speed in ChainSpeed:
        g = Grok420(
            hardware_profile=HardwareProfile.STANDARD,
            cluster_mode=ClusterMode.SINGLE,
            blockchain_chains=2,
            blockchain_shards=4,
        )
        await g.start()
        result = await g.process("speed_test", {}, speed=speed)
        assert result["success"] is True
        await g.stop()
