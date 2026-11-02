import asyncio
import json
import unittest
from datetime import date, timedelta
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
import app.models as models
from app.models import Role, User, Destination, Vehicle, Booking
from app.security import hash_password
from app.main import app

class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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

    def request(self, method: str, path: str, json_data=None, headers=None):
        return asyncio.run(self._asgi_request(method, path, json_data, headers))

    async def _asgi_request(self, method: str, path: str, json_data=None, headers=None):
        parsed = urlparse(path)
        path_only = parsed.path
        query_string = parsed.query.encode("utf-8")
        header_list = []
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

if __name__ == "__main__":
    unittest.main()
