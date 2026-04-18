from __future__ import annotations

import json
import threading
from collections import deque
from pathlib import Path
from typing import Any


class LoggingService:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.fallback_log_path = self.log_path.with_name(f"{self.log_path.stem}.fallback{self.log_path.suffix}")
        self._lock = threading.Lock()
        self.last_error: str | None = None
        self._recent_entries: deque[dict[str, Any]] = deque(maxlen=1000)
        self._recent_counter = 0

    def append(self, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=True)
        with self._lock:
            if self._append_to(self.log_path, serialized):
                self._append_recent(payload=payload, log_source=self.log_path.name)
                self.last_error = None
                return

            # Logging should never take down inference. If the primary file is locked
            # or otherwise unavailable, fall back to a sidecar file and keep serving.
            if self._append_to(self.fallback_log_path, serialized):
                self._append_recent(payload=payload, log_source=self.fallback_log_path.name)
                self.last_error = f"primary_log_unavailable:{self.log_path}"
                return

            self.last_error = f"logging_unavailable:{self.log_path}"

    def read_recent(self, limit: int = 250) -> list[dict[str, Any]]:
        max_entries = max(int(limit), 1)
        entries: list[dict[str, Any]] = []

        with self._lock:
            if self._recent_entries:
                recent = list(self._recent_entries)[-max_entries:]
                return list(reversed(recent))

            for path in self._candidate_paths():
                for line_number, serialized in self._tail_lines(path, max_entries):
                    try:
                        payload = json.loads(serialized)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue

                    entry = dict(payload)
                    entry["log_id"] = f"{path.name}:{line_number}"
                    entry["log_source"] = path.name
                    entries.append(entry)

        entries.sort(
            key=lambda item: (str(item.get("timestamp", "")), str(item.get("log_id", ""))),
            reverse=True,
        )
        return entries[:max_entries]

    def _append_recent(self, payload: dict[str, Any], log_source: str) -> None:
        self._recent_counter += 1
        entry = dict(payload)
        entry["log_id"] = f"{log_source}:mem:{self._recent_counter}"
        entry["log_source"] = log_source
        self._recent_entries.append(entry)

    def _append_to(self, path: Path, serialized: str) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(serialized + "\n")
            return True
        except OSError:
            return False

    def _candidate_paths(self) -> list[Path]:
        candidates = [self.log_path]
        if self.fallback_log_path.exists():
            candidates.append(self.fallback_log_path)
        return candidates

    @staticmethod
    def _tail_lines(path: Path, limit: int) -> list[tuple[int, str]]:
        if not path.exists():
            return []

        tail: deque[tuple[int, str]] = deque(maxlen=max(int(limit), 1))
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    serialized = line.strip()
                    if serialized:
                        tail.append((line_number, serialized))
        except OSError:
            return []

        return list(tail)
