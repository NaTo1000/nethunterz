"""Tests for 80s scene animations and splash screen."""
from __future__ import annotations

import pytest

from flipper.scenes_80s import Scenes80s, SceneType, SceneFrame, SCENE_TAGLINES
from flipper.splash_screen import SplashScreen, SplashMode, SplashFrame
from flipper.gui import DisplayFrame


# ---------------------------------------------------------------------------
# Scenes80s tests
# ---------------------------------------------------------------------------

def test_scenes_80s_initialisation():
    scenes = Scenes80s(simulation=True)
    status = scenes.get_status()
    assert status["active_scene"] is None
    assert status["simulation"] is True


def test_all_scenes_renderable():
    scenes = Scenes80s(simulation=True)
    for scene_type in SceneType:
        scenes.set_scene(scene_type)
        frame = scenes.render_next_frame()
        assert isinstance(frame, SceneFrame)
        assert isinstance(frame.display, DisplayFrame)
        assert frame.scene_type == scene_type
        assert frame.frame_index == 0


def test_scene_tick_increments():
    scenes = Scenes80s(simulation=True)
    scenes.set_scene(SceneType.BAYWATCH)
    for i in range(5):
        frame = scenes.render_next_frame()
        assert frame.frame_index == i


def test_scene_taglines_present():
    for scene_type in SceneType:
        assert scene_type in SCENE_TAGLINES
        assert len(SCENE_TAGLINES[scene_type]) > 0


def test_available_scenes():
    scenes = Scenes80s()
    available = scenes.available_scenes()
    assert len(available) == len(SceneType)
    for scene_type in SceneType:
        assert scene_type.value in available


def test_render_none_without_active_scene():
    scenes = Scenes80s()
    frame = scenes.render_next_frame()
    assert frame is None


def test_scene_reset_on_set():
    scenes = Scenes80s(simulation=True)
    scenes.set_scene(SceneType.TRON)
    for _ in range(10):
        scenes.render_next_frame()
    scenes.set_scene(SceneType.TRON)
    assert scenes._tick == 0


@pytest.mark.asyncio
async def test_play_scene_async():
    scenes = Scenes80s(simulation=True)
    collected: list[SceneFrame] = []
    await scenes.play_scene(SceneType.MIAMI_VICE, num_frames=5,
                            frame_callback=collected.append)
    assert len(collected) == 5


@pytest.mark.asyncio
async def test_all_scenes_playable():
    scenes = Scenes80s(simulation=True)
    for scene_type in SceneType:
        await scenes.play_scene(scene_type, num_frames=3)
    status = scenes.get_status()
    for scene_type in SceneType:
        assert status["rendered_frames"][scene_type.value] >= 3


def test_scenes_status_rendered_frames_tracked():
    scenes = Scenes80s(simulation=True)
    scenes.set_scene(SceneType.KNIGHT_RIDER)
    for _ in range(7):
        scenes.render_next_frame()
    status = scenes.get_status()
    assert status["rendered_frames"][SceneType.KNIGHT_RIDER.value] == 7


# ---------------------------------------------------------------------------
# SplashScreen tests
# ---------------------------------------------------------------------------

def test_splash_screen_initialisation():
    splash = SplashScreen(simulation=True)
    status = splash.get_status()
    assert status["simulation"] is True
    assert status["mode"] == SplashMode.BOOT.value


def test_build_boot_sequence_returns_frames():
    splash = SplashScreen(simulation=True)
    frames = splash.build_boot_sequence()
    assert len(frames) > 0
    for f in frames:
        assert isinstance(f, SplashFrame)
        assert isinstance(f.display, DisplayFrame)


def test_screensaver_frame_renderable():
    splash = SplashScreen(simulation=True)
    for tick in range(10):
        frame = splash.build_screensaver_frame(tick)
        assert isinstance(frame, DisplayFrame)


@pytest.mark.asyncio
async def test_play_boot_sequence():
    splash = SplashScreen(simulation=True)
    collected: list[SplashFrame] = []
    await splash.play_boot_sequence(frame_callback=collected.append)
    assert len(collected) > 0


@pytest.mark.asyncio
async def test_play_boot_sequence_callback_invoked():
    splash = SplashScreen(simulation=True)
    count = {"n": 0}

    def cb(_f):
        count["n"] += 1

    await splash.play_boot_sequence(frame_callback=cb)
    assert count["n"] > 10  # Should have at least 16 + boot message frames


def test_splash_on_complete_callback():
    splash = SplashScreen(simulation=True)
    fired = {"done": False}
    splash.set_on_complete(lambda: fired.update({"done": True}))
    # Build triggers the callback on play; test callback registration
    assert splash._on_complete is not None
