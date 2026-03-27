"""Encryptor — end-to-end AES-256-GCM encryption for inter-layer communication."""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    _CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("cryptography package not available; using fallback XOR stub")


class Encryptor:
    """Symmetric AES-256-GCM encryptor for Grok 420 inter-component traffic.

    Usage
    -----
    ::

        enc = Encryptor()            # generates a new random key
        ciphertext = enc.encrypt(b"hello world")
        plaintext  = enc.decrypt(ciphertext)  # b"hello world"
    """

    KEY_SIZE = 32  # 256-bit

    def __init__(self, key: bytes | None = None) -> None:
        self._key = key if key is not None else os.urandom(self.KEY_SIZE)
        if len(self._key) != self.KEY_SIZE:
            raise ValueError(f"key must be exactly {self.KEY_SIZE} bytes")

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt *plaintext* and return *nonce || ciphertext*."""
        if _CRYPTOGRAPHY_AVAILABLE:
            return self._aes_gcm_encrypt(plaintext)
        return self._xor_encrypt(plaintext)

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt *nonce || ciphertext* produced by :meth:`encrypt`."""
        if _CRYPTOGRAPHY_AVAILABLE:
            return self._aes_gcm_decrypt(data)
        return self._xor_decrypt(data)

    def encrypt_b64(self, plaintext: bytes) -> str:
        """Encrypt and base64-encode for wire transport."""
        return base64.b64encode(self.encrypt(plaintext)).decode()

    def decrypt_b64(self, data: str) -> bytes:
        """Decode base64 and decrypt."""
        return self.decrypt(base64.b64decode(data))

    # ------------------------------------------------------------------
    # AES-GCM implementation
    # ------------------------------------------------------------------

    _NONCE_SIZE = 12  # 96-bit GCM nonce

    def _aes_gcm_encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(self._NONCE_SIZE)
        aesgcm = AESGCM(self._key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def _aes_gcm_decrypt(self, data: bytes) -> bytes:
        if len(data) < self._NONCE_SIZE:
            raise ValueError("Ciphertext too short")
        nonce = data[: self._NONCE_SIZE]
        ciphertext = data[self._NONCE_SIZE:]
        aesgcm = AESGCM(self._key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    # ------------------------------------------------------------------
    # XOR fallback (testing only — NOT cryptographically secure)
    # ------------------------------------------------------------------

    def _xor_encrypt(self, plaintext: bytes) -> bytes:
        import struct
        nonce = os.urandom(self._NONCE_SIZE)
        key_stream = (self._key * ((len(plaintext) // self.KEY_SIZE) + 1))[: len(plaintext)]
        ct = bytes(a ^ b for a, b in zip(plaintext, key_stream))
        return nonce + ct

    def _xor_decrypt(self, data: bytes) -> bytes:
        plaintext_bytes = data[self._NONCE_SIZE:]
        key_stream = (self._key * ((len(plaintext_bytes) // self.KEY_SIZE) + 1))[
            : len(plaintext_bytes)
        ]
        return bytes(a ^ b for a, b in zip(plaintext_bytes, key_stream))

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls, env_var: str = "GROK420_ENCRYPTION_KEY") -> "Encryptor":
        """Load key from environment (base64-encoded 32-byte key)."""
        raw = os.environ.get(env_var)
        if raw:
            key = base64.b64decode(raw)
            if len(key) == cls.KEY_SIZE:
                return cls(key)
            logger.warning(
                "Env key has wrong length (%d), generating new key", len(key)
            )
        return cls()

    def export_key_b64(self) -> str:
        return base64.b64encode(self._key).decode()
