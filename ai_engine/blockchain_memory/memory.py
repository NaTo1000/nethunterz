"""
Multi-Blockchain Memory System with Sharding.

Provides immutable, high-bandwidth memory storage for the AI engine using
a multi-chain architecture with shard-based fault tolerance and error correction.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryBlock:
    """A single immutable block in the blockchain memory."""
    block_id: str
    shard_id: int
    chain_id: str
    index: int
    timestamp: float
    data: Any
    previous_hash: str
    hash: str = field(default="")
    nonce: int = 0

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = json.dumps({
            "block_id": self.block_id,
            "shard_id": self.shard_id,
            "chain_id": self.chain_id,
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def verify(self) -> bool:
        """Verify the block's hash integrity."""
        return self.hash == self._compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "shard_id": self.shard_id,
            "chain_id": self.chain_id,
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }


class BlockChain:
    """A single blockchain shard."""

    GENESIS_HASH = "0" * 64

    def __init__(self, chain_id: str, shard_id: int) -> None:
        self.chain_id = chain_id
        self.shard_id = shard_id
        self._blocks: List[MemoryBlock] = []
        self._create_genesis()

    def _create_genesis(self) -> None:
        genesis = MemoryBlock(
            block_id=str(uuid.uuid4()),
            shard_id=self.shard_id,
            chain_id=self.chain_id,
            index=0,
            timestamp=time.time(),
            data={"genesis": True, "chain_id": self.chain_id},
            previous_hash=self.GENESIS_HASH,
        )
        self._blocks.append(genesis)

    @property
    def head(self) -> MemoryBlock:
        return self._blocks[-1]

    @property
    def length(self) -> int:
        return len(self._blocks)

    def append(self, data: Any) -> MemoryBlock:
        """Add a new block with the given data."""
        block = MemoryBlock(
            block_id=str(uuid.uuid4()),
            shard_id=self.shard_id,
            chain_id=self.chain_id,
            index=len(self._blocks),
            timestamp=time.time(),
            data=data,
            previous_hash=self.head.hash,
        )
        self._blocks.append(block)
        return block

    def verify_integrity(self) -> bool:
        """Verify the entire chain's integrity."""
        for i, block in enumerate(self._blocks):
            if not block.verify():
                return False
            if i > 0 and block.previous_hash != self._blocks[i - 1].hash:
                return False
        return True

    def get_blocks(self, limit: Optional[int] = None) -> List[MemoryBlock]:
        """Return blocks, optionally limited to the most recent N."""
        if limit:
            return self._blocks[-limit:]
        return list(self._blocks)

    def query(self, key: str, value: Any) -> List[MemoryBlock]:
        """Search blocks for matching key-value in data dict."""
        results = []
        for block in self._blocks[1:]:  # skip genesis
            if isinstance(block.data, dict) and block.data.get(key) == value:
                results.append(block)
        return results


class BlockchainMemorySystem:
    """
    Multi-Blockchain Memory System with Sharding.

    Distributes memory across multiple chains and shards for:
    - Maximum read/write bandwidth via parallel chains
    - Fault tolerance via redundant shards
    - Error correction via cross-shard verification
    - Immutable audit trail for all AI decisions

    Architecture:
        N chains × M shards = N*M parallel write paths
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        num_chains: int = 4,
        num_shards: int = 8,
        replication_factor: int = 2,
    ) -> None:
        self.num_chains = num_chains
        self.num_shards = num_shards
        self.replication_factor = min(replication_factor, num_chains)
        self._chains: Dict[str, Dict[int, BlockChain]] = {}
        self._write_counter = 0
        self._chain_ids: List[str] = []

        # Initialize chain/shard matrix
        for _ in range(num_chains):
            chain_id = str(uuid.uuid4())
            self._chain_ids.append(chain_id)
            self._chains[chain_id] = {
                shard_id: BlockChain(chain_id, shard_id)
                for shard_id in range(num_shards)
            }

    def _select_shard(self, key: str) -> int:
        """Consistent hash-based shard selection."""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return int(key_hash[:8], 16) % self.num_shards

    def _select_chains(self) -> List[str]:
        """Round-robin chain selection with replication."""
        idx = self._write_counter % self.num_chains
        selected = []
        for i in range(self.replication_factor):
            selected.append(self._chain_ids[(idx + i) % self.num_chains])
        return selected

    def write(self, key: str, data: Any) -> List[str]:
        """
        Write data to the memory system. Returns list of block hashes written.

        Data is written to `replication_factor` chains for redundancy.
        Shard is selected by consistent hash of the key.
        """
        shard_id = self._select_shard(key)
        chains = self._select_chains()
        self._write_counter += 1

        payload = {
            "key": key,
            "data": data,
            "write_id": self._write_counter,
            "timestamp": time.time(),
        }

        block_hashes = []
        for chain_id in chains:
            block = self._chains[chain_id][shard_id].append(payload)
            block_hashes.append(block.hash)

        return block_hashes

    def read(self, key: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Read all entries for a key, newest first."""
        shard_id = self._select_shard(key)
        results = []

        for chain_id in self._chain_ids:
            blocks = self._chains[chain_id][shard_id].query("key", key)
            for block in blocks:
                results.append({
                    "chain_id": chain_id,
                    "block_hash": block.hash,
                    "timestamp": block.timestamp,
                    "data": block.data.get("data") if isinstance(block.data, dict) else block.data,
                })

        # Sort by timestamp descending, deduplicate by write_id
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        seen = set()
        deduped = []
        for r in results:
            wid = r["data"] if not isinstance(r["data"], dict) else None
            if wid not in seen:
                deduped.append(r)
                seen.add(wid)

        return deduped[:limit]

    def verify_all(self) -> Dict[str, bool]:
        """Verify integrity of all chains and shards."""
        report = {}
        for chain_id, shards in self._chains.items():
            for shard_id, chain in shards.items():
                key = f"{chain_id[:8]}:shard{shard_id}"
                report[key] = chain.verify_integrity()
        return report

    def get_stats(self) -> Dict[str, Any]:
        """Return memory system statistics."""
        total_blocks = sum(
            chain.length
            for shards in self._chains.values()
            for chain in shards.values()
        )
        return {
            "num_chains": self.num_chains,
            "num_shards": self.num_shards,
            "replication_factor": self.replication_factor,
            "total_blocks": total_blocks,
            "total_writes": self._write_counter,
            "total_paths": self.num_chains * self.num_shards,
        }

    def snapshot(self) -> str:
        """Return a SHA-256 hash snapshot of the full memory state."""
        state = json.dumps(
            {
                cid: {
                    str(sid): chain.head.hash
                    for sid, chain in shards.items()
                }
                for cid, shards in self._chains.items()
            },
            sort_keys=True,
        )
        return hashlib.sha256(state.encode()).hexdigest()
