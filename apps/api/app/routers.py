from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, Role, Destination, Itinerary, Vehicle, Booking, Review
from app.schemas import RegisterIn, LoginIn, VehicleIn, ItineraryIn, BookingIn, BookingStatusIn, ReviewIn
from app.security import hash_password, verify_password, create_token, current_user, require_roles

api = APIRouter()

def public_user(user: User):
    return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone, "role": user.role.value}

def public_vehicle(vehicle: Vehicle):
    return {"id": vehicle.id, "title": vehicle.title, "category": vehicle.category,
            "make_model": vehicle.make_model, "seats": vehicle.seats,
            "price_per_day": float(vehicle.price_per_day), "city": vehicle.city,
            "description": vehicle.description, "image_url": vehicle.image_url,
            "verified": vehicle.verified, "available": vehicle.available}

@api.post("/auth/register", status_code=201, tags=["authentication"])
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "Email already registered")
    allowed_roles = {"customer": Role.customer, "owner": Role.owner, "agency": Role.agency}
    if data.role not in allowed_roles:
        raise HTTPException(400, "Choose Traveller, Vehicle owner or Travel agency")
    user = User(name=data.name.strip(), email=email, phone=data.phone,
                password_hash=hash_password(data.password), role=allowed_roles[data.role])
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": create_token(user), "token_type": "bearer", "user": public_user(user)}

@api.post("/auth/login", tags=["authentication"])
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == str(data.email).lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_token(user), "token_type": "bearer", "user": public_user(user)}

@api.get("/auth/me", tags=["authentication"])
def me(user: User = Depends(current_user)):
    return public_user(user)

@api.get("/destinations", tags=["destinations"])
def destinations(q: str | None = None, category: str | None = None,
                 limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db)):
    query = db.query(Destination).filter(Destination.is_published.is_(True))
    if q: query = query.filter(Destination.name.ilike(f"%{q}%"))
    if category: query = query.filter(Destination.category.ilike(category))
    rows = query.order_by(Destination.name).offset(offset).limit(limit).all()
    return [{"id": x.id, "name": x.name, "region": x.region, "category": x.category,
             "description": x.description, "image_url": x.image_url,
             "latitude": x.latitude, "longitude": x.longitude} for x in rows]

@api.get("/destinations/{destination_id}", tags=["destinations"])
def destination_detail(destination_id: str, db: Session = Depends(get_db)):
    item = db.get(Destination, destination_id)
    if not item or not item.is_published: raise HTTPException(404, "Destination not found")
    return {"id": item.id, "name": item.name, "region": item.region, "category": item.category,
            "description": item.description, "image_url": item.image_url,
            "latitude": item.latitude, "longitude": item.longitude}

@api.post("/destinations", status_code=201, tags=["administration"])
def add_destination(data: dict, db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    allowed = {"name", "region", "category", "description", "image_url", "latitude", "longitude", "is_published"}
    item = Destination(**{k: v for k, v in data.items() if k in allowed})
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "name": item.name}

@api.post("/itineraries", status_code=201, tags=["itineraries"])
def create_itinerary(data: ItineraryIn, db: Session = Depends(get_db)):
    item = Itinerary(title=f"{data.origin} to {data.destination}", origin=data.origin,
                     destination=data.destination, start_date=data.start_date, days=data.days,
                     travellers=data.travellers, interests=data.interests,
                     estimated_budget=data.estimated_budget)
    db.add(item); db.commit(); db.refresh(item)
    stops = [{"day": n, "title": "Arrival & local discovery" if n == 1 else "Explore nearby highlights",
              "detail": "Draft suggestion. Confirm route, opening hours and travel times before departure."}
             for n in range(1, min(data.days, 5) + 1)]
    return {"id": item.id, "title": item.title, "origin": item.origin, "destination": item.destination,
            "days": item.days, "travellers": item.travellers, "estimated_budget": item.estimated_budget,
            "stops": stops, "status": "draft"}

@api.get("/itineraries/mine", tags=["itineraries"])
def my_itineraries(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Itinerary).filter(Itinerary.user_id == user.id).order_by(Itinerary.created_at.desc()).all()
    return [{"id": x.id, "title": x.title, "origin": x.origin, "destination": x.destination,
             "days": x.days, "start_date": str(x.start_date) if x.start_date else None} for x in rows]

