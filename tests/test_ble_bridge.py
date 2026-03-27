"""
tests/test_ble_bridge.py – Unit tests for the BLE bridge module.
"""

import asyncio
import hashlib
import hmac
import pytest

from nrf_module.ble_bridge import BLEBridge


# ---------------------------------------------------------------------------
# BLEBridge tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_stop():
    bridge = BLEBridge(simulation=True)
    await bridge.start()
    assert bridge.get_status()["running"] is True
    await bridge.stop()
    assert bridge.get_status()["running"] is False


@pytest.mark.asyncio
async def test_command_callback_invoked():
    received = []

    def on_cmd(cmd):
        received.append(cmd)

    bridge = BLEBridge(simulation=True, command_callback=on_cmd)
    await bridge.start()
    await bridge.inject_command({"action": "start_capture"})
    await asyncio.sleep(0.1)
    await bridge.stop()
    assert len(received) == 1
    assert received[0]["action"] == "start_capture"


@pytest.mark.asyncio
async def test_authentication_success():
    secret = "supersecret123"
    bridge = BLEBridge(shared_secret=secret, simulation=True)
    await bridge.start()

    challenge = bridge.generate_challenge("device-001")
    response = hmac.new(
        secret.encode(), challenge.encode(), hashlib.sha256
    ).hexdigest()
    ok = bridge.verify_response("device-001", challenge, response)
    assert ok is True
    assert bridge.is_authenticated("device-001") is True
    await bridge.stop()


@pytest.mark.asyncio
async def test_authentication_failure():
    bridge = BLEBridge(shared_secret="correctsecret", simulation=True)
    await bridge.start()
    challenge = bridge.generate_challenge("device-002")
    ok = bridge.verify_response("device-002", challenge, "wrongresponse" * 4)
    assert ok is False
    assert bridge.is_authenticated("device-002") is False
    await bridge.stop()


@pytest.mark.asyncio
async def test_notify_status_buffered():
    bridge = BLEBridge(simulation=True)
    await bridge.start()
    await bridge.notify_status({"running": True, "packet_count": 42})
    buf = bridge.get_notification_buffer()
    assert len(buf) == 1
    assert buf[0]["type"] == "status"
    assert buf[0]["data"]["packet_count"] == 42
    await bridge.stop()


@pytest.mark.asyncio
async def test_notify_freq_upgrade_buffered():
    bridge = BLEBridge(simulation=True)
    await bridge.start()
    await bridge.notify_frequency_upgrade({"module_id": 0, "channel": 90, "frequency_mhz": 2490.0})
    buf = bridge.get_notification_buffer()
    assert any(n["type"] == "freq_upgrade" for n in buf)
    await bridge.stop()


@pytest.mark.asyncio
async def test_clear_notification_buffer():
    bridge = BLEBridge(simulation=True)
    await bridge.start()
    await bridge.notify_status({"running": False})
    bridge.clear_notification_buffer()
    assert bridge.get_notification_buffer() == []
    await bridge.stop()


@pytest.mark.asyncio
async def test_multiple_commands():
    received = []

    def on_cmd(cmd):
        received.append(cmd)

    bridge = BLEBridge(simulation=True, command_callback=on_cmd)
    await bridge.start()
    for action in ["start_capture", "upgrade_frequency", "stop_capture"]:
        await bridge.inject_command({"action": action})
    await asyncio.sleep(0.3)
    await bridge.stop()
    assert len(received) == 3
