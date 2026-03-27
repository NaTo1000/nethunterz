"""Tests for lora_mesh module."""
from __future__ import annotations

import asyncio
import time
import pytest

from lora_mesh.firmware import LoRaConfig, LoRaFirmware, LoRaNode
from lora_mesh.mesh_scanner import MeshScanner
from lora_mesh.frequency_ai import FrequencyAI


# ---------------------------------------------------------------------------
# LoRaFirmware tests
# ---------------------------------------------------------------------------

def test_lora_firmware_default_config():
    fw = LoRaFirmware()
    assert fw.config.region == "US"
    assert fw.config.frequency_mhz == 915.0
    assert fw.config.half_frequency_mode is True
    assert fw.simulation is True


@pytest.mark.asyncio
async def test_lora_firmware_start_stop():
    fw = LoRaFirmware(simulation=True)
    await fw.start()
    assert fw._running is True
    await asyncio.sleep(0)
    await fw.stop()
    assert fw._running is False


def test_lora_firmware_set_frequency_half_mode():
    fw = LoRaFirmware(config=LoRaConfig(half_frequency_mode=True))
    fw.set_frequency(915.0)
    # With half_frequency_mode=True, freq is divided by 2
    assert fw.config.frequency_mhz == pytest.approx(457.5)


def test_lora_firmware_set_frequency_no_half_mode():
    fw = LoRaFirmware(config=LoRaConfig(half_frequency_mode=False))
    fw.set_frequency(868.0)
    assert fw.config.frequency_mhz == pytest.approx(868.0)


def test_lora_firmware_get_status():
    fw = LoRaFirmware()
    status = fw.get_status()
    assert "running" in status
    assert "region" in status
    assert "frequency_mhz" in status
    assert "half_frequency_mode" in status
    assert "node_count" in status
    assert "simulation" in status


# ---------------------------------------------------------------------------
# MeshScanner tests
# ---------------------------------------------------------------------------

def test_mesh_scanner_init():
    fw = LoRaFirmware(simulation=False)
    scanner = MeshScanner(fw)
    assert scanner.get_status()["total_nodes"] == 0


def test_mesh_scanner_on_node_update():
    fw = LoRaFirmware(simulation=False)
    scanner = MeshScanner(fw)
    node = LoRaNode(
        node_id="node_0001",
        address=1,
        frequency_mhz=915.0,
        rssi=-70.0,
        snr=5.0,
        latitude=37.0,
        longitude=-122.0,
    )
    scanner._on_node_update(node)
    assert scanner.get_node("node_0001") is not None
    assert scanner.get_status()["total_nodes"] == 1


def test_mesh_scanner_seek_and_cancel():
    fw = LoRaFirmware(simulation=False)
    scanner = MeshScanner(fw)
    scanner.seek("node_0001")
    assert "node_0001" in scanner.get_status()["seek_targets"]
    scanner.cancel_seek("node_0001")
    assert "node_0001" not in scanner.get_status()["seek_targets"]


def test_mesh_scanner_get_status_fields():
    fw = LoRaFirmware(simulation=False)
    scanner = MeshScanner(fw)
    status = scanner.get_status()
    assert "total_nodes" in status
    assert "active_nodes" in status
    assert "inactive_nodes" in status
    assert "seek_targets" in status


def test_mesh_scanner_get_inactive_nodes():
    fw = LoRaFirmware(simulation=False)
    scanner = MeshScanner(fw)
    # Add a stale node
    node = LoRaNode(
        node_id="node_stale",
        address=99,
        frequency_mhz=915.0,
        rssi=-95.0,
        snr=-2.0,
        last_seen=time.time() - 200,  # very old
        active=False,
    )
    scanner._on_node_update(node)
    inactive = scanner.get_inactive_nodes()
    assert any(n.node_id == "node_stale" for n in inactive)


# ---------------------------------------------------------------------------
# FrequencyAI tests
# ---------------------------------------------------------------------------

def test_frequency_ai_init():
    fw = LoRaFirmware(simulation=False)
    ai = FrequencyAI(fw)
    assert ai._manual_override_mhz is None
    assert ai._running is False


def test_frequency_ai_set_manual_override():
    fw = LoRaFirmware(config=LoRaConfig(half_frequency_mode=False), simulation=False)
    ai = FrequencyAI(fw)
    ai.set_manual_override(868.0)
    assert ai._manual_override_mhz == 868.0
    assert fw.config.frequency_mhz == pytest.approx(868.0)


def test_frequency_ai_clear_manual_override():
    fw = LoRaFirmware(simulation=False)
    ai = FrequencyAI(fw)
    ai.set_manual_override(433.175)
    ai.clear_manual_override()
    assert ai._manual_override_mhz is None


def test_frequency_ai_decide_no_nodes():
    fw = LoRaFirmware(simulation=False)
    ai = FrequencyAI(fw)
    decision = ai._decide_frequency()
    assert decision.recommended_mhz == 915.0
    assert decision.reason == "no_nodes_default"


def test_frequency_ai_decide_weak_signal():
    fw = LoRaFirmware(simulation=False)
    ai = FrequencyAI(fw)
    # Inject nodes with weak signal
    for i in range(3):
        node = LoRaNode(
            node_id=f"node_{i:04x}",
            address=i,
            frequency_mhz=915.0,
            rssi=-95.0,
        )
        fw._nodes[node.node_id] = node
    decision = ai._decide_frequency()
    assert decision.recommended_mhz == pytest.approx(433.175)
    assert "weak" in decision.reason
