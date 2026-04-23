from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class SQLiteConnectionManager:
    def __init__(
        self,
        db_path: Path,
        *,
        busy_timeout_ms: int = 5000,
        enable_wal: bool = True,
    ) -> None:
        self.db_path = Path(db_path)
        self.busy_timeout_ms = max(int(busy_timeout_ms), 100)
        self.enable_wal = bool(enable_wal)
        self._connections_lock = threading.Lock()
        self._thread_connections: dict[int, sqlite3.Connection] = {}

    def create_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=self.busy_timeout_ms / 1000.0,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        if self.enable_wal:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def get_connection_for_current_thread(self) -> sqlite3.Connection:
        thread_id = threading.get_ident()
        with self._connections_lock:
            connection = self._thread_connections.get(thread_id)
            if connection is None:
                connection = self.create_connection()
                self._thread_connections[thread_id] = connection
            return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self.get_connection_for_current_thread()
        with connection:
            yield connection

    def close(self) -> None:
        with self._connections_lock:
            connections = list(self._thread_connections.values())
            self._thread_connections.clear()
        for connection in connections:
            try:
                connection.close()
            except sqlite3.Error:
                pass
