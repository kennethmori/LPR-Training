from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from src.domain.models import RecognitionEvent
from src.services.session_rules import character_distance, normalized_plate_number, parse_iso_timestamp


def find_recent_ambiguous_session(
    *,
    open_sessions: Iterable[dict[str, Any]],
    event: RecognitionEvent,
    expected_camera_role: str,
    ambiguity_window_seconds: int,
    ambiguity_char_distance: int,
) -> tuple[dict[str, Any] | None, int]:
    plate_number = normalized_plate_number(event.plate_number)
    camera_role = str(event.camera_role or "").strip().lower()
    current_ts = parse_iso_timestamp(event.timestamp)
    if camera_role != expected_camera_role or not plate_number or current_ts is None:
        return None, 0
    if ambiguity_window_seconds <= 0 or ambiguity_char_distance < 1:
        return None, 0

    best_match: dict[str, Any] | None = None
    best_distance = 0
    best_sort_key: tuple[int, float, float] | None = None

    for open_session in open_sessions:
        session_plate = normalized_plate_number(open_session.get("plate_number"))
        if not _candidate_plate_matches(session_plate, plate_number):
            continue

        distance = character_distance(plate_number, session_plate)
        if distance < 1 or distance > ambiguity_char_distance:
            continue

        session_ts = _session_reference_timestamp(open_session)
        if session_ts is None:
            continue

        seconds = abs((current_ts - session_ts).total_seconds())
        if seconds > float(ambiguity_window_seconds):
            continue

        sort_key = _ambiguous_session_sort_key(open_session, session_ts, distance)
        if best_sort_key is None or sort_key < best_sort_key:
            best_match = open_session
            best_distance = distance
            best_sort_key = sort_key

    return best_match, best_distance


def _candidate_plate_matches(session_plate: str, plate_number: str) -> bool:
    if not session_plate or session_plate == plate_number:
        return False
    return len(session_plate) == len(plate_number)


def _session_reference_timestamp(open_session: dict[str, Any]) -> datetime | None:
    return parse_iso_timestamp(open_session.get("entry_time")) or parse_iso_timestamp(
        open_session.get("updated_at")
    )


def _ambiguous_session_sort_key(
    open_session: dict[str, Any],
    session_ts: datetime,
    distance: int,
) -> tuple[int, float, float]:
    return (
        distance,
        -float(open_session.get("entry_confidence", 0.0) or 0.0),
        -session_ts.timestamp(),
    )
