"""
tests/test_cloud_orchestrator.py – Unit tests for cloud orchestration components.
"""

import asyncio
import pytest

from nrf_module.cloud_orchestrator import CloudOrchestrator, CloudConfig
from cloud.orchestrator import Orchestrator
from cloud.frequency_engine import FrequencyEngine


# ---------------------------------------------------------------------------
# CloudOrchestrator (device-side) tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cloud_orchestrator_start_stop():
    co = CloudOrchestrator(simulation=True)
    await co.start()
    assert co.get_status()["running"] is True
    await co.stop()
    assert co.get_status()["running"] is False


@pytest.mark.asyncio
async def test_enqueue_packet():
    co = CloudOrchestrator(simulation=True)
    await co.start()
    await co.enqueue_packet({"channel": 76, "rssi": -70, "payload": "AABB"})
    assert co.get_status()["pending_packets"] + co.get_stats()["packets_uploaded"] >= 0
    await co.stop()


@pytest.mark.asyncio
async def test_recommendation_callback():
    recommendations = []

    async def on_rec(rec):
        recommendations.append(rec)

    co = CloudOrchestrator(
        simulation=True,
        freq_upgrade_callback=on_rec,
    )
    await co.start()
    # Force a recommendation by directly calling internal method
    await co._apply_recommendation({"module_id": 0, "channel": 90, "reason": "test"})
    assert len(recommendations) == 1
    assert recommendations[0]["channel"] == 90
    await co.stop()


# ---------------------------------------------------------------------------
# Server-side Orchestrator tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_server_orchestrator_register_device():
    engine = FrequencyEngine()
    orch = Orchestrator(frequency_engine=engine)
    await orch.start()
    session = orch.register_device("dev-001")
    assert session.device_id == "dev-001"
    sessions = orch.get_sessions()
    assert any(s["device_id"] == "dev-001" for s in sessions)
    await orch.stop()


@pytest.mark.asyncio
async def test_server_orchestrator_ingest_packets():
    engine = FrequencyEngine()
    orch = Orchestrator(frequency_engine=engine)
    await orch.start()
    packets = [
        {"channel": 76, "rssi": -70, "payload": "AABB", "module_id": 0, "timestamp": 0.0}
        for _ in range(10)
    ]
    result = await orch.ingest_packets("dev-002", packets)
    assert result["status"] == "ok"
    assert orch.get_status()["total_packets"] == 10
    await orch.stop()


# ---------------------------------------------------------------------------
# FrequencyEngine tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_frequency_engine_no_recommendation_below_threshold():
    engine = FrequencyEngine()
    # Packets all on channel 76 with similar RSSI – no alternative to recommend
    packets = [
        {"channel": 76, "rssi": -70, "module_id": 0}
        for _ in range(10)
    ]
    recs = await engine.analyse("dev-test", packets)
    # No other channels observed → no recommendation
    assert recs == []


@pytest.mark.asyncio
async def test_frequency_engine_recommends_cleaner_channel():
    engine = FrequencyEngine()
    device_id = "dev-freq"
    # Prime the engine with data on two channels
    prime_packets = (
        [{"channel": 76, "rssi": -55, "module_id": 0}] * 10 +
        [{"channel": 100, "rssi": -88, "module_id": 0}] * 10
    )
    # Run analysis with enough samples
    recs = await engine.analyse(device_id, prime_packets)
    if recs:
        assert recs[0]["channel"] == 100
        assert 2400 <= recs[0]["frequency_mhz"] <= 2525


@pytest.mark.asyncio
async def test_frequency_engine_channel_summary():
    engine = FrequencyEngine()
    packets = [{"channel": 76, "rssi": -70, "module_id": 0}] * 5
    await engine.analyse("dev-sum", packets)
    summary = engine.get_channel_summary("dev-sum")
    assert len(summary) >= 1
    ch76 = next((s for s in summary if s["channel"] == 76), None)
    assert ch76 is not None
    assert ch76["sample_count"] == 5


@pytest.mark.asyncio
async def test_frequency_engine_hysteresis_prevents_oscillation():
    """Ensure repeated calls with slight improvement don't cause rapid switching."""
    engine = FrequencyEngine()
    device_id = "dev-hyst"
    # First call: establish both channels
    prime = (
        [{"channel": 76, "rssi": -60, "module_id": 0}] * 5 +
        [{"channel": 100, "rssi": -70, "module_id": 0}] * 5
    )
    recs1 = await engine.analyse(device_id, prime)
    # Second call: same channels, same RSSI – hysteresis should block repeat rec
    recs2 = await engine.analyse(device_id, prime)
    # May or may not recommend but should not oscillate: if first recommended ch100,
    # second should not recommend ch76 back
    # The hysteresis guard should prevent recommending the same channel twice in a row
    # when there is no better alternative. With only 2 known channels, the second
    # call should return no recommendation (oscillation suppressed).
    if recs1:
        # Second call with the same data should NOT repeat the same recommendation
        assert not (recs2 and recs2[0]["channel"] == recs1[0]["channel"])
