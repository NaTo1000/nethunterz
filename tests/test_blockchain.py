"""Tests for Blockchain Memory System."""

import asyncio
import pytest

from grok420.blockchain.chain import Block, Chain
from grok420.blockchain.memory import BlockchainMemory
from grok420.blockchain.sharding import Shard, ShardManager
from grok420.config import BlockchainConfig


# ---------------------------------------------------------------------------
# Block / Chain
# ---------------------------------------------------------------------------


def test_block_hash_deterministic():
    b = Block(index=0, data={"x": 1}, previous_hash="0" * 64)
    assert b.hash
    assert b.is_valid()


def test_block_hash_changes_with_data():
    b1 = Block(index=0, data={"x": 1}, previous_hash="0" * 64)
    b2 = Block(index=0, data={"x": 2}, previous_hash="0" * 64)
    assert b1.hash != b2.hash


def test_chain_genesis():
    chain = Chain()
    assert chain.length == 1  # genesis block
    assert chain.latest().index == 0


def test_chain_append_and_verify():
    chain = Chain()
    b = chain.append({"action": "store", "key": "k1"})
    assert b.index == 1
    assert chain.length == 2
    assert chain.verify()


def test_chain_multi_append():
    chain = Chain()
    for i in range(10):
        chain.append({"i": i})
    assert chain.length == 11
    assert chain.verify()


def test_chain_to_list():
    chain = Chain()
    chain.append({"x": 1})
    lst = chain.to_list()
    assert len(lst) == 2
    assert lst[0]["index"] == 0  # genesis


def test_chain_tamper_detection():
    chain = Chain()
    chain.append({"data": "original"})
    # Tamper with the genesis block's stored hash reference
    chain._blocks[0]._hash = "tampered_hash"
    assert not chain.verify()


# ---------------------------------------------------------------------------
# ShardManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shard_manager_write_read():
    config = BlockchainConfig(shard_count=4, replication_factor=2)
    mgr = ShardManager(config)
    await mgr.write("my_key", "my_value")
    value = await mgr.read("my_key")
    assert value == "my_value"


@pytest.mark.asyncio
async def test_shard_manager_multiple_keys():
    config = BlockchainConfig(shard_count=8, replication_factor=3)
    mgr = ShardManager(config)
    for i in range(20):
        await mgr.write(f"key_{i}", f"value_{i}")
    for i in range(20):
        v = await mgr.read(f"key_{i}")
        assert v == f"value_{i}"


@pytest.mark.asyncio
async def test_shard_manager_recovery():
    config = BlockchainConfig(shard_count=4, replication_factor=2)
    mgr = ShardManager(config)
    await mgr.write("rec_key", "rec_value")

    primary = mgr._shard_for("rec_key")
    # Mark primary as unhealthy
    mgr._shards[primary].error_count = 10
    assert not mgr._shards[primary].is_healthy

    ok = await mgr.recover_shard(primary)
    assert ok
    assert mgr._shards[primary].is_healthy


@pytest.mark.asyncio
async def test_shard_manager_status():
    config = BlockchainConfig(shard_count=4)
    mgr = ShardManager(config)
    status = mgr.get_shard_status()
    assert len(status) == 4
    assert all(s["is_healthy"] for s in status)


# ---------------------------------------------------------------------------
# BlockchainMemory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blockchain_memory_store_retrieve():
    config = BlockchainConfig(chain_count=2, shard_count=4)
    mem = BlockchainMemory(config)
    meta = await mem.store("key1", {"data": "hello"})
    assert meta["key"] == "key1"
    assert "block_hash" in meta

    value = await mem.retrieve("key1")
    assert value == {"data": "hello"}


@pytest.mark.asyncio
async def test_blockchain_memory_verify_chains():
    config = BlockchainConfig(chain_count=3)
    mem = BlockchainMemory(config)
    await mem.store("a", 1)
    await mem.store("b", 2)
    results = await mem.verify_all_chains()
    assert all(v for v in results.values())


@pytest.mark.asyncio
async def test_blockchain_memory_chain_lengths():
    config = BlockchainConfig(chain_count=2, cross_chain_sync=False)
    mem = BlockchainMemory(config)
    for i in range(4):
        await mem.store(f"k{i}", i)
    lengths = mem.get_chain_lengths()
    assert len(lengths) == 2
    # Each chain should have received at least 1 store (round-robin)
    for length in lengths.values():
        assert length >= 2  # genesis + at least 1 store


@pytest.mark.asyncio
async def test_blockchain_memory_cross_chain_sync():
    config = BlockchainConfig(chain_count=3, cross_chain_sync=True)
    mem = BlockchainMemory(config)
    await mem.store("sync_key", "sync_value")
    # With cross_chain_sync all chains should have grown
    lengths = mem.get_chain_lengths()
    # All chains should have at least the genesis block + sync entry
    for length in lengths.values():
        assert length >= 2


@pytest.mark.asyncio
async def test_blockchain_memory_recover_shard():
    config = BlockchainConfig(chain_count=2, shard_count=4, replication_factor=2)
    mem = BlockchainMemory(config)
    await mem.store("fault_key", "fault_value")

    # Mark a shard unhealthy
    primary = mem._shards._shard_for("fault_key")
    mem._shards._shards[primary].error_count = 10

    ok = await mem.recover_shard(primary)
    assert ok
