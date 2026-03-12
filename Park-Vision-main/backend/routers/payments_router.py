from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, verify_csrf
from database import get_db
from models import Booking, Payment, User
from schemas import PaymentInitiateRequest, PaymentVerifyRequest, PromoCodeRequest
from services.history_service import log_vehicle_event
from services.payment_service import create_payment_session, verify_payment
from services.slot_service import get_live_counts, serialize_slot, slot_manager


router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/promo")
async def apply_promo(payload: PromoCodeRequest, _: None = Depends(verify_csrf)):
    code = payload.code
    if code == "PARK20":
        discounted = round(payload.total * 0.8, 2)
        return {
            "valid": True,
            "discount_percent": 20,
            "new_total": discounted,
            "message": "Promo code applied successfully",
        }

    return {"valid": False, "message": "Invalid promo code"}


@router.post("/initiate")
async def initiate_payment(
    payload: PaymentInitiateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    booking = (
        db.query(Booking)
        .filter(Booking.id == payload.booking_id, Booking.user_id == current_user.id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    payment = create_payment_session(db, booking, payload.payment_method.lower())
    return {
        "message": "Payment initiated",
        "payment_id": payment.id,
        "session_token": payment.session_token,
    }


@router.post("/verify")
async def verify_payment_route(
    payload: PaymentVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    payment = db.query(Payment).filter(Payment.id == payload.payment_id, Payment.user_id == current_user.id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment, booking = verify_payment(db, payload.payment_id)

    if payment.status == "success":
        log_vehicle_event(
            db,
            user_id=current_user.id,
            vehicle_id=booking.vehicle_id,
            booking_id=booking.id,
            event_type="payment_success",
            details=f"Payment successful for booking {booking.booking_ref}",
        )
    else:
        log_vehicle_event(
            db,
            user_id=current_user.id,
            vehicle_id=booking.vehicle_id,
            booking_id=booking.id,
            event_type="payment_failed",
            details=f"Payment failed for booking {booking.booking_ref}",
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

    if payment.status == "success":
        return {
            "success": True,
            "transaction_id": payment.transaction_id,
            "payment_id": payment.id,
            "redirect_url": f"/api/payment/success?payment_id={payment.id}",
        }

    return {
        "success": False,
        "message": "Payment failed. Please retry.",
        "payment_id": payment.id,
    }


@router.get("/{payment_id}/receipt-data")
async def payment_receipt_data(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.user_id == current_user.id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment receipt not found")

    booking = payment.booking
    return {
        "payment_id": payment.id,
        "booking_ref": booking.booking_ref,
        "slot": booking.slot.slot_code,
        "zone": booking.slot.zone,
        "duration_hours": booking.duration_hours,
        "amount": payment.amount,
        "tax": payment.tax,
        "total": payment.total,
        "transaction_id": payment.transaction_id,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
    }
