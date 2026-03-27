"""80s movie/TV scene animations for the Flipper Zero 128×64 LCD."""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from .gui import DisplayFrame, DISPLAY_WIDTH, DISPLAY_HEIGHT

logger = logging.getLogger("nethunterz.flipper.scenes_80s")


class SceneType(Enum):
    BAYWATCH = "baywatch"
    MIAMI_VICE = "miami_vice"
    KNIGHT_RIDER = "knight_rider"
    BIONIC_MAN = "bionic_man"
    TOP_GUN = "top_gun"
    TRON = "tron"
    BACK_TO_THE_FUTURE = "back_to_the_future"


# One-liner taglines per scene (typewriter style)
SCENE_TAGLINES = {
    SceneType.BAYWATCH: "RUNNING IN SLOW-MO... BEACH PATROL ONLINE",
    SceneType.MIAMI_VICE: "VICE CITY: NEON NEVER DIES",
    SceneType.KNIGHT_RIDER: "KITT SCANNER ACTIVE... TURBO BOOST!",
    SceneType.BIONIC_MAN: "BIONIC ENHANCEMENT: 6 MILLION CYCLES",
    SceneType.TOP_GUN: "DANGER ZONE // MAVERICK PROTOCOL",
    SceneType.TRON: "ENTERING THE GRID... DEREZZED",
    SceneType.BACK_TO_THE_FUTURE: "88MPH! FLUX CAPACITOR: FLUXING",
}

# Scene colour palette labels (dithering approximation on mono LCD)
SCENE_PALETTES = {
    SceneType.BAYWATCH: "warm_orange",
    SceneType.MIAMI_VICE: "pink_cyan",
    SceneType.KNIGHT_RIDER: "red_black",
    SceneType.BIONIC_MAN: "blue_silver",
    SceneType.TOP_GUN: "sky_gold",
    SceneType.TRON: "neon_blue",
    SceneType.BACK_TO_THE_FUTURE: "lightning_chrome",
}


@dataclass
class SceneFrame:
    """One frame of an 80s scene animation."""

    display: DisplayFrame = field(default_factory=DisplayFrame)
    scene_type: SceneType = SceneType.BAYWATCH
    frame_index: int = 0
    tagline: str = ""
    duration_ms: int = 80


# ---------------------------------------------------------------------------
# Scene frame generators
# ---------------------------------------------------------------------------

def _baywatch_frame(tick: int) -> DisplayFrame:
    """Dolphin + NayDoeV1 bot running on the beach, slow-motion Baywatch style."""
    frame = DisplayFrame()
    frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    # Horizon line (ocean / sand border)
    for x in range(DISPLAY_WIDTH):
        wave_y = 38 + int(3 * abs(((x + tick * 2) % 20) - 10) / 10)
        frame.set_pixel(x, wave_y)

    # Sun (top right, dithered circle)
    sun_x, sun_y, sun_r = 110, 8, 6
    for angle_step in range(32):
        angle = 2 * math.pi * angle_step / 32
        px = int(sun_x + sun_r * math.cos(angle))
        py = int(sun_y + sun_r * math.sin(angle))
        frame.set_pixel(px, py)

    # Running characters (slow-motion effect: fractional x steps)
    run_offset = (tick * 2) % (DISPLAY_WIDTH - 20)

    # NayDoeV1 bot running
    bx = run_offset
    by = 24 + (tick % 3)  # slight vertical bob
    for row, line in enumerate(["O", "|", "/"]):
        for _col, _ch in enumerate(line):
            frame.set_pixel(bx + _col, by + row)

    # Flipper dolphin running
    dx = run_offset + 12
    dy = 24 + ((tick + 1) % 3)
    for row, line in enumerate(["~>", " >"]):
        for col, ch in enumerate(line):
            if ch != " ":
                frame.set_pixel(dx + col, dy + row)

    # Tagline
    tagline = SCENE_TAGLINES[SceneType.BAYWATCH]
    visible = tagline[:(tick % (len(tagline) + 8))]
    frame.draw_text(2, DISPLAY_HEIGHT - 10, visible[:21])
    return frame


