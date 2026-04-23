from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.auth import AdminAuthMiddleware
from src.api.routes import create_router
from src.bootstrap import build_auth_config, build_core_services, load_typed_settings
from src.runtime import build_camera_runtime, install_app_state

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "configs" / "app_settings.yaml"

# Paddle's source-hoster check adds noisy offline warnings and avoidable startup
# delay even when OCR models are already cached locally. Preserve any explicit
# user override, but default to the local-only path for this app.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def create_app() -> FastAPI:
    typed_settings = load_typed_settings(CONFIG_PATH)
    settings = typed_settings.to_dict()
    auth_config = build_auth_config(typed_settings)
    services = build_core_services(typed_settings, BASE_DIR)

    app = FastAPI(title=settings["app"]["title"], debug=bool(settings["app"].get("debug", False)))
    app.add_middleware(AdminAuthMiddleware, auth_config=auth_config)

    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    camera_runtime = build_camera_runtime(app, services, settings)
    install_app_state(
        app,
        settings=settings,
        typed_settings=typed_settings,
        base_dir=BASE_DIR,
        config_path=CONFIG_PATH,
        auth_config=auth_config,
        services=services,
        camera_runtime=camera_runtime,
    )

    app.include_router(create_router(templates))

    @app.on_event("shutdown")
    def _shutdown() -> None:
        app.state.camera_manager.stop_all()
        close_storage = getattr(app.state.storage_service, "close", None)
        if callable(close_storage):
            close_storage()

    return app


app = create_app()
