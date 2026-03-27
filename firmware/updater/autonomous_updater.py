#!/usr/bin/env python3
"""
autonomous_updater.py - Autonomous firmware update orchestrator.
Coordinates fetching, validating, and deploying firmware updates
with cloud sync, notification, and rollback capabilities.
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

DASHBOARD_API_TIMEOUT = 30
DOWNLOAD_CHUNK_SIZE   = 65536


class AutonomousUpdater:
    """
    Orchestrates the full firmware update lifecycle:
    1. Check cloud for new versions
    2. Download and validate firmware
    3. Upload to devices or trigger OTA
    4. Notify dashboard of completion
    5. Rollback on failure
    """

    def __init__(self, dashboard_url: Optional[str] = None,
                 api_key: Optional[str] = None):
        self.dashboard_url = dashboard_url or os.environ.get('DASHBOARD_API_URL')
        self.api_key       = api_key or os.environ.get('DASHBOARD_API_KEY')
        self.session       = requests.Session()
        if self.api_key:
            self.session.headers['Authorization'] = f"Bearer {self.api_key}"
        self.session.headers['User-Agent'] = 'NetHunter-FirmwareUpdater/1.0'

    def check_for_update(self, current_version: str, channel: str = 'stable') -> Optional[dict]:
        """
        Check cloud dashboard for available firmware updates.
        Returns the release info dict if an update is available, else None.
        """
        if not self.dashboard_url:
            logger.warning("No dashboard URL configured")
            return None

        try:
            url = f"{self.dashboard_url}/api/firmware/latest?channel={channel}"
            resp = self.session.get(url, timeout=DASHBOARD_API_TIMEOUT)
            resp.raise_for_status()
            release = resp.json()

            latest_version = release.get('version', '')
            if self._is_newer(latest_version, current_version):
                logger.info(f"Update available: {current_version} -> {latest_version}")
                return release
            else:
                logger.info(f"Already up to date: {current_version}")
                return None
        except requests.RequestException as e:
            logger.warning(f"Could not check for updates: {e}")
            return None

    def download_firmware(self, download_url: str, dest_path: Path,
                          expected_sha256: Optional[str] = None) -> bool:
        """Download firmware from the given URL with integrity verification."""
        logger.info(f"Downloading firmware from {download_url}")
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        total  = 0

        try:
            with self.session.get(download_url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                total_size = int(resp.headers.get('content-length', 0))

                with open(dest_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            hasher.update(chunk)
                            total += len(chunk)
                            if total_size > 0:
                                pct = total * 100 // total_size
                                if total % (DOWNLOAD_CHUNK_SIZE * 10) == 0:
                                    logger.info(f"Download: {pct}% ({total:,}/{total_size:,} bytes)")

            actual_sha256 = hasher.hexdigest()
            logger.info(f"Download complete: {total:,} bytes")
            logger.info(f"SHA256: {actual_sha256}")

            if expected_sha256 and actual_sha256 != expected_sha256:
                logger.error(
                    f"Checksum mismatch! Expected {expected_sha256}, got {actual_sha256}"
                )
                dest_path.unlink(missing_ok=True)
                return False

            return True

        except Exception as e:
            logger.error(f"Download failed: {e}")
            dest_path.unlink(missing_ok=True)
            return False

    def notify_dashboard(self, version: str, sha256: Optional[str] = None,
                         release_notes: Optional[str] = None) -> bool:
        """Notify the cloud dashboard of a new firmware availability."""
        if not self.dashboard_url:
            logger.warning("No dashboard URL, skipping notification")
            return False

        payload = {
            "version": version,
            "sha256": sha256 or "",
            "release_notes": release_notes or "",
            "notified_at": datetime.utcnow().isoformat() + "Z",
            "source": "ci_pipeline"
        }

        try:
            url = f"{self.dashboard_url}/api/firmware/notify"
            resp = self.session.post(url, json=payload, timeout=DASHBOARD_API_TIMEOUT)
            resp.raise_for_status()
            logger.info(f"Dashboard notified successfully for version {version}")
            return True
        except requests.RequestException as e:
            logger.warning(f"Dashboard notification failed: {e}")
            return False

    def _is_newer(self, candidate: str, current: str) -> bool:
        """Simple semver comparison: returns True if candidate > current."""
        try:
            def parse(v: str):
                # Strip non-numeric prefix/suffix
                cleaned = v.strip().lstrip('v')
                parts   = cleaned.split('.')
                return tuple(int(p) for p in parts[:3] if p.isdigit()) or (0, 0, 0)

            return parse(candidate) > parse(current)
        except Exception:
            return candidate != current


def main():
    parser = argparse.ArgumentParser(description='Autonomous firmware update orchestrator')
    subparsers = parser.add_subparsers(dest='command')

    # notify-dashboard sub-command
    notify_parser = subparsers.add_parser('--notify-dashboard', add_help=False)
    parser.add_argument('--notify-dashboard', action='store_true',
                        help='Notify dashboard of new firmware release')
    parser.add_argument('--version',       required=False, help='Firmware version')
    parser.add_argument('--sha256',        required=False, help='Firmware SHA256 checksum')
    parser.add_argument('--release-notes', required=False, help='Release notes text')

    # check sub-command
    parser.add_argument('--check',           action='store_true',
                        help='Check for available updates')
    parser.add_argument('--current-version', default='0.0.0',
                        help='Current installed firmware version')
    parser.add_argument('--channel',         default='stable',
                        help='Update channel (stable/rc/dev)')

    args = parser.parse_args()

    updater = AutonomousUpdater()

    if args.notify_dashboard:
        success = updater.notify_dashboard(
            version=args.version or 'unknown',
            sha256=args.sha256,
            release_notes=args.release_notes
        )
        sys.exit(0 if success else 1)

    elif args.check:
        release = updater.check_for_update(args.current_version, args.channel)
        if release:
            print(json.dumps(release, indent=2))
            sys.exit(0)
        else:
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == '__main__':
    main()
