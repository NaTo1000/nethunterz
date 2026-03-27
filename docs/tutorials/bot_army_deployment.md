# Tutorial: Bot Army Deployment & Scaling

## Initial Deployment

```python
from grok420.bot_army import BotArmy
from grok420.config import ConductorConfig

config = ConductorConfig(max_bots=10_000)
async with BotArmy(conductor_config=config, initial_size=64) as army:
    result = await army.dispatch(my_task)
```

## Horizontal Scaling

```python
# Scale up for peak load
await army.scale_to(512)

# Scale back during idle
await army.scale_to(32)
```

## Self-Healing

The army monitors bot health every 5 seconds. Dead bots are automatically
replaced with fresh instances. No manual intervention required.

## Per-Bot Configuration

```python
from grok420.bot_army import Bot, BotConfig

config = BotConfig(
    hardware_class="gpu",
    inference_concurrency=4,  # 4 concurrent tasks per bot
    bandwidth_priority=0.8,   # 0.0=low, 1.0=high
    max_retries=5,
)
bot = Bot(config)
```

## Monitoring Army Health

```python
status = army.get_army_status()
print(f"Total: {army.bot_count}, Healthy: {army.healthy_bot_count}")
for bot in status:
    print(f"  {bot['bot_id']}: {bot['status']} ({bot['tasks_completed']} completed)")
```
