from __future__ import annotations

import time
from typing import Any

from fastapi import Request

from src.api.dashboard_status import (
    camera_start_message,
    get_camera_or_404,
    latest_for_role,
    latest_payload_or_idle,
    latest_results_payload,
    status_payload,
)
from src.api.performance_payloads import record_performance_snapshot

_latest_results_payload = latest_results_payload


class DashboardPayloadCache:
    def __init__(self) -> None:
        self._payload: dict[str, Any] | None = None
        self._updated_at = 0.0

    def get(self, request: Request, *, force_refresh: bool = False) -> dict[str, Any]:
        dashboard_settings = dict(request.app.state.settings.get("dashboard_stream", {}))
        configured_cache_ttl = dashboard_settings.get("cache_ttl_seconds", 0.5)
        cache_ttl_seconds = max(
            float(configured_cache_ttl if configured_cache_ttl is not None else 0.5),
            0.0,
        )
        now = time.perf_counter()
        if (
            not force_refresh
            and self._payload is not None
            and (now - self._updated_at) <= cache_ttl_seconds
        ):
            return dict(self._payload)

        payload = build_dashboard_payload(request, dashboard_settings=dashboard_settings)
        record_performance_snapshot(
            request,
            source="dashboard_stream",
            status_row=payload["status"],
            active_sessions=len(payload["active"]),
            recent_events=len(payload["events"]),
            unmatched_exits=len(payload["unmatched"]),
        )
        self._payload = payload
        self._updated_at = now
        return payload


def build_dashboard_payload(request: Request, *, dashboard_settings: dict[str, Any]) -> dict[str, Any]:
    session_service = request.app.state.session_service
    logging_service = request.app.state.logging_service
    active_limit = max(int(dashboard_settings.get("active_limit", 30) or 30), 1)
    event_limit = max(int(dashboard_settings.get("event_limit", 50) or 50), 1)
    log_limit = max(int(dashboard_settings.get("log_limit", 80) or 80), 1)
    history_limit = max(int(dashboard_settings.get("history_limit", 30) or 30), 1)
    unmatched_limit = max(int(dashboard_settings.get("unmatched_limit", 30) or 30), 1)

    return {
        "status": status_payload(request),
        "active": session_service.get_active_sessions(limit=active_limit),
        "events": session_service.get_recent_events(
            limit=event_limit,
            include_unmatched=False,
            include_logged_only=False,
            include_ignored=False,
        ),
        "logs": logging_service.read_recent(limit=log_limit),
        "history": session_service.get_session_history(limit=history_limit),
        "unmatched": session_service.get_unmatched_exit_events(limit=unmatched_limit),
        "latest_results": latest_results_payload(request),
    }