def _miami_vice_frame(tick: int) -> DisplayFrame:
    """Dolphin + NayDoeV1 in a convertible, neon-lit streets."""
    frame = DisplayFrame()
    frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    # Neon road lines scrolling
    for lane_y in (32, 40, 48):
        for seg in range(8):
            x = ((seg * 16) - tick * 4) % DISPLAY_WIDTH
            for lx in range(8):
                frame.set_pixel(x + lx, lane_y)

    # Neon buildings silhouette
    buildings = [(0, 20, 10, 30), (12, 10, 8, 40), (22, 18, 14, 32),
                 (38, 5, 10, 45), (50, 15, 12, 35), (64, 8, 9, 42)]
    for bx, by, bw, bh in buildings:
        sx = (bx - tick * 2) % DISPLAY_WIDTH
        frame.draw_rect(sx, by, bw, bh)

    # Convertible car
    car_x = 30 + (tick % 6) - 3
    car_y = 50
    frame.draw_rect(car_x, car_y, 40, 10)
    frame.draw_rect(car_x + 5, car_y - 6, 25, 8)
    # Characters in car
    frame.draw_text(car_x + 6, car_y - 4, "ND FD")

    tagline = SCENE_TAGLINES[SceneType.MIAMI_VICE]
    visible = tagline[:(tick % (len(tagline) + 8))]
    frame.draw_text(2, DISPLAY_HEIGHT - 10, visible[:21])
    return frame


def _knight_rider_frame(tick: int) -> DisplayFrame:
    """KITT scanner bar animation, NayDoeV1 behind the wheel."""
    frame = DisplayFrame()
    frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    # KITT car body
    frame.draw_rect(14, 30, 100, 20)
    frame.draw_rect(28, 22, 68, 10)

    # Windshield
    frame.draw_rect(30, 23, 64, 8)

    # Driver (NayDoeV1 bot silhouette)
    frame.draw_text(48, 24, "ND")

    # KITT scanner bar (bouncing red LED strip)
    scanner_width = 20
    bounce = tick % (80 - scanner_width)
    scanner_x = 18 + (bounce if tick % (2 * (80 - scanner_width)) < (80 - scanner_width)
                      else (80 - scanner_width) - bounce)
    for sx in range(scanner_width):
        frame.set_pixel(scanner_x + sx, 40)
        frame.set_pixel(scanner_x + sx, 41)

    # Road
    for rx in range(0, DISPLAY_WIDTH, 16):
        stripe_x = (rx - tick * 6) % DISPLAY_WIDTH
        for s in range(8):
            frame.set_pixel(stripe_x + s, 56)

    tagline = SCENE_TAGLINES[SceneType.KNIGHT_RIDER]
    visible = tagline[:(tick % (len(tagline) + 8))]
    frame.draw_text(2, DISPLAY_HEIGHT - 10, visible[:21])
    return frame


def _bionic_man_frame(tick: int) -> DisplayFrame:
    """Dolphin with bionic enhancements, slow-motion scanlines."""
    frame = DisplayFrame()
    frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    # Scan-line effect (every other row, alternating with tick)
    for y in range(0, DISPLAY_HEIGHT, 2):
        if (y + tick) % 4 < 2:
            for x in range(DISPLAY_WIDTH):
                frame.set_pixel(x, y)

    # Bionic dolphin silhouette with mechanical arm overlay
    dolph_x = 20 + (tick % 4)
    dolph_y = 20 + abs((tick % 14) - 7)

    # Body
    frame.draw_rect(dolph_x, dolph_y, 30, 15)
    # Bionic limb (circuit lines)
    for arm_y in range(dolph_y + 2, dolph_y + 13, 3):
        frame.set_pixel(dolph_x + 30, arm_y)
        frame.set_pixel(dolph_x + 32, arm_y)
        frame.set_pixel(dolph_x + 34, arm_y)
    # Eye LED
    blink = tick % 8 < 6
    if blink:
        frame.set_pixel(dolph_x + 5, dolph_y + 5)
        frame.set_pixel(dolph_x + 6, dolph_y + 5)

    # "SIX MILLION CYCLE UPGRADE" text
    frame.draw_text(2, 2, "BIONIC UPGRADE ACTIVE")

    tagline = SCENE_TAGLINES[SceneType.BIONIC_MAN]
    visible = tagline[:(tick % (len(tagline) + 8))]
    frame.draw_text(2, DISPLAY_HEIGHT - 10, visible[:21])
    return frame


