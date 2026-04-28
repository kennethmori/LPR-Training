from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Form, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from src.api.auth import (
    app_template_context,
    auth_enabled,
    credentials_match,
    is_admin_authenticated,
    login_template_context,
    safe_next_path,
)
from src.api.dashboard_support import DashboardPayloadCache
from src.api.upload_support import resolve_artifact_path


def register_page_routes(
    router: APIRouter,
    *,
    templates: Jinja2Templates,
    dashboard_cache: DashboardPayloadCache,
) -> None:
    @router.get("/login")
    def login_page(request: Request, next: str = Query(default="/")):
        next_path = safe_next_path(next)
        if not auth_enabled(request):
            return RedirectResponse(url=next_path, status_code=303)
        if is_admin_authenticated(request):
            return RedirectResponse(url=next_path, status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=login_template_context(request, next_path=next_path),
        )

    @router.post("/login")
    def login_submit(
        request: Request,
        username: str = Form(default=""),
        password: str = Form(default=""),
        next: str = Form(default="/"),
    ):
        next_path = safe_next_path(next)
        if not auth_enabled(request):
            return RedirectResponse(url=next_path, status_code=303)
        if credentials_match(request, username, password):
            response = RedirectResponse(url=next_path, status_code=303)
            cookie_name = str(getattr(request.app.state, "auth_cookie_name", "plate_admin_session"))
            cookie_value_factory = getattr(request.app.state, "auth_issue_cookie_value", None)
            if callable(cookie_value_factory):
                response.set_cookie(
                    key=cookie_name,
                    value=str(cookie_value_factory()),
                    max_age=int(getattr(request.app.state, "auth_session_max_age", 43200) or 43200),
                    httponly=True,
                    samesite="lax",
                )
            return response
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=login_template_context(
                request,
                next_path=next_path,
                error_message="Invalid admin username or password.",
            ),
            status_code=401,
        )

    @router.post("/logout")
    def logout(request: Request):
        destination = "/login" if auth_enabled(request) else "/"
        response = RedirectResponse(url=destination, status_code=303)
        response.delete_cookie(str(getattr(request.app.state, "auth_cookie_name", "plate_admin_session")))
        return response

    @router.get("/")
    def index(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=app_template_context(request),
        )

    @router.get("/settings")
    def settings_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="settings.html",
            context=app_template_context(request),
        )

    @router.get("/artifacts")
    def get_artifact(path: str = Query(..., min_length=1)):
        artifact_path = resolve_artifact_path(path)
        return FileResponse(artifact_path)

    @router.get("/stream/dashboard-events")
    async def dashboard_events(request: Request):
        app_config = getattr(request.app.state, "app_config", None)
        refresh_seconds_value = getattr(getattr(app_config, "app", None), "dashboard_refresh_seconds", None)
        refresh_seconds = max(
            float(
                refresh_seconds_value
                if refresh_seconds_value is not None
                else request.app.state.settings.get("app", {}).get("dashboard_refresh_seconds", 1.0)
            ),
            0.0,
        )

        async def event_generator():
            while True:
                payload = dashboard_cache.get(request)
                yield f"data: {json.dumps(jsonable_encoder(payload), ensure_ascii=True)}\n\n"
                try:
                    await asyncio.sleep(refresh_seconds)
                except asyncio.CancelledError:
                    break

        return StreamingResponse(event_generator(), media_type="text/event-stream")
