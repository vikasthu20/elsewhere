from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=30)
    role: str = "customer"

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class VehicleIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=2, max_length=60)
    make_model: str = Field(default="", max_length=120)
    seats: int = Field(default=4, ge=1, le=100)
    price_per_day: float = Field(gt=0, le=1000000)
    city: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=4000)
    image_url: Optional[str] = Field(default=None, max_length=500)

class ItineraryIn(BaseModel):
    origin: str = Field(min_length=2, max_length=180)
    destination: str = Field(min_length=2, max_length=180)
    start_date: Optional[date] = None
    days: int = Field(default=1, ge=1, le=60)
    travellers: int = Field(default=1, ge=1, le=100)
    interests: str = Field(default="", max_length=1000)
    estimated_budget: float = Field(default=0, ge=0, le=100000000)

class BookingIn(BaseModel):
    vehicle_id: str
    start_date: date
    end_date: date
    pickup_location: str = Field(min_length=2, max_length=180)

class BookingStatusIn(BaseModel):
    status: str = Field(pattern="^(confirmed|rejected|cancelled|completed)$")

class ReviewIn(BaseModel):
    booking_id: str
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=3000)


class ProviderProfileIn(BaseModel):
    business_name: str = Field(default="", max_length=180)
    description: str = Field(default="", max_length=12000)
    contact_phone: str | None = Field(default=None, max_length=30)
    website_url: str | None = Field(default=None, max_length=500)
    address: str = Field(default="", max_length=300)
    service_areas: list[str] = Field(default_factory=list, max_length=50)
    pricing_notes: str = Field(default="", max_length=1000)


class TourPackageIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=12000)
    destination: str = Field(default="", max_length=180)
    duration_days: int = Field(default=1, ge=1, le=365)
    price_per_person: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    max_travellers: int = Field(default=10, ge=1, le=500)
    inclusions: list[str] = Field(default_factory=list, max_length=100)
    exclusions: list[str] = Field(default_factory=list, max_length=100)
    itinerary: list[dict] = Field(default_factory=list, max_length=100)
    image_url: str | None = Field(default=None, max_length=500)
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")


class SupportTicketIn(BaseModel):
    subject: str = Field(min_length=4, max_length=180)
    message: str = Field(min_length=10, max_length=10000)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")

    @field_validator("subject", "message", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

class TicketUpdateIn(BaseModel):
    status: str = Field(pattern="^(open|in_progress|waiting_customer|resolved|closed)$")
    resolution: str | None = Field(default=None, max_length=10000)
    assigned_to: str | None = None

class DriverIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    licence_number: str = Field(min_length=4, max_length=80)
    licence_expiry: date | None = None

class DriverAssignmentIn(BaseModel):
    driver_id: str

class MaintenanceIn(BaseModel):
    description: str = Field(min_length=5, max_length=4000)
    service_date: date
    next_service_date: date | None = None
    cost: float = Field(default=0, ge=0, le=100000000)
    status: str = Field(default="scheduled", pattern="^(scheduled|in_progress|completed|cancelled)$")

class RefundRequestIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)

class AdminVehicleVerificationIn(BaseModel):
    verified: bool
    note: str = Field(default="", max_length=1000)

class DocumentMetadataIn(BaseModel):
    document_type: str = Field(min_length=2, max_length=60)
    original_name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=120)
    size_bytes: int = Field(gt=0, le=15 * 1024 * 1024)


class OtpRequestIn(BaseModel):
    destination: str = Field(min_length=5, max_length=255)
    purpose: str = Field(pattern="^(verify_contact|password_reset)$")

class PasswordResetIn(BaseModel):
    destination: str = Field(min_length=5, max_length=255)
    code: str = Field(pattern="^[0-9]{6}$")
    new_password: str = Field(min_length=10, max_length=128)


class TourPackageRequestIn(BaseModel):
    start_date: date
    travellers: int = Field(ge=1, le=500)
    contact_phone: str = Field(min_length=7, max_length=30)
    message: str = Field(default="", max_length=2000)

class TourPackageRequestUpdateIn(BaseModel):
    status: str = Field(pattern="^(reviewing|confirmed|declined|cancelled)$")
    provider_note: str = Field(default="", max_length=2000)


class TourPackagePaymentReferenceIn(BaseModel):
    payment_reference: str = Field(min_length=4, max_length=160)

class TourPackagePaymentDecisionIn(BaseModel):
    status: str = Field(pattern="^(paid|rejected)$")
    note: str = Field(default="", max_length=1000)


class TourPackagePayoutRequestIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    account_holder: str = Field(min_length=2, max_length=160)
    bank_name: str = Field(min_length=2, max_length=120)
    account_last4: str = Field(pattern="^[0-9]{4}$")
    provider_note: str = Field(default="", max_length=1000)


class TourPackagePayoutDecisionIn(BaseModel):
    status: str = Field(pattern="^(processing|paid|rejected)$")
    payout_reference: str = Field(default="", max_length=160)
    admin_note: str = Field(default="", max_length=1000)
