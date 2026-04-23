from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _section_dict(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, dict) else {}


def _merge_with_extras(payload: dict[str, Any], extras: dict[str, Any]) -> dict[str, Any]:
    merged = dict(payload)
    merged.update(extras)
    return merged


@dataclass(slots=True)
class AppSection:
    title: str = ""
    subtitle: str = ""
    university: str = ""
    debug: bool = False
    default_camera_role: str = "entry"
    dashboard_refresh_seconds: float = 1.0
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Any) -> "AppSection":
        data = _section_dict(raw)
        known = {
            "title",
            "subtitle",
            "university",
            "debug",
            "default_camera_role",
            "dashboard_refresh_seconds",
        }
        return cls(
            title=str(data.get("title", "") or ""),
            subtitle=str(data.get("subtitle", "") or ""),
            university=str(data.get("university", "") or ""),
            debug=bool(data.get("debug", False)),
            default_camera_role=str(data.get("default_camera_role", "entry") or "entry"),
            dashboard_refresh_seconds=float(data.get("dashboard_refresh_seconds", 1.0) or 1.0),
            extras={key: value for key, value in data.items() if key not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        return _merge_with_extras(
            {
                "title": self.title,
                "subtitle": self.subtitle,
                "university": self.university,
                "debug": self.debug,
                "default_camera_role": self.default_camera_role,
                "dashboard_refresh_seconds": self.dashboard_refresh_seconds,
            },
            self.extras,
        )


@dataclass(slots=True)
class AuthSection:
    enabled: bool = False
    admin_username: str = "admin"
    admin_password: str = "admin123"
    session_secret: str = "plate-basic-admin-session-secret"
    session_max_age_seconds: int = 43200
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Any) -> "AuthSection":
        data = _section_dict(raw)
        known = {
            "enabled",
            "admin_username",
            "admin_password",
            "session_secret",
            "session_max_age_seconds",
        }
        return cls(
            enabled=bool(data.get("enabled", False)),
            admin_username=str(data.get("admin_username", "admin") or "admin"),
            admin_password=str(data.get("admin_password", "admin123") or "admin123"),
            session_secret=str(data.get("session_secret", "plate-basic-admin-session-secret") or "plate-basic-admin-session-secret"),
            session_max_age_seconds=int(data.get("session_max_age_seconds", 43200) or 43200),
            extras={key: value for key, value in data.items() if key not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        return _merge_with_extras(
            {
                "enabled": self.enabled,
                "admin_username": self.admin_username,
                "admin_password": self.admin_password,
                "session_secret": self.session_secret,
                "session_max_age_seconds": self.session_max_age_seconds,
            },
            self.extras,
        )


@dataclass(slots=True)
class CameraRoleSection:
    source: Any = None
    source_name: str = ""
    width: int = 1280
    height: int = 720
    fps_sleep_seconds: float = 0.03
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Any) -> "CameraRoleSection":
        data = _section_dict(raw)
        known = {"source", "source_name", "width", "height", "fps_sleep_seconds"}
        return cls(
            source=data.get("source"),
            source_name=str(data.get("source_name", "") or ""),
            width=int(data.get("width", 1280) or 1280),
            height=int(data.get("height", 720) or 720),
            fps_sleep_seconds=float(data.get("fps_sleep_seconds", 0.03) or 0.03),
            extras={key: value for key, value in data.items() if key not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        return _merge_with_extras(
            {
                "source": self.source,
                "source_name": self.source_name,
                "width": self.width,
                "height": self.height,
                "fps_sleep_seconds": self.fps_sleep_seconds,
            },
            self.extras,
        )


@dataclass(slots=True)
class Section:
    values: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Any) -> "Section":
        return cls(values=_section_dict(raw))

    def to_dict(self) -> dict[str, Any]:
        return dict(self.values)


@dataclass(slots=True)
class AppConfig:
    app: AppSection = field(default_factory=AppSection)
    auth: AuthSection = field(default_factory=AuthSection)
    paths: Section = field(default_factory=Section)
    detector: Section = field(default_factory=Section)
    ocr: Section = field(default_factory=Section)
    postprocess: Section = field(default_factory=Section)
    stabilization: Section = field(default_factory=Section)
    tracking: Section = field(default_factory=Section)
    stream: Section = field(default_factory=Section)
    performance: Section = field(default_factory=Section)
    vehicle_registry: Section = field(default_factory=Section)
    artifacts: Section = field(default_factory=Section)
    uploads: Section = field(default_factory=Section)
    video_upload: Section = field(default_factory=Section)
    session: Section = field(default_factory=Section)
    camera: CameraRoleSection = field(default_factory=CameraRoleSection)
    cameras: dict[str, CameraRoleSection] = field(default_factory=dict)
    extra_sections: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppConfig":
        data = _section_dict(raw)
        cameras_raw = _section_dict(data.get("cameras"))
        known = {
            "app",
            "auth",
            "paths",
            "detector",
            "ocr",
            "postprocess",
            "stabilization",
            "tracking",
            "stream",
            "performance",
            "vehicle_registry",
            "artifacts",
            "uploads",
            "video_upload",
            "session",
            "camera",
            "cameras",
        }
        return cls(
            app=AppSection.from_dict(data.get("app")),
            auth=AuthSection.from_dict(data.get("auth")),
            paths=Section.from_dict(data.get("paths")),
            detector=Section.from_dict(data.get("detector")),
            ocr=Section.from_dict(data.get("ocr")),
            postprocess=Section.from_dict(data.get("postprocess")),
            stabilization=Section.from_dict(data.get("stabilization")),
            tracking=Section.from_dict(data.get("tracking")),
            stream=Section.from_dict(data.get("stream")),
            performance=Section.from_dict(data.get("performance")),
            vehicle_registry=Section.from_dict(data.get("vehicle_registry")),
            artifacts=Section.from_dict(data.get("artifacts")),
            uploads=Section.from_dict(data.get("uploads")),
            video_upload=Section.from_dict(data.get("video_upload")),
            session=Section.from_dict(data.get("session")),
            camera=CameraRoleSection.from_dict(data.get("camera")),
            cameras={
                str(role): CameraRoleSection.from_dict(role_settings)
                for role, role_settings in cameras_raw.items()
            },
            extra_sections={key: value for key, value in data.items() if key not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "app": self.app.to_dict(),
            "auth": self.auth.to_dict(),
            "paths": self.paths.to_dict(),
            "detector": self.detector.to_dict(),
            "ocr": self.ocr.to_dict(),
            "postprocess": self.postprocess.to_dict(),
            "stabilization": self.stabilization.to_dict(),
            "tracking": self.tracking.to_dict(),
            "stream": self.stream.to_dict(),
            "performance": self.performance.to_dict(),
            "vehicle_registry": self.vehicle_registry.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "uploads": self.uploads.to_dict(),
            "video_upload": self.video_upload.to_dict(),
            "session": self.session.to_dict(),
            "camera": self.camera.to_dict(),
            "cameras": {
                role: role_settings.to_dict()
                for role, role_settings in self.cameras.items()
            },
        }
        payload.update(self.extra_sections)
        return payload
