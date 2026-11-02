"""Owner, traveller and administrator operational workflows."""
from datetime import datetime, date
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db import get_db
from app.models import (User, Booking, Vehicle, SupportTicket, Notification, Driver,
                        DriverAssignment, VehicleMaintenance, PaymentRecord, AuditLog,
                        PrivateDocument, OtpChallenge)
from app.schemas import (SupportTicketIn, TicketUpdateIn, DriverIn, DriverAssignmentIn,
                         MaintenanceIn, RefundRequestIn, AdminVehicleVerificationIn,
                         DocumentMetadataIn)
from app.security import current_user, require_roles, hash_password
from app.core.config import settings
from app.services.operations import (audit, document_is_allowed, make_otp, hash_otp,
                                      verify_otp, otp_expiry, create_payment_intent)

router = APIRouter()

def _owner_vehicle(db, vehicle_id, user):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or (vehicle.owner_id != user.id and user.role.value != "admin"):
        raise HTTPException(404, "Vehicle not found")
    return vehicle

@router.post("/support/tickets", status_code=201, tags=["support"])
def create_ticket(data: SupportTicketIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    ticket = SupportTicket(user_id=user.id, subject=data.subject, message=data.message, priority=data.priority)
    db.add(ticket); db.flush()
    audit(db, user.id, "support.ticket.created", "support_ticket", ticket.id)
    db.commit(); db.refresh(ticket)
    return {"id": ticket.id, "status": ticket.status, "created_at": ticket.created_at}

@router.get("/support/tickets/mine", tags=["support"])
def my_tickets(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(SupportTicket).filter(SupportTicket.user_id == user.id).order_by(desc(SupportTicket.created_at)).all()
    return [{"id": x.id, "subject": x.subject, "status": x.status, "priority": x.priority,
             "resolution": x.resolution, "created_at": x.created_at} for x in rows]

@router.get("/admin/support/tickets", tags=["administration", "support"])
def admin_tickets(status: str | None = None, db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin", "staff"))):
    q = db.query(SupportTicket)
    if status: q = q.filter(SupportTicket.status == status)
    return [{"id": x.id, "user_id": x.user_id, "subject": x.subject, "message": x.message,
             "status": x.status, "priority": x.priority, "assigned_to": x.assigned_to} for x in q.order_by(desc(SupportTicket.created_at)).all()]

@router.patch("/admin/support/tickets/{ticket_id}", tags=["administration", "support"])
def update_ticket(ticket_id: str, data: TicketUpdateIn, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin", "staff"))):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket: raise HTTPException(404, "Ticket not found")
    if data.assigned_to and not db.get(User, data.assigned_to): raise HTTPException(404, "Assignee not found")
    ticket.status, ticket.resolution, ticket.assigned_to = data.status, data.resolution, data.assigned_to
    audit(db, admin.id, "support.ticket.updated", "support_ticket", ticket.id, {"status": data.status})
    db.commit()
    return {"id": ticket.id, "status": ticket.status}

@router.get("/notifications/mine", tags=["notifications"])
def notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Notification).filter(Notification.user_id == user.id).order_by(desc(Notification.created_at)).limit(100).all()
    return [{"id": n.id, "title": n.title, "body": n.body, "channel": n.channel,
             "read_at": n.read_at, "created_at": n.created_at} for n in rows]

@router.post("/notifications/{notification_id}/read", tags=["notifications"])
def mark_notification_read(notification_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user.id).first()
    if not item: raise HTTPException(404, "Notification not found")
    item.read_at = datetime.utcnow(); db.commit()
    return {"id": item.id, "read": True}

@router.post("/owner/drivers", status_code=201, tags=["owner"])
def add_driver(data: DriverIn, db: Session = Depends(get_db), user: User = Depends(require_roles("owner", "agency", "admin"))):
    if db.query(Driver).filter(Driver.licence_number == data.licence_number).first():
        raise HTTPException(409, "Driver licence already exists")
    driver = Driver(owner_id=user.id, **data.model_dump())
    db.add(driver); db.flush(); audit(db, user.id, "driver.created", "driver", driver.id); db.commit(); db.refresh(driver)
    return {"id": driver.id, "name": driver.name, "active": driver.active}

@router.get("/owner/drivers", tags=["owner"])
def list_drivers(db: Session = Depends(get_db), user: User = Depends(require_roles("owner", "agency", "admin"))):
    rows = db.query(Driver).filter(Driver.owner_id == user.id).all()
    return [{"id": d.id, "name": d.name, "phone": d.phone, "licence_expiry": d.licence_expiry, "active": d.active} for d in rows]

@router.post("/owner/bookings/{booking_id}/driver", tags=["owner"])
def assign_driver(booking_id: str, data: DriverAssignmentIn, db: Session = Depends(get_db), user: User = Depends(require_roles("owner", "agency", "admin"))):
    booking = db.query(Booking).join(Vehicle, Booking.vehicle_id == Vehicle.id).filter(
        Booking.id == booking_id, Vehicle.owner_id == user.id).first()
    driver = db.query(Driver).filter(Driver.id == data.driver_id, Driver.owner_id == user.id, Driver.active.is_(True)).first()
    if not booking or not driver: raise HTTPException(404, "Booking or active driver not found")
    assignment = db.query(DriverAssignment).filter(DriverAssignment.booking_id == booking.id).first()
    if assignment: assignment.driver_id = driver.id
    else:
        assignment = DriverAssignment(booking_id=booking.id, driver_id=driver.id, assigned_by=user.id); db.add(assignment)
    audit(db, user.id, "booking.driver.assigned", "booking", booking.id, {"driver_id": driver.id})
    db.commit()
    return {"booking_id": booking.id, "driver_id": driver.id}

@router.post("/owner/vehicles/{vehicle_id}/maintenance", status_code=201, tags=["owner"])
def add_maintenance(vehicle_id: str, data: MaintenanceIn, db: Session = Depends(get_db), user: User = Depends(require_roles("owner", "agency", "admin"))):
    vehicle = _owner_vehicle(db, vehicle_id, user)
    item = VehicleMaintenance(vehicle_id=vehicle.id, owner_id=user.id, **data.model_dump())
    db.add(item); db.flush(); audit(db, user.id, "vehicle.maintenance.created", "vehicle", vehicle.id); db.commit(); db.refresh(item)
    return {"id": item.id, "status": item.status, "service_date": item.service_date}

@router.get("/owner/vehicles/{vehicle_id}/maintenance", tags=["owner"])
def list_maintenance(vehicle_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("owner", "agency", "admin"))):
    vehicle = _owner_vehicle(db, vehicle_id, user)
    rows = db.query(VehicleMaintenance).filter(VehicleMaintenance.vehicle_id == vehicle.id).order_by(desc(VehicleMaintenance.service_date)).all()
    return [{"id": x.id, "description": x.description, "service_date": x.service_date,
             "next_service_date": x.next_service_date, "cost": float(x.cost), "status": x.status} for x in rows]

@router.patch("/admin/vehicles/{vehicle_id}/verification", tags=["administration"])
def verify_vehicle(vehicle_id: str, data: AdminVehicleVerificationIn, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle: raise HTTPException(404, "Vehicle not found")
    vehicle.verified = data.verified
    audit(db, admin.id, "vehicle.verification.changed", "vehicle", vehicle.id, {"verified": data.verified, "note": data.note})
    db.commit()
    return {"id": vehicle.id, "verified": vehicle.verified}

@router.get("/admin/audit-logs", tags=["administration"])
def audit_logs(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    rows = db.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit).all()
    return [{"id": x.id, "actor_id": x.actor_id, "action": x.action, "resource_type": x.resource_type,
             "resource_id": x.resource_id, "details": x.details_json, "created_at": x.created_at} for x in rows]

@router.post("/documents/metadata", status_code=201, tags=["documents"])
def register_document(data: DocumentMetadataIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not document_is_allowed(data.original_name, data.mime_type, data.size_bytes):
        raise HTTPException(415, "Unsupported document type or size")
    # This endpoint records metadata only. Private binary upload and malware scanning need a configured storage/scanner adapter.
    key = f"pending/{user.id}/{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}/{Path(data.original_name).name}"
    item = PrivateDocument(owner_id=user.id, document_type=data.document_type, storage_key=key,
                           original_name=Path(data.original_name).name, mime_type=data.mime_type,
                           size_bytes=data.size_bytes, scan_status="not_uploaded")
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "upload_status": "storage_provider_not_configured", "scan_status": item.scan_status}

@router.post("/bookings/{booking_id}/payment-intent", tags=["payments"])
def payment_intent(booking_id: str, idempotency_key: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    booking = db.get(Booking, booking_id)
    if not booking or booking.customer_id != user.id: raise HTTPException(404, "Booking not found")
    existing = db.query(PaymentRecord).filter(PaymentRecord.idempotency_key == idempotency_key).first()
    if existing: return {"id": existing.id, "status": existing.status, "provider": existing.provider}
    result = create_payment_intent(provider=settings.payment_provider, booking_id=booking.id,
                                   amount=booking.total_amount, currency="INR", idempotency_key=idempotency_key)
    if result["status"] == "provider_not_configured":
        raise HTTPException(503, "Payment provider is not configured; no payment has been attempted")
    return result

@router.post("/bookings/{booking_id}/refund-request", tags=["payments"])
def refund_request(booking_id: str, data: RefundRequestIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    booking = db.get(Booking, booking_id)
    if not booking or booking.customer_id != user.id: raise HTTPException(404, "Booking not found")
    if booking.status not in {"cancelled", "rejected"}: raise HTTPException(409, "Only cancelled or rejected bookings can request a refund")
    ticket = SupportTicket(user_id=user.id, subject=f"Refund request for booking {booking.id}",
                           message=data.reason, priority="high")
    db.add(ticket); audit(db, user.id, "booking.refund.requested", "booking", booking.id)
    db.commit()
    return {"ticket_id": ticket.id, "status": "refund_review_required"}


@router.post("/auth/otp/request", tags=["authentication"])
def request_otp(data: OtpRequestIn, db: Session = Depends(get_db)):
    # A production delivery adapter (email/SMS) must be configured before this endpoint can send externally.
    code = make_otp()
    challenge = OtpChallenge(destination=data.destination.strip().lower(), purpose=data.purpose,
                             code_hash=hash_otp(code, settings.otp_secret), expires_at=otp_expiry(5))
    db.add(challenge); db.commit()
    response = {"status": "created", "expires_in_seconds": 300}
    if settings.otp_delivery_mode == "console":
        response["development_code"] = code
    else:
        response["delivery_status"] = "provider_not_configured"
    return response

@router.post("/auth/password-reset", tags=["authentication"])
def reset_password(data: PasswordResetIn, db: Session = Depends(get_db)):
    destination = data.destination.strip().lower()
    challenge = db.query(OtpChallenge).filter(
        OtpChallenge.destination == destination, OtpChallenge.purpose == "password_reset",
        OtpChallenge.consumed_at.is_(None)).order_by(desc(OtpChallenge.created_at)).first()
    if not challenge or challenge.expires_at < datetime.utcnow() or challenge.attempts >= 5:
        raise HTTPException(400, "Invalid or expired reset code")
    challenge.attempts += 1
    if not verify_otp(data.code, challenge.code_hash, settings.otp_secret):
        db.commit(); raise HTTPException(400, "Invalid or expired reset code")
    user = db.query(User).filter(User.email == destination).first()
    if not user:
        db.commit(); raise HTTPException(400, "Invalid or expired reset code")
    user.password_hash = hash_password(data.new_password)
    challenge.consumed_at = datetime.utcnow()
    audit(db, user.id, "auth.password.reset", "user", user.id)
    db.commit()
    return {"status": "password_reset"}

@router.post("/bookings/{booking_id}/cancel", tags=["bookings"])
def cancel_booking(booking_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.customer_id == user.id).first()
    if not booking: raise HTTPException(404, "Booking not found")
    if booking.status not in {"requested", "confirmed"}:
        raise HTTPException(409, "This booking cannot be cancelled")
    booking.status = "cancelled"
    audit(db, user.id, "booking.cancelled", "booking", booking.id)
    db.commit()
    return {"id": booking.id, "status": booking.status, "refund_status": "review_required"}
