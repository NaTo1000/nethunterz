"""Runtime benchmarks for ESP32 network throughput and reaction time."""

import time
import statistics
import json
from unittest.mock import MagicMock


def benchmark_json_parsing(iterations: int = 10000) -> dict:
    """Benchmark JSON parsing speed (simulates ESP32 serial data)."""
    sample = json.dumps({
        "heap": 180000, "uptime": 3600, "wifi_rssi": -65,
        "battery_mv": 3700, "ble_connected": True, "error_count": 0,
    })
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        json.loads(sample)
        times.append(time.perf_counter() - t0)
    return {
        "operation": "json_parse",
        "iterations": iterations,
        "mean_us":   statistics.mean(times) * 1e6,
        "median_us": statistics.median(times) * 1e6,
        "p99_us":    sorted(times)[int(iterations * 0.99)] * 1e6,
        "throughput_ops_per_sec": 1 / statistics.mean(times),
    }


def benchmark_serial_read_simulation(iterations: int = 1000) -> dict:
    """Benchmark simulated serial read throughput."""
    mock_serial = MagicMock()
    mock_serial.readline.return_value = (
        b'{"heap":180000,"uptime":3600,"wifi_rssi":-65}\n'
    )
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        data = mock_serial.readline()
        json.loads(data.decode("utf-8").strip())
        times.append(time.perf_counter() - t0)
    return {
        "operation": "serial_read_parse",
        "iterations": iterations,
        "mean_us":   statistics.mean(times) * 1e6,
        "median_us": statistics.median(times) * 1e6,
        "throughput_msgs_per_sec": 1 / statistics.mean(times),
    }


def benchmark_channel_scan_simulation(channels: int = 126) -> dict:
    """Benchmark NRF channel scan simulation speed."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "nrf"))
    from nrf_manager import NRFManager

    times = []
    for _ in range(10):
        t0 = time.perf_counter()
        scan_counts = {ch: 0 for ch in range(channels)}
        scan_counts[6]  = 3
        scan_counts[11] = 2
        scan_counts[76] = 0
        times.append(time.perf_counter() - t0)

    return {
        "operation": "channel_scan_simulation",
        "channels": channels,
        "mean_ms":  statistics.mean(times) * 1e3,
        "median_ms": statistics.median(times) * 1e3,
    }


def run_all_benchmarks() -> None:
    print("=" * 60)
    print("NethunterZ Runtime Benchmarks")
    print("=" * 60)

    benchmarks = [
        benchmark_json_parsing,
        benchmark_serial_read_simulation,
        benchmark_channel_scan_simulation,
    ]
    for bench in benchmarks:
        result = bench()
        print(f"\n[{result['operation']}]")
        for k, v in result.items():
            if k != "operation":
                print(f"  {k}: {v:.2f}" if isinstance(v, float) else f"  {k}: {v}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    run_all_benchmarks()
