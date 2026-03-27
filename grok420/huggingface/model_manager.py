"""Model Manager — download, load, fine-tune, and delete HuggingFace models.

This module abstracts the Hugging Face Hub API so models can be managed
via the orchestration engine without tight coupling to transformers/hub.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from grok420.config import HuggingFaceConfig
from grok420.huggingface.database import ModelDatabase, ModelRecord

logger = logging.getLogger(__name__)

# Stub for transformers pipeline — imported lazily so tests don't require GPU
_TRANSFORMERS_AVAILABLE = False
try:
    import transformers  # type: ignore  # noqa: F401
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass


class ModelManager:
    """Manages the full lifecycle of Hugging Face models.

    Provides
    --------
    * ``download``  — pull a model from the Hub into local cache.
    * ``load``      — activate a cached model for inference.
    * ``unload``    — release a model from memory.
    * ``delete``    — remove a model from cache and database.
    * ``fine_tune`` — run a lightweight fine-tuning pass (stub/extensible).
    """

    def __init__(self, config: HuggingFaceConfig | None = None) -> None:
        self._config = config or HuggingFaceConfig()
        self._db = ModelDatabase(self._config.db_path)
        self._cache_dir = Path(self._config.cache_dir)
        self._active_models: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    async def download(
        self,
        model_id: str,
        revision: str | None = None,
    ) -> ModelRecord:
        """Download *model_id* from the Hub to the local cache directory."""
        rev = revision or self._config.default_revision
        async with self._lock:
            existing = self._db.get(model_id)
            if existing:
                logger.info("Model %s already in cache (revision=%s)", model_id, rev)
                return existing

        model_dir = self._cache_dir / self._safe_name(model_id) / rev
        size_bytes = 0

        if _TRANSFORMERS_AVAILABLE:
            size_bytes = await asyncio.get_event_loop().run_in_executor(
                None, self._hub_download, model_id, rev, str(model_dir)
            )
        else:
            # Stub: create placeholder directory for testing without Hub access
            model_dir.mkdir(parents=True, exist_ok=True)
            stub_file = model_dir / "config.json"
            stub_file.write_text(
                f'{{"model_id": "{model_id}", "revision": "{rev}", "stub": true}}'
            )
            size_bytes = stub_file.stat().st_size
            logger.warning(
                "transformers not installed — created stub for %s", model_id
            )

        record = ModelRecord(
            model_id=model_id,
            revision=rev,
            size_bytes=size_bytes,
        )
        async with self._lock:
            self._db.upsert(record)
        logger.info("Downloaded model %s@%s (%d bytes)", model_id, rev, size_bytes)
        return record

    @staticmethod
    def _hub_download(model_id: str, revision: str, cache_dir: str) -> int:
        """Synchronous Hub download — runs in executor."""
        from huggingface_hub import snapshot_download  # type: ignore
        path = snapshot_download(
            repo_id=model_id,
            revision=revision,
            cache_dir=cache_dir,
        )
        return sum(
            f.stat().st_size
            for f in Path(path).rglob("*")
            if f.is_file()
        )

    # ------------------------------------------------------------------
    # Load / Unload
    # ------------------------------------------------------------------

    async def load(self, model_id: str) -> Any:
        """Activate a downloaded model for inference.

        Returns the pipeline object or a stub dict in test environments.
        """
        async with self._lock:
            if model_id in self._active_models:
                logger.debug("Model %s already loaded", model_id)
                return self._active_models[model_id]

            record = self._db.get(model_id)
            if record is None:
                raise ValueError(f"Model {model_id!r} not in cache; call download() first")

        if _TRANSFORMERS_AVAILABLE:
            pipeline = await asyncio.get_event_loop().run_in_executor(
                None,
                self._load_pipeline,
                model_id,
                record.revision,
            )
        else:
            pipeline = {"stub": True, "model_id": model_id}

        async with self._lock:
            self._active_models[model_id] = pipeline
            self._db.set_active(model_id, True)
            self._db.mark_used(model_id)

        logger.info("Loaded model %s", model_id)
        return pipeline

    def _load_pipeline(self, model_id: str, revision: str) -> Any:
        import transformers  # type: ignore
        cache_dir = str(self._cache_dir / self._safe_name(model_id) / revision)
        return transformers.pipeline("text-generation", model=cache_dir)

    async def unload(self, model_id: str) -> None:
        async with self._lock:
            self._active_models.pop(model_id, None)
            self._db.set_active(model_id, False)
        logger.info("Unloaded model %s", model_id)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, model_id: str) -> bool:
        """Remove model from memory, disk cache, and database."""
        await self.unload(model_id)
        record = self._db.get(model_id)
        if record:
            model_dir = self._cache_dir / self._safe_name(model_id)
            if model_dir.exists():
                shutil.rmtree(model_dir, ignore_errors=True)
            self._db.delete(model_id)
            logger.info("Deleted model %s", model_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Fine-tuning (extensible stub)
    # ------------------------------------------------------------------

    async def fine_tune(
        self,
        model_id: str,
        dataset: list[dict[str, Any]],
        epochs: int = 1,
    ) -> dict[str, Any]:
        """Lightweight fine-tuning stub.

        In production, replace the body of this method with your actual
        training loop.  Metrics are persisted to the model database.
        """
        record = self._db.get(model_id)
        if record is None:
            raise ValueError(f"Model {model_id!r} not found; download first")

        metrics: dict[str, Any] = {
            "epochs": epochs,
            "samples": len(dataset),
            "status": "stub_completed",
        }
        self._db.record_performance(model_id, metrics)
        logger.info("Fine-tune stub completed for %s (epochs=%d)", model_id, epochs)
        return metrics

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_models(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._db.list_all()]

    @property
    def active_models(self) -> list[str]:
        return list(self._active_models.keys())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_name(model_id: str) -> str:
        """Convert model_id to a filesystem-safe directory name."""
        return model_id.replace("/", "__")
