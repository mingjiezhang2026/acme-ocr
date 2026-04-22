from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_hash TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS job_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  page_no INTEGER NOT NULL,
  result_json TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS exports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  format TEXT NOT NULL,
  target_path TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row

    def initialize(self) -> None:
        self._connection.executescript(SCHEMA)
        self._connection.commit()

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cursor = self._connection.execute(query, params)
        self._connection.commit()
        return cursor

    def fetchone(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        cursor = self._connection.execute(query, params)
        return cursor.fetchone()

    def fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        cursor = self._connection.execute(query, params)
        return cursor.fetchall()

    def close(self) -> None:
        self._connection.close()

