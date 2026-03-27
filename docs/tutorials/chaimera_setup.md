# Tutorial: Setting Up CHAiMERA AI Chains

## Basic Chain

```python
from grok420.chaimera import CHAiMERAChain
from grok420.config import CHAiMERAConfig, ChainMode, SpeedMode

config = CHAiMERAConfig(
    speed_mode=SpeedMode.BALANCED,
    chain_mode=ChainMode.SERIES,
    layer_count=4,
)

async def normalise(data):
    return {"normalised": data, "confidence": 0.85}

async def enrich(data):
    return {"enriched": data, "confidence": 0.92}

async with CHAiMERAChain(config) as chain:
    chain.add_layer(normalise).add_layer(enrich)
    result = await chain.run(raw_data)
```

## Switching Modes at Runtime

```python
# Switch to parallel for redundant error-resilience
chain.set_chain_mode(ChainMode.PARALLEL)

# Switch to high-fidelity for maximum accuracy
chain.set_speed_mode(SpeedMode.HIGH_FIDELITY)

# Switch to low-latency for time-sensitive tasks
chain.set_speed_mode(SpeedMode.LOW_LATENCY)
```

## Superconductor Tuning

```python
# Increase concurrency for high-throughput scenarios
chain.superconductor.set_thread_count(32)

# Check throughput metrics
print(chain.superconductor.metrics.throughput_per_second)
```

## Hybrid Mode

Hybrid mode runs the first `speed_mode.max_layers` layers in series
(causal), then the remainder in parallel (redundant fusion):

```python
config = CHAiMERAConfig(
    chain_mode=ChainMode.HYBRID,
    speed_mode=SpeedMode.BALANCED,  # max_layers=3 for series phase
    layer_count=6,  # layers 0-2 series, 3-5 parallel
)
```
