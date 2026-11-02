"""Booking domain rules. Database locking remains the responsibility of the route transaction."""
from datetime import date
from decimal import Decimal

def validate_date_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ValueError("End date must be on or after start date")

def overlaps(start: date, end: date, other_start: date, other_end: date) -> bool:
    return start <= other_end and end >= other_start

def quote_vehicle_booking(start: date, end: date, daily_rate) -> Decimal:
    validate_date_range(start, end)
    days = max(1, (end - start).days + 1)
    return Decimal(str(daily_rate)) * days
