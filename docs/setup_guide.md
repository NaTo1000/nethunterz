# Setup and Configuration Guide

## Prerequisites

- Python 3.11+
- pip

## Installation

```bash
git clone https://github.com/NaTo1000/nethunterz.git
cd nethunterz
pip install -e ".[dev]"
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GROK420_HANDSHAKE_SECRET` | HMAC secret for bot handshake | `grok420-default-secret-change-me` |
| `GROK420_ENCRYPTION_KEY` | Base64 32-byte AES key | auto-generated |
| `GROK420_MAX_BOTS` | Maximum concurrent bots | `1000` |
| `GROK420_SPEED_MODE` | CHAiMERA speed mode | `balanced` |

## Component Setup

### Minimal Setup (CPU-only)

```python
from grok420.config import Grok420Settings

settings = Grok420Settings()
```

### GPU-Accelerated Setup

```python
from grok420.config import Grok420Settings, ConductorConfig, HardwareClass

settings = Grok420Settings(
    conductor=ConductorConfig(
        hardware_class=HardwareClass.GPU,
        max_bots=2000,
        inference_power=0.95,
    )
)
```

### High-Fidelity Chain Setup

```python
from grok420.config import CHAiMERAConfig, SpeedMode, ChainMode

chaimera_config = CHAiMERAConfig(
    speed_mode=SpeedMode.HIGH_FIDELITY,
    chain_mode=ChainMode.HYBRID,
    layer_count=8,
    superconductor_threads=32,
    adaptive_learning_rate=0.005,
)
```
