"""
firmware_builder.py – Automated firmware build pipeline for Flipper Zero.

Builds firmware from source using the Flipper Build Tool (fbt) or a
Docker-based cross-compilation environment. Supports custom NRF-Pingequa
plugins and NetHunterZ-specific patches.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Build configuration
# ---------------------------------------------------------------------------

@dataclass
class BuildConfig:
    """Describes a firmware build job."""
    target: str = "f7"                  # f7 = Flipper Zero hardware target
    build_type: str = "release"         # debug | release
    extra_defines: Dict[str, str] = None  # type: ignore
    custom_plugins: List[str] = None      # type: ignore
    output_dir: str = "build/firmware"
    source_dir: str = "."
    docker_image: str = "flipperdevices/flipperzero-firmware:latest"
    use_docker: bool = False

    def __post_init__(self):
        if self.extra_defines is None:
            self.extra_defines = {}
        if self.custom_plugins is None:
            self.custom_plugins = []


@dataclass
class BuildResult:
    success: bool
    firmware_path: Optional[str]
    sha256: Optional[str]
    build_log: str
    duration_s: float
    timestamp: float
    config: dict

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Firmware Builder
# ---------------------------------------------------------------------------

class FirmwareBuilder:
    """
    Orchestrates the Flipper Zero firmware build process.

    Supports two build backends:
    * Native ``fbt`` (Flipper Build Tool) when the SDK is installed locally.
    * Docker-based cross-compilation for CI environments without the SDK.

    After a successful build the output binary is hashed (SHA-256) and
    stored alongside a ``manifest.json`` for consumption by AIFirmwareUpdater.
    """

    def __init__(
        self,
        config: Optional[BuildConfig] = None,
        *,
        simulation: bool = True,
    ):
        self._config = config or BuildConfig()
        self._simulation = simulation
        self._build_history: List[BuildResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def build(
        self,
        version: str,
        *,
        extra_defines: Optional[Dict[str, str]] = None,
    ) -> BuildResult:
        """
        Run a full firmware build and return the result.

        Parameters
        ----------
        version:        Semantic version string to embed in the firmware.
        extra_defines:  Additional CPP define overrides for this build.
        """
        cfg = self._config
        if extra_defines:
            cfg.extra_defines.update(extra_defines)
        start = time.time()

        out_dir = Path(cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if self._simulation:
            result = await self._sim_build(version, out_dir)
        elif cfg.use_docker:
            result = await self._docker_build(version, out_dir)
        else:
            result = await self._native_build(version, out_dir)

        result.duration_s = time.time() - start
        result.timestamp = time.time()
        result.config = asdict(cfg)
        self._build_history.append(result)

        if result.success:
            await self._write_manifest(result, version)
        return result

    # ------------------------------------------------------------------
    # Simulation build
    # ------------------------------------------------------------------
    async def _sim_build(self, version: str, out_dir: Path) -> BuildResult:
        await asyncio.sleep(0.5)  # simulate build time
        fw_bytes = f"NETHUNTERZ_FW_{version}".encode() + b"\x00" * 512
        fw_path = out_dir / f"nethunterz_{version}.bin"
        fw_path.write_bytes(fw_bytes)
        sha = hashlib.sha256(fw_bytes).hexdigest()
        logger.info("[SIM] Firmware built: %s (sha256=%s)", fw_path, sha[:16])
        return BuildResult(
            success=True,
            firmware_path=str(fw_path),
            sha256=sha,
            build_log=f"[SIM] Build of version {version} succeeded.",
            duration_s=0.0,
            timestamp=0.0,
            config={},
        )

    # ------------------------------------------------------------------
    # Native fbt build
    # ------------------------------------------------------------------
    async def _native_build(self, version: str, out_dir: Path) -> BuildResult:
        if not shutil.which("fbt"):
            logger.error("fbt not found on PATH. Install Flipper Build Tool.")
            return BuildResult(
                success=False,
                firmware_path=None,
                sha256=None,
                build_log="fbt not found.",
                duration_s=0.0,
                timestamp=0.0,
                config={},
            )
        defines = " ".join(
            f"-D{k}={v}" for k, v in self._config.extra_defines.items()
        )
        cmd = f"fbt FIRMWARE_ORIGIN=nethunterz VERSION={version} {defines}"
        loop = asyncio.get_event_loop()
        proc = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=self._config.source_dir
            ),
        )
        if proc.returncode != 0:
            return BuildResult(
                success=False,
                firmware_path=None,
                sha256=None,
                build_log=proc.stdout + proc.stderr,
                duration_s=0.0,
                timestamp=0.0,
                config={},
            )
        fw_path = Path(self._config.source_dir) / "dist" / self._config.target / "nethunterz.bin"
        if not fw_path.exists():
            return BuildResult(
                success=False,
                firmware_path=None,
                sha256=None,
                build_log="Output binary not found after build.",
                duration_s=0.0,
                timestamp=0.0,
                config={},
            )
        dest = out_dir / f"nethunterz_{version}.bin"
        shutil.copy2(fw_path, dest)
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        return BuildResult(
            success=True,
            firmware_path=str(dest),
            sha256=sha,
            build_log=proc.stdout,
            duration_s=0.0,
            timestamp=0.0,
            config={},
        )

    # ------------------------------------------------------------------
    # Docker build
    # ------------------------------------------------------------------
    async def _docker_build(self, version: str, out_dir: Path) -> BuildResult:
        image = self._config.docker_image
        src_abs = os.path.abspath(self._config.source_dir)
        out_abs = str(out_dir.resolve())
        cmd = (
            f"docker run --rm "
            f"-v {src_abs}:/firmware "
            f"-v {out_abs}:/output "
            f"{image} "
            f"bash -c 'cd /firmware && fbt VERSION={version} && "
            f"cp dist/{self._config.target}/*.bin /output/nethunterz_{version}.bin'"
        )
        loop = asyncio.get_event_loop()
        proc = await loop.run_in_executor(
            None,
            lambda: subprocess.run(cmd, shell=True, capture_output=True, text=True),
        )
        if proc.returncode != 0:
            return BuildResult(
                success=False,
                firmware_path=None,
                sha256=None,
                build_log=proc.stdout + proc.stderr,
                duration_s=0.0,
                timestamp=0.0,
                config={},
            )
        fw_path = out_dir / f"nethunterz_{version}.bin"
        if not fw_path.exists():
            return BuildResult(
                success=False,
                firmware_path=None,
                sha256=None,
                build_log="Output binary not found after Docker build.",
                duration_s=0.0,
                timestamp=0.0,
                config={},
            )
        sha = hashlib.sha256(fw_path.read_bytes()).hexdigest()
        return BuildResult(
            success=True,
            firmware_path=str(fw_path),
            sha256=sha,
            build_log=proc.stdout,
            duration_s=0.0,
            timestamp=0.0,
            config={},
        )

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------
    async def _write_manifest(self, result: BuildResult, version: str) -> None:
        manifest = {
            "version": version,
            "firmware_path": result.firmware_path,
            "sha256": result.sha256,
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "target": self._config.target,
        }
        manifest_path = Path(self._config.output_dir) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info("Build manifest written: %s", manifest_path)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get_build_history(self) -> List[dict]:
        return [r.to_dict() for r in self._build_history]

    def get_latest_result(self) -> Optional[BuildResult]:
        return self._build_history[-1] if self._build_history else None
