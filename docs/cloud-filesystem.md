# Cloud Filesystem Configuration Guide

## Supported Providers

| Provider | Class | Auth Method |
|----------|-------|-------------|
| Google Drive | `CloudFilesystem.setup_google_drive()` | OAuth 2.0 |
| Microsoft OneDrive | `CloudFilesystem.setup_onedrive()` | MSAL |
| Custom VPS (SFTP) | `CloudFilesystem.setup_vps()` | SSH key |
| S3-compatible | `CloudFilesystem` | Access keys |

## Self-Installation

The cloud filesystem self-installs a pre-defined folder structure
into your chosen provider on first run:

```
/nethunterz/
├── operations/    # Active operation data
├── scans/         # Network scan results
├── reports/       # Generated reports (PDF/MD)
├── evidence/      # Blockchain-timestamped evidence
├── models/        # AI model checkpoints
├── backups/       # System snapshots
├── configs/       # Device configurations
└── logs/          # Aggregated log archive
```

## Google Drive Setup

```python
from cloud import CloudFilesystem

fs = CloudFilesystem.setup_google_drive(
    client_id="YOUR_GOOGLE_CLIENT_ID",
    client_secret="YOUR_GOOGLE_CLIENT_SECRET",
    root_path="/nethunterz",
)

# Connect and install folder structure
await fs.connect()
await fs.install()

# Upload encrypted file
cloud_file = await fs.upload_file(
    local_path="/tmp/scan_results.json",
    data=json_bytes,
    remote_subpath="scans",
)
print(f"Uploaded: {cloud_file.remote_path}")
print(f"Checksum: {cloud_file.checksum}")
print(f"Encrypted: {cloud_file.encrypted}")
```

## OneDrive Setup

```python
fs = CloudFilesystem.setup_onedrive(
    client_id="YOUR_APP_CLIENT_ID",
    tenant_id="YOUR_TENANT_ID",
    root_path="/nethunterz",
)
await fs.connect()
await fs.install()
```

## VPS / SFTP Setup

```python
fs = CloudFilesystem.setup_vps(
    host="your-secure-vps.example.com",
    username="nethunterz",
    key_path="/home/user/.ssh/id_ed25519",
    root_path="/var/nethunterz",
)
await fs.connect()
await fs.install()
```

## Encryption

All files are encrypted with AES-256 before upload by default:

```python
# Disable encryption (not recommended)
from cloud import CloudConfig, CloudProvider, CloudFilesystem

config = CloudConfig(
    provider=CloudProvider.GOOGLE_DRIVE,
    encryption_enabled=False,  # not recommended
    root_path="/nethunterz",
)
fs = CloudFilesystem(config)
```

## Auto-Sync

```python
# Start continuous background sync
await fs.start_auto_sync(
    local_dir="/var/nethunterz/operations",
    remote_subpath="operations",
)

# Stop sync
fs.stop_auto_sync()
```

## Flipper Zero Cloud Installation

The Flipper Zero can install the cloud filesystem directly:

```python
from flipper.firmware import FlipperZeroFirmware
from cloud import CloudFilesystem

cloud = CloudFilesystem.setup_google_drive()
flipper = FlipperZeroFirmware(cloud_filesystem=cloud)

await flipper.boot()
await flipper.install_cloud_filesystem()
```

## Statistics

```python
stats = fs.get_stats()
# {
#   "provider": "google_drive",
#   "connected": True,
#   "files_uploaded": 42,
#   "total_bytes": 10485760,
#   "encrypted": True,
#   "root_path": "/nethunterz",
# }
```
