"""NayDoeV1 80s-themed GUI system for Flipper Zero (128×64 monochrome LCD)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("nethunterz.flipper.gui")

# Flipper Zero display constants
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64


class MenuSection(Enum):
    MAIN = "main"
    DASHBOARD = "dashboard"
    NETWORK_SCANNER = "network_scanner"
    ATTACK_MIRROR = "attack_mirror"
    AI_STATUS = "ai_status"
    SETTINGS = "settings"


# Typewriter font dithering patterns (simulated for 128×64 mono LCD)
DITHER_PATTERNS = {
    "light": 0b10101010,
    "medium": 0b11001100,
    "heavy": 0b11101110,
    "solid": 0b11111111,
}

# NayDoeV1 branding ASCII art (typewriter font style, 128-char wide terminal)
NAYDOEV1_LOGO = [
    " ███╗   ██╗ █████╗ ██╗   ██╗██████╗  ██████╗ ███████╗██╗   ██╗ ██╗",
    " ████╗  ██║██╔══██╗╚██╗ ██╔╝██╔══██╗██╔═══██╗██╔════╝██║   ██║███║",
    " ██╔██╗ ██║███████║ ╚████╔╝ ██║  ██║██║   ██║█████╗  ██║   ██║╚██║",
    " ██║╚██╗██║██╔══██║  ╚██╔╝  ██║  ██║██║   ██║██╔══╝  ╚██╗ ██╔╝ ██║",
    " ██║ ╚████║██║  ██║   ██║   ██████╔╝╚██████╔╝███████╗ ╚████╔╝  ██║",
    " ╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝   ╚═════╝  ╚═════╝ ╚══════╝  ╚═══╝   ╚═╝",
]

# 80s menu items with animated ► indicator
MAIN_MENU_ITEMS = [
    ("► DASHBOARD", MenuSection.DASHBOARD),
    ("► NETWORK SCANNER", MenuSection.NETWORK_SCANNER),
    ("► ATTACK MIRROR", MenuSection.ATTACK_MIRROR),
    ("► AI STATUS", MenuSection.AI_STATUS),
    ("► SETTINGS", MenuSection.SETTINGS),
]


@dataclass
class DisplayFrame:
    """A single 128×64 mono display frame represented as a flat pixel buffer."""

    width: int = DISPLAY_WIDTH
    height: int = DISPLAY_HEIGHT
    pixels: bytearray = field(default_factory=lambda: bytearray(DISPLAY_WIDTH * DISPLAY_HEIGHT))

    def set_pixel(self, x: int, y: int, on: bool = True) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = 1 if on else 0

    def draw_rect(self, x: int, y: int, w: int, h: int, filled: bool = False) -> None:
        for row in range(y, min(y + h, self.height)):
            for col in range(x, min(x + w, self.width)):
                edge = row in (y, y + h - 1) or col in (x, x + w - 1)
                if filled or edge:
                    self.set_pixel(col, row)

    def draw_text(self, x: int, y: int, text: str) -> None:
        """Render text as pixel-art characters (5×7 typewriter font approximation)."""
        for i, ch in enumerate(text):
            cx = x + i * 6
            if cx >= self.width:
                break
            self.set_pixel(cx, y, ord(ch) > 32)

    def apply_dither(self, pattern_key: str = "medium") -> None:
        """Apply a dithering pattern to simulate grayscale depth."""
        pattern = DITHER_PATTERNS.get(pattern_key, DITHER_PATTERNS["medium"])
        for idx in range(len(self.pixels)):
            bit_pos = idx % 8
            if not ((pattern >> (7 - bit_pos)) & 1):
                self.pixels[idx] = 0

    def to_bytes(self) -> bytes:
        return bytes(self.pixels)


@dataclass
class GUIState:
    """Mutable GUI application state."""

    active_section: MenuSection = MenuSection.MAIN
    selected_index: int = 0
    scroll_offset: int = 0
    animation_frame: int = 0
    typewriter_cursor: int = 0
    status_message: str = ""
    connected_devices: list[str] = field(default_factory=list)
    ble_active: bool = False
    wifi_active: bool = False
    lora_active: bool = False
    cloud_synced: bool = False


class NayDoeV1GUI:
    """
    Full operational GUI for Flipper Zero with NayDoeV1 branding.

    Renders onto the 128×64 monochrome LCD using typewriter-font style
    pixel art and 80s-themed animated transitions.
    """

    def __init__(self, simulation: bool = True) -> None:
        self.simulation = simulation
        self.state = GUIState()
        self._frame_history: list[DisplayFrame] = []
        logger.info("NayDoeV1GUI initialised (sim=%s)", simulation)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_up(self) -> None:
        items = self._current_menu_items()
        if items:
            self.state.selected_index = (self.state.selected_index - 1) % len(items)

    def navigate_down(self) -> None:
        items = self._current_menu_items()
        if items:
            self.state.selected_index = (self.state.selected_index + 1) % len(items)

    def select(self) -> Optional[MenuSection]:
        items = self._current_menu_items()
        if items and self.state.selected_index < len(items):
            _, section = items[self.state.selected_index]
            self.state.active_section = section
            self.state.selected_index = 0
            logger.info("GUI navigated to section: %s", section.value)
            return section
        return None

    def back(self) -> None:
        self.state.active_section = MenuSection.MAIN
        self.state.selected_index = 0

    # ------------------------------------------------------------------
    # Frame rendering
    # ------------------------------------------------------------------

    def render_frame(self) -> DisplayFrame:
        """Render the current GUI state into a DisplayFrame."""
        frame = DisplayFrame()
        section = self.state.active_section

        if section == MenuSection.MAIN:
            self._render_main_menu(frame)
        elif section == MenuSection.DASHBOARD:
            self._render_dashboard(frame)
        elif section == MenuSection.NETWORK_SCANNER:
            self._render_network_scanner(frame)
        elif section == MenuSection.ATTACK_MIRROR:
            self._render_attack_mirror(frame)
        elif section == MenuSection.AI_STATUS:
            self._render_ai_status(frame)
        elif section == MenuSection.SETTINGS:
            self._render_settings(frame)

        self._render_status_bar(frame)
        self._frame_history.append(frame)
        self.state.animation_frame += 1
        return frame

    def _render_main_menu(self, frame: DisplayFrame) -> None:
        frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        frame.draw_text(4, 2, "NayDoeV1 // NetHunterz")
        frame.draw_rect(0, 10, DISPLAY_WIDTH, 1, filled=True)
        for idx, (label, _) in enumerate(MAIN_MENU_ITEMS):
            y = 14 + idx * 9
            if idx == self.state.selected_index:
                frame.draw_rect(2, y - 1, DISPLAY_WIDTH - 4, 9, filled=True)
            frame.draw_text(4, y, label)

    def _render_dashboard(self, frame: DisplayFrame) -> None:
        frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        frame.draw_text(2, 2, "[ DEVICE DASHBOARD ]")
        frame.draw_rect(0, 10, DISPLAY_WIDTH, 1, filled=True)
        ble = "ON " if self.state.ble_active else "OFF"
        wifi = "ON " if self.state.wifi_active else "OFF"
        lora = "ON " if self.state.lora_active else "OFF"
        cloud = "SYNC" if self.state.cloud_synced else "IDLE"
        frame.draw_text(2, 14, f"BLE:{ble}  WIFI:{wifi}")
        frame.draw_text(2, 24, f"LORA:{lora}  CLOUD:{cloud}")
        frame.draw_text(2, 34, f"DEVICES: {len(self.state.connected_devices)}")
        for i, dev in enumerate(self.state.connected_devices[:2]):
            frame.draw_text(4, 44 + i * 9, f"  {dev[:20]}")

    def _render_network_scanner(self, frame: DisplayFrame) -> None:
        frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        frame.draw_text(2, 2, "[ MESH SCANNER ]")
        frame.draw_rect(0, 10, DISPLAY_WIDTH, 1, filled=True)
        # Animated seek-and-find radar arc
        af = self.state.animation_frame % 16
        for i in range(af):
            x = 64 + int(30 * (i / 16.0))
            y = 32 + int(10 * (i / 16.0))
            frame.set_pixel(x, y)
        frame.draw_text(2, 52, "SCANNING MESH...")

    def _render_attack_mirror(self, frame: DisplayFrame) -> None:
        frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        frame.draw_text(2, 2, "[ ATTACK MIRROR ]")
        frame.draw_rect(0, 10, DISPLAY_WIDTH, 1, filled=True)
        frame.draw_text(2, 14, "DEFENSIVE STATUS: ACTIVE")
        frame.draw_text(2, 24, "MIRROR MODE: ENABLED")
        frame.draw_text(2, 34, "THREATS MIRRORED: 0")
        frame.draw_text(2, 44, "LAST EVENT: NONE")

    def _render_ai_status(self, frame: DisplayFrame) -> None:
        frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        frame.draw_text(2, 2, "[ AI: NayDoeV1 ]")
        frame.draw_rect(0, 10, DISPLAY_WIDTH, 1, filled=True)
        frame.draw_text(2, 14, "CONDUCTOR: ONLINE")
        frame.draw_text(2, 24, "GROK-420: ACTIVE")
        frame.draw_text(2, 34, "DECISIONS: 0")
        frame.draw_text(2, 44, "CHAIMERA: IDLE")

    def _render_settings(self, frame: DisplayFrame) -> None:
        frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        frame.draw_text(2, 2, "[ SETTINGS ]")
        frame.draw_rect(0, 10, DISPLAY_WIDTH, 1, filled=True)
        frame.draw_text(2, 14, "THEME: 80s RETRO")
        frame.draw_text(2, 24, "ANIM: BAYWATCH")
        frame.draw_text(2, 34, "CLOUD: GOOGLE DRIVE")
        frame.draw_text(2, 44, "SECURITY: MAX")

    def _render_status_bar(self, frame: DisplayFrame) -> None:
        """Render the bottom status bar with NayDoeV1 brand icons."""
        y = DISPLAY_HEIGHT - 8
        frame.draw_rect(0, y, DISPLAY_WIDTH, 1, filled=True)
        ble_icon = "B" if self.state.ble_active else "b"
        wifi_icon = "W" if self.state.wifi_active else "w"
        lora_icon = "L" if self.state.lora_active else "l"
        cloud_icon = "C" if self.state.cloud_synced else "c"
        af = self.state.animation_frame
        ticker = ">" * ((af % 4) + 1)
        frame.draw_text(2, y + 1, f"{ble_icon} {wifi_icon} {lora_icon} {cloud_icon}  {ticker}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_menu_items(self) -> list:
        if self.state.active_section == MenuSection.MAIN:
            return MAIN_MENU_ITEMS
        return []

    def update_device_status(
        self,
        ble: bool = False,
        wifi: bool = False,
        lora: bool = False,
        cloud: bool = False,
        devices: Optional[list[str]] = None,
    ) -> None:
        self.state.ble_active = ble
        self.state.wifi_active = wifi
        self.state.lora_active = lora
        self.state.cloud_synced = cloud
        if devices is not None:
            self.state.connected_devices = devices

    def get_status(self) -> dict:
        return {
            "section": self.state.active_section.value,
            "selected_index": self.state.selected_index,
            "animation_frame": self.state.animation_frame,
            "frames_rendered": len(self._frame_history),
            "simulation": self.simulation,
        }
