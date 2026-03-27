"""Blockchain — immutable block chain for AI state storage."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Block:
    """A single immutable block in the chain."""

    index: int
    data: Any
    previous_hash: str
    timestamp: float = field(default_factory=time.time)
    block_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    nonce: int = 0
    _hash: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self._hash = self._compute_hash()

    def _compute_hash(self) -> str:
        content = json.dumps(
            {
                "index": self.index,
                "data": self.data,
                "previous_hash": self.previous_hash,
                "timestamp": self.timestamp,
                "block_id": self.block_id,
                "nonce": self.nonce,
            },
            sort_keys=True,
            default=str,
        ).encode()
        return hashlib.sha256(content).hexdigest()

    @property
    def hash(self) -> str:
        return self._hash

    def is_valid(self) -> bool:
        return self._hash == self._compute_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "block_id": self.block_id,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
            "timestamp": self.timestamp,
        }


_GENESIS_HASH = "0" * 64


class Chain:
    """Append-only chain of :class:`Block` objects.

    Provides integrity verification and cross-chain communication hooks.
    """

    def __init__(self, chain_id: str | None = None) -> None:
        self.chain_id = chain_id or uuid.uuid4().hex[:8]
        self._blocks: list[Block] = []
        self._append_genesis()

    # ------------------------------------------------------------------
    # Block operations
    # ------------------------------------------------------------------

    def _append_genesis(self) -> None:
        genesis = Block(index=0, data={"type": "genesis"}, previous_hash=_GENESIS_HASH)
        self._blocks.append(genesis)

    def append(self, data: Any) -> Block:
        """Append a new block and return it."""
        prev_hash = self._blocks[-1].hash if self._blocks else _GENESIS_HASH
        block = Block(index=len(self._blocks), data=data, previous_hash=prev_hash)
        if not block.is_valid():
            raise ValueError("Block hash verification failed on creation")
        self._blocks.append(block)
        logger.debug(
            "Chain %s: appended block %d (hash=%s…)",
            self.chain_id,
            block.index,
            block.hash[:12],
        )
        return block

    def get(self, index: int) -> Block:
        return self._blocks[index]

    def latest(self) -> Block:
        return self._blocks[-1]

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------

    def verify(self) -> bool:
        """Verify the entire chain's hash linkage."""
        for i in range(1, len(self._blocks)):
            b = self._blocks[i]
            prev = self._blocks[i - 1]
            if b.previous_hash != prev.hash:
                logger.error(
                    "Chain %s: broken link at block %d", self.chain_id, i
                )
                return False
            if not b.is_valid():
                logger.error(
                    "Chain %s: invalid block %d", self.chain_id, i
                )
                return False
        return True

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def length(self) -> int:
        return len(self._blocks)

    def to_list(self) -> list[dict[str, Any]]:
        return [b.to_dict() for b in self._blocks]
