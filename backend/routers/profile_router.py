from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import (
    get_current_user,
    get_password_hash,
    sanitize_text,
    validate_password_strength,
    validate_phone,
    verify_csrf,
    verify_password,
)
from database import get_db
from models import Booking, NotificationPreference, User, Vehicle, VehicleHistory
from schemas import (
    NotificationPreferenceRequest,
    UpdatePasswordRequest,
    UpdateProfileRequest,
    VehicleCreateRequest,
)
from services.history_service import log_vehicle_event


router = APIRouter(prefix="/api/profile-api", tags=["profile"])


@router.get("")
async def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prefs = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.user_id == current_user.id)
        .first()
    )

    vehicles = db.query(Vehicle).filter(Vehicle.user_id == current_user.id).all()
    history_counts = {
        vehicle_id: count
        for vehicle_id, count in (
            db.query(VehicleHistory.vehicle_id, func.count(VehicleHistory.id))
            .filter(VehicleHistory.user_id == current_user.id)
            .group_by(VehicleHistory.vehicle_id)
            .all()
        )
    }

    return {
        "user": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone": current_user.phone,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "vehicles": [
            {
                "id": vehicle.id,
                "number_plate": vehicle.number_plate,
                "vehicle_type": vehicle.vehicle_type,
                "is_primary": vehicle.is_primary,
                "history_count": history_counts.get(vehicle.id, 0),
            }
            for vehicle in vehicles
        ],
        "preferences": {
            "booking_reminders": prefs.booking_reminders if prefs else True,
            "payment_receipts": prefs.payment_receipts if prefs else True,
            "promo_offers": prefs.promo_offers if prefs else False,
        },
    }


@router.put("")
async def update_profile(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    full_name = sanitize_text(payload.full_name)
    phone = sanitize_text(payload.phone)

    if not validate_phone(phone):
        raise HTTPException(status_code=400, detail="Invalid phone format")

    current_user.full_name = full_name
    current_user.phone = phone
    db.commit()
    return {"message": "Profile updated successfully"}


@router.post("/vehicles")
async def add_vehicle(
    payload: VehicleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    number_plate = sanitize_text(payload.number_plate).upper()
    vehicle_type = sanitize_text(payload.vehicle_type).lower()

    if payload.is_primary:
        db.query(Vehicle).filter(Vehicle.user_id == current_user.id).update({"is_primary": False})

    vehicle = Vehicle(
        user_id=current_user.id,
        number_plate=number_plate,
        vehicle_type=vehicle_type,
        is_primary=payload.is_primary,
    )
    db.add(vehicle)
    db.flush()
    log_vehicle_event(
        db,
        user_id=current_user.id,
        vehicle_id=vehicle.id,
        event_type="vehicle_added",
        details=f"Vehicle {vehicle.number_plate} added from profile",
    )
    db.commit()
    db.refresh(vehicle)

    return {
        "message": "Vehicle added",
        "vehicle": {
            "id": vehicle.id,
            "number_plate": vehicle.number_plate,
            "vehicle_type": vehicle.vehicle_type,
            "is_primary": vehicle.is_primary,
        },
    }


@router.delete("/vehicles/{vehicle_id}")
async def remove_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id, Vehicle.user_id == current_user.id)
        .first()
    )
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    remaining_count = db.query(Vehicle).filter(Vehicle.user_id == current_user.id).count()
    if remaining_count <= 1:
        raise HTTPException(status_code=400, detail="At least one vehicle is required")

    has_history = (
        db.query(VehicleHistory.id)
        .filter(VehicleHistory.user_id == current_user.id, VehicleHistory.vehicle_id == vehicle.id)
        .first()
        is not None
    )
    has_bookings = (
        db.query(Booking.id)
        .filter(Booking.user_id == current_user.id, Booking.vehicle_id == vehicle.id)
        .first()
        is not None
    )
    if has_history or has_bookings:
        raise HTTPException(
            status_code=400,
            detail="Vehicle has booking history and cannot be removed",
        )

    db.delete(vehicle)
    db.commit()
    return {"message": "Vehicle removed"}


@router.get("/vehicles/{vehicle_id}/history")
async def vehicle_history(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id, Vehicle.user_id == current_user.id)
        .first()
    )
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    events = (
        db.query(VehicleHistory)
        .filter(VehicleHistory.user_id == current_user.id, VehicleHistory.vehicle_id == vehicle.id)
        .order_by(VehicleHistory.created_at.desc())
        .all()
    )

    return {
        "vehicle": {
            "id": vehicle.id,
            "number_plate": vehicle.number_plate,
            "vehicle_type": vehicle.vehicle_type,
        },
        "history": [
            {
                "id": item.id,
                "event_type": item.event_type,
                "details": item.details,
                "booking_id": item.booking_id,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in events
        ],
    }


@router.put("/notifications")
async def update_notifications(
    payload: NotificationPreferenceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    prefs = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.user_id == current_user.id)
        .first()
    )
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)

    prefs.booking_reminders = payload.booking_reminders
    prefs.payment_receipts = payload.payment_receipts
    prefs.promo_offers = payload.promo_offers
    db.commit()
    return {"message": "Notification preferences updated"}


@router.put("/password")
async def update_password(
    payload: UpdatePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    if not validate_password_strength(payload.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8+ chars with at least 1 uppercase and 1 number",
        )

    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


@router.delete("/delete-account")
async def delete_account(
    confirm: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    if confirm.lower() != "delete":
        raise HTTPException(status_code=400, detail="Type 'delete' to confirm account removal")

    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted successfully", "redirect_url": "/api/register"}
