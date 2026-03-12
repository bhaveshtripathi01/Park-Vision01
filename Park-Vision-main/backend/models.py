from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


def now_utc():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    is_active = Column(Boolean, default=True)

    vehicles = relationship("Vehicle", back_populates="owner", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    vehicle_history = relationship("VehicleHistory", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship(
        "NotificationPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    number_plate = Column(String(20), nullable=False)
    vehicle_type = Column(String(20), nullable=False)
    is_primary = Column(Boolean, default=False)

    owner = relationship("User", back_populates="vehicles")
    bookings = relationship("Booking", back_populates="vehicle")
    history_events = relationship("VehicleHistory", back_populates="vehicle")


class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    id = Column(Integer, primary_key=True, index=True)
    slot_code = Column(String(10), unique=True, nullable=False, index=True)
    zone = Column(String(2), nullable=False, index=True)
    floor = Column(String(4), nullable=False, index=True)
    slot_type = Column(String(20), nullable=False)
    status = Column(String(20), default="available", index=True)
    last_updated = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    bookings = relationship("Booking", back_populates="slot")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    slot_id = Column(Integer, ForeignKey("parking_slots.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)

    check_in = Column(DateTime(timezone=True), nullable=False)
    check_out = Column(DateTime(timezone=True), nullable=False)
    duration_hours = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    tax = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    status = Column(String(20), default="pending", index=True)
    booking_ref = Column(String(32), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)

    user = relationship("User", back_populates="bookings")
    slot = relationship("ParkingSlot", back_populates="bookings")
    vehicle = relationship("Vehicle", back_populates="bookings")
    payment = relationship("Payment", back_populates="booking", uselist=False)
    history_events = relationship("VehicleHistory", back_populates="booking")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    tax = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    method = Column(String(20), nullable=False)
    status = Column(String(20), default="pending", index=True)
    transaction_id = Column(String(64), nullable=True)
    session_token = Column(String(64), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)

    booking = relationship("Booking", back_populates="payment")
    user = relationship("User", back_populates="payments")


class VehicleHistory(Base):
    __tablename__ = "vehicle_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True, index=True)
    event_type = Column(String(60), nullable=False)
    details = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc, index=True)

    user = relationship("User", back_populates="vehicle_history")
    vehicle = relationship("Vehicle", back_populates="history_events")
    booking = relationship("Booking", back_populates="history_events")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    booking_reminders = Column(Boolean, default=True)
    payment_receipts = Column(Boolean, default=True)
    promo_offers = Column(Boolean, default=False)

    user = relationship("User", back_populates="preferences")
