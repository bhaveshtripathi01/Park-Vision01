import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from auth import generate_csrf_token, limiter
from database import Base, SessionLocal, engine
from routers.auth_router import router as auth_router
from routers.bookings_router import router as bookings_router
from routers.pages_router import router as pages_router
from routers.payments_router import router as payments_router
from routers.profile_router import router as profile_router
from routers.slots_router import router as slots_router
from services.slot_service import get_live_counts, seed_slots, serialize_slot, simulate_random_slot_changes, slot_manager


async def slot_simulation_loop():
    while True:
        await asyncio.sleep(5)
        db = SessionLocal()
        try:
            changed_slots = simulate_random_slot_changes(db)
            if changed_slots:
                counts = get_live_counts(db)
                for slot in changed_slots:
                    await slot_manager.broadcast(
                        {
                            "type": "slot_update",
                            "slot": serialize_slot(slot),
                            "counts": counts,
                        }
                    )
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_slots(db)
    finally:
        db.close()

    simulation_task = asyncio.create_task(slot_simulation_loop())
    yield
    simulation_task.cancel()
    try:
        await simulation_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Park Vision", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def csrf_cookie_middleware(request: Request, call_next):
    incoming_token = request.cookies.get("csrf_token")
    request.state.csrf_token = incoming_token or generate_csrf_token()

    response = await call_next(request)
    if not incoming_token:
        response.set_cookie(
            key="csrf_token",
            value=request.state.csrf_token,
            httponly=False,
            secure=False,
            samesite="lax",
            max_age=60 * 60 * 24,
        )
    return response


static_dir = ROOT_DIR / "static"
app.mount("/api/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(pages_router)
app.include_router(auth_router)
app.include_router(slots_router)
app.include_router(bookings_router)
app.include_router(payments_router)
app.include_router(profile_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Park Vision"}
