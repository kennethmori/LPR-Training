from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse


@dataclass(frozen=True, slots=True)
class AuthConfig:
    enabled: bool
    admin_username: str
    admin_password: str
    session_secret: str
    session_max_age: int
    cookie_name: str = "plate_admin_session"


def build_auth_cookie_value(username: str, secret: str) -> str:
    username_value = str(username or "").strip()
    secret_value = str(secret or "")
    signature = hmac.new(
        secret_value.encode("utf-8"),
        username_value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{username_value}:{signature}"


def is_valid_auth_cookie(cookie_value: str | None, username: str, secret: str) -> bool:
    raw_value = str(cookie_value or "").strip()
    if ":" not in raw_value:
        return False
    cookie_username, provided_signature = raw_value.split(":", 1)
    expected_cookie = build_auth_cookie_value(username, secret)
    expected_username, expected_signature = expected_cookie.split(":", 1)
    return hmac.compare_digest(cookie_username, expected_username) and hmac.compare_digest(
        provided_signature,
        expected_signature,
    )


class AdminAuthMiddleware:
    def __init__(self, app: Any, auth_config: AuthConfig) -> None:
        self.app = app
        self.auth_config = auth_config

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if (
            not self.auth_config.enabled
            or path.startswith("/static")
            or path in {"/login", "/favicon.ico"}
        ):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        auth_cookie = request.cookies.get(self.auth_config.cookie_name)
        if is_valid_auth_cookie(
            auth_cookie,
            self.auth_config.admin_username,
            self.auth_config.session_secret,
        ):
            await self.app(scope, receive, send)
            return

        accepts_html = "text/html" in request.headers.get("accept", "")
        if request.method.upper() == "GET" and accepts_html:
            next_path = request.url.path
            if request.url.query:
                next_path += "?" + request.url.query
            response = RedirectResponse(
                url=f"/login?next={quote(next_path, safe='/?=&')}",
                status_code=303,
            )
            await response(scope, receive, send)
            return

        response = JSONResponse(status_code=401, content={"detail": "Admin login required."})
        await response(scope, receive, send)


def auth_enabled(request: Request) -> bool:
    return bool(getattr(request.app.state, "auth_enabled", False))


def is_admin_authenticated(request: Request) -> bool:
    cookie_name = str(getattr(request.app.state, "auth_cookie_name", "plate_admin_session"))
    validator = getattr(request.app.state, "auth_is_valid_cookie", None)
    if not callable(validator):
        return False
    return bool(validator(request.cookies.get(cookie_name)))


def safe_next_path(value: Any) -> str:
    candidate = str(value or "").strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return "/"
    return candidate


def app_template_context(request: Request) -> dict[str, Any]:
    settings = getattr(request.app.state, "settings", {}) or {}
    app_settings = settings.get("app", {}) if isinstance(settings, dict) else {}
    server_time_factory = getattr(request.app.state, "server_time_factory", None)
    server_time = server_time_factory() if callable(server_time_factory) else datetime.now(timezone.utc).isoformat()
    return {
        "app_title": app_settings.get("title", "USM License Plate Recognition System"),
        "subtitle": app_settings.get("subtitle", "Two-Stage YOLO + OCR Prototype"),
        "university": app_settings.get("university", "University of Southern Mindanao"),
        "server_time": server_time,
        "auth_enabled": auth_enabled(request),
    }


def login_template_context(
    request: Request,
    *,
    next_path: str = "/",
    error_message: str = "",
) -> dict[str, Any]:
    return {
        **app_template_context(request),
        "next_path": safe_next_path(next_path),
        "error_message": error_message,
    }


def credentials_match(request: Request, username: str, password: str) -> bool:
    configured_username = str(getattr(request.app.state, "auth_admin_username", "") or "")
    configured_password = str(getattr(request.app.state, "auth_admin_password", "") or "")
    return hmac.compare_digest(str(username or ""), configured_username) and hmac.compare_digest(
        str(password or ""),
        configured_password,
    )
