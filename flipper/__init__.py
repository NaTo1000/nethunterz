"""
flipper – AIO Flipper Board integration package.

Provides autonomous AI-driven firmware management, cloud-linked updates,
and a full firmware build pipeline for Flipper Zero and compatible boards.
"""

from .aio_flipper import AIOFlipperController
from .ai_updater import AIFirmwareUpdater
from .firmware_builder import FirmwareBuilder

__all__ = ["AIOFlipperController", "AIFirmwareUpdater", "FirmwareBuilder"]
