from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    limiter,
    sanitize_text,
    validate_password_strength,
    validate_phone,
    verify_csrf,
    verify_password,
)
from database import get_db
from models import NotificationPreference, User, Vehicle
from schemas import LoginRequest, RegisterRequest
from services.history_service import log_vehicle_event


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
@limiter.limit("10/minute")
async def register(
    request: Request,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    full_name = sanitize_text(payload.full_name)
    phone = sanitize_text(payload.phone)
    vehicle_number = sanitize_text(payload.vehicle_number).upper()

    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    if not validate_password_strength(payload.password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8+ chars with at least 1 uppercase and 1 number",
        )

    if not validate_phone(phone):
        raise HTTPException(status_code=400, detail="Invalid phone format")

    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        full_name=full_name,
        email=payload.email.lower(),
        phone=phone,
        hashed_password=get_password_hash(payload.password),
    )
    db.add(user)
    db.flush()

    vehicle = Vehicle(
        user_id=user.id,
        number_plate=vehicle_number,
        vehicle_type=payload.vehicle_type.lower(),
        is_primary=True,
    )
    db.add(vehicle)
    db.add(NotificationPreference(user_id=user.id))
    db.flush()
    log_vehicle_event(
        db,
        user_id=user.id,
        vehicle_id=vehicle.id,
        event_type="vehicle_registered",
        details=f"Primary vehicle {vehicle.number_plate} added during registration",
    )
    db.commit()

    return {
        "message": "Account created successfully",
        "redirect_url": "/api/login",
    }


@router.post("/login")
@limiter.limit("15/minute")
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    user = db.query(User).filter(User.email == payload.email.lower(), User.is_active.is_(True)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=timedelta(hours=24),
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24,
    )

    return {
        "message": "Login successful",
        "redirect_url": "/api/dashboard",
    }


@router.post("/logout")
async def logout(response: Response, _: None = Depends(verify_csrf)):
    response.delete_cookie("access_token")
    return {
        "message": "Logged out successfully",
        "redirect_url": "/api/login",
    }


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
