"""Deterministic INR trip-budget calculations using Decimal arithmetic."""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)

def estimate(*, days: int, travellers: int, vehicle_per_day=0, fuel=0,
             food_per_person_day=0, stay_per_room_night=0, rooms=1,
             tolls=0, activities=0, contingency=10) -> dict:
    vehicle = money(days * money(vehicle_per_day))
    fuel, tolls, activities = money(fuel), money(tolls), money(activities)
    food = money(days * travellers * money(food_per_person_day))
    stay = money(max(0, days - 1) * rooms * money(stay_per_room_night))
    subtotal = money(vehicle + fuel + food + stay + tolls + activities)
    total = money(subtotal * (Decimal("1") + Decimal(str(contingency)) / 100))
    return {"currency":"INR", "items":{"vehicle":float(vehicle),"fuel":float(fuel),"food":float(food),"accommodation":float(stay),"tolls_parking":float(tolls),"activities":float(activities)},"subtotal":float(subtotal),"contingency_percent":float(contingency),"total":float(total),"per_person":float(money(total / travellers))}
