# CoWork — Coworking Space Booking API

Multi-tenant REST API for booking rooms in coworking spaces. Built with Python 3.11, FastAPI, SQLAlchemy, SQLite. Single container, no external services.

---

## Quick Start

```bash
docker compose up --build
```

Then open `http://localhost:8000/docs` for Swagger UI.

Or run locally:

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Database auto-creates on first startup.

---

## Testing

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

**37/37 tests passing.**

---

## Bug Fixes (17 total)

| Area | Fix |
|------|-----|
| Overlap logic | Back-to-back bookings now allowed |
| Start time | Must be strictly in future (no grace window) |
| Min duration | 1-hour minimum now enforced |
| Refund tiers | <24h = 0% (was 50%) |
| Admin view | Admins see all org bookings |
| Ordering | Ascending start_time (was descending) |
| Token lifetime | 900 seconds (was 900 minutes) |
| Token revocation | Now checks `jti` instead of `sub` |
| UTC conversion | Offset datetimes properly convert to UTC |
| Race conditions | Added locks in reference, ratelimit, stats services |
| Deadlock | Fixed lock ordering in notifications |
| Refund calc | Consistent rounding between cancel and refund log |
| Code cleanup | Removed planted `time.sleep()` delays |

---

## API Endpoints

| Method | Path | Auth | What it does |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Create org + admin, or join as member |
| POST | `/auth/login` | No | Get tokens |
| POST | `/auth/refresh` | No | Rotate tokens |
| POST | `/auth/logout` | Yes | Invalidate token |
| GET | `/rooms` | Yes | List rooms |
| POST | `/rooms` | Admin | Create room |
| GET | `/rooms/{id}/availability` | Yes | Busy slots for a date |
| GET | `/rooms/{id}/stats` | Yes | Booking count + revenue |
| POST | `/bookings` | Yes | Create booking |
| GET | `/bookings` | Yes | List your bookings |
| GET | `/bookings/{id}` | Yes | Booking details |
| POST | `/bookings/{id}/cancel` | Yes | Cancel + refund |
| GET | `/admin/usage-report` | Admin | Room usage for date range |
| GET | `/admin/export` | Admin | CSV export |
| GET | `/health` | No | Health check |

---

## Project Structure

```
app/
├── main.py              # Entrypoint
├── auth.py              # JWT + password
├── config.py            # Settings
├── database.py          # DB engine
├── errors.py            # Error handling
├── models.py            # DB models
├── schemas.py           # Request models
├── serializers.py       # Response formatting
├── timeutils.py         # Datetime helpers
├── cache.py             # In-memory cache
├── routers/             # API routes
│   ├── auth.py
│   ├── bookings.py
│   ├── rooms.py
│   ├── admin.py
│   └── health.py
└── services/            # Business logic
    ├── reference.py
    ├── ratelimit.py
    ├── stats.py
    ├── refunds.py
    ├── notifications.py
    └── export.py
tests/
├── test_smoke.py
└── test_comprehensive.py
Dockerfile
docker-compose.yml
requirements.txt
```
