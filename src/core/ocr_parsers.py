from __future__ import annotations

from typing import Any, Callable


def parse_paddle_predict_output(
    result: Any,
    *,
    log_to_dict_error: Callable[[], None],
) -> tuple[list[str], list[float]]:
    texts: list[str] = []
    scores: list[float] = []

    if isinstance(result, list):
        for item in result:
            payload = item
            if hasattr(item, "res"):
                payload = getattr(item, "res")
            if hasattr(item, "to_dict"):
                try:
                    payload = item.to_dict()
                except (AttributeError, TypeError, ValueError, RuntimeError):
                    log_to_dict_error()
            if isinstance(item, dict):
                payload = item
            if isinstance(payload, dict) and "res" in payload and isinstance(payload["res"], dict):
                payload = payload["res"]
            if isinstance(payload, dict):
                rec_texts = payload.get("rec_texts") or []
                rec_scores = payload.get("rec_scores") or []
                if not rec_texts and payload.get("rec_text"):
                    rec_texts = [payload["rec_text"]]
                if not rec_scores and payload.get("rec_score") is not None:
                    rec_scores = [payload["rec_score"]]
                texts.extend([str(value) for value in rec_texts if value])
                scores.extend([float(value) for value in rec_scores])
    return texts, scores


def parse_paddle_legacy_output(result: Any) -> tuple[list[str], list[float]]:
    texts: list[str] = []
    scores: list[float] = []

    if isinstance(result, list):
        for group in result:
            if not group:
                continue
            for item in group:
                if len(item) < 2:
                    continue
                text, score = item[1]
                texts.append(str(text))
                scores.append(float(score))
    return texts, scores


def parse_easyocr_output(result: Any) -> tuple[list[str], list[float]]:
    texts = [str(item[1]) for item in result if len(item) >= 3]
    scores = [float(item[2]) for item in result if len(item) >= 3]
    return texts, scores
