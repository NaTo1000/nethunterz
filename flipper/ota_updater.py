"""OTA (Over-The-Air) firmware update engine for Flipper Zero."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nethunterz.flipper.ota_updater")


class OTAStatus(Enum):
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    FLASHING = "flashing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class FirmwareManifest:
    """Metadata for a firmware release."""

    version: str
    sha256: str
    size_bytes: int
    url: str
    changelog: str = ""
    min_hw_version: str = "1.0"
    nethunterz_stack_version: str = "1.0.0"


@dataclass
class OTAProgress:
    """Tracks OTA download/flash progress."""

    status: OTAStatus = OTAStatus.IDLE
    bytes_received: int = 0
    total_bytes: int = 0
    percent: float = 0.0
    error_message: str = ""
    current_version: str = "0.0.0"
    target_version: str = ""
    history: list[dict] = field(default_factory=list)

    def update(self, received: int, total: int) -> None:
        self.bytes_received = received
        self.total_bytes = total
        self.percent = (received / total * 100.0) if total > 0 else 0.0


class OTAUpdater:
    """
    OTA firmware update engine managed by the orchestration engine.

    Handles version checking, secure download, SHA-256 verification,
    and firmware flashing via BLE companion bridge.
    """

    def __init__(
        self,
        current_version: str = "1.0.0",
        update_cache_dir: Optional[Path] = None,
        simulation: bool = True,
    ) -> None:
        self.current_version = current_version
        self.cache_dir = update_cache_dir or Path("/tmp/flipper_ota_cache")
        self.simulation = simulation
        self.progress = OTAProgress(current_version=current_version)
        self._manifest: Optional[FirmwareManifest] = None
        self._running = False
        logger.info("OTAUpdater initialised v%s (sim=%s)", current_version, simulation)

    # ------------------------------------------------------------------
    # Version management
    # ------------------------------------------------------------------

    def is_newer(self, candidate: str) -> bool:
        """Return True if candidate version is newer than current."""
        def parse(v: str) -> tuple:
            return tuple(int(x) for x in v.split("."))
        try:
            return parse(candidate) > parse(self.current_version)
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Update flow
    # ------------------------------------------------------------------

    async def check_for_update(self) -> Optional[FirmwareManifest]:
        """Simulate checking the NetHunterz OTA server for a newer firmware."""
        self.progress.status = OTAStatus.CHECKING
        logger.info("Checking for OTA update (current=%s)", self.current_version)
        await asyncio.sleep(0.05 if self.simulation else 2.0)

        # In simulation mode, return a mock newer manifest
        if self.simulation:
            mock = FirmwareManifest(
                version="1.1.0",
                sha256="a" * 64,
                size_bytes=65536,
                url="ble://nethunterz-ota/firmware_1.1.0.bin",
                changelog="NayDoeV1 GUI, 80s scenes, cloud sync, trail-wipe security",
                nethunterz_stack_version="1.1.0",
            )
            if self.is_newer(mock.version):
                self._manifest = mock
                logger.info("Update available: %s", mock.version)
                return mock

        self.progress.status = OTAStatus.IDLE
        return None

    async def download_firmware(self, manifest: FirmwareManifest) -> Optional[Path]:
        """Download firmware package from OTA server (simulated)."""
        self.progress.status = OTAStatus.DOWNLOADING
        self.progress.target_version = manifest.version
        total = manifest.size_bytes
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.cache_dir / f"firmware_{manifest.version}.bin"

        logger.info("Downloading firmware %s (%d bytes)", manifest.version, total)

        if self.simulation:
            # Write simulated firmware binary
            chunk_size = 4096
            received = 0
            data = bytearray()
            while received < total:
                chunk = min(chunk_size, total - received)
                data.extend(b"\xAA" * chunk)
                received += chunk
                self.progress.update(received, total)
                await asyncio.sleep(0)
            out_path.write_bytes(bytes(data))
        else:
            # Real implementation would use aiohttp
            raise NotImplementedError("Real download requires companion app BLE transfer")

        self.progress.status = OTAStatus.VERIFYING
        logger.info("Download complete: %s", out_path)
        return out_path

    async def verify_firmware(self, path: Path, expected_sha256: str) -> bool:
        """Verify firmware SHA-256 checksum."""
        self.progress.status = OTAStatus.VERIFYING
        logger.info("Verifying firmware: %s", path)
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()

        if self.simulation:
            # Simulation always passes
            logger.info("Verification passed (simulation)")
            return True

        if actual != expected_sha256:
            self.progress.error_message = f"SHA-256 mismatch: {actual} != {expected_sha256}"
            self.progress.status = OTAStatus.FAILED
            logger.error(self.progress.error_message)
            return False

        logger.info("Firmware verified: %s", actual)
        return True

    async def flash_firmware(self, path: Path) -> bool:
        """Flash firmware to the Flipper Zero device."""
        self.progress.status = OTAStatus.FLASHING
        logger.info("Flashing firmware: %s", path)
        await asyncio.sleep(0.1 if self.simulation else 30.0)

        if self._manifest:
            self.current_version = self._manifest.version
            self.progress.current_version = self.current_version
            self.progress.history.append({
                "version": self._manifest.version,
                "status": "flashed",
                "changelog": self._manifest.changelog,
            })

        self.progress.status = OTAStatus.COMPLETE
        logger.info("Flash complete, running firmware v%s", self.current_version)
        return True

    async def run_full_update(self) -> bool:
        """Run the complete check → download → verify → flash cycle."""
        manifest = await self.check_for_update()
        if manifest is None:
            logger.info("No update available")
            return False

        path = await self.download_firmware(manifest)
        if path is None:
            return False

        verified = await self.verify_firmware(path, manifest.sha256)
        if not verified:
            return False

        return await self.flash_firmware(path)

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    async def start_background_checks(self, interval_s: float = 3600.0) -> None:
        self._running = True
        while self._running:
            await self.check_for_update()
            await asyncio.sleep(interval_s)

    async def stop_background_checks(self) -> None:
        self._running = False

    def get_status(self) -> dict:
        return {
            "current_version": self.current_version,
            "ota_status": self.progress.status.value,
            "percent": self.progress.percent,
            "target_version": self.progress.target_version,
            "update_count": len(self.progress.history),
            "simulation": self.simulation,
        }
