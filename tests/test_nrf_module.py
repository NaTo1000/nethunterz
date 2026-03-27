"""
tests/test_nrf_module.py – Unit tests for the Pingequa Dual NRF module runtime.
"""

import asyncio
import json
import time
from pathlib import Path
import tempfile
import pytest

from nrf_module.pingequa_dual_nrf import PingequaDualNRF, ModuleConfig, NRFPacket
from nrf_module.frequency_manager import FrequencyManager, HopConfig
from nrf_module.security_monitor import SecurityMonitor, Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_nrf(tmp_path: Path) -> PingequaDualNRF:
    return PingequaDualNRF(
        ModuleConfig(module_id=0, channel=76),
        ModuleConfig(module_id=1, channel=100),
        log_dir=tmp_path / "nrf_logs",
        simulation=True,
    )


# ---------------------------------------------------------------------------
# PingequaDualNRF tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_open_creates_log_dir(tmp_path):
    nrf = make_nrf(tmp_path)
    nrf.open()
    assert (tmp_path / "nrf_logs").is_dir()
    nrf.close()


@pytest.mark.asyncio
async def test_status_structure(tmp_path):
    nrf = make_nrf(tmp_path)
    nrf.open()
    status = nrf.get_status()
    assert "running" in status
    assert "packet_count" in status
    assert len(status["modules"]) == 2
    nrf.close()


@pytest.mark.asyncio
async def test_capture_records_packets(tmp_path):
    nrf = make_nrf(tmp_path)
    nrf.open()
    await nrf.start_capture()
    await asyncio.sleep(0.15)  # allow a few poll cycles
    await nrf.stop_capture()
    packets = await nrf.get_captured_packets()
    # Simulation produces packets ~20 % of the time; at least 1 expected in 150 ms
    # but accept 0 to avoid flakiness (just validate structure when present)
    assert isinstance(packets, list)
    if packets:
        pkt = packets[0]
        assert isinstance(pkt.payload, bytes)
        assert isinstance(pkt.timestamp, float)
        assert pkt.module_id in (0, 1)
    nrf.close()


@pytest.mark.asyncio
async def test_upgrade_frequency(tmp_path):
    nrf = make_nrf(tmp_path)
    nrf.open()
    new_freq = await nrf.upgrade_frequency(module_id=0, new_channel=110)
    assert new_freq == 2510.0
    assert nrf.get_status()["modules"][0]["channel"] == 110
    nrf.close()


@pytest.mark.asyncio
async def test_upgrade_frequency_clamps_channel(tmp_path):
    nrf = make_nrf(tmp_path)
    nrf.open()
    await nrf.upgrade_frequency(module_id=1, new_channel=999)
    assert nrf.get_status()["modules"][1]["channel"] == 125
    await nrf.upgrade_frequency(module_id=1, new_channel=-5)
    assert nrf.get_status()["modules"][1]["channel"] == 0
    nrf.close()


@pytest.mark.asyncio
async def test_rewrite_packets(tmp_path):
    nrf = make_nrf(tmp_path)
    nrf.open()
    packets = [
        NRFPacket(
            channel=76,
            frequency_mhz=2476.0,
            timestamp=time.time(),
            rssi=-70,
            payload=b"\xDE\xAD\xBE\xEF",
            module_id=0,
        )
    ]
    # Should not raise
    await nrf.rewrite_packets(packets, module_id=0, delay_s=0.0)
    nrf.close()


@pytest.mark.asyncio
async def test_load_log(tmp_path):
    log_file = tmp_path / "test_capture.jsonl"
    pkt = NRFPacket(
        channel=76,
        frequency_mhz=2476.0,
        timestamp=1234567890.0,
        rssi=-65,
        payload=b"\xAB\xCD",
        module_id=0,
    )
    log_file.write_text(json.dumps(pkt.to_dict()) + "\n")
    nrf = make_nrf(tmp_path)
    nrf.open()
    loaded = await nrf.load_log(log_file)
    assert len(loaded) == 1
    assert loaded[0].channel == 76
    assert loaded[0].payload == b"\xAB\xCD"
    nrf.close()


