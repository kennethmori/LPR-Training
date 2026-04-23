from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.schemas import VehicleLookupPayload, VehicleProfilePayload
from src.api.settings_support import vehicle_registry_service


def register_vehicle_routes(router: APIRouter) -> None:
    @router.get("/vehicles/lookup", response_model=VehicleLookupPayload)
    def vehicle_lookup(request: Request, plate_number: str = Query(default="", min_length=1)):
        registry_service = vehicle_registry_service(request)
        if registry_service is None:
            raise HTTPException(status_code=503, detail="Vehicle registry service unavailable.")
        return registry_service.lookup_plate(plate_number)

    @router.get("/vehicles/{vehicle_id}", response_model=VehicleProfilePayload)
    def one_vehicle(request: Request, vehicle_id: int):
        storage_service = getattr(request.app.state, "storage_service", None)
        if storage_service is None:
            raise HTTPException(status_code=503, detail="Storage service unavailable.")
        vehicle_row = storage_service.get_registered_vehicle(vehicle_id=vehicle_id)
        if vehicle_row is None:
            raise HTTPException(status_code=404, detail=f"Vehicle not found: {vehicle_id}")
        registry_service = vehicle_registry_service(request)
        if registry_service is None:
            raise HTTPException(status_code=503, detail="Vehicle registry service unavailable.")
        lookup = registry_service.lookup_plate(vehicle_row.get("plate_number"))
        profile = lookup.get("profile")
        if profile is None:
            raise HTTPException(status_code=404, detail=f"Vehicle not found: {vehicle_id}")
        return profile
