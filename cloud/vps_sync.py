"""VPS SSH/SFTP integration for self-hosted BLCKjACK cloud nodes."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Optional

logger = logging.getLogger("nethunterz.cloud.vps_sync")

VPS_ROOT_DIR = "/opt/blckjack"

# Docker Compose service definition for self-hosted BLCKjACK cloud
DOCKER_COMPOSE_TEMPLATE = """\
version: "3.9"
services:
  blckjack-cloud:
    image: python:3.11-slim
    container_name: blckjack-cloud
    restart: unless-stopped
    volumes:
      - blckjack_data:/data
    ports:
      - "8080:8080"
    environment:
      - BLCKJACK_DATA_DIR=/data
      - BLCKJACK_ENCRYPTION=aes256
    command: >
      sh -c "pip install aiohttp cryptography &&
             python -m blckjack.server --host 0.0.0.0 --port 8080"
volumes:
  blckjack_data:
"""

# Auto-install script for VPS setup
VPS_SETUP_SCRIPT = """\
#!/usr/bin/env bash
# BLCKjACK VPS auto-install script
set -euo pipefail

echo "[BLCKjACK] Installing dependencies..."
apt-get update -qq && apt-get install -y -qq docker.io docker-compose python3 python3-pip

echo "[BLCKjACK] Creating data directories..."
mkdir -p {root}/logs {root}/firmware_backups {root}/configurations
mkdir -p {root}/ai_decisions {root}/model_data {root}/scenes

echo "[BLCKjACK] Deploying Docker stack..."
cat > {root}/docker-compose.yml << 'EOF'
{compose}
EOF
docker-compose -f {root}/docker-compose.yml up -d

echo "[BLCKjACK] VPS node ready at $(hostname -I | awk '{{print $1}}'):8080"
""".format(root=VPS_ROOT_DIR, compose=DOCKER_COMPOSE_TEMPLATE)


@dataclass
class VPSConfig:
    """SSH/SFTP configuration for a VPS deployment."""

    host: str = "localhost"
    port: int = 22
    username: str = "root"
    key_path: str = "~/.ssh/id_ed25519"
    remote_root: str = VPS_ROOT_DIR
    known_hosts_strict: bool = True
    connection_timeout_s: float = 30.0
    extra_paths: list[str] = field(default_factory=list)


class VPSSync:
    """
    VPS SSH/SFTP sync connector for the BLCKjACK cloud filesystem.

    Supports:
    - SSH-based file upload and download
    - Auto-install script generation for VPS setup
    - Docker container deployment for self-hosted cloud services
    - Delta-sync over SFTP
    """

    def __init__(
        self,
        config: Optional[VPSConfig] = None,
        simulation: bool = True,
    ) -> None:
        self.config = config or VPSConfig()
        self.simulation = simulation
        self._connected = False
        self._uploaded_paths: list[str] = []
        logger.info("VPSSync initialised host=%s (sim=%s)", self.config.host, simulation)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Establish SSH connection to the VPS."""
        if self.simulation:
            self._connected = True
            logger.info("[VPS] Connected to %s:%d (simulation)", self.config.host, self.config.port)
            return True

        raise NotImplementedError("Real SSH requires asyncssh library via companion app")

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("[VPS] Disconnected")

    # ------------------------------------------------------------------
    # Auto-install
    # ------------------------------------------------------------------

    def generate_install_script(self) -> str:
        """Return the VPS auto-install bash script."""
        return VPS_SETUP_SCRIPT

    def generate_docker_compose(self) -> str:
        """Return the Docker Compose service definition."""
        return DOCKER_COMPOSE_TEMPLATE

    async def run_install_script(self) -> bool:
        """Execute the auto-install script on the remote VPS (simulated)."""
        if not self._connected:
            raise RuntimeError("Not connected to VPS")

        if self.simulation:
            logger.info("[VPS] Running install script on %s (simulation)", self.config.host)
            await asyncio.sleep(0)
            return True

        raise NotImplementedError("Real script execution requires SSH via companion app")

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    async def upload(self, local_data: bytes, remote_path: str) -> bool:
        """Upload data to the VPS via SFTP."""
        if not self._connected:
            raise RuntimeError("Not connected to VPS")

        full_remote = str(PurePosixPath(self.config.remote_root) / remote_path)

        if self.simulation:
            self._uploaded_paths.append(full_remote)
            logger.info("[VPS] Uploaded %d bytes to %s (simulation)", len(local_data), full_remote)
            await asyncio.sleep(0)
            return True

        raise NotImplementedError("Real SFTP upload requires asyncssh via companion app")

    async def download(self, remote_path: str) -> Optional[bytes]:
        """Download data from the VPS via SFTP."""
        if not self._connected:
            raise RuntimeError("Not connected to VPS")

        full_remote = str(PurePosixPath(self.config.remote_root) / remote_path)

        if self.simulation:
            logger.info("[VPS] Downloading %s (simulation)", full_remote)
            await asyncio.sleep(0)
            return b"sim_vps_data_" + full_remote.encode()

        raise NotImplementedError("Real SFTP download requires asyncssh via companion app")

    async def list_directory(self, remote_path: str = "") -> list[str]:
        """List files in a remote directory."""
        if not self._connected:
            raise RuntimeError("Not connected to VPS")

        if self.simulation:
            return ["sim_file_001.bin", "sim_config.json", "sim_log.txt"]

        raise NotImplementedError("Real directory listing requires asyncssh via companion app")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "host": self.config.host,
            "port": self.config.port,
            "connected": self._connected,
            "remote_root": self.config.remote_root,
            "uploaded_count": len(self._uploaded_paths),
            "simulation": self.simulation,
        }