@api.get("/vehicles", tags=["vehicles"])
def vehicles(city: str | None = None, category: str | None = None,
             seats: int | None = Query(None, ge=1, le=100), limit: int = Query(30, ge=1, le=100),
             offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    query = db.query(Vehicle).filter(Vehicle.available.is_(True), Vehicle.verified.is_(True))
    if city: query = query.filter(Vehicle.city.ilike(f"%{city}%"))
    if category: query = query.filter(Vehicle.category.ilike(category))
    if seats: query = query.filter(Vehicle.seats >= seats)
    return [public_vehicle(v) for v in query.order_by(Vehicle.price_per_day).offset(offset).limit(limit).all()]

@api.get("/vehicles/{vehicle_id}", tags=["vehicles"])
def vehicle_detail(vehicle_id: str, db: Session = Depends(get_db)):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.available: raise HTTPException(404, "Vehicle not found")
    return public_vehicle(vehicle)

@api.post("/vehicles", status_code=201, tags=["vehicles"])
def add_vehicle(data: VehicleIn, db: Session = Depends(get_db), user: User = Depends(require_roles("owner", "agency", "admin"))):
    vehicle = Vehicle(owner_id=user.id, **data.model_dump())
    db.add(vehicle); db.commit(); db.refresh(vehicle)
    return public_vehicle(vehicle)

@api.get("/vehicles/mine", tags=["vehicles"])
def my_vehicles(db: Session = Depends(get_db), user: User = Depends(require_roles("owner", "agency", "admin"))):
    return [public_vehicle(v) for v in db.query(Vehicle).filter(Vehicle.owner_id == user.id).all()]

@api.post("/bookings", status_code=201, tags=["bookings"])
def create_booking(data: BookingIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if data.end_date < data.start_date: raise HTTPException(400, "End date must be on or after start date")
    vehicle = db.query(Vehicle).filter(Vehicle.id == data.vehicle_id).with_for_update().first()
    if not vehicle or not vehicle.available or not vehicle.verified:
        raise HTTPException(400, "Vehicle is unavailable or not verified")
    overlap = db.query(Booking).filter(Booking.vehicle_id == vehicle.id,
        Booking.status.in_(["requested", "confirmed"]), Booking.start_date <= data.end_date,
        Booking.end_date >= data.start_date).first()
    if overlap: raise HTTPException(409, "Vehicle already has a booking in this date range")
    days = max(1, (data.end_date - data.start_date).days + 1)
    booking = Booking(customer_id=user.id, vehicle_id=vehicle.id, start_date=data.start_date,
                      end_date=data.end_date, pickup_location=data.pickup_location,
                      total_amount=days * vehicle.price_per_day)
    db.add(booking); db.commit(); db.refresh(booking)
    return {"id": booking.id, "status": booking.status, "total_amount": float(booking.total_amount)}

@api.get("/bookings/mine", tags=["bookings"])
def my_bookings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Booking).filter(Booking.customer_id == user.id).order_by(Booking.created_at.desc()).all()
    return [{"id": b.id, "vehicle_id": b.vehicle_id, "start_date": str(b.start_date),
             "end_date": str(b.end_date), "total_amount": float(b.total_amount), "status": b.status} for b in rows]

@api.get("/owner/bookings", tags=["owner"])
def owner_bookings(db: Session = Depends(get_db), user: User = Depends(require_roles("owner", "agency", "admin"))):
    query = db.query(Booking).join(Vehicle, Booking.vehicle_id == Vehicle.id).filter(Vehicle.owner_id == user.id)
    return [{"id": b.id, "vehicle_id": b.vehicle_id, "customer_id": b.customer_id,
             "start_date": str(b.start_date), "end_date": str(b.end_date),
             "total_amount": float(b.total_amount), "status": b.status} for b in query.order_by(Booking.created_at.desc()).all()]

@api.patch("/owner/bookings/{booking_id}", tags=["owner"])
def update_owner_booking(booking_id: str, data: BookingStatusIn, db: Session = Depends(get_db),
                         user: User = Depends(require_roles("owner", "agency", "admin"))):
    booking = db.query(Booking).join(Vehicle, Booking.vehicle_id == Vehicle.id).filter(
        Booking.id == booking_id, Vehicle.owner_id == user.id).first()
    if not booking: raise HTTPException(404, "Booking not found")
    if booking.status not in ("requested", "confirmed"):
        raise HTTPException(409, "This booking can no longer be changed")
    booking.status = data.status; db.commit()
    return {"id": booking.id, "status": booking.status}

@api.post("/reviews", status_code=201, tags=["reviews"])
def review(data: ReviewIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    booking = db.get(Booking, data.booking_id)
    if not booking or booking.customer_id != user.id or booking.status != "completed":
        raise HTTPException(400, "Only completed bookings can be reviewed")
    review_item = Review(booking_id=booking.id, user_id=user.id, rating=data.rating, comment=data.comment)
    db.add(review_item)
    try: db.commit()
    except Exception:
        db.rollback(); raise HTTPException(409, "A review already exists for this booking")
    return {"id": review_item.id, "rating": review_item.rating}

@api.get("/budget/estimate", tags=["budget"])
def budget(days: int = Query(1, ge=1, le=90), travellers: int = Query(1, ge=1, le=100),
           vehicle_per_day: float = Query(0, ge=0), fuel: float = Query(0, ge=0),
           food_per_person_day: float = Query(0, ge=0), stay_per_room_night: float = Query(0, ge=0),
           rooms: int = Query(1, ge=0, le=50), tolls: float = Query(0, ge=0),
           activities: float = Query(0, ge=0), contingency: float = Query(10, ge=0, le=100)):
    vehicle = days * vehicle_per_day; food = days * travellers * food_per_person_day
    stay = max(0, days - 1) * rooms * stay_per_room_night
    subtotal = vehicle + fuel + food + stay + tolls + activities
    total = round(subtotal * (1 + contingency / 100), 2)
    return {"currency": "INR", "items": {"vehicle": vehicle, "fuel": fuel, "food": food,
            "accommodation": stay, "tolls_parking": tolls, "activities": activities},
            "subtotal": round(subtotal, 2), "contingency_percent": contingency,
            "total": total, "per_person": round(total / travellers, 2)}

@api.get("/admin/overview", tags=["administration"])
def admin_overview(db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    return {"users": db.query(User).count(), "destinations": db.query(Destination).count(),
            "vehicles": db.query(Vehicle).count(), "bookings": db.query(Booking).count(),
            "pending_vehicles": db.query(Vehicle).filter(Vehicle.verified.is_(False)).count(),
            "pending_bookings": db.query(Booking).filter(Booking.status == "requested").count()}
