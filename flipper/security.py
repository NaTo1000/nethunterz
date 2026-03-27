"""Security manager: trail-wipe, AES-256 encryption, MAC/IP anonymisation."""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nethunterz.flipper.security")

_AES_KEY_SIZE = 32  # 256-bit AES


class WipeMode(Enum):
    """Secure erase modes."""

    SINGLE_PASS = "single_pass"     # One overwrite with zeros
    DOD_3_PASS = "dod_3_pass"       # DoD 5220.22-M (3-pass)
    GUTMANN_7 = "gutmann_7"         # 7-pass random overwrite


@dataclass
class SecurityConfig:
    """Security configuration for the Flipper Zero system."""

    ble_encryption: bool = True
    mac_randomisation: bool = True
    ip_anonymisation: bool = True
    trail_wipe_on_panic: bool = True
    wipe_mode: WipeMode = WipeMode.DOD_3_PASS
    session_key_rotation_s: float = 3600.0
    max_failed_auth: int = 3


@dataclass
class SecurityEvent:
    """Audit log entry for a security-relevant event."""

    event_type: str
    details: str
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class AES256Cipher:
    """
    Symmetric AES-256 encryption layer using the cryptography library.

    Falls back to a XOR-based simulation when the library is unavailable,
    ensuring the module can be imported in any environment.
    """

    def __init__(self, key: Optional[bytes] = None) -> None:
        self._key: bytes = key if key is not None else secrets.token_bytes(_AES_KEY_SIZE)
        self._available = self._check_crypto()

    @staticmethod
    def _check_crypto() -> bool:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
            return True
        except ImportError:
            return False

    def generate_key(self) -> bytes:
        self._key = secrets.token_bytes(_AES_KEY_SIZE)
        return self._key

    def encrypt(self, plaintext: bytes, associated_data: Optional[bytes] = None) -> bytes:
        if self._available:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = secrets.token_bytes(12)
            aad = associated_data or b""
            ciphertext = AESGCM(self._key).encrypt(nonce, plaintext, aad)
            return nonce + ciphertext
        # XOR simulation fallback
        nonce = secrets.token_bytes(12)
        ct = bytes(b ^ self._key[i % _AES_KEY_SIZE] for i, b in enumerate(plaintext))
        return nonce + ct

    def decrypt(self, ciphertext: bytes, associated_data: Optional[bytes] = None) -> bytes:
        if self._available:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce, ct = ciphertext[:12], ciphertext[12:]
            aad = associated_data or b""
            return AESGCM(self._key).decrypt(nonce, ct, aad)
        # XOR simulation fallback
        ct = ciphertext[12:]
        return bytes(b ^ self._key[i % _AES_KEY_SIZE] for i, b in enumerate(ct))


class TrailWiper:
    """
    Secure trail-wipe engine.

    Overwrites files and memory regions to prevent forensic recovery.
    Supports single-pass, DoD 3-pass, and 7-pass Gutmann overwrite modes.
    """

    def __init__(self, mode: WipeMode = WipeMode.DOD_3_PASS) -> None:
        self.mode = mode
        self._wiped_paths: list[str] = []

    def wipe_file(self, path: Path) -> bool:
        """Securely overwrite and delete a file."""
        if not path.exists():
            return False

        size = path.stat().st_size
        passes = self._overwrite_passes()

        try:
            with open(path, "r+b") as fh:
                for pass_data in passes:
                    fh.seek(0)
                    fh.write(pass_data(size))
                    fh.flush()
                    os.fsync(fh.fileno())
            path.unlink()
            self._wiped_paths.append(str(path))
            logger.info("File wiped: %s (%d bytes, mode=%s)", path, size, self.mode.value)
            return True
        except OSError as exc:
            logger.error("Wipe failed for %s: %s", path, exc)
            return False

    def wipe_directory(self, directory: Path, recursive: bool = True) -> int:
        """Wipe all files in a directory. Returns number of files wiped."""
        count = 0
        if not directory.exists():
            return count
        glob = directory.rglob("*") if recursive else directory.glob("*")
        for item in glob:
            if item.is_file():
                if self.wipe_file(item):
                    count += 1
        if directory.exists():
            try:
                directory.rmdir()
            except OSError:
                pass
        logger.info("Directory wipe complete: %s (%d files)", directory, count)
        return count

    def wipe_bytes(self, size: int) -> bytes:
        """Generate a secure overwrite buffer of the given size."""
        return secrets.token_bytes(size)

    def _overwrite_passes(self):
        if self.mode == WipeMode.SINGLE_PASS:
            return [lambda n: b"\x00" * n]
        if self.mode == WipeMode.DOD_3_PASS:
            return [
                lambda n: b"\x00" * n,
                lambda n: b"\xFF" * n,
                lambda n: secrets.token_bytes(n),
            ]
        # Gutmann 7-pass
        patterns = [
            lambda n: b"\x00" * n,
            lambda n: b"\xFF" * n,
            lambda n: b"\x55" * n,
            lambda n: b"\xAA" * n,
            lambda n: secrets.token_bytes(n),
            lambda n: secrets.token_bytes(n),
            lambda n: secrets.token_bytes(n),
        ]
        return patterns

    @property
    def wiped_paths(self) -> list[str]:
        return list(self._wiped_paths)


