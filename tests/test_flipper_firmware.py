"""
Tests for Flipper Zero Firmware and GUI.
"""
import pytest
from flipper.firmware import (
    SPLASH_SCREENS,
    THEMES_80S,
    FlipperAnimation,
    FlipperOperationsGUI,
    FlipperScreen,
    FlipperZeroFirmware,
    TypewriterEffect,
)


@pytest.fixture
def firmware():
    return FlipperZeroFirmware(theme="naydoe_default")


@pytest.fixture
def gui():
    return FlipperOperationsGUI(theme="naydoe_default")


@pytest.fixture
def animation():
    return FlipperAnimation()


# ── Theme Tests ────────────────────────────────────────────────────────────────

def test_all_themes_present():
    expected = ["miami_vice", "baywatch", "night_rider", "bionic_man", "naydoe_default"]
    for theme in expected:
        assert theme in THEMES_80S, f"Theme '{theme}' not found"


def test_theme_has_required_keys():
    for theme_name, theme in THEMES_80S.items():
        assert "primary" in theme, f"{theme_name}: missing primary"
        assert "background" in theme, f"{theme_name}: missing background"
        assert "tagline" in theme, f"{theme_name}: missing tagline"


def test_splash_screens_present():
    for key in ["boot", "miami_vice", "night_rider", "baywatch", "bionic"]:
        assert key in SPLASH_SCREENS


def test_splash_screens_content():
    assert "NayDoeV1" in SPLASH_SCREENS["boot"] or "NAYDOE" in SPLASH_SCREENS["boot"].upper()


# ── Typewriter Tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_typewriter_animate():
    tw = TypewriterEffect(speed_ms=1)
    tw.set_text("HELLO")
    result = await tw.animate_full()
    assert result == "HELLO"
    assert tw.is_complete is True


@pytest.mark.asyncio
async def test_typewriter_tick():
    tw = TypewriterEffect(speed_ms=1)
    tw.set_text("ABC")
    await tw.tick()
    assert tw._buffer == "A"


def test_typewriter_not_complete_initially():
    tw = TypewriterEffect()
    tw.set_text("test")
    assert tw.is_complete is False


def test_typewriter_empty_text():
    tw = TypewriterEffect()
    tw.set_text("")
    assert tw.is_complete is True


# ── GUI Tests ──────────────────────────────────────────────────────────────────

def test_render_dashboard(gui):
    status = {
        "ai_enabled": True,
        "voice_control": True,
        "uptime_seconds": 3661,
        "autonomy_stats": {
            "total_operations_registered": 100,
            "total_runs": 50,
            "successful_runs": 48,
        },
        "pinedap": {"modules": {}},
    }
    rendered = gui.render_dashboard(status)
    assert "NayDoeV1" in rendered
    assert "OPERATIONS" in rendered


def test_render_network_map(gui):
    networks = [
        {"ssid": "TestNet", "signal_dbm": -60},
        {"ssid": "GuestWifi", "signal_dbm": -75},
    ]
    rendered = gui.render_network_map(networks)
    assert "TestNet" in rendered
    assert "NETWORK MAP" in rendered


def test_render_voice_indicator_active(gui):
    rendered = gui.render_voice_indicator(True, "scanning...")
    assert "●" in rendered


def test_render_voice_indicator_inactive(gui):
    rendered = gui.render_voice_indicator(False)
    assert "○" in rendered
    assert "Hey NayDoe" in rendered or "activate" in rendered


def test_render_device_constellation(gui):
    devices = {
        "pineapple_pager": True,
        "flipper_zero": True,
        "esp32": False,
    }
    rendered = gui.render_device_constellation(devices)
    assert "pineapple_pager" in rendered
    assert "ONLINE" in rendered
    assert "OFFLINE" in rendered


# ── Firmware Tests ─────────────────────────────────────────────────────────────

def test_firmware_initialization(firmware):
    assert firmware.FIRMWARE_VERSION is not None
    assert firmware.theme == "naydoe_default"
    assert firmware._started is False


@pytest.mark.asyncio
async def test_firmware_boot(firmware):
    frames = await firmware.boot()
    assert len(frames) > 0
    assert firmware._started is True


def test_switch_theme(firmware):
    result = firmware.switch_theme("miami_vice")
    assert result is True
    assert firmware.theme == "miami_vice"


def test_switch_invalid_theme(firmware):
    result = firmware.switch_theme("nonexistent_theme")
    assert result is False
    assert firmware.theme == "naydoe_default"  # unchanged


def test_render_screen_splash(firmware):
    rendered = firmware.render_current_screen(FlipperScreen.SPLASH)
    assert len(rendered) > 0


@pytest.mark.asyncio
async def test_render_screen_dashboard(firmware):
    await firmware.boot()
    status = {
        "ai_enabled": True,
        "voice_control": True,
        "uptime_seconds": 100,
        "autonomy_stats": {
            "total_operations_registered": 100,
            "total_runs": 0,
            "successful_runs": 0,
        },
        "pinedap": {"modules": {}},
    }
    rendered = firmware.render_current_screen(FlipperScreen.DASHBOARD, status)
    assert len(rendered) > 0


def test_firmware_status(firmware):
    status = firmware.get_status()
    assert "firmware_version" in status
    assert "theme" in status
    assert "available_themes" in status


# ── Animation Tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_play_theme_miami_vice(animation):
    frame = await animation.play_theme("miami_vice")
    # Miami Vice splash uses decorative separated chars: ░░░M░░I░░A░░M░░I░░
    assert "BEACH" in frame or "MIAMI" in frame.upper() or "░░░M░░I░░A" in frame


@pytest.mark.asyncio
async def test_play_theme_night_rider(animation):
    frame = await animation.play_theme("night_rider")
    # Night Rider splash uses separated letters: ░░░N░░I░░G░░H░░T░░
    assert "K.I.T.T." in frame or "░░░N░░I░░G░░H░░T" in frame or "NayDoeV1" in frame


@pytest.mark.asyncio
async def test_play_boot_sequence(animation):
    frames = await animation.play_boot_sequence()
    assert len(frames) > 0
