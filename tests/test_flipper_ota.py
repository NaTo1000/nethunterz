"""Tests for OTA updater and companion bridge."""
from __future__ import annotations

import pytest

from flipper.ota_updater import OTAUpdater, OTAStatus, FirmwareManifest
from flipper.companion_bridge import CompanionBridge, BridgeState


# ---------------------------------------------------------------------------
# OTAUpdater tests
# ---------------------------------------------------------------------------

def test_ota_updater_initialisation():
    ota = OTAUpdater(current_version="1.0.0", simulation=True)
    status = ota.get_status()
    assert status["current_version"] == "1.0.0"
    assert status["ota_status"] == OTAStatus.IDLE.value
    assert status["simulation"] is True


def test_ota_is_newer_true():
    ota = OTAUpdater(current_version="1.0.0")
    assert ota.is_newer("1.1.0") is True
    assert ota.is_newer("2.0.0") is True
    assert ota.is_newer("1.0.1") is True


def test_ota_is_newer_false():
    ota = OTAUpdater(current_version="1.0.0")
    assert ota.is_newer("1.0.0") is False
    assert ota.is_newer("0.9.9") is False


def test_ota_is_newer_invalid_returns_false():
    ota = OTAUpdater(current_version="1.0.0")
    assert ota.is_newer("not_a_version") is False


@pytest.mark.asyncio
async def test_check_for_update_returns_manifest(tmp_path):
    ota = OTAUpdater(current_version="1.0.0", update_cache_dir=tmp_path, simulation=True)
    manifest = await ota.check_for_update()
    assert manifest is not None
    assert ota.is_newer(manifest.version)


@pytest.mark.asyncio
async def test_check_no_update_when_current(tmp_path):
    ota = OTAUpdater(current_version="99.0.0", update_cache_dir=tmp_path, simulation=True)
    manifest = await ota.check_for_update()
    assert manifest is None


@pytest.mark.asyncio
async def test_download_firmware(tmp_path):
    ota = OTAUpdater(current_version="1.0.0", update_cache_dir=tmp_path, simulation=True)
    manifest = FirmwareManifest(
        version="1.1.0",
        sha256="a" * 64,
        size_bytes=8192,
        url="ble://test",
    )
    path = await ota.download_firmware(manifest)
    assert path is not None
    assert path.exists()
    assert path.stat().st_size == 8192


@pytest.mark.asyncio
async def test_verify_firmware_simulation(tmp_path):
    ota = OTAUpdater(simulation=True, update_cache_dir=tmp_path)
    f = tmp_path / "fw.bin"
    f.write_bytes(b"\xAA" * 1024)
    result = await ota.verify_firmware(f, "any_hash_in_simulation")
    assert result is True


@pytest.mark.asyncio
async def test_flash_firmware_simulation(tmp_path):
    ota = OTAUpdater(current_version="1.0.0", update_cache_dir=tmp_path, simulation=True)
    ota._manifest = FirmwareManifest(
        version="1.1.0",
        sha256="a" * 64,
        size_bytes=1024,
        url="ble://test",
        changelog="test",
    )
    f = tmp_path / "fw.bin"
    f.write_bytes(b"\x00" * 1024)
    result = await ota.flash_firmware(f)
    assert result is True
    assert ota.current_version == "1.1.0"


@pytest.mark.asyncio
async def test_full_ota_update_cycle(tmp_path):
    ota = OTAUpdater(current_version="1.0.0", update_cache_dir=tmp_path, simulation=True)
    result = await ota.run_full_update()
    assert result is True
    assert ota.current_version == "1.1.0"
    status = ota.get_status()
    assert status["ota_status"] == OTAStatus.COMPLETE.value
    assert status["update_count"] == 1


# ---------------------------------------------------------------------------
# CompanionBridge tests
# ---------------------------------------------------------------------------

def test_companion_bridge_initialisation():
    bridge = CompanionBridge(simulation=True)
    status = bridge.get_status()
    assert status["state"] == BridgeState.DISCONNECTED.value
    assert status["simulation"] is True


@pytest.mark.asyncio
async def test_start_advertising():
    bridge = CompanionBridge(simulation=True)
    await bridge.start_advertising()
    assert bridge._state == BridgeState.ADVERTISING


@pytest.mark.asyncio
async def test_pair_simulation():
    bridge = CompanionBridge(simulation=True)
    await bridge.start_advertising()
    result = await bridge.pair("test_key_hash")
    assert result is True
    assert bridge._state == BridgeState.AUTHENTICATED


@pytest.mark.asyncio
async def test_disconnect():
    bridge = CompanionBridge(simulation=True)
    await bridge.start_advertising()
    await bridge.disconnect()
    assert bridge._state == BridgeState.DISCONNECTED


@pytest.mark.asyncio
async def test_send_and_process():
    bridge = CompanionBridge(simulation=True)
    await bridge.send("test_packet", b"hello")
    status = bridge.get_status()
    assert status["tx_queue_size"] == 1
    await bridge.run_once()
    assert bridge.get_status()["tx_queue_size"] == 0


@pytest.mark.asyncio
async def test_inject_and_receive():
    bridge = CompanionBridge(simulation=True)
    await bridge.inject_packet("test_type", b"payload_data")
    pkt = await bridge.receive()
    assert pkt is not None
    assert pkt.packet_type == "test_type"
    assert pkt.payload == b"payload_data"


@pytest.mark.asyncio
async def test_message_handler():
    bridge = CompanionBridge(simulation=True)
    received = []
    bridge.register_handler("test_type", lambda p: received.append(p))
    await bridge.inject_packet("test_type", b"data")
    await bridge.process_rx()
    assert len(received) == 1


def test_transfer_session_chunk_assembly():
    bridge = CompanionBridge(simulation=True)
    session = bridge.start_transfer("firmware", total_bytes=1024)
    bridge.receive_chunk(session.session_id, b"A" * 512)
    assert session.percent == 50.0
    bridge.receive_chunk(session.session_id, b"B" * 512)
    assert session.complete is True
    data = session.assemble()
    assert len(data) == 1024


def test_transfer_unknown_session():
    bridge = CompanionBridge(simulation=True)
    result = bridge.receive_chunk("unknown_session_id", b"data")
    assert result is False


@pytest.mark.asyncio
async def test_request_cloud_auth():
    bridge = CompanionBridge(simulation=True)
    await bridge.request_cloud_auth("google_drive")
    assert bridge.get_status()["tx_queue_size"] == 1


@pytest.mark.asyncio
async def test_request_scene_download():
    bridge = CompanionBridge(simulation=True)
    await bridge.request_scene_download("baywatch")
    assert bridge.get_status()["tx_queue_size"] == 1
