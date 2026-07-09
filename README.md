# CoWork — Coworking Space Booking API

## Project Overview

CoWork is a REST API for managing bookable rooms inside a coworking space across multiple tenant organizations. Each organization has its own rooms, staff (admins), and members. Members book rooms for time slots; admins manage rooms and pull reports.

Built with **Python 3.11, FastAPI, SQLAlchemy, and SQLite** — single container, no external services. JWT auth (HS256) with access/refresh token rotation.

## Key Technical Achievements

**17 bugs identified and fixed** to align the implementation with the specification:

- **Race condition fixes**: Added thread-safe locking (`threading.Lock()`) in reference code generation, rate limiting, and booking stats tracking to guarantee correctness under concurrent requests. Inlined the booking overlap check into a single SQL query to eliminate the TOCTOU window.
- **Admin/member logic**: Admins now see all bookings within their org (previously only their own). Members continue to see only their own bookings. Fixed the listing ordering to ascending `start_time` per spec.
- **Timezone accuracy**: Input datetimes with UTC offsets are now properly converted to UTC before storage (previously the offset was silently stripped). All response datetimes carry an explicit UTC designator.
- **Business rule corrections**: Back-to-back bookings allowed (overlap used `<` not `<=`); start time must be strictly in the future (no 5-minute grace window); minimum 1-hour duration enforced; <24h cancellation correctly returns 0% refund (was 50%).
- **Auth fixes**: Access token lifetime corrected to 900 seconds (was 900 minutes). Token revocation now checks `jti` instead of `sub`, making logout actually effective.
- **Cleanup**: Removed planted `time.sleep()` delays and dead code that caused race conditions and performance degradation.

## Instructions for Running the Project

### Using Docker (recommended)

```bash
docker compose up --build
```

The API listens on `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.

### Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The database is created automatically on first startup — no manual provisioning or seed scripts needed.

## Testing

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

**37/37 tests passing**, covering:

- Registration, login, logout, token refresh
- Room creation and listing (admin vs member)
- Booking creation (overlap, quota, duration, price)
- Back-to-back booking allowance
- Cancellation refund tiers (100%, 50%, 0%)
- Admin visibility of all org bookings
- Pagination and ordering
- Multi-tenant isolation
- Rate limiting
- Reference code uniqueness
- UTC timezone conversion
- Room stats and availability
- Usage report and CSV export
