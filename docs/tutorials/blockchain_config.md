# Tutorial: Blockchain Shard Configuration

## Shard Count & Replication

```python
from grok420.config import BlockchainConfig

config = BlockchainConfig(
    chain_count=5,       # number of independent chains
    shard_count=32,      # number of shards
    replication_factor=3, # 3x replication per key
    cross_chain_sync=True,
)
```

Higher `shard_count` → better parallelism but higher memory use.
Higher `replication_factor` → better fault tolerance.

## Cross-Chain Synchronisation

When `cross_chain_sync=True`, every write is propagated to all chains,
ensuring any chain can answer queries independently.

## Recovering Failed Shards

```python
# Check shard health
status = mem.get_shard_status()
for s in status:
    if not s["is_healthy"]:
        await mem.recover_shard(s["shard_id"])
```

## Verifying Chain Integrity

```python
health = await mem.verify_all_chains()
if not all(health.values()):
    broken = [k for k, v in health.items() if not v]
    print(f"Broken chains: {broken}")
```
