"""Tests for nrf_module."""
from __future__ import annotations

import pytest

from nrf_module import ModuleConfig, NRFPacket, PingequaDualNRF, FrequencyManager, HopConfig


def test_module_config_defaults():
    cfg = ModuleConfig(module_id=1)
    assert cfg.module_id == 1
    assert cfg.channel == 76


def test_nrf_packet_to_dict():
    pkt = NRFPacket(
        module_id=1,
        channel=76,
        payload=b"\xde\xad\xbe\xef",
        rssi=-55.0,
        timestamp=1234567890.0,
    )
    d = pkt.to_dict()
    assert d["module_id"] == 1
    assert d["channel"] == 76
    assert d["payload"] == "deadbeef"
    assert d["rssi"] == -55.0
    assert d["timestamp"] == 1234567890.0


@pytest.mark.asyncio
async def test_pingequa_dual_nrf_open_close(tmp_path):
    primary = ModuleConfig(module_id=1)
    secondary = ModuleConfig(module_id=2)
    nrf = PingequaDualNRF(
        primary=primary,
        secondary=secondary,
        log_dir=tmp_path / "logs/nrf",
        simulation=True,
    )
    nrf.open()
    status = nrf.get_status()
    assert status["open"] is True
    assert status["simulation"] is True

    await nrf.start_capture()
    await nrf.stop_capture()
    nrf.close()
    assert nrf.get_status()["open"] is False


@pytest.mark.asyncio
async def test_frequency_manager_current_channel():
    mgr = FrequencyManager()
    assert mgr.get_current_channel() == 76

    cfg = HopConfig(channels=[10, 20, 30], dwell_time_s=100.0)
    await mgr.start_hopping(cfg)
    # channel hasn't changed yet since dwell time is long
    await mgr.stop_hopping()
    # channel should still be valid
    assert mgr.get_current_channel() in [10, 20, 30, 76]
