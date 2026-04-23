from __future__ import annotations

from src.storage.base import BaseRepository


class VehicleRepository(BaseRepository):
    def get_registered_vehicle_by_plate(self, plate_number: str) -> dict | None:
        normalized_plate = str(plate_number or "").strip().upper()
        if not normalized_plate:
            return None
        with self.connection_manager.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM registered_vehicles
                WHERE plate_number = ?
                LIMIT 1
                """,
                (normalized_plate,),
            ).fetchone()
        return self.row_to_dict(row)

    def get_registered_vehicle(self, vehicle_id: int) -> dict | None:
        with self.connection_manager.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM registered_vehicles
                WHERE vehicle_id = ?
                LIMIT 1
                """,
                (vehicle_id,),
            ).fetchone()
        return self.row_to_dict(row)

    def list_registered_vehicles(self, limit: int = 100) -> list[dict]:
        with self.connection_manager.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM registered_vehicles
                ORDER BY updated_at DESC, vehicle_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_vehicle_documents(self, vehicle_id: int) -> list[dict]:
        with self.connection_manager.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM vehicle_documents
                WHERE vehicle_id = ?
                ORDER BY document_id ASC
                """,
                (vehicle_id,),
            ).fetchall()
        return [dict(row) for row in rows]
