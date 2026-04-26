from __future__ import annotations

import threading
from collections import Counter, deque
from typing import Any


class ResultService:
    def __init__(self, history_size: int = 5, min_repetitions: int = 2) -> None:
        self.history_size = history_size
        self.histories: dict[str, deque[tuple[str, float]]] = {}
        self.min_repetitions = min_repetitions
        self.latest_results_by_key: dict[str, dict[str, Any]] = {}
        self.latest_result: dict[str, Any] | None = None
        self._lock = threading.RLock()

    def _get_history(self, stream_key: str) -> deque[tuple[str, float]]:
        if stream_key not in self.histories:
            self.histories[stream_key] = deque(maxlen=self.history_size)
        return self.histories[stream_key]

    def update(self, cleaned_text: str, confidence: float, stream_key: str = "default") -> dict[str, Any]:
        with self._lock:
            history = self._get_history(stream_key)
            if cleaned_text:
                history.append((cleaned_text, confidence))

            counter = Counter(text for text, _ in history if text)
            best_value = ""
            occurrences = 0
            best_confidence = 0.0

            if counter:
                best_value, occurrences = counter.most_common(1)[0]
                best_confidence = max(conf for text, conf in history if text == best_value)

            stable = {
                "value": best_value,
                "confidence": best_confidence,
                "occurrences": occurrences,
                "accepted": bool(best_value and occurrences >= self.min_repetitions),
            }
            self.latest_results_by_key[stream_key] = stable
            self.latest_result = stable
            return dict(stable)

    def latest_for(self, stream_key: str = "default") -> dict[str, Any] | None:
        with self._lock:
            stable = self.latest_results_by_key.get(stream_key)
            return dict(stable) if stable is not None else None

    def clear(self, stream_key: str) -> None:
        with self._lock:
            removed = self.latest_results_by_key.pop(stream_key, None)
            self.histories.pop(stream_key, None)
            if removed is not None and self.latest_result == removed:
                remaining_results = list(self.latest_results_by_key.values())
                self.latest_result = dict(remaining_results[-1]) if remaining_results else None
