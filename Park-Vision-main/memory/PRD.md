# PRD — Park Vision (Real-Time Smart Parking Detection System)

## Original Problem Statement
Build a complete, dynamic, responsive multi-page web application called **Park Vision** with FastAPI backend, Jinja2 + vanilla JS frontend, SQLite + SQLAlchemy data layer, JWT auth, live slot updates via WebSockets, booking, mock payments, profile management, premium futuristic dark-tech design, and production-like UX quality.

## Architecture Decisions
- **Backend**: FastAPI app modularized into routers (`auth`, `slots`, `bookings`, `payments`, `profile`, `pages`) and services (`slot_service`, `booking_service`, `payment_service`).
- **Database**: SQLite + SQLAlchemy models (`User`, `Vehicle`, `ParkingSlot`, `Booking`, `Payment`, `NotificationPreference`, `VehicleHistory`).
- **Frontend**: Server-rendered Jinja2 templates + handcrafted CSS + vanilla JS modules.
- **Auth/Security**: JWT in HttpOnly cookie, bcrypt hashing, CSRF token cookie + `X-CSRF-Token` enforcement on mutating routes, slowapi rate limiting on auth routes.
- **Realtime**: WebSocket `/api/ws/slots` + fallback polling and background slot simulation.

## User Personas
- **Daily commuter**: needs quick slot discovery and instant booking.
- **Frequent driver/family user**: manages multiple vehicles and booking history.
- **Parking operator/admin observer**: monitors occupancy trends and live slot changes.

## Core Requirements (Static)
- Register/login/logout/me auth system.
- Live slot listing with zone/floor filters and real-time updates.
- Booking create, list, cancel flow with pricing + GST calculation.
- Payment initiate/verify mock flow with success/failure handling and receipt.
- Pages: landing, auth, dashboard, payment, success, bookings, profile.
- Cyber-futuristic UI with responsiveness, animations, and strong visual hierarchy.

## What’s Implemented
### 2026-03-12
- Implemented full FastAPI backend modules and SQLAlchemy models with startup DB init + slot seeding.
- Added auth (register/login/logout/me), CSRF middleware/dependency checks, and rate limiting.
- Implemented slot APIs, live counts, WebSocket broadcast manager, and periodic slot simulation.
- Implemented booking service/router including conflict checks, pricing math, and slot state transitions.
- Implemented payments (promo, initiate, verify, receipt-data) plus success/update side effects.
- Implemented profile APIs for user update, vehicles CRUD, notification preferences, password update, and account deletion.
- Built complete Jinja pages: landing, login/register, dashboard + booking modal, payment, success, receipt, bookings, profile.
- Built custom CSS system (`base.css`, `components.css`, `pages.css`) and JS modules (`main.js`, `websocket.js`, `parking-grid.js`, `payment.js`).
- Added frontend React root redirect to `/api/` so preview always launches Park Vision app.
- Resolved regressions found in testing:
  - Static asset URL host/mixed-content issue.
  - `/api/profile` page vs JSON route conflict (moved JSON to `/api/profile-api`).
  - `/api/slots/live-counts` path collision order fix.
  - Font Awesome CDN SRI mismatch causing icon rendering failure.
- Added **vehicle history persistence**:
  - New `vehicle_history` table to store vehicle lifecycle + booking/payment events.
  - Events now logged for registration, vehicle add, booking creation, booking cancellation, and payment success/failure.
  - New API `GET /api/profile-api/vehicles/{vehicle_id}/history` and profile UI “View History” panel.
  - Prevented deletion of vehicles that already have booking/history records to preserve audit continuity.
- Applied full **humanized UI redesign** (all pages) based on user references:
  - Shifted from futuristic dark style to soft cream/white muted-blue aesthetic.
  - Updated typography to `Poppins` + `Source Sans 3`.
  - Added flat vector-style illustrations on landing and auth pages.
  - Restyled buttons, cards, forms, tabs, dashboard grid, and profile/bookings/payment surfaces to look more organic and less AI-generated while preserving all existing content and flows.

## Prioritized Backlog
### P0 (Must)
- Add environment-aware secure cookie flags (`secure=True` in HTTPS deployments).
- Add complete automated E2E suite for dashboard booking and profile actions in CI.

### P1 (Should)
- Add real forgot-password flow (email OTP/reset).
- Improve payment failure UX with explicit retry timer for reserved-slot release window.
- Enhance dashboard with floor tabs and richer slot animation deltas.

### P2 (Could)
- Add operator analytics page (heatmaps, trend charts).
- Add multilingual labels and regional format settings.
- Add push notifications / reminder scheduling.

## Next Tasks List
1. Harden production security flags and cookie settings by environment.
2. Add automated browser tests for all critical routes and form validations.
3. Implement true forgot-password and account recovery flow.
4. Introduce analytics module for parking utilization insights.
