"""Entry point for NRF module orchestration."""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from pathlib import Path

from .pingequa_dual_nrf import PingequaDualNRF, ModuleConfig
from .frequency_manager import FrequencyManager, HopConfig
from .ble_bridge import BLEBridge
from .cloud_orchestrator import CloudOrchestrator
from .security_monitor import SecurityMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nethunterz.nrf.runtime")


async def run(args: argparse.Namespace) -> None:
    log_dir = Path(args.log_dir)

    primary = ModuleConfig(module_id=1, channel=76)
    secondary = ModuleConfig(module_id=2, channel=77)

    nrf = PingequaDualNRF(
        primary=primary,
        secondary=secondary,
        log_dir=log_dir,
        simulation=args.simulation,
    )
    freq_mgr = FrequencyManager()
    ble = BLEBridge(simulation=args.simulation)
    cloud = CloudOrchestrator(simulation=args.simulation)
    security = SecurityMonitor(log_path=str(log_dir / "security_audit.log"))

    nrf.open()
    await security.start()
    await ble.start()
    await cloud.start()
    await nrf.start_capture()

    if args.hop:
        hop_cfg = HopConfig(channels=list(range(2, 84, 10)))
        await freq_mgr.start_hopping(hop_cfg)

    logger.info("NRF runtime running (simulation=%s)", args.simulation)

    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    await stop_event.wait()

    await nrf.stop_capture()
    if args.hop:
        await freq_mgr.stop_hopping()
    await ble.stop()
    await cloud.stop()
    await security.stop()
    nrf.close()
    logger.info("NRF runtime stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="nethunterz NRF module runtime")
    parser.add_argument("--simulation", action="store_true")
    parser.add_argument("--log-dir", default="logs/nrf")
    parser.add_argument("--hop", action="store_true", default=False)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
