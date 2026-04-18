from __future__ import annotations

from typing import Any


class CameraManager:
    def __init__(self, camera_services: dict[str, Any], default_role: str = "entry") -> None:
        self.camera_services = camera_services
        self.default_role = default_role if default_role in camera_services else next(iter(camera_services), "entry")

    @property
    def roles(self) -> list[str]:
        return sorted(self.camera_services.keys())

    def get(self, role: str | None) -> Any | None:
        selected_role = role or self.default_role
        return self.camera_services.get(selected_role)

    def start(self, role: str | None = None) -> bool:
        camera = self.get(role)
        if camera is None:
            return False
        return camera.start()

    def stop(self, role: str | None = None) -> bool:
        camera = self.get(role)
        if camera is None:
            return False
        camera.stop()
        return True

    def stop_all(self) -> None:
        for camera in self.camera_services.values():
            camera.stop()

    def is_running(self, role: str | None = None) -> bool:
        camera = self.get(role)
        return bool(camera and camera.running)

    def running_roles(self) -> list[str]:
        return [role for role, camera in self.camera_services.items() if camera.running]

    def latest_payload(self, role: str | None = None) -> dict[str, Any] | None:
        camera = self.get(role)
        if camera is None:
            return None
        return camera.latest_payload
