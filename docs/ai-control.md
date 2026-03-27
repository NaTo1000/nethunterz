# AI Autonomous Control Documentation

## Overview

The AI control system enables autonomous decision-making for Flipper Zero control. It combines rule-based logic with TensorFlow Lite on-device ML inference.

## Architecture

```
AIController
├── DecisionEngine     (rule-based + ML hybrid)
│   ├── rules.json     (loaded rules)
│   └── MLModelManager (TFLite inference)
└── FlipperManager     (action execution)
```

## Components

### AIController

The top-level coordinator. Runs a monitoring loop every 2 seconds in autonomous mode.

```java
AIController ai = new AIController(context, flipperManager);
ai.initialize();
ai.setListener(listener);
ai.startAutonomousMode();   // Begin monitoring
ai.stopAutonomousMode();    // Stop
```

### DecisionEngine

Evaluates rules and ML predictions against the current system context.

**Rule format (rules.json):**
```json
{
  "id": "r001",
  "condition": "flipper_not_connected",
  "action": "CONNECT_FLIPPER",
  "priority": 0.90,
  "enabled": true,
  "params": {}
}
```

**Available conditions:**
- `flipper_not_connected` - Fires when Flipper is not connected
- `flipper_idle` - Fires every 10 decision cycles when connected
- `version_unknown` - Fires when firmware version hasn't been fetched yet
- `periodic_check` - Fires every 30 decision cycles
- `connection_error` - Fires on repeated failures

### MLModelManager

Loads and runs the TFLite model for learned behavior prediction.

**Model:** `assets/models/flipper_control_model.tflite`  
**Input:** 7 float features  
**Output:** 5 class probabilities (action classes)

**Action classes:**
1. `NONE` - Do nothing
2. `CONNECT_FLIPPER` - Initiate connection
3. `SEND_PING` - Test connectivity
4. `GET_VERSION` - Fetch firmware version
5. `CHECK_STORAGE` - Read storage info

## Training the Model

See [train_model.py](../ai/training/train_model.py):

```bash
cd /path/to/nethunterz
pip install tensorflow numpy
python ai/training/train_model.py \
    --output ai/models/output \
    --epochs 30
```

The trained `.tflite` file should be placed in `nethunter-app/assets/models/`.

## Confidence Threshold

Actions are only executed when confidence ≥ **0.75** (75%). Lower-confidence decisions are logged but not executed.

## Adding Custom Rules

Edit `ai/decision_engine/rules.json` to add new rules:

```json
{
  "id": "r100",
  "condition": "my_custom_condition",
  "action": "SEND_PING",
  "priority": 0.65,
  "enabled": true
}
```

Then implement the condition handler in `DecisionEngine.java`:

```java
case "my_custom_condition":
    return myCustomEvaluation(ctx);
```
