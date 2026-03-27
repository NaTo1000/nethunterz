"""
tests/test_flipper.py – Unit tests for the AIO Flipper board integration.
"""

import asyncio
import pytest
from pathlib import Path

from flipper.aio_flipper import AIOFlipperController
from flipper.ai_updater import AIFirmwareUpdater
from flipper.firmware_builder import FirmwareBuilder, BuildConfig


# ---------------------------------------------------------------------------
# AIOFlipperController tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flipper_connect_simulation():
    fc = AIOFlipperController(simulation=True)
    ok = await fc.connect()
    assert ok is True
    assert fc.get_status()["connected"] is True
    await fc.disconnect()


@pytest.mark.asyncio
async def test_flipper_get_info():
    fc = AIOFlipperController(simulation=True)
    await fc.connect()
    info = await fc.get_info()
    assert info.firmware_version != ""
    assert info.hardware_version == "f7"
    await fc.disconnect()


@pytest.mark.asyncio
async def test_flipper_get_plugins():
    fc = AIOFlipperController(simulation=True)
    await fc.connect()
    plugins = await fc.get_installed_plugins()
    assert "NRF-Pingequa" in plugins
    await fc.disconnect()


@pytest.mark.asyncio
async def test_flipper_subghz_command():
    fc = AIOFlipperController(simulation=True)
    await fc.connect()
    ok = await fc.send_subghz_command(frequency_hz=433920000, modulation="AM650")
    assert ok is True
    await fc.disconnect()


@pytest.mark.asyncio
async def test_flipper_flash_nonexistent_firmware():
    fc = AIOFlipperController(simulation=True)
    await fc.connect()
    ok = await fc.flash_firmware("/nonexistent/firmware.bin")
    assert ok is False
    await fc.disconnect()


@pytest.mark.asyncio
async def test_flipper_flash_existing_firmware(tmp_path):
    fw = tmp_path / "fw.bin"
    fw.write_bytes(b"\x00" * 512)
    fc = AIOFlipperController(simulation=True)
    await fc.connect()
    ok = await fc.flash_firmware(str(fw))
    assert ok is True
    await fc.disconnect()


@pytest.mark.asyncio
async def test_flipper_data_callback():
    events = []
    fc = AIOFlipperController(simulation=True, data_callback=lambda e: events.append(e))
    await fc.connect()
    await asyncio.sleep(0.1)
    await fc.disconnect()


# ---------------------------------------------------------------------------
# FirmwareBuilder tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_firmware_builder_simulation(tmp_path):
    cfg = BuildConfig(output_dir=str(tmp_path / "build"))
    builder = FirmwareBuilder(cfg, simulation=True)
    result = await builder.build("1.2.3")
    assert result.success is True
    assert result.firmware_path is not None
    assert result.sha256 is not None
    assert Path(result.firmware_path).exists()


@pytest.mark.asyncio
async def test_firmware_builder_manifest(tmp_path):
    cfg = BuildConfig(output_dir=str(tmp_path / "build"))
    builder = FirmwareBuilder(cfg, simulation=True)
    await builder.build("2.0.0")
    manifest_path = tmp_path / "build" / "manifest.json"
    assert manifest_path.exists()
    import json
    manifest = json.loads(manifest_path.read_text())
    assert manifest["version"] == "2.0.0"
    assert "sha256" in manifest


@pytest.mark.asyncio
async def test_firmware_builder_history(tmp_path):
    cfg = BuildConfig(output_dir=str(tmp_path / "build"))
    builder = FirmwareBuilder(cfg, simulation=True)
    await builder.build("1.0.0")
    await builder.build("1.1.0")
    history = builder.get_build_history()
    assert len(history) == 2
    assert history[0]["config"]["build_type"] == "release"


# ---------------------------------------------------------------------------
# AIFirmwareUpdater tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_updater_start_stop(tmp_path):
    fc = AIOFlipperController(simulation=True)
    await fc.connect()
    updater = AIFirmwareUpdater(fc, firmware_dir=str(tmp_path / "fw"), simulation=True)
    await updater.start()
    status = updater.get_status()
    assert status["running"] is True
    assert status["current_version"] == "0.82.3"
    await updater.stop()
    await fc.disconnect()


@pytest.mark.asyncio
async def test_is_newer_version():
    from flipper.ai_updater import AIFirmwareUpdater
    assert AIFirmwareUpdater._is_newer("1.0.0", "0.9.9") is True
    assert AIFirmwareUpdater._is_newer("0.9.9", "1.0.0") is False
    assert AIFirmwareUpdater._is_newer("1.0.0", "1.0.0") is False
    assert AIFirmwareUpdater._is_newer("2.1.3", "2.1.2") is True


@pytest.mark.asyncio
async def test_verify_sha256(tmp_path):
    import hashlib
    data = b"firmware content"
    fw_path = tmp_path / "test.bin"
    fw_path.write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()
    from flipper.ai_updater import AIFirmwareUpdater
    assert AIFirmwareUpdater._verify_sha256(fw_path, expected) is True
    assert AIFirmwareUpdater._verify_sha256(fw_path, "wrong" * 12 + "hash") is False