class SecurityManager:
    """
    Central security manager for the Flipper Zero stack.

    Provides:
    - AES-256 encrypted BLE communication
    - Trail-wipe (single-button secure erase of all local data)
    - MAC address randomisation stubs
    - Session key rotation
    - Security event audit log
    """

    def __init__(
        self,
        config: Optional[SecurityConfig] = None,
        simulation: bool = True,
    ) -> None:
        self.config = config or SecurityConfig()
        self.simulation = simulation
        self.cipher = AES256Cipher()
        self.wiper = TrailWiper(mode=self.config.wipe_mode)
        self._audit_log: list[SecurityEvent] = []
        self._session_key: bytes = secrets.token_bytes(_AES_KEY_SIZE)
        self._failed_auth_count = 0
        logger.info("SecurityManager initialised (sim=%s)", simulation)

    # ------------------------------------------------------------------
    # BLE encryption
    # ------------------------------------------------------------------

    def encrypt_ble_payload(self, payload: bytes) -> bytes:
        """Encrypt a BLE payload using AES-256-GCM."""
        ct = self.cipher.encrypt(payload)
        self._log_event("ble_encrypt", f"payload_len={len(payload)}")
        return ct

    def decrypt_ble_payload(self, ciphertext: bytes) -> bytes:
        """Decrypt an AES-256-GCM BLE payload."""
        pt = self.cipher.decrypt(ciphertext)
        self._log_event("ble_decrypt", f"ciphertext_len={len(ciphertext)}")
        return pt

    # ------------------------------------------------------------------
    # MAC / IP anonymisation stubs
    # ------------------------------------------------------------------

    def randomise_mac(self) -> str:
        """Generate and return a random MAC address (stub; applies via OS on device)."""
        octets = [secrets.randbits(8) for _ in range(6)]
        octets[0] = (octets[0] & 0xFE) | 0x02  # Locally administered, unicast
        mac = ":".join(f"{o:02x}" for o in octets)
        self._log_event("mac_randomise", f"new_mac={mac}")
        logger.info("MAC randomised: %s", mac)
        return mac

    def anonymise_ip(self) -> None:
        """Log IP anonymisation intent (actual routing handled by OS/VPN)."""
        self._log_event("ip_anonymise", "routing_through_anonymisation_layer")
        logger.info("IP anonymisation requested")

    # ------------------------------------------------------------------
    # Trail-wipe
    # ------------------------------------------------------------------

    def trail_wipe(self, data_dirs: Optional[list[Path]] = None) -> dict:
        """
        One-button secure erase of all local Flipper data.

        Wipes specified data directories, rotates session keys,
        and clears the in-memory audit log.
        """
        self._log_event("trail_wipe_initiated", f"mode={self.config.wipe_mode.value}")
        logger.warning("TRAIL WIPE INITIATED")

        wiped_files = 0
        if data_dirs:
            for d in data_dirs:
                wiped_files += self.wiper.wipe_directory(d)

        # Rotate session key
        self._session_key = secrets.token_bytes(_AES_KEY_SIZE)
        self.cipher.generate_key()

        # Clear sensitive in-memory state
        cleared_events = len(self._audit_log)
        self._audit_log.clear()
        self._failed_auth_count = 0

        logger.warning("Trail wipe complete: %d files wiped, %d events cleared", wiped_files,
                       cleared_events)
        return {
            "wiped_files": wiped_files,
            "cleared_events": cleared_events,
            "key_rotated": True,
        }

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, provided_key_hash: str) -> bool:
        """Verify a session key hash for companion app auth."""
        expected = hashlib.sha256(self._session_key).hexdigest()
        if secrets.compare_digest(provided_key_hash, expected):
            self._failed_auth_count = 0
            self._log_event("auth_success", "companion_authenticated")
            return True

        self._failed_auth_count += 1
        self._log_event("auth_failure", f"attempts={self._failed_auth_count}")
        if self._failed_auth_count >= self.config.max_failed_auth:
            logger.warning("Max auth failures reached — initiating trail wipe")
            self.trail_wipe()
        return False

    def get_session_key_hash(self) -> str:
        """Return the current session key hash (for companion pairing)."""
        return hashlib.sha256(self._session_key).hexdigest()

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def _log_event(self, event_type: str, details: str) -> None:
        import time
        evt = SecurityEvent(event_type=event_type, details=details, timestamp=time.time())
        self._audit_log.append(evt)

    def get_audit_log(self) -> list[dict]:
        return [e.to_dict() for e in self._audit_log]

    def get_status(self) -> dict:
        return {
            "ble_encryption": self.config.ble_encryption,
            "mac_randomisation": self.config.mac_randomisation,
            "ip_anonymisation": self.config.ip_anonymisation,
            "wipe_mode": self.config.wipe_mode.value,
            "failed_auth_count": self._failed_auth_count,
            "audit_log_entries": len(self._audit_log),
            "simulation": self.simulation,
        }
