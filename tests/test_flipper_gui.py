"""Tests for the NayDoeV1GUI module."""
from __future__ import annotations

from flipper.gui import (
    NayDoeV1GUI,
    MenuSection,
    DisplayFrame,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
)


def test_display_frame_dimensions():
    frame = DisplayFrame()
    assert frame.width == DISPLAY_WIDTH
    assert frame.height == DISPLAY_HEIGHT
    assert len(frame.pixels) == DISPLAY_WIDTH * DISPLAY_HEIGHT


def test_display_frame_set_pixel():
    frame = DisplayFrame()
    frame.set_pixel(0, 0)
    assert frame.pixels[0] == 1
    frame.set_pixel(0, 0, on=False)
    assert frame.pixels[0] == 0


def test_display_frame_out_of_bounds():
    frame = DisplayFrame()
    # Should not raise
    frame.set_pixel(-1, 0)
    frame.set_pixel(DISPLAY_WIDTH, 0)
    frame.set_pixel(0, DISPLAY_HEIGHT)


def test_display_frame_draw_rect():
    frame = DisplayFrame()
    frame.draw_rect(0, 0, 10, 10)
    # Corner pixels should be set
    assert frame.pixels[0] == 1


def test_display_frame_draw_rect_filled():
    frame = DisplayFrame()
    frame.draw_rect(0, 0, 5, 5, filled=True)
    # All pixels in range should be set
    for row in range(5):
        for col in range(5):
            assert frame.pixels[row * DISPLAY_WIDTH + col] == 1


def test_display_frame_to_bytes():
    frame = DisplayFrame()
    b = frame.to_bytes()
    assert isinstance(b, bytes)
    assert len(b) == DISPLAY_WIDTH * DISPLAY_HEIGHT


def test_gui_initialisation():
    gui = NayDoeV1GUI(simulation=True)
    status = gui.get_status()
    assert status["section"] == MenuSection.MAIN.value
    assert status["simulation"] is True
    assert status["frames_rendered"] == 0


def test_gui_navigate_down():
    gui = NayDoeV1GUI()
    initial = gui.state.selected_index
    gui.navigate_down()
    assert gui.state.selected_index == (initial + 1) % 5


def test_gui_navigate_up():
    gui = NayDoeV1GUI()
    gui.navigate_up()
    # Wraps around
    assert gui.state.selected_index == 4


def test_gui_select_navigates_to_section():
    gui = NayDoeV1GUI()
    gui.state.selected_index = 0  # DASHBOARD
    section = gui.select()
    assert section == MenuSection.DASHBOARD
    assert gui.state.active_section == MenuSection.DASHBOARD


def test_gui_back_returns_to_main():
    gui = NayDoeV1GUI()
    gui.state.active_section = MenuSection.DASHBOARD
    gui.back()
    assert gui.state.active_section == MenuSection.MAIN


def test_gui_render_main_menu():
    gui = NayDoeV1GUI()
    frame = gui.render_frame()
    assert isinstance(frame, DisplayFrame)
    assert gui.get_status()["frames_rendered"] == 1


def test_gui_render_all_sections():
    gui = NayDoeV1GUI()
    for section in MenuSection:
        gui.state.active_section = section
        frame = gui.render_frame()
        assert isinstance(frame, DisplayFrame)


def test_gui_update_device_status():
    gui = NayDoeV1GUI()
    gui.update_device_status(ble=True, wifi=True, lora=False, cloud=True,
                             devices=["ESP32-01", "LoRa-02"])
    assert gui.state.ble_active is True
    assert gui.state.wifi_active is True
    assert gui.state.lora_active is False
    assert gui.state.cloud_synced is True
    assert len(gui.state.connected_devices) == 2


def test_gui_animation_frame_increments():
    gui = NayDoeV1GUI()
    for _ in range(5):
        gui.render_frame()
    assert gui.state.animation_frame == 5


def test_gui_status_bar_rendered():
    gui = NayDoeV1GUI()
    gui.update_device_status(ble=True)
    frame = gui.render_frame()
    # Status bar row pixels should contain some set pixels
    y = DISPLAY_HEIGHT - 8
    row_pixels = frame.pixels[y * DISPLAY_WIDTH:(y + 1) * DISPLAY_WIDTH]
    assert any(row_pixels), "Status bar row should have set pixels"
