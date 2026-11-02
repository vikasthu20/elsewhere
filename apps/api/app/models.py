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
    auth_token_version: Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    email_verified: Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
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

class EditorialContent(Base):
    __tablename__ = "editorial_contents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="guide", index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    destination_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
    stops_json: Mapped[str]=mapped_column(Text,default="[]")
    share_token: Mapped[str|None]=mapped_column(String(64),nullable=True,unique=True,index=True)
    share_enabled: Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    budget_json: Mapped[str]=mapped_column(Text,default="{}")
    expenses_json: Mapped[str]=mapped_column(Text,default="[]")
    receipts_json: Mapped[str]=mapped_column(Text,default="{}")
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

class VehicleAvailabilityBlock(Base):
    __tablename__ = "vehicle_availability_blocks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(180), nullable=False, default="Unavailable")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

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
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    integrity_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

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

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    booking_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payment_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trip_budget_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    support_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    marketing_updates: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationEmailLog(Base):
    __tablename__ = "notification_email_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    retry_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


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


class ProviderProfile(Base):
    __tablename__ = "provider_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    business_name: Mapped[str] = mapped_column(String(180), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    service_areas_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    pricing_notes: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TourPackage(Base):
    __tablename__ = "tour_packages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    destination: Mapped[str] = mapped_column(String(180), default="", index=True)
    duration_days: Mapped[int] = mapped_column(Integer, default=1)
    price_per_person: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    max_travellers: Mapped[int] = mapped_column(Integer, default=10)
    inclusions: Mapped[str] = mapped_column(Text, default="")
    exclusions: Mapped[str] = mapped_column(Text, default="")
    itinerary_json: Mapped[str] = mapped_column(Text, default="[]")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TourPackageRequest(Base):
    __tablename__ = "tour_package_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    package_id: Mapped[str] = mapped_column(ForeignKey("tour_packages.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    travellers: Mapped[int] = mapped_column(Integer, default=1)
    contact_phone: Mapped[str] = mapped_column(String(30), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="requested", index=True)
    provider_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TourPackagePayment(Base):
    __tablename__ = "tour_package_payments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    request_id: Mapped[str] = mapped_column(ForeignKey("tour_package_requests.id"), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    payment_method: Mapped[str] = mapped_column(String(24), default="manual_transfer")
    payment_reference: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(24), default="awaiting_payment", index=True)
    verified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TourPackagePayout(Base):
    __tablename__ = "tour_package_payouts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    payout_method: Mapped[str] = mapped_column(String(24), default="bank_transfer")
    account_holder: Mapped[str] = mapped_column(String(160), default="")
    bank_name: Mapped[str] = mapped_column(String(120), default="")
    account_last4: Mapped[str] = mapped_column(String(4), default="")
    status: Mapped[str] = mapped_column(String(24), default="requested", index=True)
    provider_note: Mapped[str] = mapped_column(Text, default="")
    admin_note: Mapped[str] = mapped_column(Text, default="")
    payout_reference: Mapped[str] = mapped_column(String(160), default="")
    processed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TourPackageInvoice(Base):
    __tablename__ = "tour_package_invoices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    payment_id: Mapped[str] = mapped_column(ForeignKey("tour_package_payments.id"), unique=True, index=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("tour_package_requests.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    package_title: Mapped[str] = mapped_column(String(200))
    destination: Mapped[str] = mapped_column(String(160), default="")
    customer_name: Mapped[str] = mapped_column(String(160), default="")
    customer_email: Mapped[str] = mapped_column(String(255), default="")
    provider_name: Mapped[str] = mapped_column(String(160), default="")
    start_date: Mapped[date] = mapped_column(Date)
    travellers: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2))
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2))
    total: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(20), default="issued")
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TourPackageTravelOperation(Base):
    __tablename__ = "tour_package_travel_operations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("tour_package_invoices.id"), unique=True, index=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("tour_package_requests.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="confirmed", index=True)
    meeting_point: Mapped[str] = mapped_column(String(300), default="")
    pickup_time: Mapped[str] = mapped_column(String(80), default="")
    emergency_contact: Mapped[str] = mapped_column(String(80), default="")
    provider_instructions: Mapped[str] = mapped_column(Text, default="")
    checklist_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TourPackageTravellerDocument(Base):
    __tablename__ = "tour_package_traveller_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    operation_id: Mapped[str] = mapped_column(ForeignKey("tour_package_travel_operations.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    traveller_name: Mapped[str] = mapped_column(String(160))
    document_type: Mapped[str] = mapped_column(String(30))
    document_number: Mapped[str] = mapped_column(String(100), default="")
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    encrypted_at_rest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retention_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reviewer_note: Mapped[str] = mapped_column(String(1000), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TourPackageDocumentLifecycleNotice(Base):
    __tablename__ = "tour_package_document_lifecycle_notices"
    __table_args__ = (UniqueConstraint("document_id", "notice_type", name="uq_tpd_lifecycle_notice"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    notice_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserPrivacyConsent(Base):
    __tablename__ = "user_privacy_consents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    essential_acknowledged: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    analytics_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    marketing_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserPrivacyRequest(Base):
    __tablename__ = "user_privacy_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    request_type: Mapped[str] = mapped_column(String(30), index=True)
    details: Mapped[str] = mapped_column(String(2000), default="")
    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True)
    admin_note: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrivacyRetentionPolicy(Base):
    __tablename__ = "privacy_retention_policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    data_category: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_basis_note: Mapped[str] = mapped_column(String(1000), default="")
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PrivacyRetentionRun(Base):
    __tablename__ = "privacy_retention_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    data_category: Mapped[str] = mapped_column(String(50), index=True)
    run_mode: Mapped[str] = mapped_column(String(20), default="dry_run")
    candidates: Mapped[int] = mapped_column(Integer, default=0)
    anonymized: Mapped[int] = mapped_column(Integer, default=0)
    run_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    details: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PrivacyProcessor(Base):
    __tablename__ = "privacy_processors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(180), index=True)
    service_description: Mapped[str] = mapped_column(String(1000), default="")
    data_categories: Mapped[str] = mapped_column(String(1000), default="")
    processing_purpose: Mapped[str] = mapped_column(String(1000), default="")
    country: Mapped[str] = mapped_column(String(120), default="")
    subprocessors: Mapped[str] = mapped_column(String(1000), default="")
    contract_reference: Mapped[str] = mapped_column(String(250), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PrivacyProcessingActivity(Base):
    __tablename__ = "privacy_processing_activities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    activity_name: Mapped[str] = mapped_column(String(180), index=True)
    purpose: Mapped[str] = mapped_column(String(1000), default="")
    data_subjects: Mapped[str] = mapped_column(String(500), default="")
    data_categories: Mapped[str] = mapped_column(String(1000), default="")
    lawful_basis: Mapped[str] = mapped_column(String(250), default="")
    retention_rule: Mapped[str] = mapped_column(String(500), default="")
    security_measures: Mapped[str] = mapped_column(String(1000), default="")
    processor_ids: Mapped[str] = mapped_column(String(2000), default="")
    owner_department: Mapped[str] = mapped_column(String(160), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PrivacyCrossBorderTransfer(Base):
    __tablename__ = "privacy_cross_border_transfers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    processor_id: Mapped[str | None] = mapped_column(ForeignKey("privacy_processors.id"), nullable=True, index=True)
    origin_country: Mapped[str] = mapped_column(String(120))
    destination_country: Mapped[str] = mapped_column(String(120))
    data_categories: Mapped[str] = mapped_column(String(1000), default="")
    transfer_purpose: Mapped[str] = mapped_column(String(1000), default="")
    transfer_mechanism: Mapped[str] = mapped_column(String(500), default="")
    safeguards_note: Mapped[str] = mapped_column(String(1500), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrivacyRiskAssessment(Base):
    __tablename__ = "privacy_risk_assessments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(180), index=True)
    processing_activity_id: Mapped[str | None] = mapped_column(ForeignKey("privacy_processing_activities.id"), nullable=True, index=True)
    assessment_type: Mapped[str] = mapped_column(String(40), default="DPIA")
    scope: Mapped[str] = mapped_column(Text, default="")
    necessity_proportionality: Mapped[str] = mapped_column(Text, default="")
    consultation_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    owner: Mapped[str] = mapped_column(String(160), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PrivacyRiskItem(Base):
    __tablename__ = "privacy_risk_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("privacy_risk_assessments.id", ondelete="CASCADE"), index=True)
    risk_description: Mapped[str] = mapped_column(Text)
    affected_people: Mapped[str] = mapped_column(String(500), default="")
    likelihood: Mapped[int] = mapped_column(Integer, default=3)
    impact: Mapped[int] = mapped_column(Integer, default=3)
    mitigation: Mapped[str] = mapped_column(Text, default="")
    mitigation_owner: Mapped[str] = mapped_column(String(160), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    mitigation_status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    residual_likelihood: Mapped[int | None] = mapped_column(Integer, nullable=True)
    residual_impact: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrivacySecurityIncident(Base):
    __tablename__ = "privacy_security_incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    status: Mapped[str] = mapped_column(String(30), default="reported", index=True)
    personal_data_involved: Mapped[bool] = mapped_column(Boolean, default=False)
    data_categories: Mapped[str] = mapped_column(Text, default="")
    affected_people_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jurisdictions: Mapped[str] = mapped_column(Text, default="")
    containment_actions: Mapped[str] = mapped_column(Text, default="")
    notification_assessment: Mapped[str] = mapped_column(Text, default="pending")
    notification_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notification_decision: Mapped[str] = mapped_column(Text, default="")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PrivacyIncidentEvidence(Base):
    __tablename__ = "privacy_incident_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(ForeignKey("privacy_security_incidents.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(Text)
    reference_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PrivacyIncidentPlaybook(Base):
    __tablename__ = "privacy_incident_playbooks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    incident_type: Mapped[str] = mapped_column(String(80), default="general")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    response_steps: Mapped[str] = mapped_column(Text, default="")
    escalation_roles: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PrivacyIncidentReview(Base):
    __tablename__ = "privacy_incident_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(ForeignKey("privacy_security_incidents.id", ondelete="CASCADE"), index=True)
    root_cause: Mapped[str] = mapped_column(Text, default="")
    impact_summary: Mapped[str] = mapped_column(Text, default="")
    response_effectiveness: Mapped[str] = mapped_column(Text, default="")
    lessons_learned: Mapped[str] = mapped_column(Text, default="")
    corrective_actions: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(160), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SecurityVulnerability(Base):
    __tablename__ = "security_vulnerabilities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(80), default="manual")
    affected_component: Mapped[str] = mapped_column(String(180), default="")
    affected_version: Mapped[str] = mapped_column(String(100), default="")
    cve_id: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="identified", index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remediation_summary: Mapped[str] = mapped_column(Text, default="")
    workaround: Mapped[str] = mapped_column(Text, default="")
    assigned_to: Mapped[str] = mapped_column(String(160), default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VulnerabilityRemediationEvent(Base):
    __tablename__ = "vulnerability_remediation_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    vulnerability_id: Mapped[str] = mapped_column(ForeignKey("security_vulnerabilities.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="low", index=True)
    source_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    request_path: Mapped[str] = mapped_column(String(300), default="")
    request_method: Mapped[str] = mapped_column(String(12), default="")
    response_status: Mapped[int] = mapped_column(Integer, default=0)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

class SecurityAlertRule(Base):
    __tablename__ = "security_alert_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    threshold: Mapped[int] = mapped_column(Integer, default=5)
    window_minutes: Mapped[int] = mapped_column(Integer, default=15)
    severity: Mapped[str] = mapped_column(String(20), default="high")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SecurityAlert(Base):
    __tablename__ = "security_alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    rule_id: Mapped[str | None] = mapped_column(ForeignKey("security_alert_rules.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="high", index=True)
    title: Mapped[str] = mapped_column(String(180))
    summary: Mapped[str] = mapped_column(Text, default="")
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AuditCheckpoint(Base):
    __tablename__ = "audit_checkpoints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    checkpoint_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signature: Mapped[str] = mapped_column(String(128), nullable=False)
    signing_key_id: Mapped[str] = mapped_column(String(80), nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    head_entry_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    report_json: Mapped[str] = mapped_column(Text, default="{}")


class AuditEvidenceArchive(Base):
    __tablename__ = "audit_evidence_archives"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    checkpoint_id: Mapped[str] = mapped_column(ForeignKey("audit_checkpoints.id"), nullable=False, index=True)
    storage_provider: Mapped[str] = mapped_column(String(30), nullable=False, default="s3")
    bucket_name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    object_version_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_etag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retention_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    object_lock_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    archive_status: Mapped[str] = mapped_column(String(30), nullable=False, default="stored")
    archived_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AuditArchiveJob(Base):
    __tablename__ = "audit_archive_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    checkpoint_id: Mapped[str] = mapped_column(ForeignKey("audit_checkpoints.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    archive_id: Mapped[str | None] = mapped_column(ForeignKey("audit_evidence_archives.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditComplianceRun(Base):
    __tablename__ = "audit_compliance_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    period_key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_id: Mapped[str | None] = mapped_column(ForeignKey("audit_checkpoints.id"), nullable=True)
    archive_job_id: Mapped[str | None] = mapped_column(ForeignKey("audit_archive_jobs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class SecurityAlertDelivery(Base):
    __tablename__ = "security_alert_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    alert_id: Mapped[str] = mapped_column(ForeignKey("security_alerts.id"), index=True)
    admin_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("alert_id", "admin_id", name="uq_security_alert_delivery_admin"),)


class SecurityNotificationDelivery(Base):
    __tablename__ = "security_notification_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    alert_id: Mapped[str] = mapped_column(ForeignKey("security_alerts.id"), index=True)
    admin_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(30), default="webhook")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    escalation_status: Mapped[str] = mapped_column(String(20), default="not_required", nullable=False)
    escalation_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    escalation_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("alert_id", "admin_id", "channel", name="uq_security_notification_alert_admin_channel"),)


class SecurityNotificationPreference(Base):
    __tablename__ = "security_notification_preferences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    admin_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    delivery_mode: Mapped[str] = mapped_column(String(20), default="parallel", nullable=False)
    channel_priority: Mapped[str] = mapped_column(String(60), default="email,sms,webhook", nullable=False)
    failover_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    severity_low: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    severity_medium: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    severity_high: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    severity_critical: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SecurityNotificationVerification(Base):
    __tablename__ = "security_notification_verifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    admin_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(10))
    destination: Mapped[str] = mapped_column(String(255))
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SecurityNotificationTemplate(Base):
    __tablename__ = "security_notification_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    channel: Mapped[str] = mapped_column(String(10), unique=True)
    subject_template: Mapped[str] = mapped_column(String(200), default="[{severity}] Elsewhere security alert")
    body_template: Mapped[str] = mapped_column(Text, default="{title} - {summary}")
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SecurityNotificationProviderHealth(Base):
    __tablename__ = "security_notification_provider_health"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
