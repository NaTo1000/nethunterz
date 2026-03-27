"""NayDoeV1 boot splash screens and animated boot sequences."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from .gui import DisplayFrame, DISPLAY_WIDTH, DISPLAY_HEIGHT

logger = logging.getLogger("nethunterz.flipper.splash_screen")


class SplashMode(Enum):
    BOOT = "boot"
    SCREENSAVER = "screensaver"
    IDLE = "idle"


# NayDoeV1 bot pixel art (16×16 sprite, typewriter aesthetic)
NAYDOEV1_BOT_SPRITE = [
    "  ######  ",
    " #      # ",
    "# ^    ^ #",
    "#   __   #",
    " # ---- # ",
    "  ######  ",
    "   ||||   ",
    "  ######  ",
    " #|    |# ",
    "#  |  |  #",
    "    ||||  ",
]

# Flipper dolphin pixel art (16×16 sprite)
FLIPPER_DOLPHIN_SPRITE = [
    "    ####  ",
    "   #    # ",
    "  #  ..  #",
    " #   __   ",
    "  ##      ",
    " #  ###   ",
    "#    # #  ",
    " ####     ",
]

# Typewriter font one-liners for boot sequence
BOOT_MESSAGES = [
    "INITIALISING NETHUNTERZ STACK...",
    "LOADING NAYDOEV1 CONDUCTOR...",
    "CONNECTING BLE BRIDGE...",
    "SYNCING CLOUD FILESYSTEM...",
    "GROK-420 ORCHESTRATOR: ONLINE",
    "CHAIMERA AI: STAND BY...",
    "SECURITY MODULES: ACTIVE",
    ">>> SYSTEM READY <<<",
]


@dataclass
class SplashFrame:
    """A splash screen animation frame with metadata."""

    display: DisplayFrame = field(default_factory=DisplayFrame)
    duration_ms: int = 100
    typewriter_text: str = ""
    typewriter_pos: int = 0


def _draw_sprite(frame: DisplayFrame, sprite: list[str], ox: int, oy: int) -> None:
    """Draw a text sprite onto a display frame at offset (ox, oy)."""
    for row, line in enumerate(sprite):
        for col, ch in enumerate(line):
            if ch != " ":
                frame.set_pixel(ox + col, oy + row)


def _render_boot_frame(msg_index: int, char_index: int, anim_tick: int) -> DisplayFrame:
    """Render a single frame of the boot animation."""
    frame = DisplayFrame()

    # Outer border
    frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    # Title bar
    frame.draw_text(4, 3, "NayDoeV1 // NetHunterz FW")
    frame.draw_rect(0, 11, DISPLAY_WIDTH, 1, filled=True)

    # NayDoeV1 bot sprite (left side)
    sprite_x = 2 + (anim_tick % 4)
    _draw_sprite(frame, NAYDOEV1_BOT_SPRITE, sprite_x, 14)

    # Flipper dolphin sprite (right side, mirrored animation)
    dolphin_x = DISPLAY_WIDTH - 14 - (anim_tick % 4)
    _draw_sprite(frame, FLIPPER_DOLPHIN_SPRITE, dolphin_x, 14)

    # Typewriter boot messages
    for i, msg in enumerate(BOOT_MESSAGES[:msg_index]):
        y = 14 + i * 6
        if y < DISPLAY_HEIGHT - 10:
            frame.draw_text(2, y, msg[:22])

    # Current line with typewriter cursor
    if msg_index < len(BOOT_MESSAGES):
        current = BOOT_MESSAGES[msg_index][:char_index]
        y = 14 + msg_index * 6
        if y < DISPLAY_HEIGHT - 10:
            cursor = "_" if anim_tick % 2 == 0 else " "
            frame.draw_text(2, y, (current + cursor)[:22])

    return frame


class SplashScreen:
    """
    NayDoeV1 boot splash screen and animated sequence manager.

    Manages boot animation, idle screensavers, and custom splash
    screens for the Flipper Zero 128×64 monochrome display.
    """

    def __init__(self, simulation: bool = True) -> None:
        self.simulation = simulation
        self._mode = SplashMode.BOOT
        self._current_frame_index = 0
        self._frames: list[SplashFrame] = []
        self._on_complete: Optional[Callable] = None
        logger.info("SplashScreen initialised (sim=%s)", simulation)

    # ------------------------------------------------------------------
    # Boot sequence
    # ------------------------------------------------------------------

    def build_boot_sequence(self) -> list[SplashFrame]:
        """Build the full NayDoeV1 animated boot sequence."""
        frames: list[SplashFrame] = []
        anim_tick = 0

        # Phase 1: Logo reveal (16 frames)
        for tick in range(16):
            df = DisplayFrame()
            df.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
            # Wipe-in effect: reveal logo line by line
            for row in range(min(tick * 4, DISPLAY_HEIGHT)):
                df.draw_text(2, row, NAYDOEV1_BOT_SPRITE[row % len(NAYDOEV1_BOT_SPRITE)])
            df.draw_text(20, 28, "NayDoeV1")
            df.draw_text(14, 38, "NetHunterz v1.0")
            frames.append(SplashFrame(display=df, duration_ms=80, typewriter_text=""))
            anim_tick += 1

        # Phase 2: Typewriter boot messages
        for msg_idx in range(len(BOOT_MESSAGES)):
            msg = BOOT_MESSAGES[msg_idx]
            for char_idx in range(len(msg) + 1):
                df = _render_boot_frame(msg_idx, char_idx, anim_tick)
                frames.append(SplashFrame(
                    display=df,
                    duration_ms=40,
                    typewriter_text=msg[:char_idx],
                    typewriter_pos=char_idx,
                ))
                anim_tick += 1

        # Phase 3: Hold on "SYSTEM READY" with blinking border
        for blink in range(8):
            df = _render_boot_frame(len(BOOT_MESSAGES), 0, blink)
            if blink % 2 == 0:
                df.draw_rect(1, 1, DISPLAY_WIDTH - 2, DISPLAY_HEIGHT - 2)
            frames.append(SplashFrame(display=df, duration_ms=150))

        self._frames = frames
        self._current_frame_index = 0
        logger.info("Boot sequence built: %d frames", len(frames))
        return frames

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    async def play_boot_sequence(self, frame_callback: Optional[Callable] = None) -> None:
        """Play the complete boot sequence asynchronously."""
        frames = self.build_boot_sequence()
        self._mode = SplashMode.BOOT
        for frame in frames:
            self._current_frame_index += 1
            if frame_callback:
                frame_callback(frame)
            await asyncio.sleep(frame.duration_ms / 1000.0 if not self.simulation else 0)
        logger.info("Boot sequence complete")
        if self._on_complete:
            self._on_complete()

    def get_current_frame(self) -> Optional[SplashFrame]:
        if self._frames and self._current_frame_index < len(self._frames):
            return self._frames[self._current_frame_index]
        return None

    def set_on_complete(self, callback: Callable) -> None:
        self._on_complete = callback

    # ------------------------------------------------------------------
    # Screensaver
    # ------------------------------------------------------------------

    def build_screensaver_frame(self, tick: int) -> DisplayFrame:
        """Render an idle screensaver frame with NayDoeV1 bot bouncing."""
        frame = DisplayFrame()
        frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        # Bouncing bot
        bx = (tick * 3) % (DISPLAY_WIDTH - 12)
        by = 10 + abs(((tick * 2) % 44) - 22)
        _draw_sprite(frame, NAYDOEV1_BOT_SPRITE, bx, by)
        frame.draw_text(2, DISPLAY_HEIGHT - 10, "NayDoeV1 // IDLE")
        return frame

    def get_status(self) -> dict:
        return {
            "mode": self._mode.value,
            "frame_index": self._current_frame_index,
            "total_frames": len(self._frames),
            "simulation": self.simulation,
        }
