"""JESSICA core engine — boots the platform, loads config, and dispatches to the
appropriate runtime mode (conductor, chimera, worker, monitor, ai, or full
autonomous)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("jessica.core.engine")

CONFIG_DIR = Path(os.getenv("JESSICA_HOME", Path(__file__).resolve().parents[2])) / "configs"


class RuntimeMode(str, Enum):
    """Supported platform runtime modes."""

    AUTONOMOUS = "autonomous"
    CONDUCTOR = "conductor"
    CHIMERA = "chimera"
    WORKER = "worker"
    MONITOR = "monitor"
    AI = "ai"


@dataclass
class JessicaConfig:
    """Centralised platform configuration assembled from the YAML config files."""

    mode: RuntimeMode = RuntimeMode.AUTONOMOUS
    kali_suite: dict[str, Any] = field(default_factory=dict)
    blackarch_suite: dict[str, Any] = field(default_factory=dict)
    pineap_suite: dict[str, Any] = field(default_factory=dict)
    orchestration: dict[str, Any] = field(default_factory=dict)
    bind_address: str = "0.0.0.0"
    bind_port: int = 9000

    # ── helpers ──────────────────────────────────────────

    @property
    def chimera_cfg(self) -> dict[str, Any]:
        return self.orchestration.get("chimera", {})

    @property
    def conductorx_cfg(self) -> dict[str, Any]:
        return self.orchestration.get("conductorx", {})

    @property
    def monitoring_cfg(self) -> dict[str, Any]:
        return self.orchestration.get("monitoring", {})

    @property
    def ai_cfg(self) -> dict[str, Any]:
        return self.orchestration.get("ai_integration", {})


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML config file and return its contents as a dict."""
    if not path.exists():
        logger.warning("Config file not found: %s", path)
        return {}
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def load_config(
    mode: RuntimeMode = RuntimeMode.AUTONOMOUS,
    bind_address: str = "0.0.0.0",
    bind_port: int = 9000,
) -> JessicaConfig:
    """Load all YAML configuration files and return a unified *JessicaConfig*."""
    cfg = JessicaConfig(
        mode=mode,
        kali_suite=_load_yaml(CONFIG_DIR / "kali-suite.yml"),
        blackarch_suite=_load_yaml(CONFIG_DIR / "blackarch-suite.yml"),
        pineap_suite=_load_yaml(CONFIG_DIR / "pineap-suite.yml"),
        orchestration=_load_yaml(CONFIG_DIR / "orchestration.yml"),
        bind_address=bind_address,
        bind_port=bind_port,
    )
    logger.info(
        "Configuration loaded — mode=%s  bind=%s:%d",
        cfg.mode.value,
        cfg.bind_address,
        cfg.bind_port,
    )
    return cfg


class JessicaEngine:
    """Top‑level engine that wires all sub‑systems together and runs the
    selected mode.

    Usage::

        engine = JessicaEngine(config)
        await engine.start()
    """

    def __init__(self, config: JessicaConfig) -> None:
        self.config = config
        self._running = False
        self._components: dict[str, Any] = {}

    # ── lifecycle ────────────────────────────────────────

    async def start(self) -> None:
        """Start the engine in the configured mode."""
        logger.info("Starting iFINITEAi2025JESSICAi Huntress Edition v%s", "2025.1.0")
        self._running = True

        mode = self.config.mode
        if mode == RuntimeMode.AUTONOMOUS:
            await self._start_autonomous()
        elif mode == RuntimeMode.CONDUCTOR:
            await self._start_conductor()
        elif mode == RuntimeMode.CHIMERA:
            await self._start_chimera()
        elif mode == RuntimeMode.WORKER:
            await self._start_worker()
        elif mode == RuntimeMode.MONITOR:
            await self._start_monitor()
        elif mode == RuntimeMode.AI:
            await self._start_ai()
        else:
            raise ValueError(f"Unknown runtime mode: {mode}")

    async def stop(self) -> None:
        """Gracefully shut down all running components."""
        logger.info("Shutting down JESSICA engine …")
        self._running = False
        for name, component in reversed(list(self._components.items())):
            logger.info("Stopping component: %s", name)
            if hasattr(component, "stop"):
                await component.stop()
        self._components.clear()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── private bootstrap helpers ────────────────────────

    async def _start_autonomous(self) -> None:
        """Full autonomous mode — conductor + chimera + monitor + AI all in‑process."""
        from jessica.ai.huggingface import HuggingFaceLayer
        from jessica.chimera.chain import ChimeraChainEngine
        from jessica.conductor.conductorx import ConductorX
        from jessica.core.monitor import AutonomousMonitor

        conductor = ConductorX(self.config.conductorx_cfg)
        chimera = ChimeraChainEngine(self.config.chimera_cfg)
        monitor = AutonomousMonitor(self.config.monitoring_cfg)
        ai_layer = HuggingFaceLayer(self.config.ai_cfg)

        self._components["conductorx"] = conductor
        self._components["chimera"] = chimera
        self._components["monitor"] = monitor
        self._components["ai"] = ai_layer

        await conductor.start()
        await chimera.start()
        await monitor.start()
        await ai_layer.start()
        logger.info("Autonomous mode fully operational.")

    async def _start_conductor(self) -> None:
        from jessica.conductor.conductorx import ConductorX

        conductor = ConductorX(self.config.conductorx_cfg)
        self._components["conductorx"] = conductor
        await conductor.start()

    async def _start_chimera(self) -> None:
        from jessica.chimera.chain import ChimeraChainEngine

        chimera = ChimeraChainEngine(self.config.chimera_cfg)
        self._components["chimera"] = chimera
        await chimera.start()

    async def _start_worker(self) -> None:
        from jessica.conductor.orchestrator import OrchestratorWorker

        worker = OrchestratorWorker(self.config.conductorx_cfg)
        self._components["worker"] = worker
        await worker.start()

    async def _start_monitor(self) -> None:
        from jessica.core.monitor import AutonomousMonitor

        monitor = AutonomousMonitor(self.config.monitoring_cfg)
        self._components["monitor"] = monitor
        await monitor.start()

    async def _start_ai(self) -> None:
        from jessica.ai.huggingface import HuggingFaceLayer

        ai_layer = HuggingFaceLayer(self.config.ai_cfg)
        self._components["ai"] = ai_layer
        await ai_layer.start()
