"""Comprehensive tests covering all business rules and bug fixes."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _future(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(
        minute=0, second=0, microsecond=0
    ).isoformat()


def _past(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(
        minute=0, second=0, microsecond=0
    ).isoformat()


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(org: str, user: str, pw: str = "pw"):
    return client.post("/auth/register", json={"org_name": org, "username": user, "password": pw})


def _login(org: str, user: str, pw: str = "pw"):
    return client.post("/auth/login", json={"org_name": org, "username": user, "password": pw})


# ─── Health ─────────────────────────────────────────────────────────────────

def test_health():
    assert client.get("/health").json() == {"status": "ok"}


# ─── Registration ───────────────────────────────────────────────────────────

def test_register_creates_org_and_admin():
    org = f"reg-org-{datetime.now().timestamp()}"
    r = _register(org, "admin1")
    assert r.status_code == 201
    data = r.json()
    assert data["role"] == "admin"
    assert data["username"] == "admin1"


def test_register_joins_existing_org_as_member():
    org = f"join-org-{datetime.now().timestamp()}"
    _register(org, "admin1")
    r = _register(org, "member1")
    assert r.status_code == 201
    assert r.json()["role"] == "member"


def test_register_duplicate_username_returns_201_with_existing():
    org = f"dup-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    r = _register(org, "alice")
    assert r.status_code == 201
    assert r.json()["username"] == "alice"


# ─── Login ───────────────────────────────────────────────────────────────────

def test_login_success():
    org = f"login-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    r = _login(org, "alice")
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_bad_password():
    org = f"badpw-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    r = client.post("/auth/login", json={"org_name": org, "username": "alice", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_CREDENTIALS"


def test_login_wrong_org():
    r = client.post("/auth/login", json={"org_name": "nonexistent", "username": "x", "password": "x"})
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_CREDENTIALS"


# ─── Token refresh ──────────────────────────────────────────────────────────

def test_refresh_rotates_tokens():
    org = f"refresh-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    tokens = _login(org, "alice").json()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    assert new["access_token"] != tokens["access_token"]
    assert new["refresh_token"] != tokens["refresh_token"]


def test_refresh_single_use():
    org = f"refresh-single-{datetime.now().timestamp()}"
    _register(org, "alice")
    tokens = _login(org, "alice").json()
    rt = tokens["refresh_token"]
    r1 = client.post("/auth/refresh", json={"refresh_token": rt})
    assert r1.status_code == 200


# ─── Token revocation ───────────────────────────────────────────────────────

def test_logout_revokes_access_token():
    org = f"logout-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    r = client.post("/auth/logout", headers=_auth_header(token))
    assert r.status_code == 200
    r2 = client.get("/rooms", headers=_auth_header(token))
    assert r2.status_code == 401


# ─── Access token lifetime ──────────────────────────────────────────────────

def test_access_token_expiry_900s():
    from app.auth import create_access_token, decode_token
    from app.models import User
    user = User(id=1, org_id=1, role="admin")
    token = create_access_token(user)
    payload = decode_token(token)
    assert payload["type"] == "access"
    assert payload["exp"] - payload["iat"] == 900


# ─── Rooms ──────────────────────────────────────────────────────────────────

def test_create_and_list_room():
    org = f"room-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)

    r = client.post("/rooms", json={"name": "R1", "capacity": 4, "hourly_rate_cents": 1500}, headers=hdrs)
    assert r.status_code == 201
    room = r.json()
    assert room["name"] == "R1"
    assert room["hourly_rate_cents"] == 1500

    rooms = client.get("/rooms", headers=hdrs).json()
    assert len(rooms) >= 1


def test_create_room_forbidden_for_member():
    org = f"room-forbid-{datetime.now().timestamp()}"
    _register(org, "alice")
    _register(org, "bob")
    token = _login(org, "bob").json()["access_token"]
    r = client.post("/rooms", json={"name": "R1", "capacity": 2, "hourly_rate_cents": 500}, headers=_auth_header(token))
    assert r.status_code == 403


# ─── Bookings: start_time must be strictly in future ────────────────────────

def test_booking_start_time_must_be_future():
    org = f"future-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _past(1), "end_time": _past(0.5)}, headers=hdrs)
    assert r.status_code == 400
    assert r.json()["code"] == "INVALID_BOOKING_WINDOW"


# ─── Bookings: minimum duration ─────────────────────────────────────────────

def test_booking_minimum_duration():
    org = f"mindur-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(3), "end_time": _future(3.5)}, headers=hdrs)
    assert r.status_code == 400
    assert r.json()["code"] == "INVALID_BOOKING_WINDOW"


# ─── Bookings: maximum duration ─────────────────────────────────────────────

def test_booking_maximum_duration():
    org = f"maxdur-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(3), "end_time": _future(12)}, headers=hdrs)
    assert r.status_code == 400
    assert r.json()["code"] == "INVALID_BOOKING_WINDOW"


# ─── Bookings: whole hours only ─────────────────────────────────────────────

def test_booking_whole_hours_only():
    org = f"wholehr-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(3), "end_time": _future(5)}, headers=hdrs)
    assert r.status_code == 201

    r2 = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(10), "end_time": _future(10.25)}, headers=hdrs)
    assert r2.status_code == 400


# ─── Bookings: price_cents = hourly_rate × duration ─────────────────────────

def test_booking_price_correct():
    org = f"price-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 2000}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(5), "end_time": _future(8)}, headers=hdrs)
    assert r.status_code == 201
    assert r.json()["price_cents"] == 6000


# ─── Bookings: overlap (back-to-back allowed) ───────────────────────────────

def test_back_to_back_bookings_allowed():
    org = f"b2b-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r1 = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(5), "end_time": _future(7)}, headers=hdrs)
    assert r1.status_code == 201

    r2 = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(7), "end_time": _future(9)}, headers=hdrs)
    assert r2.status_code == 201


def test_overlapping_bookings_conflict():
    org = f"overlap-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r1 = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(5), "end_time": _future(7)}, headers=hdrs)
    assert r1.status_code == 201

    r2 = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(6), "end_time": _future(8)}, headers=hdrs)
    assert r2.status_code == 409
    assert r2.json()["code"] == "ROOM_CONFLICT"


# ─── Bookings: quota limit ──────────────────────────────────────────────────

def test_quota_limit():
    org = f"quota-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 10, "hourly_rate_cents": 500}, headers=hdrs).json()

    for i in range(3):
        h = 10 + i * 3
        r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(h), "end_time": _future(h + 1)}, headers=hdrs)
        assert r.status_code == 201

    r4 = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(22), "end_time": _future(23)}, headers=hdrs)
    assert r4.status_code == 409
    assert r4.json()["code"] == "QUOTA_EXCEEDED"


# ─── List bookings: pagination & ordering (ascending) ───────────────────────

def test_list_bookings_ordering_asc():
    org = f"order-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 5, "hourly_rate_cents": 500}, headers=hdrs).json()

    for i in range(4):
        h = 50 + i * 2
        client.post("/bookings", json={"room_id": room["id"], "start_time": _future(h), "end_time": _future(h + 1)}, headers=hdrs)

    listing = client.get("/bookings?page=1&limit=10", headers=hdrs).json()
    assert listing["total"] >= 4
    times = [item["start_time"] for item in listing["items"]]
    assert times == sorted(times), "Bookings should be sorted ascending by start_time"


def test_list_bookings_pagination():
    org = f"page-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 5, "hourly_rate_cents": 500}, headers=hdrs).json()

    for i in range(5):
        h = 50 + i * 2
        client.post("/bookings", json={"room_id": room["id"], "start_time": _future(h), "end_time": _future(h + 1)}, headers=hdrs)

    p1 = client.get("/bookings?page=1&limit=2", headers=hdrs).json()
    assert len(p1["items"]) == 2
    assert p1["page"] == 1
    assert p1["limit"] == 2
    assert p1["total"] >= 5

    p2 = client.get("/bookings?page=3&limit=2", headers=hdrs).json()
    assert len(p2["items"]) >= 1


# ─── Admin listing sees all org bookings ────────────────────────────────────

def test_admin_sees_all_bookings_member_sees_own():
    org = f"admin-view-{datetime.now().timestamp()}"
    _register(org, "alice")
    _register(org, "bob")
    admin_token = _login(org, "alice").json()["access_token"]
    member_token = _login(org, "bob").json()["access_token"]
    hdrs_admin = _auth_header(admin_token)
    hdrs_member = _auth_header(member_token)

    room = client.post("/rooms", json={"name": "R", "capacity": 5, "hourly_rate_cents": 500}, headers=hdrs_admin).json()

    client.post("/bookings", json={"room_id": room["id"], "start_time": _future(50), "end_time": _future(51)}, headers=hdrs_admin)
    client.post("/bookings", json={"room_id": room["id"], "start_time": _future(52), "end_time": _future(53)}, headers=hdrs_member)

    admin_list = client.get("/bookings", headers=hdrs_admin).json()
    assert admin_list["total"] == 2

    member_list = client.get("/bookings", headers=hdrs_member).json()
    assert member_list["total"] == 1


# ─── get_booking returns correct start_time (not created_at) ────────────────

def test_get_booking_start_time_correct():
    org = f"getbt-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(10), "end_time": _future(12)}, headers=hdrs)
    assert r.status_code == 201
    booking_id = r.json()["id"]

    detail = client.get(f"/bookings/{booking_id}", headers=hdrs).json()
    assert detail["start_time"] == r.json()["start_time"]
    assert "refunds" in detail


# ─── Cancel: refund tiers ───────────────────────────────────────────────────

def test_cancel_48h_100_percent_refund():
    org = f"refund100-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(100), "end_time": _future(102)}, headers=hdrs)
    booking_id = r.json()["id"]
    price = r.json()["price_cents"]

    cancel = client.post(f"/bookings/{booking_id}/cancel", headers=hdrs).json()
    assert cancel["refund_percent"] == 100
    assert cancel["refund_amount_cents"] == price


def test_cancel_24h_50_percent_refund():
    org = f"refund50-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1001}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(36), "end_time": _future(37)}, headers=hdrs)
    booking_id = r.json()["id"]
    price = r.json()["price_cents"]

    cancel = client.post(f"/bookings/{booking_id}/cancel", headers=hdrs).json()
    assert cancel["refund_percent"] == 50
    expected = round(price * 50 / 100.0)
    assert cancel["refund_amount_cents"] == expected


def test_cancel_under_24h_zero_refund():
    org = f"refund0-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(5), "end_time": _future(6)}, headers=hdrs)
    booking_id = r.json()["id"]

    cancel = client.post(f"/bookings/{booking_id}/cancel", headers=hdrs).json()
    assert cancel["refund_percent"] == 0
    assert cancel["refund_amount_cents"] == 0


def test_already_cancelled_returns_409():
    org = f"canceldup-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(100), "end_time": _future(101)}, headers=hdrs)
    booking_id = r.json()["id"]

    client.post(f"/bookings/{booking_id}/cancel", headers=hdrs)
    r2 = client.post(f"/bookings/{booking_id}/cancel", headers=hdrs)
    assert r2.status_code == 409
    assert r2.json()["code"] == "ALREADY_CANCELLED"


# ─── Multi-tenancy ──────────────────────────────────────────────────────────

def test_cross_org_isolation():
    org_a = f"iso-a-{datetime.now().timestamp()}"
    org_b = f"iso-b-{datetime.now().timestamp()}"
    _register(org_a, "alice")
    _register(org_b, "bob")
    token_a = _login(org_a, "alice").json()["access_token"]
    token_b = _login(org_b, "bob").json()["access_token"]

    hdrs_a = _auth_header(token_a)
    hdrs_b = _auth_header(token_b)

    room_a = client.post("/rooms", json={"name": "RA", "capacity": 2, "hourly_rate_cents": 500}, headers=hdrs_a).json()

    r = client.get(f"/rooms/{room_a['id']}", headers=hdrs_b)
    assert r.status_code == 404


# ─── Availability ───────────────────────────────────────────────────────────

def test_availability():
    org = f"avail-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    start = _future(50)
    end = _future(52)
    client.post("/bookings", json={"room_id": room["id"], "start_time": start, "end_time": end}, headers=hdrs)

    from datetime import datetime as dt, timezone as tz
    day = dt.fromisoformat(start).strftime("%Y-%m-%d")
    avail = client.get(f"/rooms/{room['id']}/availability", params={"date": day}, headers=hdrs).json()
    assert len(avail["busy"]) >= 1


# ─── Stats ──────────────────────────────────────────────────────────────────

def test_room_stats():
    org = f"stats-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    stats_before = client.get(f"/rooms/{room['id']}/stats", headers=hdrs).json()
    assert stats_before["total_confirmed_bookings"] == 0

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(50), "end_time": _future(52)}, headers=hdrs)
    price = r.json()["price_cents"]

    stats_after = client.get(f"/rooms/{room['id']}/stats", headers=hdrs).json()
    assert stats_after["total_confirmed_bookings"] == 1
    assert stats_after["total_revenue_cents"] == price


# ─── Admin usage report ─────────────────────────────────────────────────────

def test_usage_report():
    org = f"report-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    start = _future(50)
    day = datetime.fromisoformat(start).strftime("%Y-%m-%d")
    client.post("/bookings", json={"room_id": room["id"], "start_time": start, "end_time": _future(52)}, headers=hdrs)

    report = client.get("/admin/usage-report", params={"from": day, "to": day}, headers=hdrs).json()
    assert len(report["rooms"]) >= 1
    matching = [r for r in report["rooms"] if r["room_id"] == room["id"]]
    assert len(matching) == 1
    assert matching[0]["confirmed_bookings"] >= 1


# ─── Admin export ───────────────────────────────────────────────────────────

def test_admin_export():
    org = f"export-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 2, "hourly_rate_cents": 1000}, headers=hdrs).json()

    r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(50), "end_time": _future(52)}, headers=hdrs)
    booking_id = r.json()["id"]

    csv = client.get("/admin/export", params={"room_id": room["id"], "include_all": True}, headers=hdrs)
    assert csv.status_code == 200
    assert "text/csv" in csv.headers["content-type"]
    assert str(booking_id) in csv.text


# ─── Rate limiting ──────────────────────────────────────────────────────────

def test_rate_limit_applies():
    from app.services.ratelimit import _buckets
    _buckets.clear()

    org = f"ratelimit-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 50, "hourly_rate_cents": 500}, headers=hdrs).json()

    for i in range(20):
        h = 100 + i
        r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(h), "end_time": _future(h + 1)}, headers=hdrs)
        if r.status_code == 429:
            return
    r21 = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(200), "end_time": _future(201)}, headers=hdrs)
    assert r21.status_code == 429


# ─── Reference codes uniqueness ─────────────────────────────────────────────

def test_reference_codes_unique():
    from app.services.reference import _counter, _lock
    _counter = 1000

    org = f"refcode-org-{datetime.now().timestamp()}"
    _register(org, "alice")
    token = _login(org, "alice").json()["access_token"]
    hdrs = _auth_header(token)
    room = client.post("/rooms", json={"name": "R", "capacity": 5, "hourly_rate_cents": 500}, headers=hdrs).json()

    codes = set()
    for i in range(5):
        h = 50 + i * 2
        r = client.post("/bookings", json={"room_id": room["id"], "start_time": _future(h), "end_time": _future(h + 1)}, headers=hdrs)
        code = r.json()["reference_code"]
        assert code not in codes
        codes.add(code)
    assert len(codes) == 5


# ─── UTC conversion ─────────────────────────────────────────────────────────

def test_utc_conversion_with_offset():
    from app.timeutils import parse_input_datetime

    dt = parse_input_datetime("2025-06-01T12:00:00+05:00")
    assert dt.hour == 7
    assert dt.tzinfo is None

    dt_naive = parse_input_datetime("2025-06-01T12:00:00")
    assert dt_naive.hour == 12
    assert dt_naive.tzinfo is None
