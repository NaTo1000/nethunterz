"""
Tests for NayDoeV1 Conductor.
"""
import asyncio
import pytest
from ai_engine.naydoe_v1 import (
    HardwareProfile,
    NayDoeV1Conductor,
    Task,
    TaskPriority,
)


@pytest.fixture
def conductor():
    return NayDoeV1Conductor(
        hardware_profile=HardwareProfile.STANDARD,
        max_concurrent_tasks=4,
    )


def test_conductor_initialization(conductor):
    assert conductor.hardware_profile == HardwareProfile.STANDARD
    assert conductor.max_concurrent_tasks == 4
    assert conductor.conductor_id is not None


def test_for_hardware_factory():
    c = NayDoeV1Conductor.for_hardware(HardwareProfile.MINIMAL)
    assert c.max_concurrent_tasks == 4
    c2 = NayDoeV1Conductor.for_hardware(HardwareProfile.CLUSTER)
    assert c2.max_concurrent_tasks == 256


def test_register_agent(conductor):
    mock_agent = object()
    conductor.register_agent("test_agent", mock_agent)
    metrics = conductor.get_metrics()
    assert "test_agent" in metrics["registered_agents"]


@pytest.mark.asyncio
async def test_conductor_start_stop():
    conductor = NayDoeV1Conductor(max_concurrent_tasks=2)
    await conductor.start()
    assert conductor._running is True
    await conductor.stop()
    assert conductor._running is False


@pytest.mark.asyncio
async def test_submit_and_execute():
    conductor = NayDoeV1Conductor(max_concurrent_tasks=4)
    await conductor.start()

    result_holder = []

    async def sample_task():
        await asyncio.sleep(0.01)
        result_holder.append("done")
        return "success"

    task_id = await conductor.submit("sample", sample_task)
    assert task_id is not None

    # Wait for task to complete
    await asyncio.sleep(0.2)

    metrics = conductor.get_metrics()
    assert metrics["tasks_submitted"] >= 1
    await conductor.stop()


def test_get_metrics(conductor):
    m = conductor.get_metrics()
    assert "tasks_submitted" in m
    assert "tasks_completed" in m
    assert "uptime_seconds" in m
    assert "hardware_profile" in m
    assert m["hardware_profile"] == "standard"


def test_status_report(conductor):
    report = conductor.get_status_report()
    assert "NayDoeV1" in report
    assert "standard" in report


def test_hash_state(conductor):
    h1 = conductor._hash_state()
    assert len(h1) == 64  # SHA-256 hex
    # Hash is a valid hex string
    assert all(c in "0123456789abcdef" for c in h1)


def test_task_creation():
    async def noop():
        pass

    task = Task(
        task_id="test-id",
        name="test_task",
        coro=noop,
        priority=TaskPriority.HIGH,
    )
    assert task.task_id == "test-id"
    assert not task.is_complete
    assert task.elapsed == 0.0
