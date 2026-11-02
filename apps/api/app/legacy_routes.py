from datetime import date, datetime
import json, uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, Role, Destination, Itinerary, Vehicle, Booking, Review, Notification, AuditLog, ProviderProfile, TourPackage, TourPackageRequest
from app.schemas import RegisterIn, LoginIn, VehicleIn, ItineraryIn, BookingIn, BookingStatusIn, ReviewIn, ProviderProfileIn, TourPackageIn, TourPackageRequestIn, TourPackageRequestUpdateIn
from app.security import hash_password, verify_password, create_token, current_user, optional_current_user, require_roles
from app.services.auth import normalize_email, public_user as serialize_user
from app.services.vehicles import serialize_vehicle
from app.services.bookings import validate_date_range, quote_vehicle_booking
from app.services.itineraries import build_draft_stops
from app.services.budget import estimate as estimate_budget

api = APIRouter()

def public_user(user: User):
    return serialize_user(user)

def public_vehicle(vehicle: Vehicle):
    return serialize_vehicle(vehicle)

@api.post("/auth/register", status_code=201, tags=["authentication"])
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = normalize_email(str(data.email))
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
def create_itinerary(data: ItineraryIn, db: Session = Depends(get_db),
                     user: User | None = Depends(optional_current_user)):
    item = Itinerary(title=f"{data.origin} to {data.destination}", origin=data.origin,
                     destination=data.destination, start_date=data.start_date, days=data.days,
                     travellers=data.travellers, interests=data.interests,
                     estimated_budget=data.estimated_budget, user_id=user.id if user else None)
    db.add(item); db.commit(); db.refresh(item)
    stops = build_draft_stops(data.days)
    return {"id": item.id, "title": item.title, "origin": item.origin, "destination": item.destination,
            "days": item.days, "travellers": item.travellers, "estimated_budget": item.estimated_budget,
            "stops": stops, "status": "draft", "owner_id": item.user_id}

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
    try: validate_date_range(data.start_date, data.end_date)
    except ValueError as exc: raise HTTPException(400, str(exc))
    vehicle = db.query(Vehicle).filter(Vehicle.id == data.vehicle_id).with_for_update().first()
    if not vehicle or not vehicle.available or not vehicle.verified:
        raise HTTPException(400, "Vehicle is unavailable or not verified")
    overlap = db.query(Booking).filter(Booking.vehicle_id == vehicle.id,
        Booking.status.in_(["requested", "confirmed"]), Booking.start_date <= data.end_date,
        Booking.end_date >= data.start_date).first()
    if overlap: raise HTTPException(409, "Vehicle already has a booking in this date range")
    amount = quote_vehicle_booking(data.start_date, data.end_date, vehicle.price_per_day)
    booking = Booking(customer_id=user.id, vehicle_id=vehicle.id, start_date=data.start_date,
                      end_date=data.end_date, pickup_location=data.pickup_location,
                      total_amount=float(amount))
    db.add(booking)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Vehicle already has a booking in this date range")
    db.refresh(booking)
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
    return estimate_budget(days=days, travellers=travellers, vehicle_per_day=vehicle_per_day,
        fuel=fuel, food_per_person_day=food_per_person_day, stay_per_room_night=stay_per_room_night,
        rooms=rooms, tolls=tolls, activities=activities, contingency=contingency)

