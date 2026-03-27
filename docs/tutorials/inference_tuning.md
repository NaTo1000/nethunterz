# Tutorial: Adjusting Inference Power & Hardware Allocation

## Inference Power

`inference_power` (0.0–1.0) controls the fraction of `max_bots` slots
available for concurrent execution.

```python
conductor.set_inference_power(0.3)  # conservative — 30% of slots
conductor.set_inference_power(1.0)  # maximum throughput
```

## Latency vs Accuracy

```python
conductor.set_latency_vs_accuracy(0.0)  # pure low-latency
conductor.set_latency_vs_accuracy(1.0)  # pure high-accuracy
```

## Hardware Classes

```python
from grok420.config import HardwareClass

conductor.set_hardware_class(HardwareClass.GPU)    # GPU-priority tasks
conductor.set_hardware_class(HardwareClass.TPU)    # TPU tasks
conductor.set_hardware_class(HardwareClass.QUANTUM) # Quantum units
```

## Dynamic Resource Adjustment

```python
# Scale up at peak load
conductor.set_max_bots(5000)
conductor.set_inference_power(0.9)

# Scale back during quiet periods
conductor.set_max_bots(100)
conductor.set_inference_power(0.5)
```
