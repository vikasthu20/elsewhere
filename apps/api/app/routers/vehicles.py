from fastapi import APIRouter
from datetime import date
from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Booking, Vehicle, VehicleAvailabilityBlock
from app.legacy_routes import vehicles, vehicle_detail, add_vehicle, my_vehicles
router = APIRouter()
router.add_api_route('/vehicles', vehicles, methods=['GET'], tags=['vehicles'])
router.add_api_route('/vehicles/mine', my_vehicles, methods=['GET'], tags=['vehicles'])
router.add_api_route('/vehicles/{vehicle_id}', vehicle_detail, methods=['GET'], tags=['vehicles'])
router.add_api_route('/vehicles', add_vehicle, methods=['POST'], status_code=201, tags=['vehicles'])


@router.get('/vehicles/{vehicle_id}/availability', tags=['vehicles'])
def vehicle_availability(vehicle_id: str, start_date: date, end_date: date,
                          db: Session = Depends(get_db)):
    if end_date < start_date:
        raise HTTPException(422, "End date must be on or after start date")
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.available or not vehicle.verified:
        raise HTTPException(404, "Vehicle not found")
    blocked = db.query(VehicleAvailabilityBlock).filter(
        VehicleAvailabilityBlock.vehicle_id == vehicle_id,
        VehicleAvailabilityBlock.start_date <= end_date,
        VehicleAvailabilityBlock.end_date >= start_date,
    ).all()
    bookings = db.query(Booking).filter(
        Booking.vehicle_id == vehicle_id,
        Booking.status.in_(["requested", "confirmed"]),
        Booking.start_date <= end_date,
        Booking.end_date >= start_date,
    ).all()
    unavailable = [
        {"start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat(),
         "type": "blocked", "reason": row.reason}
        for row in blocked
    ] + [
        {"start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat(),
         "type": "booking", "status": row.status}
        for row in bookings
    ]
    return {"vehicle_id": vehicle_id, "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(), "available": not unavailable,
            "unavailable": unavailable}
