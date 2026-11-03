import asyncio
import json
import unittest
from unittest.mock import patch
from datetime import date, datetime, timedelta
from urllib.parse import urlparse
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
import app.models as models
from app.models import Role, User, Destination, Vehicle, Booking
from app.security import hash_password, create_token
from app.main import app
from app.core.rate_limit import limiter

class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.security_event_patcher = patch("app.main.persist_security_event")
        cls.security_event_patcher.start()
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        cls.Session = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        def override_get_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        # Seed an admin user
        db = cls.Session()
        admin = User(
            id="admin-1",
            name="Platform Admin",
            email="admin@elsewhere.com",
            password_hash=hash_password("AdminPass123!"),
            role=Role.admin,
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.close()

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=cls.engine)
        app.dependency_overrides.clear()
        cls.security_event_patcher.stop()

    def setUp(self):
        # Rate-limit state is process-global; reset it so each test starts clean.
        limiter._events.clear()

    def request(self, method: str, path: str, json_data=None, headers=None):
        return asyncio.run(self._asgi_request(method, path, json_data, headers))

    async def _asgi_request(self, method: str, path: str, json_data=None, headers=None):
        parsed = urlparse(path)
        path_only = parsed.path
        query_string = parsed.query.encode("utf-8")
        header_list = [(b"host", b"testserver")]
        if headers:
            for k, v in headers.items():
                header_list.append((k.lower().encode("utf-8"), v.encode("utf-8")))
        body_bytes = b""
        if json_data is not None:
            body_bytes = json.dumps(json_data).encode("utf-8")
            header_list.append((b"content-type", b"application/json"))
        header_list.append((b"content-length", str(len(body_bytes)).encode("utf-8")))

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": method.upper(),
            "path": path_only,
            "raw_path": path_only.encode("utf-8"),
            "query_string": query_string,
            "headers": header_list,
            "server": ("testserver", 80),
        }
        status = None
        response_body = []

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        async def send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body":
                response_body.append(message.get("body", b""))

        await app(scope, receive, send)
        raw = b"".join(response_body).decode("utf-8")
        try:
            res = json.loads(raw)
        except Exception:
            res = raw
        return status, res

    def test_01_health_endpoint(self):
        status, body = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("service"), "elsewhere-api")

    def test_02_auth_register_and_login_flow(self):
        # Register a traveller
        reg_payload = {
            "name": "Jane Traveller",
            "email": "jane@example.com",
            "password": "Password123!",
            "phone": "+919876543210",
            "role": "customer"
        }
        status, body = self.request("POST", "/api/v1/auth/register", reg_payload)
        self.assertEqual(status, 201)
        self.assertIn("access_token", body)
        token = body["access_token"]
        self.assertEqual(body["user"]["email"], "jane@example.com")
        self.assertEqual(body["user"]["role"], "customer")

        # Duplicate email
        status, body = self.request("POST", "/api/v1/auth/register", reg_payload)
        self.assertEqual(status, 409)

        # Invalid role
        invalid_role_payload = {**reg_payload, "email": "other@example.com", "role": "superman"}
        status, _ = self.request("POST", "/api/v1/auth/register", invalid_role_payload)
        self.assertEqual(status, 400)

        # Login success
        status, body = self.request("POST", "/api/v1/auth/login", {
            "email": "jane@example.com",
            "password": "Password123!"
        })
        self.assertEqual(status, 200)
        self.assertIn("access_token", body)

        # Login incorrect password
        status, _ = self.request("POST", "/api/v1/auth/login", {
            "email": "jane@example.com",
            "password": "WrongPassword!"
        })
        self.assertEqual(status, 401)

        # Me endpoint with valid token
        status, me = self.request("GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(status, 200)
        self.assertEqual(me["name"], "Jane Traveller")

        # Me endpoint without token
        status, _ = self.request("GET", "/api/v1/auth/me")
        self.assertEqual(status, 401)

    def test_03_destinations_api(self):
        # Login admin to seed a destination
        _, login_body = self.request("POST", "/api/v1/auth/login", {
            "email": "admin@elsewhere.com",
            "password": "AdminPass123!"
        })
        admin_token = login_body["access_token"]

        # Admin adds destination
        dest_payload = {
            "name": "Ooty",
            "region": "Tamil Nadu, India",
            "category": "Nature",
            "description": "Queen of Nilgiris tea plantations.",
            "is_published": True
        }
        status, body = self.request(
            "POST",
            "/api/v1/destinations",
            dest_payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        self.assertEqual(status, 201)
        dest_id = body["id"]

        # List destinations
        status, list_body = self.request("GET", "/api/v1/destinations")
        self.assertEqual(status, 200)
        self.assertIsInstance(list_body, list)
        self.assertTrue(any(d["id"] == dest_id for d in list_body))

        # Query filter
        status, q_body = self.request("GET", "/api/v1/destinations?q=Ooty")
        self.assertEqual(status, 200)
        self.assertEqual(len(q_body), 1)
        self.assertEqual(q_body[0]["name"], "Ooty")

        # Destination detail
        status, detail = self.request("GET", f"/api/v1/destinations/{dest_id}")
        self.assertEqual(status, 200)
        self.assertEqual(detail["name"], "Ooty")

        # Non-existent destination
        status, _ = self.request("GET", "/api/v1/destinations/non-existent-id")
        self.assertEqual(status, 404)

    def test_04_vehicles_and_bookings_flow(self):
        # 1. Register vehicle owner
        status, owner_res = self.request("POST", "/api/v1/auth/register", {
            "name": "Ravi Owner",
            "email": "ravi@rides.com",
            "password": "OwnerPassword123!",
            "role": "owner"
        })
        self.assertEqual(status, 201)
        owner_token = owner_res["access_token"]

        # 2. Owner adds vehicle
        veh_payload = {
            "title": "Mahindra Thar 4x4",
            "category": "SUV",
            "make_model": "Mahindra Thar",
            "seats": 4,
            "price_per_day": 3500.0,
            "city": "Coimbatore",
            "description": "Ready for mountain roads"
        }
        status, veh_body = self.request(
            "POST",
            "/api/v1/vehicles",
            veh_payload,
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        self.assertEqual(status, 201)
        vehicle_id = veh_body["id"]

        # 3. Owner checks my vehicles
        status, my_veh = self.request("GET", "/api/v1/vehicles/mine", headers={"Authorization": f"Bearer {owner_token}"})
        self.assertEqual(status, 200)
        self.assertEqual(len(my_veh), 1)

        # 4. Mark vehicle as verified in DB so it can be booked
        db = self.Session()
        v = db.get(Vehicle, vehicle_id)
        v.verified = True
        db.commit()
        db.close()

        # 5. Customer logs in
        _, cust_res = self.request("POST", "/api/v1/auth/login", {
            "email": "jane@example.com",
            "password": "Password123!"
        })
        cust_token = cust_res["access_token"]

        # 6. Customer creates booking
        start = (date.today() + timedelta(days=10)).isoformat()
        end = (date.today() + timedelta(days=12)).isoformat()  # 3 days inclusive: 10, 11, 12
        booking_payload = {
            "vehicle_id": vehicle_id,
            "start_date": start,
            "end_date": end,
            "pickup_location": "Coimbatore Airport"
        }
        status, _ = self.request("POST", "/api/v1/bookings", booking_payload)
        self.assertEqual(status, 401)
        status, book_body = self.request(
            "POST",
            "/api/v1/bookings",
            booking_payload,
            headers={"Authorization": f"Bearer {cust_token}"}
        )
        self.assertEqual(status, 201)
        self.assertEqual(book_body["status"], "requested")
        self.assertEqual(book_body["total_amount"], 3500.0 * 3)
        booking_id = book_body["id"]

        # Payment intent endpoint must exist, enforce ownership, and never imply
        # that a charge was made when the gateway is not configured.
        payment_path = f"/api/v1/bookings/{booking_id}/payment-intent?idempotency_key=test-payment-{booking_id}"
        status, _ = self.request("POST", payment_path)
        self.assertEqual(status, 401)
        status, payment_error = self.request(
            "POST", payment_path, headers={"Authorization": f"Bearer {cust_token}"}
        )
        self.assertEqual(status, 503)
        self.assertIn("no payment has been attempted", payment_error["detail"])

        # A different authenticated customer cannot create a payment intent.
        _, other_customer = self.request("POST", "/api/v1/auth/register", {
            "name": "Other Traveller", "email": "other-traveller@example.com",
            "password": "OtherPassword123!", "role": "customer"
        })
        status, _ = self.request(
            "POST", payment_path,
            headers={"Authorization": f"Bearer {other_customer['access_token']}"}
        )
        self.assertEqual(status, 404)

        # 7. Overlapping booking rejection
        status, conflict = self.request(
            "POST",
            "/api/v1/bookings",
            booking_payload,
            headers={"Authorization": f"Bearer {cust_token}"}
        )
        self.assertEqual(status, 409)

        # 8. Customer views my bookings
        status, my_bookings = self.request("GET", "/api/v1/bookings/mine", headers={"Authorization": f"Bearer {cust_token}"})
        self.assertEqual(status, 200)
        self.assertTrue(any(b["id"] == booking_id for b in my_bookings))

        # 9. Owner updates booking to confirmed
        status, patch_res = self.request(
            "PATCH",
            f"/api/v1/owner/bookings/{booking_id}",
            {"status": "confirmed"},
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(patch_res["status"], "confirmed")

    def test_05_itineraries_draft_api(self):
        itinerary_payload = {
            "origin": "Bangalore",
            "destination": "Coorg",
            "days": 3,
            "travellers": 2,
            "interests": "Coffee plantations & nature",
            "estimated_budget": 12000
        }
        status, body = self.request("POST", "/api/v1/itineraries", itinerary_payload)
        self.assertEqual(status, 201)
        self.assertEqual(body["title"], "Bangalore to Coorg")
        self.assertEqual(len(body["stops"]), 3)
        self.assertEqual(body["status"], "draft")

    def test_06_budget_estimate_api(self):
        status, body = self.request(
            "GET",
            "/api/v1/budget/estimate?days=3&travellers=2&vehicle_per_day=2000&fuel=600&food_per_person_day=300&stay_per_room_night=2500&rooms=1&contingency=10"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["currency"], "INR")
        self.assertIn("total", body)
        self.assertIn("per_person", body)
        self.assertGreater(body["total"], 0)

    def test_07_admin_overview(self):
        # Non-admin attempt
        _, login_cust = self.request("POST", "/api/v1/auth/login", {
            "email": "jane@example.com",
            "password": "Password123!"
        })
        cust_token = login_cust["access_token"]
        status, _ = self.request("GET", "/api/v1/admin/overview", headers={"Authorization": f"Bearer {cust_token}"})
        self.assertEqual(status, 403)

        # Admin attempt
        _, login_admin = self.request("POST", "/api/v1/auth/login", {
            "email": "admin@elsewhere.com",
            "password": "AdminPass123!"
        })
        admin_token = login_admin["access_token"]
        status, overview = self.request("GET", "/api/v1/admin/overview", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(status, 200)
        self.assertGreaterEqual(overview["users"], 2)
        self.assertGreaterEqual(overview["destinations"], 1)

    def test_08_itinerary_expense_positive_and_negative_amounts(self):
        status, registered = self.request("POST", "/api/v1/auth/register", {
            "name": "Expense Traveller", "email": "expense@example.com",
            "password": "ExpensePassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        headers = {"Authorization": f"Bearer {registered['access_token']}"}

        status, itinerary = self.request("POST", "/api/v1/itineraries", {
            "origin": "Chennai", "destination": "Pondicherry", "days": 2,
            "travellers": 1, "estimated_budget": 12000
        }, headers)
        self.assertEqual(status, 201)
        itinerary_id = itinerary["id"]

        status, body = self.request("POST", f"/api/v1/itineraries/{itinerary_id}/expenses", {
            "date": "2027-02-01", "category": "food", "amount": "125.456",
            "note": "Lunch"
        }, headers)
        self.assertEqual(status, 201)
        self.assertEqual(len(body["expenses"]), 1)
        expense = body["expenses"][0]
        self.assertEqual(expense["amount"], 125.46)
        self.assertEqual(expense["category"], "food")
        status, body = self.request("GET", f"/api/v1/itineraries/{itinerary_id}/expenses", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(body["expenses"][0]["id"], expense["id"])

        for amount in (0, -1, "not-a-number", None):
            with self.subTest(amount=amount):
                status, body = self.request("POST", f"/api/v1/itineraries/{itinerary_id}/expenses", {
                    "amount": amount
                }, headers)
                self.assertEqual(status, 400)
                self.assertEqual(body["detail"], "Enter an amount greater than zero.")

        status, body = self.request("DELETE", f"/api/v1/itineraries/{itinerary_id}/expenses/{expense['id']}",
                                    headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(body["expenses"], [])

        status, body = self.request("DELETE", f"/api/v1/itineraries/{itinerary_id}/expenses/missing",
                                    headers=headers)
        self.assertEqual(status, 404)

    def test_09_itinerary_expenses_require_auth_and_owner(self):
        status, owner = self.request("POST", "/api/v1/auth/register", {
            "name": "Itinerary Owner", "email": "itinerary-owner@example.com",
            "password": "OwnerPassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
        status, itinerary = self.request("POST", "/api/v1/itineraries", {
            "origin": "Chennai", "destination": "Pondicherry", "days": 1,
            "travellers": 1
        }, owner_headers)
        self.assertEqual(status, 201)
        itinerary_id = itinerary["id"]

        status, body = self.request("GET", f"/api/v1/itineraries/{itinerary_id}/expenses")
        self.assertEqual(status, 401)
        status, body = self.request("POST", f"/api/v1/itineraries/{itinerary_id}/expenses", {
            "date": "2027-02-01", "category": "food", "amount": 125, "note": "Lunch"
        })
        self.assertEqual(status, 401)
        status, body = self.request("GET", f"/api/v1/itineraries/{itinerary_id}/expenses",
                                    headers={"Authorization": "Bearer invalid-token"})
        self.assertEqual(status, 401)
        status, body = self.request("POST", f"/api/v1/itineraries/{itinerary_id}/expenses", {
            "amount": 125
        }, {"Authorization": "Bearer invalid-token"})
        self.assertEqual(status, 401)

        status, other = self.request("POST", "/api/v1/auth/register", {
            "name": "Different Traveller", "email": "different-traveller@example.com",
            "password": "DifferentPassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        headers = {"Authorization": f"Bearer {other['access_token']}"}
        status, body = self.request("GET", f"/api/v1/itineraries/{itinerary_id}/expenses", headers=headers)
        self.assertEqual(status, 404)
        self.assertEqual(body["detail"], "Itinerary not found")

        # A public draft has no owner; signing in later cannot claim it by ID.
        status, public_draft = self.request("POST", "/api/v1/itineraries", {
            "origin": "Madurai", "destination": "Rameswaram", "days": 2,
            "travellers": 2
        })
        self.assertEqual(status, 201)
        status, body = self.request("GET",
                                    f"/api/v1/itineraries/{public_draft['id']}/expenses",
                                    headers=headers)
        self.assertEqual(status, 404)

    def test_10_editorial_content_public_get_and_admin_create(self):
        db = self.Session()
        admin_token = create_token(db.get(User, "admin-1"))
        db.close()
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        status, body = self.request("POST", "/api/v1/admin/content", {
            "title": "Hidden guide", "slug": "hidden-guide", "is_published": False
        }, admin_headers)
        self.assertEqual(status, 201)
        content_id = body["id"]
        status, body = self.request("GET", "/api/v1/content")
        self.assertEqual(status, 200)
        self.assertEqual(body, [])
        status, body = self.request("GET", "/api/v1/content/hidden-guide")
        self.assertEqual(status, 404)

        status, body = self.request("PATCH", f"/api/v1/admin/content/{content_id}", {
            "is_published": True
        }, admin_headers)
        self.assertEqual(status, 200)
        status, body = self.request("GET", "/api/v1/content?content_type=guide")
        self.assertEqual(status, 200)
        self.assertEqual(body[0]["slug"], "hidden-guide")
        status, body = self.request("GET", "/api/v1/content/hidden-guide")
        self.assertEqual(status, 200)
        self.assertEqual(body["title"], "Hidden guide")

    def test_11_admin_content_post_requires_admin(self):
        status, body = self.request("POST", "/api/v1/admin/content", {
            "title": "Unauthorised", "slug": "unauthorised"
        })
        self.assertEqual(status, 401)

    def test_12_vehicle_availability_positive_and_negative(self):
        status, owner = self.request("POST", "/api/v1/auth/register", {
            "name": "Availability Owner", "email": "availability-owner@example.com",
            "password": "AvailabilityPassword123!", "role": "owner"
        })
        self.assertEqual(status, 201)
        owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
        status, vehicle = self.request("POST", "/api/v1/vehicles", {
            "title": "Availability car", "category": "Sedan", "price_per_day": 100,
            "city": "Chennai"
        }, owner_headers)
        self.assertEqual(status, 201)
        db = self.Session()
        db.get(Vehicle, vehicle["id"]).verified = True
        db.commit()
        db.close()
        status, result = self.request("GET", f"/api/v1/vehicles/{vehicle['id']}/availability?start_date=2026-11-03&end_date=2026-11-12")
        self.assertEqual(status, 200)
        self.assertTrue(result["available"])
        self.assertEqual(result["unavailable"], [])
        status, result = self.request("GET", f"/api/v1/vehicles/{vehicle['id']}/availability?start_date=2026-11-12&end_date=2026-11-03")
        self.assertEqual(status, 422)
        status, result = self.request("GET", "/api/v1/vehicles/missing/availability?start_date=2026-11-03&end_date=2026-11-12")
        self.assertEqual(status, 404)

    def test_13_cors_allows_configured_web_origin_and_rejects_other_origins(self):
        preflight = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
        status, _ = self.request("OPTIONS", "/api/v1/itineraries/mine", headers=preflight)
        self.assertEqual(status, 200)

        loopback = {**preflight, "Origin": "http://127.0.0.1:5173"}
        status, _ = self.request("OPTIONS", "/api/v1/itineraries/mine", headers=loopback)
        self.assertEqual(status, 200)

        disallowed = {**preflight, "Origin": "http://untrusted.example"}
        status, _ = self.request("OPTIONS", "/api/v1/itineraries/mine", headers=disallowed)
        self.assertEqual(status, 400)

    def test_14_notification_unread_count_auth_and_read_filter(self):
        status, registered = self.request("POST", "/api/v1/auth/register", {
            "name": "Notification Reader", "email": "notification-reader@example.com",
            "password": "NotificationPassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        headers = {"Authorization": f"Bearer {registered['access_token']}"}
        status, body = self.request("GET", "/api/v1/notifications/unread-count")
        self.assertEqual(status, 401)
        status, body = self.request("GET", "/api/v1/notifications/unread-count", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(body["unread_count"], 0)
        db = self.Session()
        db.add_all([
            models.Notification(user_id=registered["user"]["id"], title="Unread", body="One"),
            models.Notification(user_id=registered["user"]["id"], title="Read", body="Two",
                                read_at=datetime.utcnow()),
        ])
        db.commit()
        db.close()
        status, body = self.request("GET", "/api/v1/notifications/unread-count", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(body["unread_count"], 1)

    def test_15_email_verification_console_mode_and_invalid_code(self):
        status, registered = self.request("POST", "/api/v1/auth/register", {
            "name": "Verify Email", "email": "verify-email@example.com",
            "password": "VerifyPassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        headers = {"Authorization": f"Bearer {registered['access_token']}"}
        with patch("app.routers.auth.settings.otp_delivery_mode", "console"), \
                patch("app.routers.auth._send_security_code", side_effect=AssertionError("SMTP must not be used in console mode")):
            status, challenge = self.request("POST", "/api/v1/auth/email-verification/request", headers=headers)
        self.assertEqual(status, 200)
        code = challenge["development_code"]
        self.assertRegex(code, r"^[0-9]{6}$")
        invalid_code = "000000" if code != "000000" else "000001"
        status, _ = self.request("POST", "/api/v1/auth/email-verification/confirm",
                                 {"code": invalid_code}, headers)
        self.assertEqual(status, 400)
        status, result = self.request("POST", "/api/v1/auth/email-verification/confirm",
                                      {"code": code}, headers)
        self.assertEqual(status, 200)
        self.assertTrue(result["user"]["email_verified"])
        status, registered = self.request("POST", "/api/v1/auth/register", {
            "name": "SMTP Missing", "email": "smtp-missing@example.com",
            "password": "VerifyPassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        with patch("app.routers.auth.settings.otp_delivery_mode", "email"), \
                patch("app.routers.auth._send_security_code", side_effect=HTTPException(503, "SMTP unavailable")):
            status, _ = self.request("POST", "/api/v1/auth/email-verification/request",
                                     headers={"Authorization": f"Bearer {registered['access_token']}"})
        self.assertEqual(status, 503)

    def test_16_itinerary_budget_patch_auth_ownership_and_validation(self):
        status, owner = self.request("POST", "/api/v1/auth/register", {
            "name": "Budget Owner", "email": "budget-owner@example.com",
            "password": "BudgetPassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
        status, itinerary = self.request("POST", "/api/v1/itineraries", {
            "origin": "Chennai", "destination": "Pondicherry", "days": 2,
            "travellers": 2
        }, owner_headers)
        self.assertEqual(status, 201)
        path = f"/api/v1/itineraries/{itinerary['id']}/budget"
        payload = {"currency": "inr", "accommodation": 2500, "food": 500,
                   "transport": 0, "activities": 125.456, "other": 0,
                   "notes": "First estimate", "alert_threshold": 80}
        status, _ = self.request("PATCH", path, payload)
        self.assertEqual(status, 401)
        status, body = self.request("PATCH", path, payload, owner_headers)
        self.assertEqual(status, 200)
        self.assertEqual(body["budget"]["currency"], "INR")
        self.assertEqual(body["budget"]["activities"], 125.46)
        status, _ = self.request("PATCH", path, {**payload, "food": -1}, owner_headers)
        self.assertEqual(status, 422)
        status, other = self.request("POST", "/api/v1/auth/register", {
            "name": "Other Owner", "email": "budget-other@example.com",
            "password": "OtherPassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        status, _ = self.request("PATCH", path, payload,
                                 {"Authorization": f"Bearer {other['access_token']}"})
        self.assertEqual(status, 404)

    def test_17_itinerary_stops_patch_auth_ownership_and_validation(self):
        status, owner = self.request("POST", "/api/v1/auth/register", {
            "name": "Stops Owner", "email": "stops-owner@example.com",
            "password": "StopsPassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
        status, itinerary = self.request("POST", "/api/v1/itineraries", {
            "origin": "Chennai", "destination": "Pondicherry", "days": 2,
            "travellers": 2
        }, owner_headers)
        self.assertEqual(status, 201)
        path = f"/api/v1/itineraries/{itinerary['id']}/stops"
        stops = [{"day": 1, "title": "Promenade", "detail": "Visit the waterfront"},
                 {"day": 2, "title": "Auroville", "detail": "Check visiting hours"}]
        status, _ = self.request("PATCH", path, {"stops": stops})
        self.assertEqual(status, 401)
        status, body = self.request("PATCH", path, {"stops": stops}, owner_headers)
        self.assertEqual(status, 200)
        self.assertEqual(body["stops"], stops)
        status, _ = self.request("PATCH", path, {"stops": [{"day": 3, "title": "Outside trip"}]}, owner_headers)
        self.assertEqual(status, 422)
        status, other = self.request("POST", "/api/v1/auth/register", {
            "name": "Stops Other", "email": "stops-other@example.com",
            "password": "OtherPassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        status, _ = self.request("PATCH", path, {"stops": stops},
                                 {"Authorization": f"Bearer {other['access_token']}"})
        self.assertEqual(status, 404)

    def test_18_notification_preferences_and_email_history(self):
        status, registered = self.request("POST", "/api/v1/auth/register", {
            "name": "Preference User", "email": "preference-user@example.com",
            "password": "PreferencePassword123!", "role": "customer"
        })
        self.assertEqual(status, 201)
        headers = {"Authorization": f"Bearer {registered['access_token']}"}

        for path in ("/api/v1/notifications/preferences", "/api/v1/notifications/email-deliveries"):
            status, _ = self.request("GET", path)
            self.assertEqual(status, 401)

        status, defaults = self.request("GET", "/api/v1/notifications/preferences", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(defaults["booking_updates"], True)
        self.assertEqual(defaults["marketing_updates"], False)
        status, saved = self.request("PUT", "/api/v1/notifications/preferences", {
            "booking_updates": False, "payment_updates": True, "trip_budget_alerts": False,
            "support_updates": True, "marketing_updates": True, "email_enabled": True
        }, headers)
        self.assertEqual(status, 200)
        self.assertEqual(saved["booking_updates"], False)
        self.assertEqual(saved["email_enabled"], True)
        status, persisted = self.request("GET", "/api/v1/notifications/preferences", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(persisted["trip_budget_alerts"], False)
        status, echoed = self.request("PUT", "/api/v1/notifications/preferences", persisted, headers)
        self.assertEqual(status, 200)
        self.assertEqual(echoed["email_enabled"], True)
        status, _ = self.request("PUT", "/api/v1/notifications/preferences", {
            "booking_updates": "not-a-boolean"
        }, headers)
        self.assertEqual(status, 422)

        db = self.Session()
        user_id = registered["user"]["id"]
        db.add(models.NotificationEmailLog(
            user_id=user_id, recipient_email="preference-user@example.com", subject="Booking update",
            category="booking_updates", status="sent", email_body="private email content"
        ))
        db.add(models.NotificationEmailLog(
            user_id="admin-1", recipient_email="admin@elsewhere.com", subject="Private admin mail",
            category="security", status="sent"
        ))
        db.commit()
        db.close()
        status, deliveries = self.request("GET", "/api/v1/notifications/email-deliveries", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(len(deliveries["items"]), 1)
        self.assertEqual(deliveries["items"][0]["subject"], "Booking update")
        self.assertNotIn("email_body", deliveries["items"][0])

    def test_19_notifications_mine_requires_auth_and_returns_only_callers_notifications(self):
        _, first = self.request("POST", "/api/v1/auth/register", {
            "name": "Inbox Owner", "email": "inbox-owner@example.com",
            "password": "InboxPassword123!", "role": "customer"
        })
        _, second = self.request("POST", "/api/v1/auth/register", {
            "name": "Other Inbox", "email": "other-inbox@example.com",
            "password": "OtherInboxPassword123!", "role": "customer"
        })
        first_headers = {"Authorization": f"Bearer {first['access_token']}"}
        second_headers = {"Authorization": f"Bearer {second['access_token']}"}
        status, _ = self.request("GET", "/api/v1/notifications/mine")
        self.assertEqual(status, 401)

        db = self.Session()
        db.add_all([
            models.Notification(user_id=first["user"]["id"], title="My booking", body="Confirmed"),
            models.Notification(user_id=second["user"]["id"], title="Private update", body="Not yours"),
        ])
        db.commit()
        db.close()

        status, first_notifications = self.request("GET", "/api/v1/notifications/mine", headers=first_headers)
        self.assertEqual(status, 200)
        self.assertEqual([n["title"] for n in first_notifications], ["My booking"])
        status, second_notifications = self.request("GET", "/api/v1/notifications/mine", headers=second_headers)
        self.assertEqual(status, 200)
        self.assertEqual([n["title"] for n in second_notifications], ["Private update"])

    def test_20_support_ticket_create_validation_and_trim(self):
        _, registered = self.request("POST", "/api/v1/auth/register", {
            "name": "Support Customer", "email": "support-customer@example.com",
            "password": "SupportPassword123!", "role": "customer"
        })
        headers = {"Authorization": f"Bearer {registered['access_token']}"}
        payload = {"subject": "  Booking help  ", "message": "  I need help with my booking.  ", "priority": "normal"}
        status, _ = self.request("POST", "/api/v1/support/tickets", payload)
        self.assertEqual(status, 401)
        status, created = self.request("POST", "/api/v1/support/tickets", payload, headers)
        self.assertEqual(status, 201)
        self.assertEqual(created["status"], "open")
        status, mine = self.request("GET", "/api/v1/support/tickets/mine", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(mine[0]["subject"], "Booking help")
        self.assertEqual(mine[0]["priority"], "normal")

        for invalid in (
            {"subject": "abc", "message": "This message is long enough", "priority": "normal"},
            {"subject": "Valid subject", "message": "short", "priority": "normal"},
            {"subject": "Valid subject", "message": "This message is long enough", "priority": "immediate"},
            {"subject": "    ", "message": "This message is long enough", "priority": "normal"},
        ):
            status, _ = self.request("POST", "/api/v1/support/tickets", invalid, headers)
            self.assertEqual(status, 422)

    def test_21_itinerary_detail_share_and_owner_management_endpoints(self):
        status, registered = self.request("POST", "/api/v1/auth/register", {
            "name": "Itinerary Share Owner", "email": "itinerary-share-owner@example.com",
            "password": "ItineraryPassword123!", "role": "customer"
        })
        self.assertEqual(status, 201, registered)
        headers = {"Authorization": f"Bearer {registered['access_token']}"}
        _, itinerary = self.request("POST", "/api/v1/itineraries", {
            "origin": "Chennai", "destination": "Pondicherry", "days": 2, "travellers": 2
        }, headers)
        itinerary_id = itinerary["id"]
        status, detail = self.request("GET", f"/api/v1/itineraries/{itinerary_id}", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(detail["owner_id"], registered["user"]["id"])
        status, shared = self.request("POST", f"/api/v1/itineraries/{itinerary_id}/share", headers=headers)
        self.assertEqual(status, 200)
        status, shared_detail = self.request("GET", f"/api/v1{shared['share_path']}")
        self.assertEqual(status, 200)
        self.assertEqual(shared_detail["id"], itinerary_id)
        status, _ = self.request("DELETE", f"/api/v1/itineraries/{itinerary_id}/share", headers=headers)
        self.assertEqual(status, 200)
        status, _ = self.request("GET", f"/api/v1{shared['share_path']}")
        self.assertEqual(status, 404)
        status, _ = self.request("DELETE", f"/api/v1/itineraries/{itinerary_id}", headers=headers)
        self.assertEqual(status, 200)

    def test_22_owner_availability_maintenance_and_driver_routes(self):
        _, registered = self.request("POST", "/api/v1/auth/register", {
            "name": "Owner Routes", "email": "owner-routes@example.com",
            "password": "OwnerRoutesPassword123!", "role": "owner"
        })
        headers = {"Authorization": f"Bearer {registered['access_token']}"}
        _, vehicle = self.request("POST", "/api/v1/vehicles", {
            "title": "City car", "category": "Car", "price_per_day": 1000, "city": "Chennai"
        }, headers)
        vehicle_id = vehicle["id"]
        block_path = f"/api/v1/owner/vehicles/{vehicle_id}/availability-blocks"
        status, _ = self.request("GET", block_path)
        self.assertEqual(status, 401)
        status, _ = self.request("POST", block_path, {"start_date":"2027-04-05","end_date":"2027-04-04","reason":"Maintenance"}, headers)
        self.assertEqual(status, 422)
        status, block = self.request("POST", block_path, {"start_date":"2027-04-04","end_date":"2027-04-05","reason":"Maintenance"}, headers)
        self.assertEqual(status, 201)
        status, blocks = self.request("GET", block_path, headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(len(blocks), 1)
        maintenance_path = f"/api/v1/owner/vehicles/{vehicle_id}/maintenance"
        status, maintenance = self.request("POST", maintenance_path, {
            "description":"Scheduled service", "service_date":"2027-04-06", "cost":1200, "status":"scheduled"
        }, headers)
        self.assertEqual(status, 201)
        maintenance_id = maintenance["id"]
        status, _ = self.request("PATCH", f"{maintenance_path}/{maintenance_id}", {
            "description":"Scheduled service", "service_date":"2027-04-06", "cost":1200, "status":"completed"
        }, headers)
        self.assertEqual(status, 200)
        _, driver = self.request("POST", "/api/v1/owner/drivers", {
            "name":"Test Driver", "phone":"+919876543210", "licence_number":"LIC-ROUTES-001"
        }, headers)
        status, inactive = self.request("PATCH", f"/api/v1/owner/drivers/{driver['id']}/status?active=false", headers=headers)
        self.assertEqual(status, 200)
        self.assertFalse(inactive["active"])
        status, reputation = self.request("GET", "/api/v1/owner/reputation", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(reputation["vehicle_count"], 1)
        status, _ = self.request("DELETE", f"{block_path}/{block['id']}", headers=headers)
        self.assertEqual(status, 200)

    def test_23_admin_workspace_routes_filter_and_enforce_authorization(self):
        _, admin_login = self.request("POST", "/api/v1/auth/login", {
            "email":"admin@elsewhere.com", "password":"AdminPass123!"
        })
        admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}
        status, _ = self.request("GET", "/api/v1/admin/users")
        self.assertEqual(status, 401)
        status, users = self.request("GET", "/api/v1/admin/users?q=admin%40elsewhere.com&page=1&page_size=10", headers=admin_headers)
        self.assertEqual(status, 200)
        self.assertTrue(any(user["email"] == "admin@elsewhere.com" for user in users["items"]))
        status, destinations = self.request("GET", "/api/v1/admin/destinations?status=all", headers=admin_headers)
        self.assertEqual(status, 200)
        self.assertIn("pages", destinations)
        status, analytics = self.request("GET", "/api/v1/admin/analytics/overview?days=30", headers=admin_headers)
        self.assertEqual(status, 200)
        self.assertIn("booking_status", analytics)

    def test_24_email_admin_routes_and_retry_provider_failure(self):
        _, admin_login = self.request("POST", "/api/v1/auth/login", {
            "email":"admin@elsewhere.com", "password":"AdminPass123!"
        })
        headers = {"Authorization": f"Bearer {admin_login['access_token']}"}
        db = self.Session()
        item = models.NotificationEmailLog(user_id="admin-1", recipient_email="a@example.com",
            subject="Retry me", category="booking_updates", status="dead_letter", email_body="Details", retry_count=3)
        db.add(item); db.commit(); db.refresh(item); log_id = item.id; db.close()
        status, _ = self.request("GET", "/api/v1/admin/email-delivery-logs")
        self.assertEqual(status, 401)
        status, listing = self.request("GET", "/api/v1/admin/email-delivery-logs?status=dead_letter", headers=headers)
        self.assertEqual(status, 200)
        self.assertTrue(any(row["id"] == log_id for row in listing["items"]))
        status, detail = self.request("GET", f"/api/v1/admin/email-delivery-logs/{log_id}", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(detail["email_body"], "Details")
        status, summary = self.request("GET", "/api/v1/admin/email-delivery-logs/summary", headers=headers)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(summary["dead_letter"], 1)
        status, _ = self.request("POST", f"/api/v1/admin/email-delivery-logs/{log_id}/requeue", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(self.Session().get(models.NotificationEmailLog, log_id).status, "failed")

    def test_25_provider_catalog_and_tour_request_endpoints(self):
        _, provider = self.request("POST", "/api/v1/auth/register", {
            "name":"Agency Routes", "email":"agency-routes@example.com",
            "password":"AgencyRoutesPassword123!", "role":"agency"
        })
        provider_headers={"Authorization":f"Bearer {provider['access_token']}"}
        status, _ = self.request("PUT", "/api/v1/providers/me/profile", {
            "business_name":"Agency Routes", "description":"Local journeys", "service_areas":["Chennai"]
        }, provider_headers)
        self.assertEqual(status, 200)
        status, profile = self.request("GET", "/api/v1/providers/me/profile", headers=provider_headers)
        self.assertEqual(status, 200)
        self.assertEqual(profile["profile"]["business_name"], "Agency Routes")
        status, package = self.request("POST", "/api/v1/providers/me/tour-packages", {
            "title":"Coastal Escape", "destination":"Pondicherry", "summary":"A relaxed coast break",
            "description":"Three days by the sea", "duration_days":3,"price_per_person":5000,
            "currency":"INR","max_travellers":8,"itinerary":[{"title":"Day 1","details":"Arrival"}],
            "inclusions":["Breakfast"],"exclusions":[],"is_published":True
        }, provider_headers)
        self.assertEqual(status, 201)
        status, public_list = self.request("GET", "/api/v1/tour-packages?destination=Pondicherry")
        self.assertEqual(status, 200)
        self.assertTrue(any(row["id"]==package["id"] for row in public_list))
        status, public_detail = self.request("GET", f"/api/v1/tour-packages/{package['slug']}")
        self.assertEqual(status, 200)
        self.assertEqual(public_detail["currency"], "INR")
        _, customer = self.request("POST", "/api/v1/auth/register", {
            "name":"Package Traveller", "email":"package-traveller@example.com",
            "password":"PackageTravellerPassword123!", "role":"customer"
        })
        customer_headers={"Authorization":f"Bearer {customer['access_token']}"}
        db=self.Session();request=models.TourPackageRequest(package_id=package["id"],customer_id=customer["user"]["id"],
          provider_id=provider["user"]["id"],start_date=date.today()+timedelta(days=40),travellers=2,contact_phone="1234567890",message="Please confirm")
        db.add(request);db.commit();request_id=request.id;db.close()
        status, requests=self.request("GET","/api/v1/tour-package-requests/mine",headers=customer_headers)
        self.assertEqual(status,200);self.assertTrue(any(row["id"]==request_id for row in requests))
        status, provider_requests=self.request("GET","/api/v1/providers/me/tour-package-requests",headers=provider_headers)
        self.assertEqual(status,200);self.assertTrue(any(row["id"]==request_id for row in provider_requests))
        status, updated=self.request("PATCH",f"/api/v1/providers/me/tour-package-requests/{request_id}",
          {"status":"reviewing","provider_note":"Checking dates"},provider_headers)
        self.assertEqual(status,200);self.assertEqual(updated["status"],"reviewing")
        status,cancelled=self.request("PATCH",f"/api/v1/tour-package-requests/{request_id}/cancel",headers=customer_headers)
        self.assertEqual(status,200);self.assertEqual(cancelled["status"],"cancelled")

if __name__ == "__main__":
    unittest.main()