def _top_gun_frame(tick: int) -> DisplayFrame:
    """Dolphin + NayDoeV1 in aviator shades, jet flyby."""
    frame = DisplayFrame()
    frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    # Cloud layers
    for cloud_i in range(3):
        cx = ((cloud_i * 42 + tick * 3) % DISPLAY_WIDTH)
        cy = 8 + cloud_i * 5
        frame.draw_rect(cx, cy, 20, 5)

    # Jet (top-to-bottom swoosh)
    jet_x = (tick * 5) % DISPLAY_WIDTH
    jet_y = 20 + int(8 * math.sin(tick * 0.3))
    # Jet body
    for jx in range(16):
        frame.set_pixel(jet_x + jx, jet_y)
    # Wings
    for wx in range(5):
        frame.set_pixel(jet_x + 4 + wx, jet_y - 2 + wx)
        frame.set_pixel(jet_x + 4 + wx, jet_y + 2 - wx)

    # Aviator duo portrait
    frame.draw_rect(10, 36, 18, 18)
    frame.draw_rect(34, 36, 18, 18)
    frame.draw_text(11, 40, "ND")
    frame.draw_text(35, 40, "FD")
    frame.draw_text(11, 49, "8o")  # sunglasses
    frame.draw_text(35, 49, "8o")

    tagline = SCENE_TAGLINES[SceneType.TOP_GUN]
    visible = tagline[:(tick % (len(tagline) + 8))]
    frame.draw_text(2, DISPLAY_HEIGHT - 10, visible[:21])
    return frame


