"""OTA update speed benchmarks."""

import time
import statistics
import io
import hashlib


def simulate_firmware_download(size_bytes: int, chunk_size: int = 1024) -> dict:
    """Simulate downloading a firmware binary in chunks."""
    firmware = b"\xAB" * size_bytes
    checksum = hashlib.sha256(firmware).hexdigest()
    buf = io.BytesIO(firmware)
    chunks_received = 0
    bytes_received  = 0
    t0 = time.perf_counter()
    while True:
        chunk = buf.read(chunk_size)
        if not chunk:
            break
        bytes_received  += len(chunk)
        chunks_received += 1
    elapsed = time.perf_counter() - t0
    verify_t0 = time.perf_counter()
    calc = hashlib.sha256(firmware).hexdigest()
    verify_time = time.perf_counter() - verify_t0
    return {
        "firmware_size_kb":    size_bytes / 1024,
        "chunk_size_bytes":    chunk_size,
        "chunks_count":        chunks_received,
        "download_time_s":     elapsed,
        "throughput_kbs":      (bytes_received / 1024) / max(elapsed, 1e-9),
        "sha256_match":        calc == checksum,
        "verify_time_ms":      verify_time * 1000,
    }


def benchmark_ota_chunk_sizes() -> None:
    print("=" * 60)
    print("OTA Update Speed Benchmarks")
    print("=" * 60)
    firmware_sizes = [512 * 1024, 1 * 1024 * 1024, 2 * 1024 * 1024]
    chunk_sizes    = [256, 512, 1024, 4096]
    for fw_size in firmware_sizes:
        print(f"\nFirmware: {fw_size // 1024} KB")
        for chunk in chunk_sizes:
            result = simulate_firmware_download(fw_size, chunk)
            print(f"  chunk={chunk:5d}B | "
                  f"time={result['download_time_s']:.3f}s | "
                  f"throughput={result['throughput_kbs']:.0f} KB/s | "
                  f"verify={result['verify_time_ms']:.2f}ms | "
                  f"SHA256={'✓' if result['sha256_match'] else '✗'}")
    print("\n" + "=" * 60)


def benchmark_sha256_verification() -> dict:
    sizes = [512 * 1024, 1024 * 1024, 2048 * 1024]
    results = {}
    for size in sizes:
        data = b"\x00" * size
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            hashlib.sha256(data).hexdigest()
            times.append(time.perf_counter() - t0)
        results[f"{size // 1024}KB"] = {
            "mean_ms":   statistics.mean(times) * 1000,
            "median_ms": statistics.median(times) * 1000,
        }
    return results


if __name__ == "__main__":
    benchmark_ota_chunk_sizes()
    print("\nSHA256 Verification Speed:")
    sha_results = benchmark_sha256_verification()
    for size_label, stats in sha_results.items():
        print(f"  {size_label}: mean={stats['mean_ms']:.2f}ms")
