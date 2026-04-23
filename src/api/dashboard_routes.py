from __future__ import annotations

from fastapi import APIRouter, Request

from src.api.dashboard_support import DashboardPayloadCache, record_performance_snapshot, status_payload
from src.api.schemas import AppStatusPayload


def register_dashboard_routes(
    router: APIRouter,
    *,
    dashboard_cache: DashboardPayloadCache,
) -> None:
    @router.get("/status", response_model=AppStatusPayload)
    def status(request: Request):
        status_row = status_payload(request)
        record_performance_snapshot(request, source="status_endpoint", status_row=status_row)
        return status_row

    @router.get("/dashboard/snapshot")
    def dashboard_snapshot(request: Request):
        return dashboard_cache.get(request, force_refresh=True)
