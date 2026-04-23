from __future__ import annotations

import sqlite3
from typing import Any

from src.storage.connection import SQLiteConnectionManager


class BaseRepository:
    def __init__(self, connection_manager: SQLiteConnectionManager) -> None:
        self.connection_manager = connection_manager

    @staticmethod
    def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def merge_note(existing: str | None, extra: str) -> str:
        current = str(existing or "").strip()
        addition = str(extra or "").strip()
        if not addition:
            return current
        if not current:
            return addition
        if addition in current:
            return current
        return f"{current} | {addition}"
