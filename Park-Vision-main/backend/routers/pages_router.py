import json
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from auth import get_current_user_optional
from database import get_db
from models import Booking, Payment, Vehicle


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/api", tags=["pages"])


def user_payload(user):
    if not user:
        return None
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "initials": "".join([part[0].upper() for part in user.full_name.split()[:2]]) or "PV",
    }


def template_context(request: Request, user, extra: dict | None = None):
    context = {
        "request": request,
        "current_user": user,
        "user_json": json.dumps(user_payload(user)) if user else "null",
        "csrf_token": request.state.csrf_token,
    }
    if extra:
        context.update(extra)
    return context


@router.get("/")
async def landing(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    return templates.TemplateResponse(
        "index.html",
        template_context(request, user),
    )


@router.get("/login")
async def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/api/dashboard", status_code=302)
    return templates.TemplateResponse("auth/login.html", template_context(request, user))


@router.get("/register")
async def register_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/api/dashboard", status_code=302)
    return templates.TemplateResponse("auth/register.html", template_context(request, user))


@router.get("/dashboard")
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/api/login", status_code=302)

    vehicles = db.query(Vehicle).filter(Vehicle.user_id == user.id).all()
    return templates.TemplateResponse(
        "dashboard/dashboard.html",
        template_context(
            request,
            user,
            {
                "vehicles_json": json.dumps(
                    [
                        {
                            "id": vehicle.id,
                            "number_plate": vehicle.number_plate,
                            "vehicle_type": vehicle.vehicle_type,
                            "is_primary": vehicle.is_primary,
                        }
                        for vehicle in vehicles
                    ]
                )
            },
        ),
    )


@router.get("/payment")
async def payment_page(booking_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/api/login", status_code=302)

    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        return RedirectResponse(url="/api/dashboard", status_code=302)

    booking_payload = {
        "id": booking.id,
        "booking_ref": booking.booking_ref,
        "slot_code": booking.slot.slot_code,
        "zone": booking.slot.zone,
        "floor": booking.slot.floor,
        "slot_type": booking.slot.slot_type,
        "check_in": booking.check_in.isoformat(),
        "check_out": booking.check_out.isoformat(),
        "duration_hours": booking.duration_hours,
        "amount": booking.amount,
        "tax": booking.tax,
        "total": booking.total,
    }

    return templates.TemplateResponse(
        "payment/payment.html",
        template_context(
            request,
            user,
            {
                "booking": booking_payload,
                "booking_json": json.dumps(booking_payload),
            },
        ),
    )


@router.get("/payment/success")
async def payment_success_page(payment_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/api/login", status_code=302)

    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id == user.id).first()
    if not payment:
        return RedirectResponse(url="/api/dashboard", status_code=302)

    return templates.TemplateResponse(
        "payment/success.html",
        template_context(request, user, {"payment": payment, "booking": payment.booking}),
    )


@router.get("/my-bookings")
async def my_bookings_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/api/login", status_code=302)

    return templates.TemplateResponse(
        "profile/bookings.html",
        template_context(request, user),
    )


@router.get("/profile")
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/api/login", status_code=302)

    return templates.TemplateResponse(
        "profile/profile.html",
        template_context(request, user),
    )


@router.get("/payments/{payment_id}/receipt")
async def receipt_page(payment_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/api/login", status_code=302)

    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id == user.id).first()
    if not payment:
        return RedirectResponse(url="/api/my-bookings", status_code=302)

    return templates.TemplateResponse(
        "payment/receipt.html",
        template_context(request, user, {"payment": payment, "booking": payment.booking}),
    )
