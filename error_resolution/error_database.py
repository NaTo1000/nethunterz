"""SQLite-based error log database for NethunterZ."""

import sqlite3
import logging
import json
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).parent / "errors.db"


@dataclass
class ErrorRecord:
    id: Optional[int]
    timestamp: float
    source: int
    source_name: str
    error_code: int
    message: str
    resolved: bool = False
    resolution: Optional[str] = None
    device_id: str = "esp32"


SOURCE_NAMES = {0: "WiFi", 1: "BLE", 2: "IoT", 3: "OTA", 4: "Power", 5: "User"}


class ErrorDatabase:
    """Manages persistent error logs in SQLite."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._initialize()

    def _initialize(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("Error database initialised: %s", self.db_path)

    def _create_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   REAL    NOT NULL,
                source      INTEGER NOT NULL,
                source_name TEXT    NOT NULL,
                error_code  INTEGER NOT NULL,
                message     TEXT    NOT NULL,
                resolved    INTEGER DEFAULT 0,
                resolution  TEXT,
                device_id   TEXT    DEFAULT 'esp32',
                created_at  REAL    DEFAULT (strftime('%s', 'now'))
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_errors_resolved ON errors(resolved)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_errors_source ON errors(source)
        """)
        self._conn.commit()

    def insert_error(self, source: int, error_code: int,
                     message: str, device_id: str = "esp32",
                     timestamp: Optional[float] = None) -> int:
        cursor = self._conn.execute("""
            INSERT INTO errors (timestamp, source, source_name, error_code, message, device_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp or time.time(), source,
              SOURCE_NAMES.get(source, "Unknown"),
              error_code, message, device_id))
        self._conn.commit()
        return cursor.lastrowid

    def get_unresolved(self) -> List[ErrorRecord]:
        rows = self._conn.execute("""
            SELECT * FROM errors WHERE resolved = 0 ORDER BY timestamp DESC
        """).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_all(self, limit: int = 1000) -> List[ErrorRecord]:
        rows = self._conn.execute("""
            SELECT * FROM errors ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [self._row_to_record(r) for r in rows]

    def mark_resolved(self, error_id: int, resolution: str) -> None:
        self._conn.execute("""
            UPDATE errors SET resolved = 1, resolution = ? WHERE id = ?
        """, (resolution, error_id))
        self._conn.commit()

    def get_statistics(self) -> Dict[str, Any]:
        total    = self._conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
        resolved = self._conn.execute("SELECT COUNT(*) FROM errors WHERE resolved=1").fetchone()[0]
        by_src   = self._conn.execute("""
            SELECT source_name, COUNT(*) as cnt FROM errors GROUP BY source_name
        """).fetchall()
        return {
            "total": total,
            "resolved": resolved,
            "unresolved": total - resolved,
            "resolution_rate": resolved / max(total, 1),
            "by_source": {row["source_name"]: row["cnt"] for row in by_src},
        }

    def _row_to_record(self, row: sqlite3.Row) -> ErrorRecord:
        return ErrorRecord(
            id=row["id"],
            timestamp=row["timestamp"],
            source=row["source"],
            source_name=row["source_name"],
            error_code=row["error_code"],
            message=row["message"],
            resolved=bool(row["resolved"]),
            resolution=row["resolution"],
            device_id=row["device_id"],
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
