from __future__ import annotations

from pathlib import Path
from typing import Any


class UploadProcessingError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = int(status_code)
        self.detail = detail
        super().__init__(detail)


class UploadSizeLimitExceededError(Exception):
    def __init__(self, limit_bytes: int) -> None:
        self.limit_bytes = int(limit_bytes)
        super().__init__(f"upload_size_limit_exceeded:{self.limit_bytes}")


def safe_upload_name(filename: str | None, fallback: str) -> str:
    candidate = (filename or "").strip()
    return candidate or fallback


def as_normalized_set(values: Any, defaults: tuple[str, ...]) -> set[str]:
    if not isinstance(values, list):
        return set(defaults)
    normalized = {
        str(item).strip().lower()
        for item in values
        if str(item).strip()
    }
    return normalized or set(defaults)


def upload_settings_for_state(app_state: Any) -> dict[str, Any]:
    return dict(app_state.settings.get("uploads", {}))


def resolve_max_upload_bytes(settings: dict[str, Any], key: str, fallback: int) -> int:
    configured = int(settings.get(key, fallback) or fallback)
    return max(configured, 1)


def validate_upload_type(
    *,
    content_type: str | None,
    filename: str,
    allowed_extensions: set[str],
    allowed_mime_types: set[str],
    file_kind: str,
) -> None:
    extension = Path(filename).suffix.lower()
    media_type = str(content_type or "").split(";", 1)[0].strip().lower()

    extension_ok = extension in allowed_extensions
    content_type_ok = bool(media_type and media_type in allowed_mime_types)

    if media_type and not content_type_ok:
        raise UploadProcessingError(415, f"Unsupported {file_kind} content type: {media_type}")
    if not extension_ok and not content_type_ok:
        extension_label = extension or "<missing>"
        raise UploadProcessingError(415, f"Unsupported {file_kind} file type: {extension_label}")
