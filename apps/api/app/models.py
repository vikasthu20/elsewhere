import enum, uuid
from datetime import datetime, date
from sqlalchemy import String, Boolean, DateTime, Date, Float, Integer, ForeignKey, Text, Enum, UniqueConstraint, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
def uid(): return str(uuid.uuid4())
class Role(str, enum.Enum): customer="customer"; owner="owner"; agency="agency"; staff="staff"; admin="admin"
class User(Base):
    __tablename__="users"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    name: Mapped[str]=mapped_column(String(120))
    email: Mapped[str]=mapped_column(String(255),unique=True,index=True)
    phone: Mapped[str|None]=mapped_column(String(30),nullable=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    role: Mapped[Role]=mapped_column(Enum(Role),default=Role.customer)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Destination(Base):
    __tablename__="destinations"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    name: Mapped[str]=mapped_column(String(160),index=True)
    region: Mapped[str]=mapped_column(String(160),default="India")
    category: Mapped[str]=mapped_column(String(80),default="destination")
    description: Mapped[str]=mapped_column(Text,default="")
    image_url: Mapped[str|None]=mapped_column(String(500),nullable=True)
    latitude: Mapped[float|None]=mapped_column(Float,nullable=True)
    longitude: Mapped[float|None]=mapped_column(Float,nullable=True)
    is_published: Mapped[bool]=mapped_column(Boolean,default=True)
class Itinerary(Base):
    __tablename__="itineraries"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    title: Mapped[str]=mapped_column(String(180))
    origin: Mapped[str]=mapped_column(String(180))
    destination: Mapped[str]=mapped_column(String(180))
    start_date: Mapped[date|None]=mapped_column(Date,nullable=True)
    days: Mapped[int]=mapped_column(Integer,default=1)
    travellers: Mapped[int]=mapped_column(Integer,default=1)
    interests: Mapped[str]=mapped_column(Text,default="")
    estimated_budget: Mapped[float]=mapped_column(Float,default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Vehicle(Base):
    __tablename__="vehicles"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    owner_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    title: Mapped[str]=mapped_column(String(180))
    category: Mapped[str]=mapped_column(String(60),index=True)
    make_model: Mapped[str]=mapped_column(String(120),default="")
    seats: Mapped[int]=mapped_column(Integer,default=4)
    price_per_day: Mapped[float]=mapped_column(Numeric(12, 2))
    city: Mapped[str]=mapped_column(String(120),index=True)
    description: Mapped[str]=mapped_column(Text,default="")
    image_url: Mapped[str|None]=mapped_column(String(500),nullable=True)
    verified: Mapped[bool]=mapped_column(Boolean,default=False)
    available: Mapped[bool]=mapped_column(Boolean,default=True)
class Booking(Base):
    __tablename__="bookings"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    customer_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    vehicle_id: Mapped[str]=mapped_column(ForeignKey("vehicles.id"),index=True)
    start_date: Mapped[date]=mapped_column(Date)
    end_date: Mapped[date]=mapped_column(Date)
    pickup_location: Mapped[str]=mapped_column(String(180))
    total_amount: Mapped[float]=mapped_column(Numeric(12, 2))
    status: Mapped[str]=mapped_column(String(30),default="requested")
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Review(Base):
    __tablename__="reviews"
    __table_args__=(UniqueConstraint("booking_id",name="uq_review_booking"),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    booking_id: Mapped[str]=mapped_column(ForeignKey("bookings.id"))
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"))
    rating: Mapped[int]=mapped_column(Integer)
    comment: Mapped[str]=mapped_column(Text,default="")
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)


# Operational modules added in the Elsewhere platform continuation.
from sqlalchemy import CheckConstraint

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(20), default="in_app")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Driver(Base):
    __tablename__ = "drivers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30))
    licence_number: Mapped[str] = mapped_column(String(80), unique=True)
    licence_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class DriverAssignment(Base):
    __tablename__ = "driver_assignments"
    __table_args__ = (UniqueConstraint("booking_id", name="uq_driver_assignment_booking"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), index=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), index=True)
    assigned_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class VehicleMaintenance(Base):
    __tablename__ = "vehicle_maintenance"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    service_date: Mapped[date] = mapped_column(Date)
    next_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")

class PaymentRecord(Base):
    __tablename__ = "payment_records"
    __table_args__ = (
        UniqueConstraint("provider", "provider_reference", name="uq_payment_provider_reference"),
        CheckConstraint("amount >= 0", name="ck_payment_amount_nonnegative"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="unconfigured")
    provider_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    destination: Mapped[str] = mapped_column(String(255), index=True)
    purpose: Mapped[str] = mapped_column(String(40), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PrivateDocument(Base):
    __tablename__ = "private_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(60))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    scan_status: Mapped[str] = mapped_column(String(24), default="pending")
    verification_status: Mapped[str] = mapped_column(String(24), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
