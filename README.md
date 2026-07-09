<div align="center">
  <h1>CoWork</h1>
  <p><strong>Coworking Space Booking API</strong></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11-blue?logo=python" alt="Python 3.11">
    <img src="https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi" alt="FastAPI">
    <img src="https://img.shields.io/badge/SQLAlchemy-2.0-red" alt="SQLAlchemy">
    <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite" alt="SQLite">
    <img src="https://img.shields.io/badge/JWT-HS256-000000?logo=jsonwebtokens" alt="JWT HS256">
    <img src="https://img.shields.io/badge/tests-37%2F37-brightgreen" alt="37/37 tests passing">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  </p>
</div>

---

## Overview

CoWork is a **multi-tenant REST API** for booking rooms in coworking spaces. Each organization gets its own rooms, admins, and members. Members book time slots, admins manage rooms and generate reports.

Built as a **single container** — no external databases or services required.

---

## Key Technical Achievements

**17 bugs identified and fixed** to align the implementation with specification:

- **Race condition fixes** — Added `threading.Lock()` in reference code generation, rate limiting, and booking stats to guarantee correctness under concurrent requests. Inlined the overlap check into a single SQL query to eliminate the TOCTOU window.

- **Admin/member logic** — Admins now see all bookings within their org. Members see only their own. Fixed listing ordering to ascending `start_time`.

- **Timezone accuracy** — Input datetimes with UTC offsets are properly converted to UTC before storage. All responses carry an explicit UTC designator.

- **Business rule corrections** — Back-to-back bookings allowed (overlap uses `<` not `<=`); start time strictly in the future (no 5-minute grace window); minimum 1-hour duration enforced; under-24h cancellation returns 0% refund.

- **Auth fixes** — Access token lifetime corrected to 900 seconds (was 900 minutes). Token revocation now checks `jti` instead of `sub`.

- **Cleanup** — Removed planted `time.sleep()` delays and dead code causing race conditions and performance degradation.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11 |
| Framework | FastAPI 0.111 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite |
| Auth | JWT (HS256) |
| Server | Uvicorn |

---

## Quick Start

### Using Docker (recommended)

```bash
docker compose up --build
```

App → `http://localhost:8000`  
Docs → `http://localhost:8000/docs`

### Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> The database is created automatically on first startup — no manual setup needed.

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Register org admin or join as member |
| POST | `/auth/login` | No | Get access + refresh tokens |
| POST | `/auth/refresh` | No | Rotate tokens |
| POST | `/auth/logout` | Yes | Invalidate access token |
| GET | `/rooms` | Yes | List rooms in your org |
| POST | `/rooms` | Admin | Create a room |
| GET | `/rooms/{id}/availability` | Yes | Busy intervals for a date |
| GET | `/rooms/{id}/stats` | Yes | Live booking count & revenue |
| POST | `/bookings` | Yes | Create a booking |
| GET | `/bookings` | Yes | Your bookings (paginated) |
| GET | `/bookings/{id}` | Yes | Single booking with refunds |
| POST | `/bookings/{id}/cancel` | Yes | Cancel + refund |
| GET | `/admin/usage-report` | Admin | Per-room usage for date range |
| GET | `/admin/export` | Admin | Bookings CSV export |
| GET | `/health` | No | `{"status": "ok"}` |

---

## Business Rules

- **Datetimes** — ISO 8601, always UTC. Input with offset is converted; naive treated as UTC.
- **Pricing** — `price_cents = hourly_rate_cents × whole_hours`. Duration: 1–8 hours.
- **Double-booking** — Rejected with `409 ROOM_CONFLICT`. Back-to-back allowed.
- **Quota** — Max 3 confirmed bookings per user within the next 24 hours (`409 QUOTA_EXCEEDED`).
- **Rate limit** — 20 requests per 60 seconds per user on `POST /bookings` (`429 RATE_LIMITED`).
- **Refunds** — ≥48h → 100%; 24–48h → 50%; <24h → 0%. Rounded to nearest cent, half up.
- **Multi-tenancy** — Users only see their own org's data. Cross-org IDs → `404`.
- **Token lifetime** — Access: 900s. Refresh: 7 days. Logout revokes immediately.

---

## Testing

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

**37/37 tests passing** covering registration, login, rooms, bookings, overlap, quota, cancellation refunds, admin visibility, pagination, rate limiting, UTC conversion, stats, and export.

---

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI entrypoint
│   ├── auth.py              # JWT + password hashing
│   ├── config.py            # Environment config
│   ├── database.py          # SQLAlchemy engine
│   ├── errors.py            # AppError handler
│   ├── models.py            # ORM models
│   ├── schemas.py           # Pydantic request models
│   ├── serializers.py       # Response serializers
│   ├── timeutils.py         # UTC datetime helpers
│   ├── cache.py             # In-memory caching
│   ├── routers/
│   │   ├── auth.py          # Register/login/refresh/logout
│   │   ├── bookings.py      # Create/list/cancel bookings
│   │   ├── rooms.py         # Room CRUD + availability
│   │   ├── admin.py         # Reports + export
│   │   └── health.py        # Liveness check
│   └── services/
│       ├── reference.py     # Unique reference codes
│       ├── ratelimit.py     # Rolling-window rate limiter
│       ├── stats.py         # Live per-room stats
│       ├── refunds.py       # Refund ledger
│       ├── notifications.py # Simulated email/audit
│       └── export.py        # CSV generation
├── tests/
│   ├── test_smoke.py        # Happy-path smoke test
│   └── test_comprehensive.py # 37 full-coverage tests
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

<div align="center">
  <p>Built for <strong>ICT Fest Hackathon</strong></p>
</div>
