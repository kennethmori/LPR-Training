from __future__ import annotations

from fastapi import APIRouter
from fastapi.templating import Jinja2Templates

from src.api.camera_routes import register_camera_routes
from src.api.dashboard_routes import register_dashboard_routes
from src.api.dashboard_support import DashboardPayloadCache
from src.api.moderation_routes import register_moderation_routes
from src.api.pages_routes import register_page_routes
from src.api.performance_routes import register_performance_routes
from src.api.predict_routes import register_predict_routes
from src.api.session_routes import register_session_routes
from src.api.settings_routes import register_settings_routes
from src.api.vehicle_routes import register_vehicle_routes
from src.core.detector import PlateDetector


def create_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()
    dashboard_cache = DashboardPayloadCache()

    register_page_routes(router, templates=templates, dashboard_cache=dashboard_cache)
    register_settings_routes(router, detector_factory_provider=lambda: PlateDetector)
    register_predict_routes(router)
    register_camera_routes(router)
    register_dashboard_routes(router, dashboard_cache=dashboard_cache)
    register_vehicle_routes(router)
    register_session_routes(router)
    register_performance_routes(router)
    register_moderation_routes(router)

    return router
