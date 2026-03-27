"""Audit Trail — immutable, append-only log of all AI decisions and state changes."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """A single immutable audit record."""

    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)
    component: str = ""
    event: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    integrity_hash: str = ""

    def __post_init__(self) -> None:
        if not self.integrity_hash:
            self.integrity_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        import hashlib
        raw = json.dumps(
            {
                "entry_id": self.entry_id,
                "timestamp": self.timestamp,
                "component": self.component,
                "event": self.event,
                "details": self.details,
            },
            sort_keys=True,
            default=str,
        ).encode()
        return hashlib.sha256(raw).hexdigest()

    def verify(self) -> bool:
        return self.integrity_hash == self._compute_hash()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditTrail:
    """Append-only audit trail backed by a JSONL file.

    Every entry is hash-verified to detect tampering.  Entries are
    flushed to disk after each write to ensure durability.
    """

    def __init__(
        self,
        path: str = "/tmp/grok420_audit.jsonl",
        max_entries: int = 100_000,
    ) -> None:
        self._path = Path(path)
        self._max_entries = max_entries
        self._entries: list[AuditEntry] = []
        self._load()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(
        self,
        component: str,
        event: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            component=component,
            event=event,
            details=details or {},
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        self._append_to_file(entry)
        logger.debug("Audit[%s/%s]: %s", component, event, entry.entry_id)
        return entry

    # ------------------------------------------------------------------
    # Read & verify
    # ------------------------------------------------------------------

    def get_all(self) -> list[AuditEntry]:
        return list(self._entries)

    def query(
        self,
        component: str | None = None,
        event: str | None = None,
        since: float | None = None,
    ) -> list[AuditEntry]:
        result = self._entries
        if component:
            result = [e for e in result if e.component == component]
        if event:
            result = [e for e in result if e.event == event]
        if since is not None:
            result = [e for e in result if e.timestamp >= since]
        return result

    def verify_integrity(self) -> tuple[int, int]:
        """Returns (valid_count, invalid_count)."""
        valid = sum(1 for e in self._entries if e.verify())
        invalid = len(self._entries) - valid
        if invalid:
            logger.error("Audit integrity: %d invalid entries detected", invalid)
        return valid, invalid

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            for line in self._path.read_text().splitlines():
                if line.strip():
                    d = json.loads(line)
                    self._entries.append(AuditEntry(**d))
            logger.debug("Loaded %d audit entries", len(self._entries))
        except Exception as exc:
            logger.warning("Failed to load audit trail: %s", exc)

    def _append_to_file(self, entry: AuditEntry) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a") as f:
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")
        except Exception as exc:
            logger.error("Failed to append audit entry: %s", exc)
