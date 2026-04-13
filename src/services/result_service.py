from __future__ import annotations

from collections import Counter, deque
from typing import Any


class ResultService:
    def __init__(self, history_size: int = 5, min_repetitions: int = 2) -> None:
        self.history = deque(maxlen=history_size)
        self.min_repetitions = min_repetitions
        self.latest_result: dict[str, Any] | None = None

    def update(self, cleaned_text: str, confidence: float) -> dict[str, Any]:
        if cleaned_text:
            self.history.append((cleaned_text, confidence))

        counter = Counter(text for text, _ in self.history if text)
        best_value = ""
        occurrences = 0
        best_confidence = 0.0

        if counter:
            best_value, occurrences = counter.most_common(1)[0]
            best_confidence = max(conf for text, conf in self.history if text == best_value)

        stable = {
            "value": best_value,
            "confidence": best_confidence,
            "occurrences": occurrences,
            "accepted": bool(best_value and occurrences >= self.min_repetitions),
        }
        self.latest_result = stable
        return stable
