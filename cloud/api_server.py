"""Minimal aiohttp REST API server for packet ingestion."""
from __future__ import annotations

import logging

logger = logging.getLogger("nethunterz.cloud.api_server")


class APIServer:
    """Minimal REST API server stub."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self.host = host
        self.port = port
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("APIServer started at %s:%d", self.host, self.port)

    async def stop(self) -> None:
        self._running = False
        logger.info("APIServer stopped")

    def get_status(self) -> dict:
        return {"running": self._running, "host": self.host, "port": self.port}
