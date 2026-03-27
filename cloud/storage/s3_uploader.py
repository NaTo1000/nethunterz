#!/usr/bin/env python3
"""
s3_uploader.py - AWS S3 upload/download for NetHunter firmware files.
Supports versioned uploads, metadata tagging, and public-read permissions.
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class S3Uploader:
    """Manages firmware file uploads and downloads to/from AWS S3."""

    def __init__(self, bucket: str, region: str = 'us-east-1'):
        self.bucket = bucket
        self.region = region
        try:
            self.s3 = boto3.client('s3', region_name=region)
            self.s3_resource = boto3.resource('s3', region_name=region)
            logger.info(f"S3 client initialized for bucket: {bucket} region: {region}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise

    def upload_firmware(self, firmware_dir: Path, version: str,
                        prefix: str = 'firmware/',
                        make_public: bool = False) -> list:
        """
        Upload all firmware files from directory to S3.
        Returns list of S3 keys that were uploaded.
        """
        uploaded = []
        firmware_files = list(firmware_dir.glob('*.bin')) + \
                         list(firmware_dir.glob('*.zip')) + \
                         list(firmware_dir.glob('*.sig')) + \
                         list(firmware_dir.glob('checksums.txt')) + \
                         list(firmware_dir.glob('build_manifest.json'))

        if not firmware_files:
            logger.warning(f"No firmware files found in {firmware_dir}")
            return uploaded

        for file_path in firmware_files:
            s3_key = f"{prefix.rstrip('/')}/{version}/{file_path.name}"
            try:
                self._upload_file(file_path, s3_key, make_public=make_public)
                uploaded.append(s3_key)
            except Exception as e:
                logger.error(f"Failed to upload {file_path.name}: {e}")

        logger.info(f"Uploaded {len(uploaded)} files to s3://{self.bucket}/{prefix}{version}/")
        return uploaded

    def _upload_file(self, local_path: Path, s3_key: str,
                     make_public: bool = False):
        """Upload a single file to S3 with metadata."""
        sha256 = compute_sha256(local_path)
        size   = local_path.stat().st_size

        extra_args = {
            'Metadata': {
                'sha256': sha256,
                'original_filename': local_path.name,
            }
        }

        if make_public:
            extra_args['ACL'] = 'public-read'

        # Determine content type
        if local_path.suffix == '.bin':
            extra_args['ContentType'] = 'application/octet-stream'
        elif local_path.suffix == '.json':
            extra_args['ContentType'] = 'application/json'
        elif local_path.suffix in ('.sig', '.asc'):
            extra_args['ContentType'] = 'application/pgp-signature'

        logger.info(f"Uploading {local_path.name} ({size:,} bytes) -> s3://{self.bucket}/{s3_key}")

        self.s3.upload_file(
            str(local_path),
            self.bucket,
            s3_key,
            ExtraArgs=extra_args
        )
        logger.info(f"Upload complete: {s3_key} sha256={sha256}")

    def download_firmware(self, version: str, dest_dir: Path,
                          prefix: str = 'firmware/') -> list:
        """Download all firmware files for a specific version from S3."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []
        s3_prefix = f"{prefix.rstrip('/')}/{version}/"

        try:
            paginator = self.s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket, Prefix=s3_prefix)

            for page in pages:
                for obj in page.get('Contents', []):
                    key  = obj['Key']
                    name = Path(key).name
                    dest = dest_dir / name

                    logger.info(f"Downloading s3://{self.bucket}/{key} -> {dest}")
                    self.s3.download_file(self.bucket, key, str(dest))
                    downloaded.append(str(dest))

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"No firmware found for version {version}")
            else:
                raise

        logger.info(f"Downloaded {len(downloaded)} files for version {version}")
        return downloaded

    def get_latest_version(self, channel: str = 'stable',
                           prefix: str = 'firmware/') -> Optional[str]:
        """Get the latest firmware version from S3 metadata."""
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key='latest.json')
            manifest = json.loads(resp['Body'].read())
            return manifest.get('latest_version')
        except ClientError:
            return None

    def update_latest_pointer(self, version: str, make_public: bool = True):
        """Update the latest.json pointer in S3."""
        import datetime
        manifest = {
            "latest_version": version,
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
        extra_args = {"ContentType": "application/json"}
        if make_public:
            extra_args["ACL"] = "public-read"

        self.s3.put_object(
            Bucket=self.bucket,
            Key='latest.json',
            Body=json.dumps(manifest, indent=2),
            **extra_args
        )
        logger.info(f"Updated latest.json -> version {version}")


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Upload firmware to AWS S3')
    parser.add_argument('--bucket',       required=True, help='S3 bucket name')
    parser.add_argument('--firmware-dir', required=True, type=Path,
                        help='Directory containing firmware files')
    parser.add_argument('--version',      required=True, help='Firmware version string')
    parser.add_argument('--prefix',       default='firmware/', help='S3 key prefix')
    parser.add_argument('--make-public',  action='store_true',
                        help='Make uploaded files publicly readable')
    parser.add_argument('--region',       default='us-east-1', help='AWS region')
    args = parser.parse_args()

    if not args.firmware_dir.exists():
        logger.error(f"Firmware directory not found: {args.firmware_dir}")
        sys.exit(1)

    try:
        uploader = S3Uploader(args.bucket, args.region)
        uploaded = uploader.upload_firmware(
            args.firmware_dir,
            args.version,
            args.prefix,
            make_public=args.make_public
        )

        if uploaded:
            uploader.update_latest_pointer(args.version, make_public=args.make_public)
            logger.info(f"Successfully uploaded {len(uploaded)} files")
            sys.exit(0)
        else:
            logger.warning("No files uploaded")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
