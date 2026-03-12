import random
from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy.orm import Session

from models import Booking, ParkingSlot


class SlotBroadcastManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, payload: dict):
        stale_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                stale_connections.append(connection)

        for stale in stale_connections:
            self.disconnect(stale)


slot_manager = SlotBroadcastManager()


def serialize_slot(slot: ParkingSlot):
    return {
        "id": slot.id,
        "slot_code": slot.slot_code,
        "zone": slot.zone,
        "floor": slot.floor,
        "slot_type": slot.slot_type,
        "status": slot.status,
        "last_updated": slot.last_updated.isoformat() if slot.last_updated else None,
    }


def get_live_counts(db: Session):
    total = db.query(ParkingSlot).count()
    available = db.query(ParkingSlot).filter(ParkingSlot.status == "available").count()
    occupied = db.query(ParkingSlot).filter(ParkingSlot.status == "occupied").count()
    reserved = db.query(ParkingSlot).filter(ParkingSlot.status == "reserved").count()
    return {
        "total": total,
        "available": available,
        "occupied": occupied,
        "reserved": reserved,
    }


def seed_slots(db: Session):
    existing = db.query(ParkingSlot).count()
    if existing:
        return

    zones = ["A", "B", "C"]
    floors = ["G", "1", "2"]

    for zone in zones:
        for i in range(1, 17):
            slot_type = "standard"
            if i % 8 == 0:
                slot_type = "ev"
            elif i % 11 == 0:
                slot_type = "handicapped"

            slot = ParkingSlot(
                slot_code=f"{zone}{i}",
                zone=zone,
                floor=floors[(i - 1) % len(floors)],
                slot_type=slot_type,
                status="available",
                last_updated=datetime.now(timezone.utc),
            )
            db.add(slot)

    db.commit()


def release_expired_pending_reservations(db: Session):
    now = datetime.now(timezone.utc)
    pending = db.query(Booking).filter(Booking.status == "pending").all()

    updated = False
    for booking in pending:
        expiry_cutoff = (booking.created_at or now).astimezone(timezone.utc)
        if (now - expiry_cutoff).total_seconds() >= 600:
            booking.status = "cancelled"
            if booking.slot.status == "reserved":
                booking.slot.status = "available"
                booking.slot.last_updated = now
            updated = True

    if updated:
        db.commit()


def simulate_random_slot_changes(db: Session):
    release_expired_pending_reservations(db)

    mutable_slots = (
        db.query(ParkingSlot)
        .filter(ParkingSlot.status.in_(["available", "occupied"]))
        .all()
    )

    if len(mutable_slots) < 3:
        return []

    changes = []
    sample_count = random.choice([2, 3])
    for slot in random.sample(mutable_slots, sample_count):
        slot.status = "occupied" if slot.status == "available" else "available"
        slot.last_updated = datetime.now(timezone.utc)
        changes.append(slot)

    db.commit()
    return changes
