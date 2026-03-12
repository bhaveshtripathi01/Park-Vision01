import random
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Booking, Payment


def create_payment_session(db: Session, booking: Booking, method: str):
    payment = Payment(
        booking_id=booking.id,
        user_id=booking.user_id,
        amount=booking.amount,
        tax=booking.tax,
        total=booking.total,
        method=method,
        status="pending",
        session_token=secrets.token_hex(16),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def verify_payment(db: Session, payment_id: int):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    is_success = random.random() <= 0.95

    if is_success:
        payment.status = "success"
        payment.transaction_id = f"TXN{secrets.token_hex(6).upper()}"
        payment.paid_at = datetime.now(timezone.utc)
        booking.status = "active"
        booking.slot.status = "occupied"
        booking.slot.last_updated = datetime.now(timezone.utc)
    else:
        payment.status = "failed"
        booking.status = "pending"
        booking.slot.status = "reserved"
        booking.slot.last_updated = datetime.now(timezone.utc)

    db.commit()
    db.refresh(payment)
    db.refresh(booking)
    return payment, booking
