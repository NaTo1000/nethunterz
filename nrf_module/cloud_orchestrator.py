"""
cloud_orchestrator.py – Cloud computation and orchestration layer.

Responsibilities
----------------
* POST captured packet batches to the cloud analysis endpoint.
* Poll the cloud for frequency upgrade recommendations.
* Relay real-time decisions back to FrequencyManager and BLEBridge.
* Maintain an encrypted HTTPS session with mTLS or token-based auth.
* Provide a WebSocket feed for real-time cloud-to-device push.
* Handle retry / back-off logic and offline queuing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cloud configuration
# ---------------------------------------------------------------------------

@dataclass
class CloudConfig:
    """Runtime configuration for the cloud connection."""
    endpoint: str = ""
    api_key: str = ""
    device_id: str = "nethunterz-device-001"
    ws_endpoint: str = ""
    tls_cert: Optional[str] = None   # path to client cert PEM
    tls_key: Optional[str] = None    # path to client key PEM
    timeout_s: float = 10.0
    retry_max: int = 5
    retry_backoff_s: float = 2.0
    batch_size: int = 50

    @classmethod
    def from_env(cls) -> "CloudConfig":
        return cls(
            endpoint=os.environ.get("CLOUD_ENDPOINT", ""),
            api_key=os.environ.get("CLOUD_API_KEY", ""),
            device_id=os.environ.get("CLOUD_DEVICE_ID", "nethunterz-device-001"),
            ws_endpoint=os.environ.get("CLOUD_WS_ENDPOINT", ""),
            tls_cert=os.environ.get("CLOUD_TLS_CERT"),
            tls_key=os.environ.get("CLOUD_TLS_KEY"),
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class CloudOrchestrator:
    """
    Cloud computation orchestrator for the NetHunterZ NRF runtime.

    When a real cloud endpoint is configured (CLOUD_ENDPOINT env var),
    the orchestrator sends packets and polls for decisions over HTTPS.
    In simulation mode it operates entirely in-process with mock responses.
    """

    def __init__(
        self,
        config: Optional[CloudConfig] = None,
        *,
        simulation: bool = True,
        freq_upgrade_callback: Optional[Any] = None,
    ):
        self._config = config or CloudConfig.from_env()
        self._simulation = simulation or not self._config.endpoint
        self._freq_upgrade_callback = freq_upgrade_callback
        self._upload_queue: asyncio.Queue = asyncio.Queue()
        self._pending_packets: List[dict] = []
        self._worker_task: Optional[asyncio.Task] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._running = False
        self._stats = {
            "packets_uploaded": 0,
            "recommendations_applied": 0,
            "errors": 0,
            "last_upload_ts": None,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._upload_worker())
        if self._config.ws_endpoint and not self._simulation:
            self._ws_task = asyncio.create_task(self._ws_listener())
        logger.info(
            "CloudOrchestrator started (simulation=%s, endpoint=%s).",
            self._simulation, self._config.endpoint or "(none)"
        )

    async def stop(self) -> None:
        self._running = False
        for task in [self._worker_task, self._ws_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._worker_task = None
        self._ws_task = None
        logger.info("CloudOrchestrator stopped.")

    # ------------------------------------------------------------------
    # Packet upload
    # ------------------------------------------------------------------
    async def enqueue_packet(self, packet_dict: dict) -> None:
        """Add a packet to the upload queue."""
        await self._upload_queue.put(packet_dict)

    async def _upload_worker(self) -> None:
        """Batch and upload packets; poll for recommendations."""
        while self._running:
            # Drain queue into pending buffer
            try:
                while True:
                    pkt = self._upload_queue.get_nowait()
                    self._pending_packets.append(pkt)
            except asyncio.QueueEmpty:
                pass

            if len(self._pending_packets) >= self._config.batch_size:
                await self._flush_batch()
            else:
                await self._poll_for_recommendations()

            await asyncio.sleep(5)

    async def _flush_batch(self) -> None:
        batch = self._pending_packets[: self._config.batch_size]
        self._pending_packets = self._pending_packets[self._config.batch_size:]

        if self._simulation:
            await self._sim_upload(batch)
        else:
            await self._real_upload(batch)

    async def _sim_upload(self, batch: List[dict]) -> None:
        """Simulate successful cloud upload and generate mock recommendations."""
        await asyncio.sleep(0.05)  # simulate network latency
        self._stats["packets_uploaded"] += len(batch)
        self._stats["last_upload_ts"] = time.time()
        logger.debug("[SIM] Uploaded %d packets to cloud.", len(batch))
        # Occasionally produce a mock frequency recommendation
        import random
        if random.random() < 0.3:
            recommendation = {
                "module_id": random.randint(0, 1),
                "channel": random.randint(0, 125),
                "reason": "simulated cloud recommendation",
            }
            await self._apply_recommendation(recommendation)

    async def _real_upload(self, batch: List[dict]) -> None:
        """Upload a packet batch to the real cloud endpoint."""
        try:
            import aiohttp  # type: ignore
            ssl_ctx = self._build_ssl_context()
            headers = {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
                "X-Device-ID": self._config.device_id,
            }
            payload = json.dumps({"packets": batch, "device_id": self._config.device_id})
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._config.endpoint}/api/v1/packets",
                    data=payload,
                    headers=headers,
                    ssl=ssl_ctx,
                    timeout=aiohttp.ClientTimeout(total=self._config.timeout_s),
                ) as resp:
                    if resp.status == 200:
                        self._stats["packets_uploaded"] += len(batch)
                        self._stats["last_upload_ts"] = time.time()
                        body = await resp.json()
                        if "recommendation" in body:
                            await self._apply_recommendation(body["recommendation"])
                    else:
                        logger.error(
                            "Cloud upload failed: HTTP %d", resp.status
                        )
                        self._stats["errors"] += 1
                        self._pending_packets = batch + self._pending_packets
        except Exception as exc:
            logger.error("Cloud upload exception: %s", exc)
            self._stats["errors"] += 1
            self._pending_packets = batch + self._pending_packets

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------
    async def _poll_for_recommendations(self) -> None:
        if self._simulation:
            return  # recommendations come via _sim_upload
        try:
            import aiohttp  # type: ignore
            headers = {
                "Authorization": f"Bearer {self._config.api_key}",
                "X-Device-ID": self._config.device_id,
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._config.endpoint}/api/v1/recommendations",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._config.timeout_s),
                ) as resp:
                    if resp.status == 200:
                        body = await resp.json()
                        for rec in body.get("recommendations", []):
                            await self._apply_recommendation(rec)
        except Exception as exc:
            logger.debug("Poll for recommendations failed: %s", exc)

    async def _apply_recommendation(self, recommendation: dict) -> None:
        logger.info("Applying cloud recommendation: %s", recommendation)
        self._stats["recommendations_applied"] += 1
        if self._freq_upgrade_callback:
            try:
                await self._freq_upgrade_callback(recommendation)
            except Exception as exc:  # pragma: no cover
                logger.error("Frequency upgrade callback error: %s", exc)

    # ------------------------------------------------------------------
    # WebSocket real-time feed
    # ------------------------------------------------------------------
    async def _ws_listener(self) -> None:
        """Listen for real-time cloud push over WebSocket."""
        try:
            import aiohttp  # type: ignore
            headers = {"Authorization": f"Bearer {self._config.api_key}"}
            while self._running:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.ws_connect(
                            self._config.ws_endpoint,
                            headers=headers,
                        ) as ws:
                            logger.info("WebSocket connected to cloud.")
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    data = json.loads(msg.data)
                                    if data.get("type") == "recommendation":
                                        await self._apply_recommendation(data["payload"])
                                elif msg.type == aiohttp.WSMsgType.ERROR:
                                    break
                except Exception as exc:
                    logger.warning("WebSocket error: %s – reconnecting in 10s.", exc)
                    await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_ssl_context(self):
        if self._config.tls_cert and self._config.tls_key:
            import ssl
            ctx = ssl.create_default_context()
            ctx.load_cert_chain(self._config.tls_cert, self._config.tls_key)
            return ctx
        return None

    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "simulation": self._simulation,
            "endpoint": self._config.endpoint or "(none)",
            "stats": self.get_stats(),
            "pending_packets": len(self._pending_packets),
        }
