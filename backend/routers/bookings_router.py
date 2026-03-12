from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, verify_csrf
from database import get_db
from models import Booking, User
from schemas import BookingCreateRequest
from services.history_service import log_vehicle_event
from services.booking_service import create_booking
from services.slot_service import get_live_counts, serialize_slot, slot_manager


router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("")
async def create_booking_route(
    payload: BookingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    booking = create_booking(
        db=db,
        user_id=current_user.id,
        slot_id=payload.slot_id,
        vehicle_id=payload.vehicle_id,
        check_in=payload.check_in,
        check_out=payload.check_out,
    )

    log_vehicle_event(
        db,
        user_id=current_user.id,
        vehicle_id=booking.vehicle_id,
        booking_id=booking.id,
        event_type="booking_created",
        details=f"Booking {booking.booking_ref} reserved slot {booking.slot.slot_code}",
    )
    db.commit()

    await slot_manager.broadcast(
        {
            "type": "slot_update",
            "slot": serialize_slot(booking.slot),
            "counts": get_live_counts(db),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    return {
        "message": "Booking created and slot reserved",
        "booking": {
            "id": booking.id,
            "booking_ref": booking.booking_ref,
            "slot_id": booking.slot_id,
            "vehicle_id": booking.vehicle_id,
            "check_in": booking.check_in.isoformat(),
            "check_out": booking.check_out.isoformat(),
            "duration_hours": booking.duration_hours,
            "amount": booking.amount,
            "tax": booking.tax,
            "total": booking.total,
            "status": booking.status,
        },
        "redirect_url": f"/api/payment?booking_id={booking.id}",
    }


@router.get("/my")
async def my_bookings(
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Booking).filter(Booking.user_id == current_user.id)
    if vehicle_id:
        query = query.filter(Booking.vehicle_id == vehicle_id)

    bookings = query.order_by(Booking.created_at.desc()).all()

    return {
        "bookings": [
            {
                "id": booking.id,
                "booking_ref": booking.booking_ref,
                "slot_code": booking.slot.slot_code,
                "zone": booking.slot.zone,
                "floor": booking.slot.floor,
                "vehicle_id": booking.vehicle_id,
                "vehicle_number": booking.vehicle.number_plate,
                "vehicle_type": booking.vehicle.vehicle_type,
                "duration_hours": booking.duration_hours,
                "amount": booking.total,
                "status": booking.status,
                "created_at": booking.created_at.isoformat() if booking.created_at else None,
                "check_in": booking.check_in.isoformat(),
                "check_out": booking.check_out.isoformat(),
                "payment_id": booking.payment.id if booking.payment else None,
            }
            for booking in bookings
        ]
    }


@router.delete("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id, Booking.user_id == current_user.id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status not in ["active", "pending"]:
        raise HTTPException(status_code=400, detail="Only active/pending booking can be cancelled")

    booking.status = "cancelled"
    booking.slot.status = "available"
    booking.slot.last_updated = datetime.now(timezone.utc)
    log_vehicle_event(
        db,
        user_id=current_user.id,
        vehicle_id=booking.vehicle_id,
        booking_id=booking.id,
        event_type="booking_cancelled",
        details=f"Booking {booking.booking_ref} cancelled by user",
    )

    db.commit()

    await slot_manager.broadcast(
        {
            "type": "slot_update",
            "slot": serialize_slot(booking.slot),
            "counts": get_live_counts(db),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    return {"message": "Booking cancelled successfully"}
