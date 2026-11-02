import unittest
from datetime import date
from pydantic import ValidationError
from app.security import hash_password, verify_password, create_token
from app.models import User, Role
from app.schemas import RegisterIn, LoginIn, VehicleIn, ItineraryIn, BookingIn, ReviewIn

class TestSecurityAndSchemas(unittest.TestCase):
    def test_password_hashing_and_verification(self):
        plain = "SecureP@ssw0rd123"
        hashed = hash_password(plain)
        self.assertNotEqual(plain, hashed)
        self.assertTrue(verify_password(plain, hashed))
        self.assertFalse(verify_password("wrong_password", hashed))

    def test_create_token(self):
        user = User(id="user-123", name="Traveller", email="user@test.com", role=Role.customer)
        token = create_token(user)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 20)

    def test_register_schema_validation(self):
        # Valid schema
        valid = RegisterIn(
            name="Alice Smith",
            email="alice@example.com",
            password="StrongPassword123",
            role="customer"
        )
        self.assertEqual(valid.role, "customer")

        # Invalid: password too short (< 8 chars)
        with self.assertRaises(ValidationError):
            RegisterIn(
                name="Alice",
                email="alice@example.com",
                password="short",
                role="customer"
            )

        # Invalid: bad email format
        with self.assertRaises(ValidationError):
            RegisterIn(
                name="Alice",
                email="not-an-email",
                password="StrongPassword123",
                role="customer"
            )

    def test_vehicle_schema_validation(self):
        valid = VehicleIn(
            title="Toyota Innova",
            category="SUV",
            seats=7,
            price_per_day=4000,
            city="Chennai"
        )
        self.assertEqual(valid.seats, 7)

        # Invalid price (<= 0)
        with self.assertRaises(ValidationError):
            VehicleIn(
                title="Toyota Innova",
                category="SUV",
                seats=7,
                price_per_day=0,
                city="Chennai"
            )

    def test_itinerary_schema_validation(self):
        valid = ItineraryIn(
            origin="Chennai",
            destination="Munnar",
            days=4,
            travellers=2
        )
        self.assertEqual(valid.days, 4)

        # Invalid days (< 1 or > 60)
        with self.assertRaises(ValidationError):
            ItineraryIn(origin="A", destination="B", days=0)
        with self.assertRaises(ValidationError):
            ItineraryIn(origin="A", destination="B", days=100)

    def test_review_schema_validation(self):
        valid = ReviewIn(booking_id="b123", rating=5, comment="Wonderful experience")
        self.assertEqual(valid.rating, 5)

        # Rating out of bounds (1..5)
        with self.assertRaises(ValidationError):
            ReviewIn(booking_id="b123", rating=0)
        with self.assertRaises(ValidationError):
            ReviewIn(booking_id="b123", rating=6)

if __name__ == "__main__":
    unittest.main()

