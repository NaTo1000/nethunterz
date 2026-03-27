"""
Tests for Blockchain Memory System.
"""
import pytest
from ai_engine.blockchain_memory import BlockChain, BlockchainMemorySystem, MemoryBlock


@pytest.fixture
def chain():
    return BlockChain("test-chain", shard_id=0)


@pytest.fixture
def memory():
    return BlockchainMemorySystem(num_chains=2, num_shards=4, replication_factor=2)


def test_chain_genesis(chain):
    assert chain.length == 1  # Genesis block
    assert chain.head.index == 0
    assert chain.head.data["genesis"] is True


def test_chain_append(chain):
    block = chain.append({"key": "value", "number": 42})
    assert block.index == 1
    assert block.previous_hash == chain._blocks[0].hash
    assert block.data["key"] == "value"
    assert chain.length == 2


def test_chain_integrity(chain):
    chain.append({"data": "test1"})
    chain.append({"data": "test2"})
    assert chain.verify_integrity() is True


def test_chain_tamper_detection(chain):
    chain.append({"data": "original"})
    # Tamper with block
    chain._blocks[1].data = {"data": "tampered"}
    assert chain.verify_integrity() is False


def test_chain_query(chain):
    chain.append({"key": "target", "value": 1})
    chain.append({"key": "other", "value": 2})
    chain.append({"key": "target", "value": 3})

    results = chain.query("key", "target")
    assert len(results) == 2


def test_memory_write(memory):
    hashes = memory.write("test_key", {"data": "hello"})
    assert len(hashes) > 0
    assert all(len(h) == 64 for h in hashes)


def test_memory_read(memory):
    memory.write("my.key", {"value": 42})
    results = memory.read("my.key")
    assert len(results) >= 1


def test_memory_replication(memory):
    # With replication_factor=2, data should be in multiple chains
    hashes = memory.write("replicated_key", "data")
    assert len(hashes) == 2  # replication_factor=2


def test_memory_verify_all(memory):
    memory.write("k1", "v1")
    memory.write("k2", "v2")
    report = memory.verify_all()
    assert all(report.values())


def test_memory_stats(memory):
    memory.write("stats_test", {"x": 1})
    stats = memory.get_stats()
    assert stats["num_chains"] == 2
    assert stats["num_shards"] == 4
    assert stats["total_writes"] == 1
    assert stats["total_paths"] == 8  # 2 chains × 4 shards


def test_memory_snapshot(memory):
    snap1 = memory.snapshot()
    assert len(snap1) == 64

    memory.write("after_snap", "data")
    snap2 = memory.snapshot()
    # Snapshot should change after write
    assert snap1 != snap2


def test_shard_selection_consistency(memory):
    # Same key should always go to same shard
    s1 = memory._select_shard("consistent_key")
    s2 = memory._select_shard("consistent_key")
    assert s1 == s2


def test_memory_block_verify():
    block = MemoryBlock(
        block_id="test",
        shard_id=0,
        chain_id="chain",
        index=1,
        timestamp=1234567890.0,
        data={"test": True},
        previous_hash="0" * 64,
    )
    assert block.verify() is True


def test_memory_multiple_reads(memory):
    for i in range(5):
        memory.write("multi_key", {"iteration": i})

    results = memory.read("multi_key", limit=10)
    assert len(results) <= 10
