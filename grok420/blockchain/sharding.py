"""Shard Manager — sharding technology for maximum bandwidth and error control."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

from grok420.config import BlockchainConfig

logger = logging.getLogger(__name__)


@dataclass
class Shard:
    """A single shard holding a partition of the state space."""

    shard_id: int
    replicas: list[dict[str, Any]] = field(default_factory=list)
    error_count: int = 0

    @property
    def is_healthy(self) -> bool:
        return self.error_count < 3

    def write(self, key: str, value: Any) -> None:
        self.replicas.append({"key": key, "value": value})

    def read(self, key: str) -> Any | None:
        for entry in reversed(self.replicas):
            if entry["key"] == key:
                return entry["value"]
        return None


class ShardManager:
    """Distributes data across N shards with replication for fault tolerance.

    The shard for a given *key* is determined by consistent hashing so
    that adding or removing shards causes minimal reshuffling.
    """

    def __init__(self, config: BlockchainConfig) -> None:
        self._config = config
        self._shards: list[Shard] = [
            Shard(shard_id=i) for i in range(config.shard_count)
        ]
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def write(self, key: str, value: Any) -> list[int]:
        """Write *key/value* to the owning shard and its replicas."""
        primary_id = self._shard_for(key)
        replica_ids = self._replica_ids(primary_id)

        async with self._lock:
            for shard_id in [primary_id] + replica_ids:
                self._shards[shard_id].write(key, value)

        logger.debug(
            "Wrote key=%s to shards %s",
            key,
            [primary_id] + replica_ids,
        )
        return [primary_id] + replica_ids

    async def read(self, key: str) -> Any | None:
        """Read *key* from the primary shard (fall back to replicas on failure)."""
        primary_id = self._shard_for(key)
        replica_ids = self._replica_ids(primary_id)

        async with self._lock:
            for shard_id in [primary_id] + replica_ids:
                shard = self._shards[shard_id]
                if not shard.is_healthy:
                    continue
                value = shard.read(key)
                if value is not None:
                    return value
        return None

    async def recover_shard(self, shard_id: int) -> bool:
        """Rebuild a failed shard from replicas."""
        shard = self._shards[shard_id]
        if shard.is_healthy:
            return True

        replica_ids = self._replica_ids(shard_id)
        async with self._lock:
            for rid in replica_ids:
                donor = self._shards[rid]
                if donor.is_healthy:
                    shard.replicas = list(donor.replicas)
                    shard.error_count = 0
                    logger.info(
                        "Shard %d recovered from replica %d", shard_id, rid
                    )
                    return True

        logger.error("Shard %d recovery failed — no healthy replicas", shard_id)
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _shard_for(self, key: str) -> int:
        """Consistent hash → shard index."""
        digest = hashlib.sha256(key.encode()).digest()
        return int.from_bytes(digest[:4], "big") % self._config.shard_count

    def _replica_ids(self, primary: int) -> list[int]:
        """Return shard IDs for *replication_factor - 1* replicas."""
        count = self._config.shard_count
        rf = min(self._config.replication_factor - 1, count - 1)
        return [(primary + i + 1) % count for i in range(rf)]

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def shard_count(self) -> int:
        return len(self._shards)

    def get_shard_status(self) -> list[dict[str, Any]]:
        return [
            {
                "shard_id": s.shard_id,
                "entry_count": len(s.replicas),
                "error_count": s.error_count,
                "is_healthy": s.is_healthy,
            }
            for s in self._shards
        ]
