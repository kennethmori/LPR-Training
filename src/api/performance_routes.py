from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.api.schemas import PerformanceSnapshotPayload, PerformanceSummaryPayload


def register_performance_routes(router: APIRouter) -> None:
    @router.get("/performance/recent", response_model=list[PerformanceSnapshotPayload])
    def performance_recent(request: Request, limit: int = Query(default=120, ge=1, le=1000)):
        return request.app.state.performance_service.read_recent(limit=limit)

    @router.get("/performance/summary", response_model=PerformanceSummaryPayload)
    def performance_summary(request: Request, limit: int = Query(default=240, ge=1, le=5000)):
        entries = request.app.state.performance_service.read_recent(limit=limit)
        return request.app.state.performance_service.summarize(entries)
