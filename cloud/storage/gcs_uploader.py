#!/usr/bin/env python3
"""
gcs_uploader.py - Google Cloud Storage upload/download for NetHunter firmware.
Supports versioned uploads, signed URLs, and lifecycle management.
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class GCSUploader:
    """Manages firmware file uploads and downloads to/from Google Cloud Storage."""

    def __init__(self, bucket_name: str, project_id: Optional[str] = None):
        self.bucket_name = bucket_name
        self.project_id  = project_id or os.environ.get('GOOGLE_CLOUD_PROJECT')
        self.client      = None
        self.bucket      = None
        self._init_client()

    def _init_client(self):
        """Initialize the GCS client."""
        try:
            from google.cloud import storage
            self.client = storage.Client(project=self.project_id)
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(f"GCS client initialized for bucket: {self.bucket_name}")
        except ImportError:
            logger.error("google-cloud-storage not installed. Run: pip install google-cloud-storage")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            raise

    def upload_firmware(self, firmware_dir: Path, version: str,
                        prefix: str = 'firmware/') -> list:
        """
        Upload all firmware files to GCS with versioned path.
        Returns list of GCS blob names that were uploaded.
        """
        uploaded = []
        patterns = ['*.bin', '*.zip', '*.sig', 'checksums.txt', 'build_manifest.json']
        files = []
        for pattern in patterns:
            files.extend(firmware_dir.glob(pattern))

        if not files:
            logger.warning(f"No firmware files found in {firmware_dir}")
            return uploaded

        for file_path in files:
            blob_name = f"{prefix.rstrip('/')}/{version}/{file_path.name}"
            try:
                self._upload_file(file_path, blob_name)
                uploaded.append(blob_name)
            except Exception as e:
                logger.error(f"Failed to upload {file_path.name}: {e}")

        if uploaded:
            self._update_latest_pointer(version, prefix)

        logger.info(f"Uploaded {len(uploaded)} files to gs://{self.bucket_name}/{prefix}{version}/")
        return uploaded

    def _upload_file(self, local_path: Path, blob_name: str):
        """Upload a single file to GCS with checksum metadata."""
        sha256 = compute_sha256(local_path)
        size   = local_path.stat().st_size

        blob = self.bucket.blob(blob_name)
        blob.metadata = {
            'sha256': sha256,
            'original_filename': local_path.name,
            'upload_timestamp': datetime.utcnow().isoformat() + 'Z',
        }

        # Set content type
        if local_path.suffix == '.bin':
            content_type = 'application/octet-stream'
        elif local_path.suffix == '.json':
            content_type = 'application/json'
        elif local_path.suffix in ('.sig', '.asc'):
            content_type = 'application/pgp-signature'
        else:
            content_type = 'application/octet-stream'

        logger.info(f"Uploading {local_path.name} ({size:,} bytes) "
                    f"-> gs://{self.bucket_name}/{blob_name}")

        blob.upload_from_filename(str(local_path), content_type=content_type)
        logger.info(f"Upload complete: {blob_name} sha256={sha256}")

    def _update_latest_pointer(self, version: str, prefix: str = 'firmware/'):
        """Update the latest version pointer JSON in GCS."""
        manifest = {
            "latest_version": version,
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "prefix": prefix,
        }
        blob = self.bucket.blob("latest.json")
        blob.upload_from_string(
            json.dumps(manifest, indent=2),
            content_type='application/json'
        )
        logger.info(f"Updated latest.json pointer -> {version}")

    def download_firmware(self, version: str, dest_dir: Path,
                          prefix: str = 'firmware/') -> list:
        """Download all firmware files for a version from GCS."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []
        gcs_prefix = f"{prefix.rstrip('/')}/{version}/"

        blobs = list(self.client.list_blobs(self.bucket_name, prefix=gcs_prefix))
        if not blobs:
            logger.warning(f"No files found at gs://{self.bucket_name}/{gcs_prefix}")
            return downloaded

        for blob in blobs:
            name = Path(blob.name).name
            dest = dest_dir / name
            logger.info(f"Downloading gs://{self.bucket_name}/{blob.name} -> {dest}")
            blob.download_to_filename(str(dest))
            downloaded.append(str(dest))

        logger.info(f"Downloaded {len(downloaded)} files for version {version}")
        return downloaded

    def get_latest_version(self) -> Optional[str]:
        """Get the latest firmware version from GCS metadata."""
        try:
            blob = self.bucket.blob("latest.json")
            content = blob.download_as_text()
            manifest = json.loads(content)
            return manifest.get("latest_version")
        except Exception:
            return None

    def generate_signed_url(self, blob_name: str, expiration_minutes: int = 60) -> str:
        """Generate a signed URL for temporary public access to a blob."""
        from datetime import timedelta
        blob = self.bucket.blob(blob_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
        )
        logger.info(f"Generated signed URL for {blob_name} (expires in {expiration_minutes}m)")
        return url


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Upload firmware to Google Cloud Storage')
    parser.add_argument('--bucket',       required=True, help='GCS bucket name')
    parser.add_argument('--firmware-dir', required=True, type=Path)
    parser.add_argument('--version',      required=True, help='Firmware version string')
    parser.add_argument('--prefix',       default='firmware/', help='GCS key prefix')
    parser.add_argument('--project',      default=None, help='GCP project ID')
    args = parser.parse_args()

    if not args.firmware_dir.exists():
        logger.error(f"Firmware directory not found: {args.firmware_dir}")
        sys.exit(1)

    try:
        uploader = GCSUploader(args.bucket, args.project)
        uploaded = uploader.upload_firmware(args.firmware_dir, args.version, args.prefix)

        if uploaded:
            logger.info(f"Successfully uploaded {len(uploaded)} files to GCS")
            sys.exit(0)
        else:
            logger.warning("No files uploaded to GCS")
            sys.exit(1)

    except Exception as e:
        logger.error(f"GCS upload failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
