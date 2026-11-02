import unittest
from datetime import date
from decimal import Decimal
from app.services.budget import estimate as estimate_budget, money
from app.services.bookings import validate_date_range, overlaps, quote_vehicle_booking
from app.services.auth import normalize_email
from app.services.reviews import validate_review_rating, normalize_comment
from app.services.vehicles import can_be_booked

class DummyVehicle:
    def __init__(self, available=True, verified=True):
        self.available = available
        self.verified = verified

class TestDomainServices(unittest.TestCase):
    def test_budget_estimate_service(self):
        res = estimate_budget(
            days=3,
            travellers=2,
            vehicle_per_day=1000,
            fuel=500,
            food_per_person_day=200,
            stay_per_room_night=1500,
            rooms=1,
            tolls=100,
            activities=300,
            contingency=10
        )
        self.assertEqual(res["currency"], "INR")
        self.assertEqual(res["subtotal"], 8100.0)
        self.assertEqual(res["total"], 8910.0)
        self.assertEqual(res["per_person"], 4455.0)

    def test_budget_estimate_one_day_no_stay(self):
        res = estimate_budget(
            days=1,
            travellers=1,
            vehicle_per_day=1000,
            fuel=0,
            food_per_person_day=100,
            stay_per_room_night=1500,
            rooms=1,
            tolls=0,
            activities=0,
            contingency=0
        )
        self.assertEqual(res["items"]["accommodation"], 0.0)
        self.assertEqual(res["total"], 1100.0)

    def test_booking_validate_date_range(self):
        d1 = date(2026, 11, 1)
        d2 = date(2026, 11, 5)
        validate_date_range(d1, d2)  # Should not raise
        validate_date_range(d1, d1)  # Same-day should not raise

        with self.assertRaises(ValueError):
            validate_date_range(d2, d1)

    def test_booking_overlaps(self):
        d1 = date(2026, 11, 1)
        d2 = date(2026, 11, 5)
        d3 = date(2026, 11, 4)
        d4 = date(2026, 11, 8)
        d5 = date(2026, 11, 6)
        d6 = date(2026, 11, 10)

        self.assertTrue(overlaps(d1, d2, d3, d4))
        self.assertFalse(overlaps(d1, d2, d5, d6))

    def test_quote_vehicle_booking(self):
        # 3 days: Nov 1, 2, 3
        d1 = date(2026, 11, 1)
        d2 = date(2026, 11, 3)
        quote = quote_vehicle_booking(d1, d2, 2500)
        self.assertEqual(quote, Decimal("7500"))

    def test_auth_normalize_email(self):
        self.assertEqual(normalize_email("  User@Example.COM "), "user@example.com")

    def test_review_validation(self):
        validate_review_rating(1)
        validate_review_rating(5)
        with self.assertRaises(ValueError):
            validate_review_rating(0)
        with self.assertRaises(ValueError):
            validate_review_rating(6)
        self.assertEqual(normalize_comment("  Great trip!  "), "Great trip!")

    def test_vehicle_can_be_booked(self):
        self.assertTrue(can_be_booked(DummyVehicle(available=True, verified=True)))
        self.assertFalse(can_be_booked(DummyVehicle(available=False, verified=True)))
        self.assertFalse(can_be_booked(DummyVehicle(available=True, verified=False)))
        self.assertFalse(can_be_booked(None))

if __name__ == "__main__":
    unittest.main()

