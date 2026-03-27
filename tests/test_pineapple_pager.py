"""
Tests for Pineapple Pager Firmware.
"""
import pytest
from pineapple_pager.firmware import (
    ConnectivityMode,
    FirmwareConfig,
    FirmwareState,
    OTAManager,
    PineapplePagerFirmware,
)
from pineapple_pager.pinedap import PineDAPStack


@pytest.fixture
def firmware():
    config = FirmwareConfig(
        ai_enabled=True,
        autonomy_level=100,
        connectivity=ConnectivityMode.ALL,
    )
    return PineapplePagerFirmware(config=config)


@pytest.fixture
def pinedap():
    return PineDAPStack()


def test_firmware_initialization(firmware):
    assert firmware.state == FirmwareState.BOOTING
    assert firmware.config.ai_enabled is True
    assert firmware.config.autonomy_level == 100


def test_default_config():
    fw = PineapplePagerFirmware()
    assert fw.config.encryption_key_bits == 256
    assert fw.config.wake_word == "hey naydoe"
    assert fw.config.trail_wipe_on_shutdown is True


@pytest.mark.asyncio
async def test_boot_sequence(firmware):
    await firmware.boot()
    assert firmware.state == FirmwareState.RUNNING
    assert firmware._boot_time is not None


@pytest.mark.asyncio
async def test_shutdown_with_wipe(firmware):
    await firmware.boot()
    await firmware.shutdown(wipe_trails=True)
    assert firmware.state == FirmwareState.SHUTDOWN


@pytest.mark.asyncio
async def test_shutdown_without_wipe(firmware):
    await firmware.boot()
    await firmware.shutdown(wipe_trails=False)
    assert firmware.state == FirmwareState.SHUTDOWN


@pytest.mark.asyncio
async def test_mac_randomization(firmware):
    mac = await firmware._randomize_mac()
    parts = mac.split(":")
    assert len(parts) == 6
    # Check locally administered bit is set
    first = int(parts[0], 16)
    assert first & 0x02


def test_get_status(firmware):
    status = firmware.get_status()
    assert "device_id" in status
    assert "firmware_version" in status
    assert "state" in status
    assert "ai_enabled" in status


@pytest.mark.asyncio
async def test_ota_check(firmware):
    result = await firmware.ota.check_update()
    assert "update_available" in result
    assert "current_version" in result


@pytest.mark.asyncio
async def test_ota_apply_update():
    config = FirmwareConfig()
    ota = OTAManager(config)
    result = await ota.apply_update(b"fake_firmware_package")
    assert result is True
    assert len(ota.get_history()) == 1


# ── PineDAP Tests ──────────────────────────────────────────────────────────────

def test_pinedap_initialization(pinedap):
    assert pinedap.VERSION is not None
    assert len(pinedap._modules) > 0


def test_pinedap_modules_registered(pinedap):
    expected = ["pineap_suite", "recon", "logging", "naydoe_v1", "mesh_bridge"]
    for mod_id in expected:
        assert mod_id in pinedap._modules


def test_activate_module(pinedap):
    result = pinedap.activate_module("recon")
    assert result is True
    assert pinedap._modules["recon"].status.value == "active"


def test_deactivate_module(pinedap):
    pinedap.activate_module("recon")
    result = pinedap.deactivate_module("recon")
    assert result is True
    assert pinedap._modules["recon"].status.value == "inactive"


def test_activate_nonexistent_module(pinedap):
    result = pinedap.activate_module("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_auto_configure(pinedap):
    result = await pinedap.auto_configure()
    assert result["auto_configured"] is True
    assert "modules_activated" in result


def test_pinedap_status(pinedap):
    status = pinedap.get_status()
    assert "version" in status
    assert "modules" in status
    assert "pineap" in status


@pytest.mark.asyncio
async def test_pineap_suite(pinedap):
    pinedap.pineap.add_ssid("TestSSID")
    pinedap.pineap.add_ssid("GuestNet")
    result = await pinedap.pineap.start_beacons(ai_optimized=True)
    assert result["beacons_active"] is True
    assert result["ssid_count"] == 2
    assert result["ai_optimized"] is True


@pytest.mark.asyncio
async def test_recon_scan(pinedap):
    result = await pinedap.recon.scan(passive=True, duration_seconds=5.0)
    assert "scan_id" in result
    assert "networks_found" in result


@pytest.mark.asyncio
async def test_campaign_manager(pinedap):
    camp_id = pinedap.campaigns.create_campaign(
        "Test Campaign",
        objectives=["scan", "report"],
        success_metrics={"networks_found": 10},
    )
    assert camp_id is not None
    campaign = pinedap.campaigns.get_campaign(camp_id)
    assert campaign["name"] == "Test Campaign"


@pytest.mark.asyncio
async def test_mesh_bridge(pinedap):
    pinedap.mesh_bridge.register_node("esp32-001", "esp32", ["wifi", "ble"])
    result = await pinedap.mesh_bridge.broadcast({"cmd": "status"})
    assert result["delivered"] is True
    topology = pinedap.mesh_bridge.get_topology()
    assert topology["nodes"] == 1
