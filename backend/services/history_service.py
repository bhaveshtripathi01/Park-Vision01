from models import VehicleHistory


def log_vehicle_event(
    db,
    *,
    user_id: int,
    vehicle_id: int,
    event_type: str,
    booking_id: int | None = None,
    details: str | None = None,
):
    db.add(
        VehicleHistory(
            user_id=user_id,
            vehicle_id=vehicle_id,
            booking_id=booking_id,
            event_type=event_type,
            details=details,
        )
    )
