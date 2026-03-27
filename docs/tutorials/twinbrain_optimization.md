# Tutorial: TWINBRAIN Configuration & Optimisation

## Basic Setup

```python
from grok420.twinbrain import TwinBrain
from grok420.config import TwinBrainConfig

async def my_eval(data):
    # Your AI evaluation logic
    score = model.predict(data)
    return {"result": score, "confidence": 0.88}

config = TwinBrainConfig(
    consensus_threshold=0.75,
    sync_interval_ms=100,
    max_divergence_retries=3,
)

async with TwinBrain(my_eval, config=config) as tb:
    result = await tb.evaluate(input_data)
```

## Two Independent Evaluation Functions

For maximum independence, provide separate eval functions for each brain:

```python
async def eval_a(data):  # Model A — high accuracy
    return {"result": model_a.predict(data), "confidence": 0.90}

async def eval_b(data):  # Model B — high speed
    return {"result": model_b.predict(data), "confidence": 0.85}

async with TwinBrain(eval_a, eval_b, config=config) as tb:
    consensus = await tb.evaluate(data)
```

## Tuning Consensus Threshold

- `0.5` — agree if average confidence is above 50% (permissive)
- `0.75` — balanced (default)
- `0.95` — near-certain agreement required (strict)

```python
tb.set_consensus_threshold(0.85)
```

## Interpreting Results

```python
result = await tb.evaluate(data)
print(f"Agreed: {result.agreed}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Output: {result.output}")
print(f"Retries: {result.retries}")
if result.error:
    print(f"Error: {result.error}")
```
