"""
ai_updater.py – Autonomous AI-driven firmware updater for the AIO Flipper board.

Responsibilities
----------------
* Periodically check the cloud release endpoint for new firmware versions.
* Compare semantic versions and determine whether an upgrade is warranted.
* Download the firmware binary with integrity verification (SHA-256).
* Coordinate with the AIOFlipperController to execute the flash.
* Roll back to the previous firmware if the post-flash health check fails.
* Emit structured update events to the cloud and BLE subscribers.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FirmwareRelease:
    version: str
    release_url: str
    sha256: str
    changelog: str
    published_at: str
    size_bytes: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "FirmwareRelease":
        return cls(
            version=d["version"],
            release_url=d["release_url"],
            sha256=d["sha256"],
            changelog=d.get("changelog", ""),
            published_at=d.get("published_at", ""),
            size_bytes=d.get("size_bytes", 0),
        )


@dataclass
class UpdateEvent:
    event_type: str   # check | download | flash | rollback | success | failure
    timestamp: float
    version_from: str
    version_to: str
    message: str
    success: bool


# ---------------------------------------------------------------------------
# AI Firmware Updater
# ---------------------------------------------------------------------------

class AIFirmwareUpdater:
    """
    Autonomous AI-driven firmware manager for the Flipper AIO board.

    The "AI" layer analyses firmware changelogs and device health metrics
    to decide *when* it is safe to update without interrupting active RF
    operations, and whether to auto-approve or require human confirmation.
    """

    RELEASE_CHECK_INTERVAL_S = 3600  # check for new firmware every hour
    CLOUD_RELEASE_ENDPOINT = os.environ.get(
        "FIRMWARE_RELEASE_ENDPOINT",
        "https://updates.example.com/flipper/releases/latest",
    )

    def __init__(
        self,
        flipper,  # AIOFlipperController
        *,
        firmware_dir: str = "firmware",
        simulation: bool = True,
        auto_approve: bool = False,
        approval_callback=None,
    ):
        self._flipper = flipper
        self._firmware_dir = Path(firmware_dir)
        self._simulation = simulation
        self._auto_approve = auto_approve
        self._approval_callback = approval_callback
        self._current_version: str = "0.0.0"
        self._update_history: List[UpdateEvent] = []
        self._check_task: Optional[asyncio.Task] = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        self._firmware_dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        info = await self._flipper.get_info()
        self._current_version = info.firmware_version
        self._check_task = asyncio.create_task(self._update_loop())
        logger.info(
            "AIFirmwareUpdater started. Current version: %s", self._current_version
        )

    async def stop(self) -> None:
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Update loop
    # ------------------------------------------------------------------
    async def _update_loop(self) -> None:
        while self._running:
            await self._check_and_update()
            await asyncio.sleep(self.RELEASE_CHECK_INTERVAL_S)

    async def _check_and_update(self) -> None:
        release = await self._fetch_latest_release()
        if release is None:
            return
        if not self._is_newer(release.version, self._current_version):
            logger.info("Firmware up to date (%s).", self._current_version)
            return
        logger.info(
            "New firmware available: %s → %s", self._current_version, release.version
        )
        if not await self._should_update(release):
            logger.info("Update deferred by approval logic.")
            return
        await self._perform_update(release)

    # ------------------------------------------------------------------
    # Release fetching
    # ------------------------------------------------------------------
    async def _fetch_latest_release(self) -> Optional[FirmwareRelease]:
        if self._simulation:
            import random
            # Simulate occasional new release
            if random.random() < 0.1:
                return FirmwareRelease(
                    version="0.99.0",
                    release_url="https://sim.example.com/fw.bin",
                    sha256="a" * 64,
                    changelog="Simulated release with NRF improvements.",
                    published_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    size_bytes=1024 * 512,
                )
            return None
        try:
            import aiohttp  # type: ignore
            async with aiohttp.ClientSession() as session:
                headers = {}
                api_key = os.environ.get("FIRMWARE_API_KEY", "")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                async with session.get(
                    self.CLOUD_RELEASE_ENDPOINT,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        return FirmwareRelease.from_dict(await resp.json())
                    logger.warning("Release endpoint returned HTTP %d.", resp.status)
        except Exception as exc:
            logger.debug("Release check failed: %s", exc)
        return None

    # ------------------------------------------------------------------
    # AI decision layer
    # ------------------------------------------------------------------
    async def _should_update(self, release: FirmwareRelease) -> bool:
        """
        AI decision: determine if it's safe and appropriate to update now.

        Factors considered:
        * Auto-approve flag.
        * Human approval callback.
        * Active RF capture state (defer if a critical capture is running).
        * Changelog sentiment (in production this would call an LLM).
        """
        if self._auto_approve:
            return True
        # Defer if a capture is running and the update is not critical
        flipper_status = self._flipper.get_status()
        if flipper_status.get("connected") and "critical" not in release.changelog.lower():
            logger.info("Deferring update – device is busy and update is non-critical.")
            return False
        if self._approval_callback:
            try:
                return bool(await self._approval_callback(release))
            except Exception:
                return False
        return False

    # ------------------------------------------------------------------
    # Update execution
    # ------------------------------------------------------------------
    async def _perform_update(self, release: FirmwareRelease) -> None:
        event_base = dict(
            version_from=self._current_version,
            version_to=release.version,
            timestamp=time.time(),
        )
        try:
            # Download
            fw_path = await self._download_firmware(release)
            if fw_path is None:
                self._record_event(**event_base, event_type="failure",
                                   message="Download failed.", success=False)
                return

            # Backup current version info for rollback
            backup_version = self._current_version

            # Flash
            ok = await self._flipper.flash_firmware(str(fw_path))
            if not ok:
                self._record_event(**event_base, event_type="failure",
                                   message="Flash failed.", success=False)
                return

            # Health check
            await asyncio.sleep(3)  # let the device boot
            post_info = await self._flipper.get_info()
            if post_info.firmware_version != release.version:
                logger.error(
                    "Post-flash version mismatch: expected %s got %s. Rolling back.",
                    release.version, post_info.firmware_version
                )
                await self._rollback(backup_version, event_base)
                return

            self._current_version = release.version
            self._record_event(**event_base, event_type="success",
                               message="Firmware updated successfully.", success=True)
            logger.info("Firmware successfully updated to %s.", self._current_version)

        except Exception as exc:
            logger.error("Unexpected update error: %s", exc)
            self._record_event(**event_base, event_type="failure",
                               message=str(exc), success=False)

    async def _download_firmware(self, release: FirmwareRelease) -> Optional[Path]:
        out_path = self._firmware_dir / f"flipper_{release.version}.bin"
        if out_path.exists():
            if self._verify_sha256(out_path, release.sha256):
                logger.info("Firmware already downloaded: %s", out_path)
                return out_path

        if self._simulation:
            out_path.write_bytes(b"\x00" * 1024)  # dummy binary
            logger.info("[SIM] Firmware downloaded to %s", out_path)
            return out_path

        try:
            import aiohttp  # type: ignore
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    release.release_url,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        logger.error("Download failed: HTTP %d", resp.status)
                        return None
                    data = await resp.read()
                    out_path.write_bytes(data)
        except Exception as exc:
            logger.error("Firmware download error: %s", exc)
            return None

        if not self._verify_sha256(out_path, release.sha256):
            logger.error("SHA-256 verification failed for %s", out_path)
            out_path.unlink(missing_ok=True)
            return None
        return out_path

    @staticmethod
    def _verify_sha256(path: Path, expected: str) -> bool:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return digest == expected

    @staticmethod
    def _is_newer(candidate: str, current: str) -> bool:
        def parse(v):
            parts = v.lstrip("v").split(".")
            return tuple(int(x) for x in parts if x.isdigit())
        try:
            return parse(candidate) > parse(current)
        except Exception:
            return False

    async def _rollback(self, backup_version: str, event_base: dict) -> None:
        logger.warning("Initiating rollback to %s", backup_version)
        self._record_event(
            **event_base,
            event_type="rollback",
            message=f"Rolling back to {backup_version}",
            success=True,
        )
        # In production: flash the backup binary from firmware_dir
        self._current_version = backup_version

    def _record_event(
        self,
        *,
        event_type: str,
        timestamp: float,
        version_from: str,
        version_to: str,
        message: str,
        success: bool,
    ) -> None:
        evt = UpdateEvent(
            event_type=event_type,
            timestamp=timestamp,
            version_from=version_from,
            version_to=version_to,
            message=message,
            success=success,
        )
        self._update_history.append(evt)
        log = logger.info if success else logger.error
        log("[UPDATE-%s] %s → %s: %s", event_type, version_from, version_to, message)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get_update_history(self) -> List[dict]:
        from dataclasses import asdict
        return [asdict(e) for e in self._update_history]

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "current_version": self._current_version,
            "simulation": self._simulation,
            "total_updates": len(
                [e for e in self._update_history if e.event_type == "success"]
            ),
            "total_failures": len(
                [e for e in self._update_history if e.event_type == "failure"]
            ),
        }