def _tron_frame(tick: int) -> DisplayFrame:
    """Both characters in a digital grid world with neon glow effects."""
    frame = DisplayFrame()
    frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    # Grid lines (perspective road)
    for gx in range(0, DISPLAY_WIDTH, 8):
        for gy in range(0, DISPLAY_HEIGHT, 8):
            frame.set_pixel((gx + tick) % DISPLAY_WIDTH, gy)
            frame.set_pixel(gx, (gy + tick // 2) % DISPLAY_HEIGHT)

    # Light cycle trails
    lx = (tick * 4) % (DISPLAY_WIDTH - 10)
    for trail in range(12):
        frame.set_pixel(lx - trail, 32)
        frame.set_pixel(lx - trail, 33)

    lx2 = DISPLAY_WIDTH - 10 - (tick * 3) % (DISPLAY_WIDTH - 10)
    for trail in range(10):
        frame.set_pixel(lx2 + trail, 26)
        frame.set_pixel(lx2 + trail, 27)

    # Characters (glowing outlines)
    frame.draw_rect(lx, 28, 8, 10)
    frame.draw_text(lx + 1, 30, "ND")
    frame.draw_rect(lx2 - 2, 22, 8, 10)
    frame.draw_text(lx2 - 1, 24, "FD")

    tagline = SCENE_TAGLINES[SceneType.TRON]
    visible = tagline[:(tick % (len(tagline) + 8))]
    frame.draw_text(2, DISPLAY_HEIGHT - 10, visible[:21])
    return frame


def _bttf_frame(tick: int) -> DisplayFrame:
    """DeLorean time travel sequence with flux capacitor animation."""
    frame = DisplayFrame()
    frame.draw_rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)

    # Lightning bolts (simulated)
    for bolt in range(3):
        bx = (bolt * 40 + tick * 7) % DISPLAY_WIDTH
        for by in range(0, DISPLAY_HEIGHT, 4):
            frame.set_pixel(bx + (by % 3), by)

    # DeLorean body
    car_x = 18 + int(6 * math.sin(tick * 0.4))
    car_y = 35
    frame.draw_rect(car_x, car_y, 80, 16)
    frame.draw_rect(car_x + 10, car_y - 8, 50, 10)
    # Gull-wing doors
    frame.draw_rect(car_x + 12, car_y - 14, 18, 8)
    frame.draw_rect(car_x + 40, car_y - 14, 18, 8)

    # Flux capacitor (Y-shape, blinking)
    fc_x, fc_y = car_x + 36, car_y + 2
    if tick % 4 < 3:
        frame.set_pixel(fc_x, fc_y)
        frame.set_pixel(fc_x, fc_y + 1)
        frame.set_pixel(fc_x - 2, fc_y + 3)
        frame.set_pixel(fc_x + 2, fc_y + 3)

    # Speed readout
    speed_str = f"{(tick * 5) % 89 + 1}MPH"
    frame.draw_text(car_x + 22, car_y + 4, speed_str)

    tagline = SCENE_TAGLINES[SceneType.BACK_TO_THE_FUTURE]
    visible = tagline[:(tick % (len(tagline) + 8))]
    frame.draw_text(2, DISPLAY_HEIGHT - 10, visible[:21])
    return frame


# Map scene types to their generator functions
_SCENE_GENERATORS = {
    SceneType.BAYWATCH: _baywatch_frame,
    SceneType.MIAMI_VICE: _miami_vice_frame,
    SceneType.KNIGHT_RIDER: _knight_rider_frame,
    SceneType.BIONIC_MAN: _bionic_man_frame,
    SceneType.TOP_GUN: _top_gun_frame,
    SceneType.TRON: _tron_frame,
    SceneType.BACK_TO_THE_FUTURE: _bttf_frame,
}


class Scenes80s:
    """
    Manager for all 80s movie/TV scene animations.

    Scenes can be used as idle animations, boot screens, or screensavers.
    Each scene uses pixel art and typewriter-style text overlays.
    """

    def __init__(self, simulation: bool = True) -> None:
        self.simulation = simulation
        self._active_scene: Optional[SceneType] = None
        self._tick = 0
        self._rendered_frames: dict[SceneType, int] = {s: 0 for s in SceneType}
        logger.info("Scenes80s initialised (sim=%s)", simulation)

    def set_scene(self, scene: SceneType) -> None:
        self._active_scene = scene
        self._tick = 0
        logger.info("Scene set: %s", scene.value)

    def render_next_frame(self) -> Optional[SceneFrame]:
        """Render the next frame of the currently active scene."""
        if self._active_scene is None:
            return None
        generator = _SCENE_GENERATORS[self._active_scene]
        display = generator(self._tick)
        sf = SceneFrame(
            display=display,
            scene_type=self._active_scene,
            frame_index=self._tick,
            tagline=SCENE_TAGLINES[self._active_scene],
            duration_ms=80,
        )
        self._rendered_frames[self._active_scene] += 1
        self._tick += 1
        return sf

    async def play_scene(
        self,
        scene: SceneType,
        num_frames: int = 120,
        frame_callback: Optional[Callable] = None,
    ) -> None:
        """Play a scene asynchronously for `num_frames` frames."""
        self.set_scene(scene)
        for _ in range(num_frames):
            sf = self.render_next_frame()
            if sf and frame_callback:
                frame_callback(sf)
            await asyncio.sleep(sf.duration_ms / 1000.0 if not self.simulation else 0)
        logger.info("Scene %s finished (%d frames)", scene.value, num_frames)

    def available_scenes(self) -> list[str]:
        return [s.value for s in SceneType]

    def get_status(self) -> dict:
        return {
            "active_scene": self._active_scene.value if self._active_scene else None,
            "tick": self._tick,
            "rendered_frames": {k.value: v for k, v in self._rendered_frames.items()},
            "simulation": self.simulation,
        }
