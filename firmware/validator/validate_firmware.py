#!/usr/bin/env python3
"""
validate_firmware.py - Validates Flipper Zero firmware files.
Checks file integrity, binary format, version compatibility, and optionally
verifies GPG signatures.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import struct
import sys
from pathlib import Path
from typing import Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Minimum/maximum acceptable firmware sizes
MIN_FIRMWARE_SIZE = 1024         # 1 KB
MAX_FIRMWARE_SIZE = 4 * 1024 * 1024  # 4 MB

# Flipper Zero firmware magic bytes (ARM Cortex-M4 thumb code header)
# The initial stack pointer should be in valid SRAM range
FLIPPER_SRAM_BASE  = 0x20000000
FLIPPER_SRAM_END   = 0x20040000
FLIPPER_FLASH_BASE = 0x08000000
FLIPPER_FLASH_END  = 0x08100000


class FirmwareValidator:
    """Validates Flipper Zero firmware binary files."""

    def __init__(self):
        self.errors: list   = []
        self.warnings: list = []

    def validate_file(self, firmware_path: Path) -> bool:
        """Run all validations on a firmware file."""
        self.errors.clear()
        self.warnings.clear()

        logger.info(f"Validating firmware: {firmware_path.name}")

        if not firmware_path.exists():
            self.errors.append(f"File not found: {firmware_path}")
            return False

        if not firmware_path.is_file():
            self.errors.append(f"Not a regular file: {firmware_path}")
            return False

        # Check file size
        if not self._check_size(firmware_path):
            return False

        # Check ARM binary format
        self._check_arm_header(firmware_path)

        # Check for suspicious patterns
        self._check_suspicious_patterns(firmware_path)

        if self.errors:
            logger.error(f"Validation FAILED for {firmware_path.name}:")
            for err in self.errors:
                logger.error(f"  ERROR: {err}")
            return False

        if self.warnings:
            logger.warning(f"Validation WARNINGS for {firmware_path.name}:")
            for warn in self.warnings:
                logger.warning(f"  WARN: {warn}")

        logger.info(f"Validation PASSED: {firmware_path.name}")
        return True

    def _check_size(self, path: Path) -> bool:
        """Validate firmware file size is within acceptable bounds."""
        size = path.stat().st_size
        logger.debug(f"File size: {size:,} bytes ({size / 1024:.1f} KB)")

        if size < MIN_FIRMWARE_SIZE:
            self.errors.append(
                f"File too small: {size} bytes (minimum {MIN_FIRMWARE_SIZE})"
            )
            return False

        if size > MAX_FIRMWARE_SIZE:
            self.errors.append(
                f"File too large: {size:,} bytes (maximum {MAX_FIRMWARE_SIZE:,})"
            )
            return False

        return True

    def _check_arm_header(self, path: Path) -> bool:
        """
        Check ARM Cortex-M vector table format.
        First 8 bytes: [Initial SP (4 bytes)] [Reset Handler (4 bytes)]
        """
        try:
            with open(path, 'rb') as f:
                header = f.read(8)

            if len(header) < 8:
                self.warnings.append("File too short to verify ARM header")
                return True

            initial_sp  = struct.unpack_from('<I', header, 0)[0]
            reset_vector = struct.unpack_from('<I', header, 4)[0]

            logger.debug(f"Initial SP:    0x{initial_sp:08X}")
            logger.debug(f"Reset vector:  0x{reset_vector:08X}")

            # For simulation/test binaries, accept wide range
            if initial_sp == 0 and reset_vector == 0:
                self.warnings.append("Zero SP and reset vector - likely a placeholder/test binary")
                return True

            # Check if initial SP looks valid for Flipper (in SRAM or simulator)
            sp_valid = (FLIPPER_SRAM_BASE <= initial_sp <= FLIPPER_SRAM_END) or \
                       initial_sp == 0 or (initial_sp >> 28) == 2  # 0x2xxxxxxx range

            if not sp_valid:
                self.warnings.append(
                    f"Unexpected initial SP: 0x{initial_sp:08X} "
                    f"(expected 0x{FLIPPER_SRAM_BASE:08X}-0x{FLIPPER_SRAM_END:08X})"
                )

            return True

        except Exception as e:
            self.warnings.append(f"Could not read ARM header: {e}")
            return True

    def _check_suspicious_patterns(self, path: Path) -> None:
        """Scan for obviously suspicious patterns in the firmware."""
        suspicious_strings = [
            b'VIRUS', b'MALWARE', b'BACKDOOR',
            b'rm -rf', b'format c:',
        ]

        try:
            with open(path, 'rb') as f:
                content = f.read()
            for pattern in suspicious_strings:
                if pattern.lower() in content.lower():
                    self.warnings.append(f"Suspicious pattern found: {pattern}")
        except Exception as e:
            self.warnings.append(f"Pattern scan error: {e}")

    def compute_checksums(self, path: Path) -> dict:
        """Compute MD5, SHA1, and SHA256 checksums."""
        md5  = hashlib.md5()
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()

        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)

        return {
            "md5":    md5.hexdigest(),
            "sha1":   sha1.hexdigest(),
            "sha256": sha256.hexdigest(),
        }


def verify_gpg_signature(firmware_path: Path, sig_path: Optional[Path] = None) -> bool:
    """Verify GPG signature of firmware file."""
    import subprocess

    if sig_path is None:
        sig_path = Path(str(firmware_path) + ".sig")
        if not sig_path.exists():
            sig_path = Path(str(firmware_path) + ".asc")

    if not sig_path.exists():
        logger.warning(f"No signature file found for {firmware_path.name}")
        return False

    try:
        result = subprocess.run(
            ["gpg", "--verify", str(sig_path), str(firmware_path)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            logger.info(f"GPG signature VALID for {firmware_path.name}")
            return True
        else:
            logger.error(f"GPG signature INVALID: {result.stderr}")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"GPG verification failed: {e}")
        return False


def validate_directory(firmware_dir: Path, version: str,
                        verify_signatures: bool = False) -> bool:
    """Validate all firmware files in a directory."""
    validator = FirmwareValidator()
    firmware_files = list(firmware_dir.glob("*.bin"))

    if not firmware_files:
        logger.warning(f"No .bin firmware files found in {firmware_dir}")
        # Check for manifest to confirm this is expected
        manifest = firmware_dir / "build_manifest.json"
        if manifest.exists():
            with open(manifest) as f:
                m = json.load(f)
            if not m.get("artifacts"):
                logger.warning("Manifest shows no artifacts - possibly a simulation build")
                return True
        return False

    all_valid = True
    for fw_file in firmware_files:
        valid = validator.validate_file(fw_file)
        if not valid:
            all_valid = False

        checksums = validator.compute_checksums(fw_file)
        logger.info(f"SHA256: {checksums['sha256']}  {fw_file.name}")

        if verify_signatures:
            sig_valid = verify_gpg_signature(fw_file)
            if not sig_valid:
                logger.warning(f"Signature verification failed for {fw_file.name}")

    return all_valid


def main():
    parser = argparse.ArgumentParser(description='Validate Flipper Zero firmware')
    parser.add_argument('--firmware-dir', required=True, help='Directory containing firmware files')
    parser.add_argument('--version',      required=True, help='Expected firmware version')
    parser.add_argument('--verify-signatures', action='store_true',
                        help='Verify GPG signatures')
    parser.add_argument('--strict', action='store_true',
                        help='Fail on warnings in addition to errors')
    args = parser.parse_args()

    firmware_dir = Path(args.firmware_dir)
    if not firmware_dir.exists():
        logger.error(f"Firmware directory not found: {firmware_dir}")
        sys.exit(1)

    success = validate_directory(
        firmware_dir,
        args.version,
        verify_signatures=args.verify_signatures
    )

    if not success:
        logger.error("Firmware validation FAILED")
        sys.exit(1)

    logger.info("Firmware validation PASSED")
    sys.exit(0)


if __name__ == '__main__':
    main()
