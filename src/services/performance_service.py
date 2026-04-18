from __future__ import annotations

import json
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PerformanceService:
    def __init__(
        self,
        log_path: Path,
        min_interval_seconds: float = 1.0,
        max_recent_entries: int = 5000,
    ) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.fallback_log_path = self.log_path.with_name(f"{self.log_path.stem}.fallback{self.log_path.suffix}")
        self._lock = threading.Lock()
        self.last_error: str | None = None
        self.min_interval_seconds = max(float(min_interval_seconds), 0.0)
        self._last_append_monotonic = 0.0
        self._recent_counter = 0
        self._recent_entries: deque[dict[str, Any]] = deque(maxlen=max(int(max_recent_entries), 1))

    def append(self, snapshot: dict[str, Any], force: bool = False) -> bool:
        payload = dict(snapshot)
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        serialized = json.dumps(payload, ensure_ascii=True)
        now = time.perf_counter()
        with self._lock:
            if not force and self.min_interval_seconds > 0:
                elapsed = now - self._last_append_monotonic
                if elapsed < self.min_interval_seconds:
                    return False

            if self._append_to(self.log_path, serialized):
                self._last_append_monotonic = now
                self._append_recent(payload=payload, log_source=self.log_path.name)
                self.last_error = None
                return True

            if self._append_to(self.fallback_log_path, serialized):
                self._last_append_monotonic = now
                self._append_recent(payload=payload, log_source=self.fallback_log_path.name)
                self.last_error = f"primary_log_unavailable:{self.log_path}"
                return True

            self.last_error = f"performance_logging_unavailable:{self.log_path}"
            return False

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

    def summarize(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        rows = [row for row in entries if isinstance(row, dict)]
        if not rows:
            return {
                "sample_count": 0,
                "from_timestamp": None,
                "to_timestamp": None,
                "avg_running_cameras": 0.0,
                "avg_input_fps_by_role": {},
                "avg_processed_fps_by_role": {},
                "avg_pipeline_ms_by_stream": {},
            }

        timestamps = [str(row.get("timestamp", "")).strip() for row in rows if str(row.get("timestamp", "")).strip()]
        sample_count = len(rows)
        avg_running_cameras = round(
            sum(self._as_float(row.get("running_camera_count")) for row in rows) / sample_count,
            3,
        )

        input_fps_totals: defaultdict[str, float] = defaultdict(float)
        input_fps_counts: defaultdict[str, int] = defaultdict(int)
        processed_fps_totals: defaultdict[str, float] = defaultdict(float)
        processed_fps_counts: defaultdict[str, int] = defaultdict(int)
        pipeline_ms_totals: defaultdict[str, float] = defaultdict(float)
        pipeline_ms_counts: defaultdict[str, int] = defaultdict(int)

        for row in rows:
            camera_fps = row.get("camera_fps")
            if isinstance(camera_fps, dict):
                for role, metrics in camera_fps.items():
                    if not isinstance(metrics, dict):
                        continue
                    role_key = str(role)

                    if "input_fps" in metrics:
                        input_fps_totals[role_key] += self._as_float(metrics.get("input_fps"))
                        input_fps_counts[role_key] += 1
                    if "processed_fps" in metrics:
                        processed_fps_totals[role_key] += self._as_float(metrics.get("processed_fps"))
                        processed_fps_counts[role_key] += 1

            latest_timings = row.get("latest_timings_ms")
            if isinstance(latest_timings, dict):
                for stream_key, timing_row in latest_timings.items():
                    if not isinstance(timing_row, dict):
                        continue
                    if "pipeline" not in timing_row:
                        continue
                    pipeline_ms_totals[str(stream_key)] += self._as_float(timing_row.get("pipeline"))
                    pipeline_ms_counts[str(stream_key)] += 1

        return {
            "sample_count": sample_count,
            "from_timestamp": min(timestamps) if timestamps else None,
            "to_timestamp": max(timestamps) if timestamps else None,
            "avg_running_cameras": avg_running_cameras,
            "avg_input_fps_by_role": self._averages(input_fps_totals, input_fps_counts),
            "avg_processed_fps_by_role": self._averages(processed_fps_totals, processed_fps_counts),
            "avg_pipeline_ms_by_stream": self._averages(pipeline_ms_totals, pipeline_ms_counts),
        }

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

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _averages(
        totals: dict[str, float],
        counts: dict[str, int],
    ) -> dict[str, float]:
        averages: dict[str, float] = {}
        for key, total in totals.items():
            count = counts.get(key, 0)
            if count <= 0:
                continue
            averages[key] = round(total / count, 3)
        return averages