@api.get("/admin/overview", tags=["administration"])
def admin_overview(db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    return {"users": db.query(User).count(), "destinations": db.query(Destination).count(),
            "vehicles": db.query(Vehicle).count(), "bookings": db.query(Booking).count(),
            "pending_vehicles": db.query(Vehicle).filter(Vehicle.verified.is_(False)).count(),
            "pending_bookings": db.query(Booking).filter(Booking.status == "requested").count()}


# Step 64 — customer tour package enquiry and provider request management
def _tour_request_payload(item: TourPackageRequest, db: Session):
    package=db.get(TourPackage,item.package_id); customer=db.get(User,item.customer_id)
    return {"id":item.id,"package_id":item.package_id,"package_title":package.title if package else "Tour package","package_slug":package.slug if package else "","destination":package.destination if package else "","customer_id":item.customer_id,"customer_name":customer.name if customer else "Traveller","customer_email":customer.email if customer else "","provider_id":item.provider_id,"start_date":item.start_date.isoformat(),"travellers":item.travellers,"contact_phone":item.contact_phone,"message":item.message,"status":item.status,"provider_note":item.provider_note,"created_at":item.created_at.isoformat() if item.created_at else None}

@api.post("/tour-packages/{slug}/requests", tags=["tour-package-requests"])
def create_tour_package_request(slug: str, data: TourPackageRequestIn, db: Session=Depends(get_db), user: User=Depends(current_user)):
    package=db.query(TourPackage).filter(TourPackage.slug==slug,TourPackage.is_published.is_(True)).first()
    if not package: raise HTTPException(404,"Tour package not found.")
    if data.start_date < date.today(): raise HTTPException(400,"Choose a future start date.")
    if data.travellers > package.max_travellers: raise HTTPException(400,f"This package accepts up to {package.max_travellers} travellers.")
    if package.provider_id==user.id: raise HTTPException(400,"You cannot request your own package.")
    item=TourPackageRequest(package_id=package.id,customer_id=user.id,provider_id=package.provider_id,start_date=data.start_date,travellers=data.travellers,contact_phone=data.contact_phone.strip(),message=data.message.strip())
    db.add(item); db.flush()
    add_preference_notification(db,package.provider_id,"booking_updates","New tour package request",f"{user.name} requested {package.title} for {data.travellers} traveller(s), starting {data.start_date.isoformat()}.")
    db.add(AuditLog(actor_id=user.id,action="tour_package_request_created",resource_type="tour_package_request",resource_id=item.id,details_json=json.dumps({"package_id":package.id})))
    db.commit(); db.refresh(item); return _tour_request_payload(item,db)

@api.get("/tour-package-requests/mine", tags=["tour-package-requests"])
def my_tour_package_requests(db: Session=Depends(get_db),user: User=Depends(current_user)):
    rows=db.query(TourPackageRequest).filter(TourPackageRequest.customer_id==user.id).order_by(TourPackageRequest.created_at.desc()).all(); return [_tour_request_payload(x,db) for x in rows]

@api.patch("/tour-package-requests/{request_id}/cancel", tags=["tour-package-requests"])
def cancel_my_tour_package_request(request_id: str,db: Session=Depends(get_db),user: User=Depends(current_user)):
    item=db.query(TourPackageRequest).filter(TourPackageRequest.id==request_id,TourPackageRequest.customer_id==user.id).first()
    if not item: raise HTTPException(404,"Tour package request not found.")
    if item.status not in ("requested","reviewing"): raise HTTPException(400,"This request can no longer be cancelled online.")
    item.status="cancelled"; db.add(AuditLog(actor_id=user.id,action="tour_package_request_cancelled",resource_type="tour_package_request",resource_id=item.id,details_json="{}")); db.commit(); db.refresh(item); return _tour_request_payload(item,db)

@api.get("/providers/me/tour-package-requests", tags=["tour-package-requests"])
def provider_tour_package_requests(status: str="",db: Session=Depends(get_db),user: User=Depends(require_roles("agency","owner","admin"))):
    query=db.query(TourPackageRequest).filter(TourPackageRequest.provider_id==user.id)
    if status.strip(): query=query.filter(TourPackageRequest.status==status.strip())
    rows=query.order_by(TourPackageRequest.created_at.desc()).all(); return [_tour_request_payload(x,db) for x in rows]

@api.patch("/providers/me/tour-package-requests/{request_id}", tags=["tour-package-requests"])
def update_provider_tour_package_request(request_id: str,data: TourPackageRequestUpdateIn,db: Session=Depends(get_db),user: User=Depends(require_roles("agency","owner","admin"))):
    item=db.query(TourPackageRequest).filter(TourPackageRequest.id==request_id,TourPackageRequest.provider_id==user.id).first()
    if not item: raise HTTPException(404,"Tour package request not found.")
    if item.status in ("declined","cancelled"): raise HTTPException(400,"This request is closed.")
    if item.status=="confirmed" and data.status not in ("confirmed","cancelled"): raise HTTPException(400,"A confirmed request can only remain confirmed or be cancelled.")
    item.status=data.status; item.provider_note=data.provider_note.strip(); package=db.get(TourPackage,item.package_id)
    add_preference_notification(db,item.customer_id,"booking_updates","Tour package request updated",f"Your request for {package.title if package else 'a tour package'} is now {item.status}. {item.provider_note}".strip())
    db.add(AuditLog(actor_id=user.id,action="tour_package_request_updated",resource_type="tour_package_request",resource_id=item.id,details_json=json.dumps({"status":item.status}))); db.commit(); db.refresh(item); return _tour_request_payload(item,db)
