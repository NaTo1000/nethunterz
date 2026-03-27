"""
api_server.py – Cloud REST + WebSocket API server for NetHunterZ.

Provides:
  POST /api/v1/packets          – ingest packet batches from devices
  GET  /api/v1/recommendations  – poll for pending frequency recommendations
  GET  /api/v1/sessions         – list active device sessions
  GET  /api/v1/status           – service health
  WS   /api/v1/ws/{device_id}   – real-time bi-directional channel

Built with aiohttp; falls back to a stub if aiohttp is not installed.
"""

from __future__ import annotations

import json
import logging
import os
from functools import wraps
from typing import Optional

logger = logging.getLogger(__name__)


def _require_auth(handler):
    """Decorator that validates the Bearer token on each request."""
    @wraps(handler)
    async def wrapper(request):
        api_key = os.environ.get("CLOUD_API_KEY", "")
        if api_key:
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {api_key}":
                from aiohttp import web  # type: ignore
                return web.Response(status=401, text="Unauthorized")
        return await handler(request)
    return wrapper


def create_app(orchestrator=None):
    """
    Create and configure the aiohttp web application.

    Parameters
    ----------
    orchestrator : Orchestrator | None
        If None, a standalone orchestrator with a FrequencyEngine is created.

    Returns
    -------
    aiohttp.web.Application  (or a stub dict in envs without aiohttp)
    """
    try:
        from aiohttp import web  # type: ignore
    except ImportError:
        logger.warning("aiohttp not installed – API server unavailable.")
        return None

    from .orchestrator import Orchestrator
    from .frequency_engine import FrequencyEngine

    if orchestrator is None:
        engine = FrequencyEngine()
        orchestrator = Orchestrator(frequency_engine=engine)

    app = web.Application()
    ws_clients: dict = {}

    # ------------------------------------------------------------------ routes

    @_require_auth
    async def post_packets(request):
        try:
            body = await request.json()
        except Exception:
            return web.Response(status=400, text="Invalid JSON")
        device_id = body.get("device_id") or request.headers.get("X-Device-ID", "unknown")
        packets = body.get("packets", [])
        result = await orchestrator.ingest_packets(device_id, packets)
        # Push recommendations via WebSocket if client is connected
        if device_id in ws_clients:
            for rec in result.get("recommendations", []):
                try:
                    await ws_clients[device_id].send_json(
                        {"type": "recommendation", "payload": rec}
                    )
                except Exception:
                    pass
        return web.json_response(result)

    @_require_auth
    async def get_recommendations(request):
        device_id = request.rel_url.query.get("device_id") or \
                    request.headers.get("X-Device-ID", "unknown")
        recs = orchestrator.get_pending_recommendations(device_id)
        return web.json_response({"recommendations": recs})

    @_require_auth
    async def get_sessions(request):
        return web.json_response({"sessions": orchestrator.get_sessions()})

    async def get_status(request):
        return web.json_response(orchestrator.get_status())

    async def websocket_handler(request):
        device_id = request.match_info.get("device_id", "unknown")
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        ws_clients[device_id] = ws
        logger.info("WebSocket connection: %s", device_id)
        try:
            async for msg in ws:
                if msg.type == 0x1:  # WSMsgType.TEXT
                    try:
                        data = json.loads(msg.data)
                        # Treat incoming WS messages as packet uploads
                        if data.get("type") == "packets":
                            result = await orchestrator.ingest_packets(
                                device_id, data.get("packets", [])
                            )
                            await ws.send_json(result)
                    except Exception as exc:
                        logger.debug("WS parse error: %s", exc)
        finally:
            ws_clients.pop(device_id, None)
            logger.info("WebSocket disconnected: %s", device_id)
        return ws

    app.router.add_post("/api/v1/packets", post_packets)
    app.router.add_get("/api/v1/recommendations", get_recommendations)
    app.router.add_get("/api/v1/sessions", get_sessions)
    app.router.add_get("/api/v1/status", get_status)
    app.router.add_get("/api/v1/ws/{device_id}", websocket_handler)

    # Start orchestrator on app startup
    async def on_startup(app):
        await orchestrator.start()

    async def on_cleanup(app):
        await orchestrator.stop()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        from aiohttp import web  # type: ignore
    except ImportError:
        print("aiohttp required: pip install aiohttp")
        raise SystemExit(1)

    app = create_app()
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
