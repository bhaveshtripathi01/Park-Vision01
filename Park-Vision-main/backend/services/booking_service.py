import random
import string
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Booking, ParkingSlot, Vehicle


BASE_RATE_PER_HOUR = 20.0
GST_RATE = 0.18


def ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def calculate_pricing(check_in: datetime, check_out: datetime):
    check_in_utc = ensure_aware(check_in)
    check_out_utc = ensure_aware(check_out)
    duration_seconds = (check_out_utc - check_in_utc).total_seconds()

    if duration_seconds < 3600:
        raise HTTPException(status_code=400, detail="Minimum booking duration is 1 hour")

    duration_hours = round(duration_seconds / 3600, 2)
    amount = round(duration_hours * BASE_RATE_PER_HOUR, 2)
    tax = round(amount * GST_RATE, 2)
    total = round(amount + tax, 2)
    return duration_hours, amount, tax, total


def generate_booking_ref():
    year = datetime.now(timezone.utc).year
    suffix = "".join(random.choices(string.digits, k=6))
    return f"PV-{year}-{suffix}"


def validate_booking_window(check_in: datetime, check_out: datetime):
    now = datetime.now(timezone.utc)
    check_in_utc = ensure_aware(check_in)
    check_out_utc = ensure_aware(check_out)

    if check_in_utc < now:
        raise HTTPException(status_code=400, detail="Check-in cannot be in the past")
    if check_out_utc <= check_in_utc:
        raise HTTPException(status_code=400, detail="Check-out must be after check-in")


def check_slot_conflict(db: Session, slot_id: int, check_in: datetime, check_out: datetime):
    conflicting = (
        db.query(Booking)
        .filter(
            Booking.slot_id == slot_id,
            Booking.status.in_(["active", "pending"]),
            Booking.check_out > ensure_aware(check_in),
            Booking.check_in < ensure_aware(check_out),
        )
        .first()
    )
    return conflicting is not None


def create_booking(
    db: Session,
    user_id: int,
    slot_id: int,
    vehicle_id: int,
    check_in: datetime,
    check_out: datetime,
):
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    if slot.status != "available":
        raise HTTPException(status_code=400, detail="Slot is not available")

    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.user_id == user_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found for user")

    validate_booking_window(check_in, check_out)

    if check_slot_conflict(db, slot_id, check_in, check_out):
        raise HTTPException(status_code=409, detail="Slot has conflicting booking")

    duration_hours, amount, tax, total = calculate_pricing(check_in, check_out)

    booking = Booking(
        user_id=user_id,
        slot_id=slot.id,
        vehicle_id=vehicle.id,
        check_in=ensure_aware(check_in),
        check_out=ensure_aware(check_out),
        duration_hours=duration_hours,
        amount=amount,
        tax=tax,
        total=total,
        status="pending",
        booking_ref=generate_booking_ref(),
    )

    slot.status = "reserved"
    slot.last_updated = datetime.now(timezone.utc)

    db.add(booking)
    db.commit()
    db.refresh(booking)
    db.refresh(slot)
    return booking
