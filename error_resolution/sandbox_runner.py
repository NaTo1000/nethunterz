"""Sandboxed test runner for verifying error fixes."""

import subprocess
import tempfile
import logging
import os
import sys
import json
import time
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SandboxRunner:
    """Runs fix verification tests in an isolated subprocess."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = project_root or Path(__file__).parent.parent
        self.sandbox_dir  = self.project_root / "sandbox"
        self._results: Dict[str, Any] = {}

    def run_test_suite(self, test_file: str = "test_firmware.py",
                       timeout_s: int = 60) -> Dict[str, Any]:
        """Run a specific test file in a subprocess."""
        test_path = self.sandbox_dir / test_file
        if not test_path.exists():
            return {"success": False, "error": f"Test file not found: {test_path}"}
        cmd = [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short", "--json-report"]
        logger.info("Running sandbox test: %s", test_file)
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env={**os.environ, "PYTHONPATH": str(self.project_root)},
            )
            elapsed = time.time() - t0
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-5000:],  # Last 5KB
                "stderr": proc.stderr[-2000:],
                "elapsed_s": elapsed,
                "test_file": test_file,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Test timed out after {timeout_s}s", "test_file": test_file}
        except Exception as exc:
            return {"success": False, "error": str(exc), "test_file": test_file}

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all sandbox tests and return aggregated results."""
        test_files = [
            "test_firmware.py",
            "test_ble.py",
            "test_wifi.py",
            "test_quantum.py",
        ]
        results = {}
        passed = 0
        failed = 0
        for test_file in test_files:
            result = self.run_test_suite(test_file)
            results[test_file] = result
            if result.get("success"):
                passed += 1
            else:
                failed += 1
            logger.info("  %s: %s (%.2fs)",
                        test_file,
                        "PASS" if result.get("success") else "FAIL",
                        result.get("elapsed_s", 0))
        return {
            "total": len(test_files),
            "passed": passed,
            "failed": failed,
            "results": results,
        }

    def verify_fix(self, fix_description: str, test_file: str) -> bool:
        """Verify a fix works by running related tests."""
        logger.info("Verifying fix: %s", fix_description[:80])
        result = self.run_test_suite(test_file)
        success = result.get("success", False)
        self._results[fix_description] = result
        logger.info("Fix verification: %s", "PASS" if success else "FAIL")
        return success
