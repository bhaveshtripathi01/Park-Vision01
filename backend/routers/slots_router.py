import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database import get_db
from models import Booking, ParkingSlot
from services.slot_service import get_live_counts, serialize_slot, slot_manager


router = APIRouter(prefix="/api", tags=["slots"])


@router.get("/slots")
async def get_slots(
    zone: str | None = None,
    floor: str | None = None,
    slot_type: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(ParkingSlot)
    if zone:
        query = query.filter(ParkingSlot.zone == zone.upper())
    if floor:
        query = query.filter(ParkingSlot.floor == floor.upper())
    if slot_type:
        query = query.filter(ParkingSlot.slot_type == slot_type.lower())

    slots = query.order_by(ParkingSlot.zone, ParkingSlot.id).all()
    active_bookings = db.query(Booking).filter(Booking.status == "active").all()
    user_slot_map = {booking.slot_id: booking.user_id for booking in active_bookings}

    return {
        "slots": [{**serialize_slot(slot), "booked_by": user_slot_map.get(slot.id)} for slot in slots],
        "counts": get_live_counts(db),
    }


@router.get("/slots/live-counts")
async def get_counts(db: Session = Depends(get_db)):
    return get_live_counts(db)


@router.get("/slots/{slot_id}")
async def get_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    current_booking = (
        db.query(Booking)
        .filter(Booking.slot_id == slot.id, Booking.status.in_(["active", "pending"]))
        .order_by(Booking.created_at.desc())
        .first()
    )

    return {
        "slot": serialize_slot(slot),
        "booking": {
            "booking_ref": current_booking.booking_ref,
            "status": current_booking.status,
            "check_in": current_booking.check_in.isoformat(),
            "check_out": current_booking.check_out.isoformat(),
        }
        if current_booking
        else None,
    }


@router.websocket("/ws/slots")
async def slots_websocket(websocket: WebSocket):
    await slot_manager.connect(websocket)
    db = next(get_db())
    try:
        await websocket.send_json(
            {
                "type": "snapshot",
                "slots": [serialize_slot(slot) for slot in db.query(ParkingSlot).all()],
                "counts": get_live_counts(db),
            }
        )

        while True:
            await asyncio.sleep(20)
            await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        slot_manager.disconnect(websocket)
    except Exception:
        slot_manager.disconnect(websocket)
    finally:
        db.close()
