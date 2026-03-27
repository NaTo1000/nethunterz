"""Blockchain Memory System — multi-chain AI memory and state management.

Provides a unified interface over multiple :class:`Chain` instances and
a :class:`ShardManager` for high-bandwidth key/value access.  Every
write is committed to a chain block for immutable audit trail.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from grok420.blockchain.chain import Chain
from grok420.blockchain.sharding import ShardManager
from grok420.config import BlockchainConfig

logger = logging.getLogger(__name__)


class BlockchainMemory:
    """Multi-blockchain memory system with sharding and cross-chain sync.

    Architecture
    -----------
    * Multiple :class:`Chain` instances — one per ``chain_count`` setting.
    * A :class:`ShardManager` for bandwidth-efficient key/value storage.
    * Round-robin chain selection for write distribution.
    * Cross-chain sync propagates critical state to all chains.
    """

    def __init__(self, config: BlockchainConfig | None = None) -> None:
        self._config = config or BlockchainConfig()
        self._chains: list[Chain] = [
            Chain(chain_id=f"chain_{i}") for i in range(self._config.chain_count)
        ]
        self._shards = ShardManager(self._config)
        self._write_index = 0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def store(self, key: str, value: Any) -> dict[str, Any]:
        """Persist *key/value* in the shard layer and commit to a chain block."""
        shard_ids = await self._shards.write(key, value)

        async with self._lock:
            chain = self._chains[self._write_index % len(self._chains)]
            self._write_index += 1

        block = chain.append({"op": "store", "key": key, "shard_ids": shard_ids})

        if self._config.cross_chain_sync:
            await self._sync_to_all_chains({"op": "sync", "key": key, "block_hash": block.hash})

        logger.debug("Stored key=%s → block %d on %s", key, block.index, chain.chain_id)
        return {
            "key": key,
            "chain_id": chain.chain_id,
            "block_index": block.index,
            "block_hash": block.hash,
            "shard_ids": shard_ids,
        }

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def retrieve(self, key: str) -> Any | None:
        """Retrieve the most recent value for *key* from the shard layer."""
        return await self._shards.read(key)

    # ------------------------------------------------------------------
    # Integrity & recovery
    # ------------------------------------------------------------------

    async def verify_all_chains(self) -> dict[str, bool]:
        """Verify integrity of every chain."""
        results: dict[str, bool] = {}
        async with self._lock:
            chains = list(self._chains)
        for chain in chains:
            results[chain.chain_id] = chain.verify()
        return results

    async def recover_shard(self, shard_id: int) -> bool:
        return await self._shards.recover_shard(shard_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _sync_to_all_chains(self, data: dict[str, Any]) -> None:
        async with self._lock:
            chains = list(self._chains)
        for chain in chains:
            try:
                chain.append(data)
            except Exception as exc:
                logger.warning(
                    "Cross-chain sync failed for %s: %s", chain.chain_id, exc
                )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def chain_count(self) -> int:
        return len(self._chains)

    @property
    def shard_manager(self) -> ShardManager:
        return self._shards

    def get_chain_lengths(self) -> dict[str, int]:
        return {c.chain_id: c.length for c in self._chains}

    def get_shard_status(self) -> list[dict[str, Any]]:
        return self._shards.get_shard_status()
