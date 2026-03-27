# API Reference

## NayDoev1Conductor

### `async start() -> None`
Start the conductor and background health monitor.

### `async stop() -> None`
Gracefully stop all services.

### `async register_bot(hardware_class) -> (bot_id, token)`
Register a new bot. Returns (bot_id, auth_token) for handshake confirmation.

### `async confirm_handshake(bot_id, token) -> bool`
Validate bot handshake token.

### `async dispatch(coro_factory, hardware_class=None) -> Any`
Execute a coroutine via the resource allocator.

### `set_inference_power(power: float)`
Adjust inference power 0.0–1.0.

### `set_latency_vs_accuracy(ratio: float)`
0.0 = pure latency, 1.0 = pure accuracy.

---

## Grok420Engine

### `async run_parallel(tasks) -> list`
Execute tasks concurrently. Failures captured as exceptions.

### `async run_serial(tasks, initial_input=None) -> Any`
Causal pipeline: each task receives previous output.

### `async make_decision(payload, mode, priority) -> DecisionResult`
Route a decision through the multiplexed decision engine.

---

## CHAiMERAChain

### `add_layer(fn) -> CHAiMERAChain`
Add an AI layer (fluent API).

### `async run(data) -> ChainResult`
Execute the chain.

### `set_speed_mode(mode: SpeedMode)`
Switch speed mode at runtime.

### `set_chain_mode(mode: ChainMode)`
Switch chain mode at runtime.

---

## TwinBrain

### `async evaluate(data) -> ConsensusResult`
Run both brains and return consensus result.

### `set_consensus_threshold(threshold: float)`
Adjust consensus threshold 0.5–1.0.

---

## BlockchainMemory

### `async store(key, value) -> dict`
Persist key/value and return block metadata.

### `async retrieve(key) -> Any`
Retrieve most recent value for key.

### `async verify_all_chains() -> dict[str, bool]`
Verify integrity of all chains.

### `async recover_shard(shard_id) -> bool`
Rebuild failed shard from replicas.

---

## ModelManager

### `async download(model_id, revision=None) -> ModelRecord`
Download from Hugging Face Hub.

### `async load(model_id) -> Any`
Activate model for inference.

### `async unload(model_id) -> None`
Release model from memory.

### `async delete(model_id) -> bool`
Remove from memory, disk, and database.

### `async fine_tune(model_id, dataset, epochs) -> dict`
Run fine-tuning pass.

---

## BotArmy

### `async dispatch(coro_factory) -> Any`
Assign task to least-loaded healthy bot.

### `async dispatch_all(coro_factories) -> list`
Distribute tasks across all bots concurrently.

### `async scale_to(n) -> None`
Scale army to exactly n bots.

---

## Encryptor

### `encrypt(plaintext: bytes) -> bytes`
AES-256-GCM encrypt.

### `decrypt(data: bytes) -> bytes`
AES-256-GCM decrypt.

### `encrypt_b64(plaintext: bytes) -> str`
Encrypt and base64-encode.

### `decrypt_b64(data: str) -> bytes`
Decode and decrypt.

---

## AuditTrail

### `record(component, event, details=None) -> AuditEntry`
Append an immutable audit entry.

### `query(component=None, event=None, since=None) -> list`
Filter entries.

### `verify_integrity() -> (valid, invalid)`
Hash-verify all entries.

---

## MonitoringDashboard

### `async raise_alert(component, message, severity) -> Alert`
Raise an alert and trigger automated resolution.

### `async resolve_alert(alert_id) -> bool`
Mark alert as resolved.

### `register_resolver(component, fn)`
Register async resolution pipeline.

### `record_metric(name, value)`
Store a metric value.

### `get_summary() -> dict`
Return alert and metric summary.
