import unittest

def estimate(days, travellers, vehicle, fuel, food, stay, rooms, tolls, activities, contingency):
    vehicle_total = days * vehicle
    food_total = days * travellers * food
    stay_total = max(0, days - 1) * rooms * stay
    subtotal = vehicle_total + fuel + food_total + stay_total + tolls + activities
    total = round(subtotal * (1 + contingency / 100), 2)
    return total, round(total / travellers, 2)

class TestBudgetFormula(unittest.TestCase):
    def test_budget_estimate_includes_room_nights_and_contingency(self):
        total, per_person = estimate(3, 2, 1000, 500, 200, 1500, 1, 100, 300, 10)
        self.assertEqual(total, 8910.0)
        self.assertEqual(per_person, 4455.0)

    def test_one_day_trip_has_no_accommodation_night(self):
        total, _ = estimate(1, 1, 1000, 0, 100, 1500, 1, 0, 0, 0)
        self.assertEqual(total, 1100.0)

if __name__ == "__main__":
    unittest.main()
