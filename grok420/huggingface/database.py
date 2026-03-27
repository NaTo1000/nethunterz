"""Model Database — metadata, performance metrics, and usage tracking."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelRecord:
    """Persistent metadata record for a cached model."""

    model_id: str
    revision: str
    cached_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    size_bytes: int = 0
    tags: list[str] = field(default_factory=list)
    performance: dict[str, Any] = field(default_factory=dict)
    active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ModelRecord":
        return cls(**d)


class ModelDatabase:
    """JSON-backed model metadata store.

    Provides CRUD operations over :class:`ModelRecord` instances,
    persisted to a local JSON file.
    """

    def __init__(self, db_path: str = "/tmp/grok420_models.json") -> None:
        self._path = Path(db_path)
        self._records: dict[str, ModelRecord] = {}
        self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def upsert(self, record: ModelRecord) -> None:
        self._records[record.model_id] = record
        self._save()

    def get(self, model_id: str) -> ModelRecord | None:
        return self._records.get(model_id)

    def delete(self, model_id: str) -> bool:
        if model_id in self._records:
            del self._records[model_id]
            self._save()
            logger.info("Deleted record for model %s", model_id)
            return True
        return False

    def list_all(self) -> list[ModelRecord]:
        return list(self._records.values())

    def mark_used(self, model_id: str) -> None:
        rec = self._records.get(model_id)
        if rec:
            rec.last_used = time.time()
            rec.use_count += 1
            self._save()

    def set_active(self, model_id: str, active: bool) -> None:
        rec = self._records.get(model_id)
        if rec:
            rec.active = active
            self._save()

    def record_performance(self, model_id: str, metrics: dict[str, Any]) -> None:
        rec = self._records.get(model_id)
        if rec:
            rec.performance.update(metrics)
            self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text())
            for model_id, d in raw.items():
                self._records[model_id] = ModelRecord.from_dict(d)
            logger.debug("Loaded %d model records from %s", len(self._records), self._path)
        except Exception as exc:
            logger.warning("Failed to load model DB: %s", exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            raw = {k: v.to_dict() for k, v in self._records.items()}
            self._path.write_text(json.dumps(raw, indent=2))
        except Exception as exc:
            logger.error("Failed to save model DB: %s", exc)
