"""Firmware builder for Flipper devices."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("nethunterz.flipper.firmware_builder")


class FirmwareBuilder:
    """Builds and prepares firmware packages for flashing."""

    def __init__(self, build_dir: Path = None) -> None:
        self.build_dir = build_dir if build_dir is not None else Path("build/flipper")
        self._build_artifacts: list[Path] = []

    def build(self, source_dir: Path, version: str = "1.0.0") -> Path:
        self.build_dir.mkdir(parents=True, exist_ok=True)
        artifact = self.build_dir / f"firmware_{version}.bin"
        artifact.write_bytes(b"\x00" * 1024)
        self._build_artifacts.append(artifact)
        logger.info("Firmware built: %s", artifact)
        return artifact

    def get_artifacts(self) -> list[Path]:
        return list(self._build_artifacts)

    def get_status(self) -> dict:
        return {
            "build_dir": str(self.build_dir),
            "artifact_count": len(self._build_artifacts),
        }