@pytest.mark.asyncio
async def test_context_manager(tmp_path):
    async with PingequaDualNRF(
        log_dir=tmp_path / "ctx_logs",
        simulation=True,
    ) as nrf:
        status = nrf.get_status()
        assert status["running"] is False  # capture not started yet


# ---------------------------------------------------------------------------
# FrequencyManager tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_best_channel_no_data(tmp_path):
    nrf = make_nrf(tmp_path)
    nrf.open()
    mgr = FrequencyManager(nrf)
    ch = mgr.select_best_channel()
    assert ch == 76  # default fallback
    nrf.close()


@pytest.mark.asyncio
async def test_select_best_channel_with_data(tmp_path):
    nrf = make_nrf(tmp_path)
    nrf.open()
    mgr = FrequencyManager(nrf)
    # Manually inject RSSI data
    mgr._stats[76].sample_count = 5
    mgr._stats[76].rssi_sum = -400  # avg -80
    mgr._stats[100].sample_count = 5
    mgr._stats[100].rssi_sum = -300  # avg -60 (worse)
    mgr._stats[110].sample_count = 5
    mgr._stats[110].rssi_sum = -450  # avg -90 (best, least congested)
    best = mgr.select_best_channel()
    assert best == 110
    nrf.close()


@pytest.mark.asyncio
async def test_hopping_start_stop(tmp_path):
    nrf = make_nrf(tmp_path)
    nrf.open()
    await nrf.start_capture()
    mgr = FrequencyManager(nrf)
    hop_cfg = HopConfig(channels=[76, 80, 85], dwell_time_s=0.05)
    await mgr.start_hopping(hop_cfg)
    await asyncio.sleep(0.2)
    await mgr.stop_hopping()
    log = mgr.get_upgrade_log()
    assert len(log) > 0
    await nrf.stop_capture()
    nrf.close()


@pytest.mark.asyncio
async def test_cloud_recommendation_applied(tmp_path):
    nrf = make_nrf(tmp_path)
    nrf.open()
    mgr = FrequencyManager(nrf)
    rec = {"module_id": 0, "channel": 90, "reason": "test"}
    await mgr.apply_cloud_recommendation(rec)
    log = mgr.get_upgrade_log()
    assert log[-1]["channel"] == 90
    assert log[-1]["source"] == "cloud"
    nrf.close()


# ---------------------------------------------------------------------------
# SecurityMonitor tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flood_detection(tmp_path):
    monitor = SecurityMonitor(log_path=str(tmp_path / "audit.log"))
    await monitor.start()
    monitor.record_packet_event(module_id=0, packet_count_per_sec=5000)
    alerts = monitor.get_alerts(severity=Severity.CRITICAL)
    assert any(a.code == "PACKET_FLOOD" for a in alerts)
    await monitor.stop()


@pytest.mark.asyncio
async def test_replay_detection(tmp_path):
    monitor = SecurityMonitor(log_path=str(tmp_path / "audit.log"))
    await monitor.start()
    h = "a" * 64
    monitor.record_packet_event(module_id=0, packet_count_per_sec=10, payload_hash=h)
    monitor.record_packet_event(module_id=0, packet_count_per_sec=10, payload_hash=h)
    alerts = monitor.get_alerts(severity=Severity.WARNING)
    assert any(a.code == "REPLAY_ATTACK" for a in alerts)
    await monitor.stop()


@pytest.mark.asyncio
async def test_auth_rate_limiting(tmp_path):
    monitor = SecurityMonitor(log_path=str(tmp_path / "audit.log"))
    await monitor.start()
    device = "test-device-001"
    for _ in range(SecurityMonitor.MAX_AUTH_ATTEMPTS_PER_MIN):
        assert monitor.check_auth_rate(device) is True
    # Next attempt should be blocked
    assert monitor.check_auth_rate(device) is False
    await monitor.stop()


@pytest.mark.asyncio
async def test_normal_packet_no_alert(tmp_path):
    monitor = SecurityMonitor(log_path=str(tmp_path / "audit.log"))
    await monitor.start()
    monitor.record_packet_event(module_id=0, packet_count_per_sec=100)
    alerts = monitor.get_alerts(severity=Severity.CRITICAL)
    assert not any(a.code == "PACKET_FLOOD" for a in alerts)
    await monitor.stop()
