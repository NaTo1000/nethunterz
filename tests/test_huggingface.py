"""Tests for Hugging Face Model Manager and Database."""

import asyncio
import json
import os
import tempfile
import pytest

from grok420.config import HuggingFaceConfig
from grok420.huggingface.database import ModelDatabase, ModelRecord
from grok420.huggingface.model_manager import ModelManager


# ---------------------------------------------------------------------------
# ModelDatabase
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "models.json")


def test_model_database_upsert_get(tmp_db):
    db = ModelDatabase(tmp_db)
    rec = ModelRecord(model_id="org/model", revision="main", size_bytes=1024)
    db.upsert(rec)
    retrieved = db.get("org/model")
    assert retrieved is not None
    assert retrieved.model_id == "org/model"


def test_model_database_delete(tmp_db):
    db = ModelDatabase(tmp_db)
    rec = ModelRecord(model_id="org/model2", revision="main")
    db.upsert(rec)
    assert db.delete("org/model2")
    assert db.get("org/model2") is None
    assert not db.delete("nonexistent")


def test_model_database_list_all(tmp_db):
    db = ModelDatabase(tmp_db)
    for i in range(3):
        db.upsert(ModelRecord(model_id=f"model_{i}", revision="main"))
    assert len(db.list_all()) == 3


def test_model_database_mark_used(tmp_db):
    db = ModelDatabase(tmp_db)
    rec = ModelRecord(model_id="use_model", revision="main")
    db.upsert(rec)
    db.mark_used("use_model")
    assert db.get("use_model").use_count == 1


def test_model_database_set_active(tmp_db):
    db = ModelDatabase(tmp_db)
    db.upsert(ModelRecord(model_id="active_model", revision="main"))
    db.set_active("active_model", True)
    assert db.get("active_model").active


def test_model_database_record_performance(tmp_db):
    db = ModelDatabase(tmp_db)
    db.upsert(ModelRecord(model_id="perf_model", revision="main"))
    db.record_performance("perf_model", {"accuracy": 0.95, "latency_ms": 120})
    assert db.get("perf_model").performance["accuracy"] == 0.95


def test_model_database_persistence(tmp_db):
    db1 = ModelDatabase(tmp_db)
    db1.upsert(ModelRecord(model_id="persistent", revision="v1"))

    db2 = ModelDatabase(tmp_db)
    assert db2.get("persistent") is not None


# ---------------------------------------------------------------------------
# ModelManager
# ---------------------------------------------------------------------------


@pytest.fixture
def model_config(tmp_path):
    return HuggingFaceConfig(
        cache_dir=str(tmp_path / "cache"),
        db_path=str(tmp_path / "models.json"),
    )


@pytest.mark.asyncio
async def test_model_manager_download_stub(model_config):
    mgr = ModelManager(model_config)
    record = await mgr.download("test/model-stub")
    assert record.model_id == "test/model-stub"
    assert record.revision == "main"


@pytest.mark.asyncio
async def test_model_manager_download_idempotent(model_config):
    mgr = ModelManager(model_config)
    r1 = await mgr.download("test/idempotent")
    r2 = await mgr.download("test/idempotent")
    assert r1.model_id == r2.model_id


@pytest.mark.asyncio
async def test_model_manager_load_unload(model_config):
    mgr = ModelManager(model_config)
    await mgr.download("test/load-model")
    pipeline = await mgr.load("test/load-model")
    assert pipeline == {"stub": True, "model_id": "test/load-model"}
    assert "test/load-model" in mgr.active_models
    await mgr.unload("test/load-model")
    assert "test/load-model" not in mgr.active_models


@pytest.mark.asyncio
async def test_model_manager_load_not_downloaded(model_config):
    mgr = ModelManager(model_config)
    with pytest.raises(ValueError, match="not in cache"):
        await mgr.load("nonexistent/model")


@pytest.mark.asyncio
async def test_model_manager_delete(model_config, tmp_path):
    mgr = ModelManager(model_config)
    await mgr.download("test/to-delete")
    assert await mgr.delete("test/to-delete")
    assert not await mgr.delete("test/to-delete")  # second delete returns False


@pytest.mark.asyncio
async def test_model_manager_fine_tune(model_config):
    mgr = ModelManager(model_config)
    await mgr.download("test/ft-model")
    metrics = await mgr.fine_tune(
        "test/ft-model",
        dataset=[{"input": "a", "label": "b"}, {"input": "c", "label": "d"}],
        epochs=2,
    )
    assert metrics["epochs"] == 2
    assert metrics["samples"] == 2
    assert metrics["status"] == "stub_completed"


@pytest.mark.asyncio
async def test_model_manager_list_models(model_config):
    mgr = ModelManager(model_config)
    for i in range(3):
        await mgr.download(f"test/model-{i}")
    models = mgr.list_models()
    assert len(models) == 3
