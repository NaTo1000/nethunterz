#!/usr/bin/env python3
"""
runtime.py – NetHunterZ Pingequa Dual NRF Module Runtime Entry Point.

Starts all subsystems:
  1. PingequaDualNRF  – dual-channel capture / replay
  2. FrequencyManager – spectrum scan + live upgrades
  3. BLEBridge        – smartphone connectivity
  4. CloudOrchestrator – cloud upload + frequency recommendations
  5. SecurityMonitor  – anomaly detection + encrypted audit log

Usage::

    python -m nrf_module.runtime
    python -m nrf_module.runtime --simulation   # (default in CI)
    python -m nrf_module.runtime --log-dir /var/log/nethunterz
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from .pingequa_dual_nrf import PingequaDualNRF, ModuleConfig
from .frequency_manager import FrequencyManager, HopConfig
from .ble_bridge import BLEBridge
from .cloud_orchestrator import CloudOrchestrator, CloudConfig
from .security_monitor import SecurityMonitor, Severity

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("nethunterz.runtime")


# ---------------------------------------------------------------------------
# Main runtime coroutine
# ---------------------------------------------------------------------------

async def run(
    *,
    simulation: bool = True,
    log_dir: str = "logs",
    enable_hopping: bool = False,
) -> None:
    logger.info("=== NetHunterZ Pingequa Dual NRF Runtime starting ===")
    logger.info("Simulation mode: %s", simulation)

    # -- Security monitor ---------------------------------------------------
    monitor = SecurityMonitor(log_path=f"{log_dir}/security_audit.log")
    await monitor.start()

    # -- NRF modules --------------------------------------------------------
    primary = ModuleConfig(module_id=0, channel=76)
    secondary = ModuleConfig(module_id=1, channel=100)

    def on_packet(pkt):
        import hashlib
        h = hashlib.sha256(pkt.payload).hexdigest()
        monitor.record_packet_event(
            module_id=pkt.module_id,
            packet_count_per_sec=0,  # rate tracking in prod
            payload_hash=h,
        )

    from pathlib import Path
    nrf = PingequaDualNRF(
        primary,
        secondary,
        log_dir=Path(log_dir) / "nrf",
        simulation=simulation,
        packet_callback=on_packet,
    )
    nrf.open()
    monitor.watch_task("nrf_capture", asyncio.current_task())  # type: ignore

    # -- Frequency manager --------------------------------------------------
    freq_mgr = FrequencyManager(nrf)

    # -- Cloud orchestrator -------------------------------------------------
    async def on_cloud_recommendation(rec: dict) -> None:
        await freq_mgr.apply_cloud_recommendation(rec)
        if ble_bridge:
            await ble_bridge.notify_frequency_upgrade(rec)

    cloud = CloudOrchestrator(
        simulation=simulation,
        freq_upgrade_callback=on_cloud_recommendation,
    )
    await cloud.start()

    # -- BLE bridge ---------------------------------------------------------
    def on_ble_command(cmd: dict) -> None:
        action = cmd.get("action", "")
        logger.info("BLE command: %s", action)

    ble_bridge = BLEBridge(
        simulation=simulation,
        command_callback=on_ble_command,
    )
    await ble_bridge.start()

    # -- Start capture ------------------------------------------------------
    await nrf.start_capture()

    if enable_hopping:
        hop_cfg = HopConfig(channels=list(range(0, 126, 10)), dwell_time_s=1.0)
        await freq_mgr.start_hopping(hop_cfg)

    # -- Status push loop ---------------------------------------------------
    async def status_loop() -> None:
        while True:
            status = {
                "nrf": nrf.get_status(),
                "cloud": cloud.get_status(),
                "ble": ble_bridge.get_status(),
                "security": monitor.get_status(),
            }
            await ble_bridge.notify_status(status)
            # Route any captured packets to cloud
            packets = await nrf.get_captured_packets()
            for pkt in packets[-10:]:  # last 10 for demo
                await cloud.enqueue_packet(pkt.to_dict())
            await asyncio.sleep(5)

    status_task = asyncio.create_task(status_loop())
    monitor.watch_task("status_loop", status_task)

    # -- Graceful shutdown --------------------------------------------------
    loop = asyncio.get_running_loop()

    def _shutdown_handler():
        logger.info("Shutdown signal received.")
        status_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown_handler)
        except NotImplementedError:
            pass  # Windows

    try:
        logger.info("Runtime operational. Press Ctrl+C to stop.")
        await status_task
    except asyncio.CancelledError:
        pass
    finally:
        if enable_hopping:
            await freq_mgr.stop_hopping()
        await nrf.stop_capture()
        nrf.close()
        await cloud.stop()
        await ble_bridge.stop()
        await monitor.stop()
        logger.info("=== NetHunterZ runtime shut down cleanly ===")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="NetHunterZ Pingequa Dual NRF Module Runtime"
    )
    parser.add_argument(
        "--simulation",
        action="store_true",
        default=True,
        help="Run without hardware (default: enabled)",
    )
    parser.add_argument(
        "--no-simulation",
        dest="simulation",
        action="store_false",
        help="Use real NRF hardware",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory for log files (default: logs/)",
    )
    parser.add_argument(
        "--hop",
        action="store_true",
        default=False,
        help="Enable automatic frequency hopping",
    )
    args = parser.parse_args()

    asyncio.run(
        run(
            simulation=args.simulation,
            log_dir=args.log_dir,
            enable_hopping=args.hop,
        )
    )


if __name__ == "__main__":
    main()
