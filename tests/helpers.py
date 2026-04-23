from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from src.api.routes import create_router


def templates_directory() -> Path:
    return Path(__file__).resolve().parents[1] / "templates"


def build_templates() -> Jinja2Templates:
    return Jinja2Templates(directory=str(templates_directory()))


def include_main_router(app: FastAPI) -> FastAPI:
    app.include_router(create_router(build_templates()))
    return app


def create_test_workspace(name: str) -> Path:
    root = Path(".tmp") / "tests" / name / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def remove_test_workspace(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
