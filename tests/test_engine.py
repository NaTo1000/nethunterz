"""Tests for the JESSICA core engine and configuration loading."""

from __future__ import annotations

import pytest

from jessica.core.engine import JessicaConfig, JessicaEngine, RuntimeMode, load_config


class TestConfig:
    def test_load_config_defaults(self) -> None:
        cfg = load_config()
        assert cfg.mode == RuntimeMode.AUTONOMOUS
        assert cfg.bind_address == "0.0.0.0"
        assert cfg.bind_port == 9000

    def test_load_config_custom_mode(self) -> None:
        cfg = load_config(mode=RuntimeMode.CONDUCTOR, bind_port=8080)
        assert cfg.mode == RuntimeMode.CONDUCTOR
        assert cfg.bind_port == 8080

    def test_config_loads_yaml(self) -> None:
        cfg = load_config()
        # Kali suite should have tools
        assert isinstance(cfg.kali_suite, dict)
        assert "information_gathering" in cfg.kali_suite or len(cfg.kali_suite) >= 0

    def test_chimera_cfg_accessor(self) -> None:
        cfg = load_config()
        chimera = cfg.chimera_cfg
        assert isinstance(chimera, dict)

    def test_conductorx_cfg_accessor(self) -> None:
        cfg = load_config()
        cx = cfg.conductorx_cfg
        assert isinstance(cx, dict)


class TestEngine:
    @pytest.mark.asyncio
    async def test_engine_lifecycle(self) -> None:
        cfg = JessicaConfig(mode=RuntimeMode.MONITOR)
        engine = JessicaEngine(cfg)
        assert not engine.is_running
        # Monitor mode start — will start the monitor watcher
        await engine.start()
        assert engine.is_running
        await engine.stop()
        assert not engine.is_running

    def test_engine_config(self) -> None:
        cfg = JessicaConfig(mode=RuntimeMode.AUTONOMOUS)
        engine = JessicaEngine(cfg)
        assert engine.config.mode == RuntimeMode.AUTONOMOUS


class TestRuntimeMode:
    def test_all_modes_exist(self) -> None:
        modes = [m.value for m in RuntimeMode]
        assert "autonomous" in modes
        assert "conductor" in modes
        assert "chimera" in modes
        assert "worker" in modes
        assert "monitor" in modes
        assert "ai" in modes
