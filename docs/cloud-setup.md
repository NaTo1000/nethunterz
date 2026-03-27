# Cloud Services Setup Guide

## Overview

NetHunterZ uses two cloud storage backends for firmware distribution:

| Service | Python Class | Android Class |
|---|---|---|
| AWS S3 | `s3_uploader.py` | `CloudStorageManager` |
| Google Cloud Storage | `gcs_uploader.py` | `CloudStorageManager` |
| Dashboard API | `dashboard_server.py` | `CloudDashboardClient` |

## AWS S3 Setup

### 1. Create S3 Bucket

```bash
aws s3 mb s3://nethunterz-firmware --region us-east-1
aws s3api put-bucket-versioning \
    --bucket nethunterz-firmware \
    --versioning-configuration Status=Enabled
```

### 2. Configure GitHub Secrets

Add these secrets to your GitHub repository:

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM access key |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key |
| `AWS_REGION` | AWS region (e.g., `us-east-1`) |
| `S3_FIRMWARE_BUCKET` | S3 bucket name |

### 3. Test Upload

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
python cloud/storage/s3_uploader.py \
    --bucket nethunterz-firmware \
    --firmware-dir firmware/build/output \
    --version 1.0.0 \
    --make-public
```

## Google Cloud Storage Setup

### 1. Create GCS Bucket

```bash
gsutil mb -l US gs://nethunterz-firmware
```

### 2. Configure Service Account

```bash
gcloud iam service-accounts create nethunterz-ci
gcloud projects add-iam-policy-binding YOUR_PROJECT \
    --member="serviceAccount:nethunterz-ci@YOUR_PROJECT.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"
gcloud iam service-accounts keys create sa-key.json \
    --iam-account=nethunterz-ci@YOUR_PROJECT.iam.gserviceaccount.com
```

### 3. Add GitHub Secrets

| Secret | Description |
|---|---|
| `GCP_SERVICE_ACCOUNT_KEY` | JSON service account key (base64) |
| `GCS_FIRMWARE_BUCKET` | GCS bucket name |

## Dashboard Server

### Local Development

```bash
pip install flask
cd cloud/dashboard
export FLASK_SECRET_KEY=dev-secret
export DASHBOARD_API_KEY=dev-api-key
python dashboard_server.py
# Opens on http://localhost:5000
```

### Production Deployment

The dashboard can be deployed to any WSGI-compatible host:

```bash
# With Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 \
    --chdir cloud/dashboard \
    dashboard_server:app
```

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `FLASK_SECRET_KEY` | Flask session secret | `dev-secret-change-in-prod` |
| `DASHBOARD_API_KEY` | API authentication key | `dev-api-key` |
| `PORT` | Server port | `5000` |
| `FLASK_DEBUG` | Enable debug mode | `false` |

## Android Configuration

In the Android app, configure cloud endpoints:

```java
CloudDashboardClient dashboard = new CloudDashboardClient(
    context,
    "https://your-dashboard.example.com",
    "your-api-key"
);

CloudStorageManager storage = new CloudStorageManager(context);
storage.configureS3("https://nethunterz-firmware.s3.amazonaws.com/", apiKey);
// or
storage.configureGCS("https://storage.googleapis.com/nethunterz-firmware/", apiKey);
```
