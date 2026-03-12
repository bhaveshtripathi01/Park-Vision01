from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    password: str
    confirm_password: str
    vehicle_number: str
    vehicle_type: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class BookingCreateRequest(BaseModel):
    slot_id: int
    vehicle_id: int
    check_in: datetime
    check_out: datetime


class PaymentInitiateRequest(BaseModel):
    booking_id: int
    payment_method: str
    payment_details: Optional[dict] = None


class PaymentVerifyRequest(BaseModel):
    payment_id: int


class VehicleCreateRequest(BaseModel):
    number_plate: str
    vehicle_type: str
    is_primary: bool = False


class UpdateProfileRequest(BaseModel):
    full_name: str
    phone: str


class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class NotificationPreferenceRequest(BaseModel):
    booking_reminders: bool
    payment_receipts: bool
    promo_offers: bool


class PromoCodeRequest(BaseModel):
    code: str
    total: float

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str):
        return value.strip().upper()
