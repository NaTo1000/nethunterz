# CI/CD Pipeline Documentation

## Overview

NetHunterZ uses GitHub Actions for continuous integration and deployment. Five workflows automate the build, test, sign, and deploy lifecycle.

## Workflows

### 1. Android Build & Test (`.github/workflows/android-build.yml`)

**Triggers:** Push and pull requests to `main`/`develop`

**Jobs:**
- `build` - Compiles debug APK and runs unit tests
- `build-release` - Compiles signed release APK (main branch only)

**Artifacts:**
- `nethunter-debug-apk` - Debug APK (30 day retention)
- `nethunter-release-apk` - Release APK (90 day retention)
- `lint-report` - Android lint HTML report

**Required Secrets:**
| Secret | Purpose |
|---|---|
| `KEYSTORE_BASE64` | Base64-encoded release keystore |
| `KEYSTORE_PASSWORD` | Keystore password |
| `KEY_ALIAS` | Key alias |
| `KEY_PASSWORD` | Key password |

### 2. Flipper Firmware Build (`.github/workflows/flipper-firmware.yml`)

**Triggers:** Push/PR to firmware paths, `workflow_dispatch`

**Jobs:**
- `build-firmware` - Runs `build_firmware.py` + `validate_firmware.py`
- `validate-firmware` - Independent signature/checksum verification
- `deploy-firmware` - Uploads to S3 (main branch only)

**Manual trigger parameters:**
- `firmware_version` - Override version string
- `target_device` - Target device type

### 3. Nightly Build (`.github/workflows/nightly-build.yml`)

**Triggers:** Scheduled at 02:00 UTC daily, `workflow_dispatch`

**Jobs:**
- `nightly-android` - Full release Android build
- `nightly-firmware` - Full firmware build + S3 deploy
- `create-release` - Creates a GitHub pre-release with artifacts

**Note:** Releases are tagged `nightly-{run_number}` and marked as pre-release.

### 4. Deploy to Cloud (`.github/workflows/deploy-cloud.yml`)

**Triggers:** GitHub release published, `workflow_dispatch`

**Jobs:**
- `deploy-s3` - Upload firmware to AWS S3
- `deploy-gcs` - Upload firmware to Google Cloud Storage
- `update-dashboard` - Notify dashboard API of new release

### 5. Security Scan (`.github/workflows/security-scan.yml`)

**Triggers:** Push, pull request, weekly schedule (Monday 04:00 UTC)

**Jobs:**
- `codeql-analysis` - CodeQL static analysis (Java + Python)
- `dependency-check` - OWASP dependency vulnerability check + Bandit + Safety
- `firmware-signature-verify` - Verify GPG signatures on firmware files
- `secret-scan` - GitLeaks secret detection

## Setting Up CI/CD

### 1. Fork and configure secrets

Add all required secrets in **Settings → Secrets → Actions**:

```
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
S3_FIRMWARE_BUCKET
GCP_SERVICE_ACCOUNT_KEY, GCS_FIRMWARE_BUCKET
DASHBOARD_API_URL, DASHBOARD_API_KEY
GPG_PRIVATE_KEY, GPG_PASSPHRASE, GPG_PUBLIC_KEY
KEYSTORE_BASE64, KEYSTORE_PASSWORD, KEY_ALIAS, KEY_PASSWORD
```

### 2. Enable required permissions

In **Settings → Actions → General**:
- Workflow permissions: Read and write
- Allow GitHub Actions to create pull requests

### 3. Trigger first build

```bash
git push origin main
```

Or manually trigger via **Actions → Android Build & Test → Run workflow**.

## Monitoring

All workflow runs appear in **Actions** tab. Failed runs send notifications to repository watchers.
