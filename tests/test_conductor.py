"""Tests for ConductorX orchestrator and transformer bots."""

from __future__ import annotations

import pytest

from jessica.conductor.conductorx import ConductorX, OrchestratorTask, TaskPriority, TaskState
from jessica.conductor.transformers import BotConfig, BotRole, TransformerBot, TransformerBotPool


class TestConductorX:
    @pytest.fixture
    def conductor(self) -> ConductorX:
        return ConductorX({
            "cluster": {"replicas": 1},
            "scheduling": {"strategy": "adaptive", "max_workers": 10},
            "orchestrators": {"min_replicas": 1, "max_replicas": 5, "autoscale": {"target": 5}},
        })

    @pytest.mark.asyncio
    async def test_start_stop(self, conductor: ConductorX) -> None:
        await conductor.start()
        await conductor.stop()

    @pytest.mark.asyncio
    async def test_submit_task(self, conductor: ConductorX) -> None:
        await conductor.start()
        task = OrchestratorTask(name="nmap_scan", payload={"target": "10.0.0.1"})
        task_id = await conductor.submit_task(task)
        assert task_id == task.id
        assert conductor.queue_depth == 1
        await conductor.stop()

    @pytest.mark.asyncio
    async def test_get_task(self, conductor: ConductorX) -> None:
        await conductor.start()
        task = OrchestratorTask(name="test")
        await conductor.submit_task(task)
        retrieved = conductor.get_task(task.id)
        assert retrieved is not None
        assert retrieved.name == "test"
        await conductor.stop()

    @pytest.mark.asyncio
    async def test_list_tasks_by_state(self, conductor: ConductorX) -> None:
        await conductor.start()
        t1 = OrchestratorTask(name="t1")
        t2 = OrchestratorTask(name="t2")
        await conductor.submit_task(t1)
        await conductor.submit_task(t2)
        queued = conductor.list_tasks(state=TaskState.QUEUED)
        assert len(queued) == 2
        await conductor.stop()

    def test_register_worker(self, conductor: ConductorX) -> None:
        conductor.register_worker("w1", ["nmap", "nikto"])
        conductor.register_worker("w2")
        assert len(conductor.list_tasks()) == 0  # no tasks yet
        conductor.deregister_worker("w1")

    def test_desired_worker_count(self, conductor: ConductorX) -> None:
        # With empty queue, should return min_replicas
        assert conductor.desired_worker_count() >= 1

    @pytest.mark.asyncio
    async def test_priority_ordering(self, conductor: ConductorX) -> None:
        await conductor.start()
        low = OrchestratorTask(name="low", priority=TaskPriority.LOW)
        critical = OrchestratorTask(name="critical", priority=TaskPriority.CRITICAL)
        await conductor.submit_task(low)
        await conductor.submit_task(critical)
        assert conductor.queue_depth == 2
        await conductor.stop()


class TestTransformerBots:
    @pytest.mark.asyncio
    async def test_classifier_bot_stub(self) -> None:
        config = BotConfig(role=BotRole.CLASSIFIER, model_id="test-model")
        bot = TransformerBot(config, hf_layer=None)
        result = await bot.run({"text": "port 80 is open", "labels": ["recon", "exploit"]})
        assert "classification" in result

    @pytest.mark.asyncio
    async def test_analyser_bot_stub(self) -> None:
        config = BotConfig(role=BotRole.ANALYSER, model_id="test-model")
        bot = TransformerBot(config, hf_layer=None)
        result = await bot.run({"text": "Nmap scan results..."})
        assert "analysis" in result

    @pytest.mark.asyncio
    async def test_planner_bot_stub(self) -> None:
        config = BotConfig(role=BotRole.PLANNER, model_id="test-model")
        bot = TransformerBot(config, hf_layer=None)
        result = await bot.run({"findings": ["open SSH", "weak password"]})
        assert "plan" in result

    @pytest.mark.asyncio
    async def test_scorer_bot_stub(self) -> None:
        config = BotConfig(role=BotRole.SCORER, model_id="test-model")
        bot = TransformerBot(config, hf_layer=None)
        result = await bot.run({"finding": "SQL injection in login form"})
        assert "threat_score" in result

    @pytest.mark.asyncio
    async def test_bot_pool(self) -> None:
        pool = TransformerBotPool()
        pool.add_bot(BotConfig(role=BotRole.CLASSIFIER, model_id="cls"))
        pool.add_bot(BotConfig(role=BotRole.SCORER, model_id="scr"))
        assert len(pool.list_bots()) == 2
        result = await pool.run(BotRole.CLASSIFIER, {"text": "test", "labels": ["a"]})
        assert "classification" in result

    @pytest.mark.asyncio
    async def test_bot_pool_missing_role(self) -> None:
        pool = TransformerBotPool()
        with pytest.raises(KeyError):
            await pool.run(BotRole.PLANNER, {"findings": []})
