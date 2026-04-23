from __future__ import annotations

from pathlib import Path

import yaml

from src.config.models import AppConfig


def load_settings_dict(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return payload if isinstance(payload, dict) else {}


def load_app_config(config_path: Path) -> AppConfig:
    return AppConfig.from_dict(load_settings_dict(config_path))


def write_settings_dict(config_path: Path, settings: dict) -> None:
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            settings,
            handle,
            sort_keys=False,
            allow_unicode=False,
        )


def write_app_config(config_path: Path, config: AppConfig) -> None:
    write_settings_dict(config_path, config.to_dict())
