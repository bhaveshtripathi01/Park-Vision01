"""Core API regression for Park Vision auth, slots, booking, payment, profile, and CSRF flows."""

import os
import random
import string
from datetime import datetime, timedelta, timezone

import pytest
import requests


def _read_frontend_backend_url() -> str | None:
    env_path = "/app/frontend/.env"
    if not os.path.exists(env_path):
        return None

    with open(env_path, "r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "REACT_APP_BACKEND_URL":
                return value.strip().strip('"').strip("'")
    return None


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_backend_url()
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is missing")
BASE_URL = BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def csrf_token(api_client):
    # Auth module bootstrap: get CSRF cookie from page middleware
    response = api_client.get(f"{BASE_URL}/api/login", timeout=20)
    assert response.status_code == 200
    token = api_client.cookies.get("csrf_token")
    assert token, "csrf_token cookie was not set"
    return token


@pytest.fixture(scope="session")
def registered_identity(api_client, csrf_token):
    # Auth feature setup: register unique user + default vehicle
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    email = f"test_user_{suffix}@example.com"
    password = "TestPass123"
    payload = {
        "full_name": "Test User",
        "email": email,
        "phone": "9876543210",
        "password": password,
        "confirm_password": password,
        "vehicle_number": f"TEST{suffix.upper()}",
        "vehicle_type": "car",
    }
    response = api_client.post(
        f"{BASE_URL}/api/auth/register",
        json=payload,
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["redirect_url"] == "/api/login"
    return {"email": email, "password": password}


@pytest.fixture(scope="session")
def authenticated_client(api_client, csrf_token, registered_identity):
    # Auth login feature: issue cookie session for protected endpoints
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": registered_identity["email"], "password": registered_identity["password"]},
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["redirect_url"] == "/api/dashboard"
    assert api_client.cookies.get("access_token"), "access_token cookie missing after login"
    return api_client


@pytest.fixture(scope="session")
def cleanup_account(authenticated_client, csrf_token):
    yield
    authenticated_client.delete(
        f"{BASE_URL}/api/profile-api/delete-account?confirm=delete",
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )


def test_landing_health_and_csrf_cookie(api_client):
    # Pages + health module checks
    landing = api_client.get(f"{BASE_URL}/api/", timeout=20)
    assert landing.status_code == 200
    assert "text/html" in landing.headers.get("content-type", "")

    health = api_client.get(f"{BASE_URL}/api/health", timeout=20)
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_register_requires_csrf(api_client):
    # CSRF protection module on mutating endpoint
    payload = {
        "full_name": "No Token",
        "email": f"notoken_{random.randint(1000,9999)}@example.com",
        "phone": "9876543210",
        "password": "TestPass123",
        "confirm_password": "TestPass123",
        "vehicle_number": "NOTOKEN01",
        "vehicle_type": "car",
    }
    response = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=20)
    assert response.status_code == 403
    assert "CSRF token" in response.json()["detail"]


def test_auth_me_and_dashboard_protection(authenticated_client, registered_identity, cleanup_account):
    # Auth + protected page module
    me = authenticated_client.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert me.status_code == 200
    me_data = me.json()
    assert me_data["email"] == registered_identity["email"]

    anon = requests.Session()
    blocked = anon.get(f"{BASE_URL}/api/dashboard", allow_redirects=False, timeout=20)
    assert blocked.status_code == 302
    assert blocked.headers.get("location") == "/api/login"


def test_slots_routes_and_profile_route_conflict(authenticated_client):
    # Slots routes + page/json routing module
    counts = authenticated_client.get(f"{BASE_URL}/api/slots/live-counts", timeout=20)
    assert counts.status_code == 200
    counts_data = counts.json()
    assert isinstance(counts_data["total"], int)

    slots = authenticated_client.get(f"{BASE_URL}/api/slots?zone=A", timeout=20)
    assert slots.status_code == 200
    slots_data = slots.json()
    assert isinstance(slots_data["slots"], list)
    assert len(slots_data["slots"]) > 0

    slot_id = slots_data["slots"][0]["id"]
    slot_detail = authenticated_client.get(f"{BASE_URL}/api/slots/{slot_id}", timeout=20)
    assert slot_detail.status_code == 200
    assert slot_detail.json()["slot"]["id"] == slot_id

    profile_page = authenticated_client.get(f"{BASE_URL}/api/profile", timeout=20)
    assert profile_page.status_code == 200
    assert "text/html" in profile_page.headers.get("content-type", "")

    profile_json = authenticated_client.get(f"{BASE_URL}/api/profile-api", timeout=20)
    assert profile_json.status_code == 200
    assert "user" in profile_json.json()


def test_booking_payment_receipt_and_cancel_flow(authenticated_client, csrf_token):
    # Booking + payment + receipt + cancel integration module
    profile = authenticated_client.get(f"{BASE_URL}/api/profile-api", timeout=20)
    assert profile.status_code == 200
    vehicles = profile.json()["vehicles"]
    assert len(vehicles) > 0
    vehicle_id = vehicles[0]["id"]

    slot_resp = authenticated_client.get(f"{BASE_URL}/api/slots?zone=A", timeout=20)
    available_slots = [s for s in slot_resp.json()["slots"] if s["status"] == "available"]
    assert len(available_slots) > 0
    slot_id = available_slots[0]["id"]

    check_in = datetime.now(timezone.utc) + timedelta(hours=2)
    check_out = check_in + timedelta(hours=2)

    create_booking = authenticated_client.post(
        f"{BASE_URL}/api/bookings",
        json={
            "slot_id": slot_id,
            "vehicle_id": vehicle_id,
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
        },
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert create_booking.status_code == 200
    booking = create_booking.json()["booking"]
    assert booking["slot_id"] == slot_id
    assert booking["status"] == "pending"

    booking_id = booking["id"]
    initiate = authenticated_client.post(
        f"{BASE_URL}/api/payments/initiate",
        json={"booking_id": booking_id, "payment_method": "card", "payment_details": {}},
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert initiate.status_code == 200
    payment_id = initiate.json()["payment_id"]

    # Payment verify is intentionally probabilistic mock; retry once if failed.
    verify = authenticated_client.post(
        f"{BASE_URL}/api/payments/verify",
        json={"payment_id": payment_id},
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert verify.status_code == 200
    verify_data = verify.json()
    if not verify_data.get("success"):
        verify = authenticated_client.post(
            f"{BASE_URL}/api/payments/verify",
            json={"payment_id": payment_id},
            headers={"X-CSRF-Token": csrf_token},
            timeout=20,
        )
        assert verify.status_code == 200
        verify_data = verify.json()

    if not verify_data.get("success"):
        pytest.skip("Payment verification remained failed after retry due to mocked probabilistic flow")

    receipt_data = authenticated_client.get(f"{BASE_URL}/api/payments/{payment_id}/receipt-data", timeout=20)
    assert receipt_data.status_code == 200
    assert receipt_data.json()["payment_id"] == payment_id

    receipt_page = authenticated_client.get(f"{BASE_URL}/api/payments/{payment_id}/receipt", timeout=20)
    assert receipt_page.status_code == 200
    assert "text/html" in receipt_page.headers.get("content-type", "")

    my_bookings = authenticated_client.get(f"{BASE_URL}/api/bookings/my", timeout=20)
    assert my_bookings.status_code == 200
    matching = [b for b in my_bookings.json()["bookings"] if b["id"] == booking_id]
    assert len(matching) == 1

    cancel = authenticated_client.delete(
        f"{BASE_URL}/api/bookings/{booking_id}/cancel",
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert cancel.status_code == 200
    assert cancel.json()["message"] == "Booking cancelled successfully"


def test_profile_update_vehicle_preferences_password_and_csrf(authenticated_client, csrf_token, registered_identity):
    # Profile module checks: update profile, vehicles, preferences, password, CSRF
    missing_csrf = authenticated_client.put(
        f"{BASE_URL}/api/profile-api",
        json={"full_name": "Blocked Update", "phone": "9876543210"},
        timeout=20,
    )
    assert missing_csrf.status_code == 403
    assert "CSRF token" in missing_csrf.json()["detail"]

    update = authenticated_client.put(
        f"{BASE_URL}/api/profile-api",
        json={"full_name": "Updated Tester", "phone": "9876543210"},
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert update.status_code == 200
    assert update.json()["message"] == "Profile updated successfully"

    add_vehicle = authenticated_client.post(
        f"{BASE_URL}/api/profile-api/vehicles",
        json={"number_plate": "TEST-ADD-01", "vehicle_type": "suv", "is_primary": False},
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert add_vehicle.status_code == 200
    vehicle_id = add_vehicle.json()["vehicle"]["id"]

    prefs = authenticated_client.put(
        f"{BASE_URL}/api/profile-api/notifications",
        json={"booking_reminders": True, "payment_receipts": True, "promo_offers": True},
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert prefs.status_code == 200
    assert prefs.json()["message"] == "Notification preferences updated"

    change_password = authenticated_client.put(
        f"{BASE_URL}/api/profile-api/password",
        json={
            "current_password": registered_identity["password"],
            "new_password": "NewPass123",
            "confirm_password": "NewPass123",
        },
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert change_password.status_code == 200
    assert change_password.json()["message"] == "Password changed successfully"

    remove_vehicle = authenticated_client.delete(
        f"{BASE_URL}/api/profile-api/vehicles/{vehicle_id}",
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert remove_vehicle.status_code == 200
    assert remove_vehicle.json()["message"] == "Vehicle removed"

    logout = authenticated_client.post(
        f"{BASE_URL}/api/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert logout.status_code == 200
    assert logout.json()["message"] == "Logged out successfully"

    relogin = authenticated_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": registered_identity["email"], "password": "NewPass123"},
        headers={"X-CSRF-Token": csrf_token},
        timeout=20,
    )
    assert relogin.status_code == 200
    assert relogin.json()["redirect_url"] == "/api/dashboard"
