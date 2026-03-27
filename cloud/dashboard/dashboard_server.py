#!/usr/bin/env python3
"""
dashboard_server.py - Flask-based cloud dashboard for NetHunter firmware management.
Provides a REST API and web interface for managing firmware releases and device statistics.
"""

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request, abort, send_from_directory

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-in-prod')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB max upload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory data stores (replace with a database in production)
firmware_releases: list  = []
device_stats: dict       = {}
device_logs: dict        = {}

API_KEY = os.environ.get('DASHBOARD_API_KEY', 'dev-api-key')

# --- Auth Middleware ---

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer ') or auth[7:] != API_KEY:
            abort(401, description="Invalid or missing API key")
        return f(*args, **kwargs)
    return decorated


# --- API Routes ---

@app.route('/api/firmware/latest', methods=['GET'])
def get_latest_firmware():
    """Get the latest firmware release for a given channel."""
    channel = request.args.get('channel', 'stable')
    stable = [r for r in firmware_releases if r.get('channel') == channel]

    if not stable:
        # Return a mock release for development
        return jsonify({
            "version": "0.0.0",
            "channel": channel,
            "download_url": "",
            "sha256": "",
            "release_notes": "No releases yet",
            "release_date": datetime.utcnow().isoformat() + "Z",
            "is_stable": channel == "stable"
        })

    latest = sorted(stable, key=lambda x: x.get('release_date', ''), reverse=True)[0]
    return jsonify(latest)


@app.route('/api/firmware/releases', methods=['GET'])
def list_firmware_releases():
    """List firmware releases with pagination."""
    limit   = min(int(request.args.get('limit', 10)), 100)
    channel = request.args.get('channel', None)
    page    = int(request.args.get('page', 1))

    releases = firmware_releases
    if channel:
        releases = [r for r in releases if r.get('channel') == channel]

    total  = len(releases)
    start  = (page - 1) * limit
    paged  = releases[start:start + limit]

    return jsonify({
        "releases": paged,
        "total": total,
        "page": page,
        "limit": limit
    })


@app.route('/api/firmware/notify', methods=['POST'])
@require_api_key
def notify_new_firmware():
    """Receive notification of a new firmware release."""
    data = request.get_json()
    if not data or 'version' not in data:
        abort(400, description="Missing required field: version")

    release = {
        "id":            str(uuid.uuid4()),
        "version":       data.get("version"),
        "sha256":        data.get("sha256", ""),
        "release_notes": data.get("release_notes", ""),
        "channel":       data.get("channel", "stable"),
        "source":        data.get("source", "api"),
        "is_stable":     data.get("channel", "stable") == "stable",
        "release_date":  datetime.utcnow().isoformat() + "Z",
        "notified_at":   data.get("notified_at", datetime.utcnow().isoformat() + "Z"),
    }

    firmware_releases.append(release)
    logger.info(f"New firmware release registered: {release['version']}")

    return jsonify({"success": True, "id": release["id"]})


@app.route('/api/device/stats', methods=['POST'])
@require_api_key
def receive_device_stats():
    """Receive device statistics from a NetHunter device."""
    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON")

    device_id = data.get("device_id", "unknown")
    device_stats[device_id] = {
        **data,
        "received_at": datetime.utcnow().isoformat() + "Z"
    }

    return jsonify({"success": True})


@app.route('/api/device/stats/<device_id>', methods=['GET'])
@require_api_key
def get_device_stats(device_id: str):
    """Get stats for a specific device."""
    stats = device_stats.get(device_id)
    if not stats:
        abort(404, description=f"No stats for device {device_id}")
    return jsonify(stats)


@app.route('/api/device/logs', methods=['POST'])
@require_api_key
def receive_device_log():
    """Receive a log entry from a device."""
    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON")

    device_id = data.get("device_id", "unknown")
    if device_id not in device_logs:
        device_logs[device_id] = []

    log_entry = {
        **data,
        "received_at": datetime.utcnow().isoformat() + "Z"
    }
    device_logs[device_id].append(log_entry)
    # Keep last 100 log entries per device
    device_logs[device_id] = device_logs[device_id][-100:]

    return jsonify({"success": True})


@app.route('/api/security/check', methods=['GET'])
def check_firmware_security():
    """Check if a firmware version has known security issues."""
    version = request.args.get('version', '')
    # In production, this would check a security advisory database
    return jsonify({"version": version, "safe": True, "advisories": []})


@app.route('/api/firmware/update-complete', methods=['POST'])
@require_api_key
def firmware_update_complete():
    """Record that a device successfully updated its firmware."""
    data = request.get_json()
    logger.info(f"Device {data.get('device_id')} updated "
                f"{data.get('from_version')} -> {data.get('to_version')}")
    return jsonify({"success": True})


# --- Web Dashboard Routes ---

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html',
                           releases=firmware_releases[-10:],
                           device_count=len(device_stats))


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"})


# --- Error handlers ---

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": str(e.description)}), 400


@app.errorhandler(401)
def unauthorized(e):
    return jsonify({"error": "Unauthorized"}), 401


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": str(e.description)}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f"Starting NetHunter Dashboard on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
