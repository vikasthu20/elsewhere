"""Owner, traveller and administrator operational workflows."""
from datetime import datetime, date
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from app.db import get_db
from app.models import (User, Role, Booking, Vehicle, SupportTicket, Notification, Driver,
                        DriverAssignment, VehicleMaintenance, PaymentRecord, AuditLog,
                        PrivateDocument, OtpChallenge, NotificationPreference,
                        NotificationEmailLog, VehicleAvailabilityBlock, Review)
from app.models import RefundRequest
from app.schemas import (SupportTicketIn, TicketUpdateIn, DriverIn, DriverAssignmentIn,
                         MaintenanceIn, RefundRequestIn, AdminVehicleVerificationIn,
                         DocumentMetadataIn, OtpRequestIn, PasswordResetIn)
from app.security import current_user, require_roles, hash_password
from app.core.config import settings
from app.services.operations import (audit, document_is_allowed, make_otp, hash_otp,
                                      verify_otp, otp_expiry, create_payment_intent)

router = APIRouter()

class NotificationPreferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_updates: bool = True
    payment_updates: bool = True
    trip_budget_alerts: bool = True
    support_updates: bool = True
    marketing_updates: bool = False
    email_enabled: bool = False
    # GET responses include this read-only field, so clients may safely PUT
    # the returned representation while the server remains authoritative.
    updated_at: datetime | None = None

class AvailabilityBlockIn(BaseModel):
    start_date: date
    end_date: date
    reason: str = "Unavailable"

def _notification_preferences(row=None):
    return {
        "booking_updates": row.booking_updates if row else True,
        "payment_updates": row.payment_updates if row else True,
        "trip_budget_alerts": row.trip_budget_alerts if row else True,
        "support_updates": row.support_updates if row else True,
        "marketing_updates": row.marketing_updates if row else False,
        "email_enabled": row.email_enabled if row else False,
        "updated_at": row.updated_at if row else None,
    }

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
def admin_tickets(status: str = "all", priority: str = "all", q: str = "",
                  page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin", "staff"))):
    query = db.query(SupportTicket, User).join(User, SupportTicket.user_id == User.id)
    if status != "all": query = query.filter(SupportTicket.status == status)
    if priority != "all": query = query.filter(SupportTicket.priority == priority)
    if q.strip():
        like=f"%{q.strip()}%"
        query=query.filter(or_(SupportTicket.subject.ilike(like),SupportTicket.message.ilike(like),User.name.ilike(like),User.email.ilike(like)))
    total=query.count();rows=query.order_by(desc(SupportTicket.created_at)).offset((page-1)*page_size).limit(page_size).all()
    items=[{"id":ticket.id,"user_id":ticket.user_id,"customer_name":customer.name,"customer_email":customer.email,
      "subject":ticket.subject,"message":ticket.message,"status":ticket.status,"priority":ticket.priority,
      "assigned_to":ticket.assigned_to,"resolution":ticket.resolution,"created_at":ticket.created_at,
      "updated_at":ticket.updated_at} for ticket,customer in rows]
    staff=[{"id":user.id,"name":user.name,"role":user.role.value} for user in db.query(User).filter(User.role.in_([Role.staff,Role.admin]),User.is_active.is_(True)).order_by(User.name).all()]
    return {"items":items,"staff":staff,"total":total,"page":page,"pages":max(1,(total+page_size-1)//page_size)}

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

@router.get("/notifications/unread-count", tags=["notifications"])
def unread_notification_count(db: Session = Depends(get_db), user: User = Depends(current_user)):
    count = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    ).count()
    return {"unread_count": count}

@router.get("/notifications/preferences", tags=["notifications"])
def get_notification_preferences(db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.query(NotificationPreference).filter(NotificationPreference.user_id == user.id).first()
    return _notification_preferences(row)

@router.put("/notifications/preferences", tags=["notifications"])
def update_notification_preferences(data: NotificationPreferenceIn, db: Session = Depends(get_db),
                                    user: User = Depends(current_user)):
    row = db.query(NotificationPreference).filter(NotificationPreference.user_id == user.id).first()
    if row is None:
        row = NotificationPreference(user_id=user.id)
        db.add(row)
    for key, value in data.model_dump(exclude={"updated_at"}).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _notification_preferences(row)

@router.get("/notifications/email-deliveries", tags=["notifications"])
def notification_email_deliveries(limit: int = Query(50, ge=1, le=100),
                                  db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(NotificationEmailLog).filter(
        NotificationEmailLog.user_id == user.id
    ).order_by(desc(NotificationEmailLog.created_at)).limit(limit).all()
    return {"items": [{
        "id": row.id, "subject": row.subject, "category": row.category,
        "status": row.status, "error_message": row.error_message,
        "sent_at": row.sent_at, "created_at": row.created_at,
    } for row in rows]}

@router.post("/notifications/{notification_id}/read", tags=["notifications"])
@router.patch("/notifications/{notification_id}/read", tags=["notifications"])
def mark_notification_read(notification_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user.id).first()
    if not item: raise HTTPException(404, "Notification not found")
    item.read_at = datetime.utcnow(); db.commit()
    return {"id": item.id, "read": True}

@router.patch("/notifications/{notification_id}/unread", tags=["notifications"])
def mark_notification_unread(notification_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.query(Notification).filter(Notification.id == notification_id,
                                         Notification.user_id == user.id).first()
    if not item: raise HTTPException(404, "Notification not found")
    item.read_at = None; db.commit()
    return {"id": item.id, "read": False}

@router.patch("/notifications/read-all", tags=["notifications"])
def mark_all_notifications_read(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Notification).filter(Notification.user_id == user.id,
                                         Notification.read_at.is_(None)).all()
    stamp = datetime.utcnow()
    for item in rows: item.read_at = stamp
    db.commit()
    return {"updated": len(rows)}

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

@router.patch("/owner/drivers/{driver_id}/status", tags=["owner"])
def set_driver_status(driver_id: str, active: bool, db: Session = Depends(get_db),
                      user: User = Depends(require_roles("owner", "agency", "admin"))):
    driver = db.query(Driver).filter(Driver.id == driver_id, Driver.owner_id == user.id).first()
    if not driver: raise HTTPException(404, "Driver not found")
    driver.active = active
    audit(db, user.id, "driver.status.changed", "driver", driver.id, {"active": active})
    db.commit()
    return {"id": driver.id, "active": driver.active}

@router.get("/owner/reputation", tags=["owner"])
def owner_reputation(db: Session = Depends(get_db), user: User = Depends(require_roles("owner", "agency", "admin"))):
    vehicles = db.query(Vehicle).filter(Vehicle.owner_id == user.id).order_by(Vehicle.title).all()
    results = []
    weighted_rating = 0.0
    review_count = 0
    for vehicle in vehicles:
        avg_rating, count = db.query(func.avg(Review.rating), func.count(Review.id)).join(
            Booking, Review.booking_id == Booking.id
        ).filter(Booking.vehicle_id == vehicle.id).first()
        count = int(count or 0)
        avg_rating = round(float(avg_rating), 2) if avg_rating is not None else None
        if avg_rating is not None: weighted_rating += avg_rating * count
        review_count += count
        results.append({"vehicle_id": vehicle.id, "vehicle_title": vehicle.title,
                        "average_rating": avg_rating, "review_count": count})
    return {"average_rating": round(weighted_rating / review_count, 2) if review_count else None,
            "review_count": review_count, "vehicle_count": len(vehicles), "vehicles": results}

@router.get("/owner/vehicles/{vehicle_id}/availability-blocks", tags=["owner"])
def list_availability_blocks(vehicle_id: str, db: Session = Depends(get_db),
                             user: User = Depends(require_roles("owner", "agency", "admin"))):
    vehicle = _owner_vehicle(db, vehicle_id, user)
    rows = db.query(VehicleAvailabilityBlock).filter(
        VehicleAvailabilityBlock.vehicle_id == vehicle.id
    ).order_by(VehicleAvailabilityBlock.start_date).all()
    return [{"id": row.id, "vehicle_id": row.vehicle_id,
             "start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat(),
             "reason": row.reason} for row in rows]

@router.post("/owner/vehicles/{vehicle_id}/availability-blocks", status_code=201, tags=["owner"])
def create_availability_block(vehicle_id: str, data: AvailabilityBlockIn, db: Session = Depends(get_db),
                              user: User = Depends(require_roles("owner", "agency", "admin"))):
    vehicle = _owner_vehicle(db, vehicle_id, user)
    if data.end_date < data.start_date: raise HTTPException(422, "End date must be on or after start date")
    reason = data.reason.strip()
    if not reason or len(reason) > 180: raise HTTPException(422, "Reason is required and must be 180 characters or fewer")
    row = VehicleAvailabilityBlock(vehicle_id=vehicle.id, owner_id=user.id,
                                  start_date=data.start_date, end_date=data.end_date, reason=reason)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "vehicle_id": row.vehicle_id, "start_date": row.start_date.isoformat(),
            "end_date": row.end_date.isoformat(), "reason": row.reason}

@router.delete("/owner/vehicles/{vehicle_id}/availability-blocks/{block_id}", tags=["owner"])
def delete_availability_block(vehicle_id: str, block_id: str, db: Session = Depends(get_db),
                              user: User = Depends(require_roles("owner", "agency", "admin"))):
    vehicle = _owner_vehicle(db, vehicle_id, user)
    row = db.query(VehicleAvailabilityBlock).filter(
        VehicleAvailabilityBlock.id == block_id, VehicleAvailabilityBlock.vehicle_id == vehicle.id
    ).first()
    if not row: raise HTTPException(404, "Availability block not found")
    db.delete(row); db.commit()
    return {"id": block_id, "deleted": True}

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

@router.patch("/owner/vehicles/{vehicle_id}/maintenance/{maintenance_id}", tags=["owner"])
def update_maintenance(vehicle_id: str, maintenance_id: str, data: MaintenanceIn,
                       db: Session = Depends(get_db), user: User = Depends(require_roles("owner", "agency", "admin"))):
    vehicle = _owner_vehicle(db, vehicle_id, user)
    item = db.query(VehicleMaintenance).filter(
        VehicleMaintenance.id == maintenance_id, VehicleMaintenance.vehicle_id == vehicle.id
    ).first()
    if not item: raise HTTPException(404, "Maintenance record not found")
    for key, value in data.model_dump().items(): setattr(item, key, value)
    audit(db, user.id, "vehicle.maintenance.updated", "vehicle_maintenance", item.id)
    db.commit()
    return {"id": item.id, "status": item.status, "service_date": item.service_date}

@router.delete("/owner/vehicles/{vehicle_id}/maintenance/{maintenance_id}", tags=["owner"])
def delete_maintenance(vehicle_id: str, maintenance_id: str, db: Session = Depends(get_db),
                       user: User = Depends(require_roles("owner", "agency", "admin"))):
    vehicle = _owner_vehicle(db, vehicle_id, user)
    item = db.query(VehicleMaintenance).filter(
        VehicleMaintenance.id == maintenance_id, VehicleMaintenance.vehicle_id == vehicle.id
    ).first()
    if not item: raise HTTPException(404, "Maintenance record not found")
    db.delete(item); db.commit()
    return {"id": maintenance_id, "deleted": True}

@router.patch("/admin/vehicles/{vehicle_id}/verification", tags=["administration"])
def verify_vehicle(vehicle_id: str, data: AdminVehicleVerificationIn, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle: raise HTTPException(404, "Vehicle not found")
    vehicle.verified = data.verified
    audit(db, admin.id, "vehicle.verification.changed", "vehicle", vehicle.id, {"verified": data.verified, "note": data.note})
    db.commit()
    return {"id": vehicle.id, "verified": vehicle.verified}

@router.get("/admin/audit-logs", tags=["administration"])
def audit_logs(q: str = "", action: str = "all", resource_type: str = "all", actor_id: str = "all",
               from_date: date | None = None, to_date: date | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
               db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    query=db.query(AuditLog)
    if action!="all":query=query.filter(AuditLog.action==action)
    if resource_type!="all":query=query.filter(AuditLog.resource_type==resource_type)
    if actor_id!="all":query=query.filter(AuditLog.actor_id==actor_id)
    if from_date:query=query.filter(AuditLog.created_at>=datetime.combine(from_date,datetime.min.time()))
    if to_date:query=query.filter(AuditLog.created_at<datetime.combine(to_date,datetime.max.time()))
    if q.strip():
        like=f"%{q.strip()}%";query=query.filter(or_(AuditLog.action.ilike(like),AuditLog.resource_type.ilike(like),AuditLog.resource_id.ilike(like),AuditLog.details_json.ilike(like)))
    total=query.count();rows=query.order_by(desc(AuditLog.created_at)).offset((page-1)*page_size).limit(page_size).all()
    items=[]
    for row in rows:
        actor=db.get(User,row.actor_id) if row.actor_id else None
        try:details=json.loads(row.details_json or "{}")
        except (TypeError,ValueError):details={"raw":row.details_json}
        items.append({"id":row.id,"actor_id":row.actor_id,"actor_name":actor.name if actor else "System",
          "actor_email":actor.email if actor else "","action":row.action,"resource_type":row.resource_type,
          "resource_id":row.resource_id,"details":details,"created_at":row.created_at})
    filters={"actions":[x[0] for x in db.query(AuditLog.action).distinct().order_by(AuditLog.action).all()],
      "resource_types":[x[0] for x in db.query(AuditLog.resource_type).distinct().order_by(AuditLog.resource_type).all()],
      "actors":[{"id":u.id,"name":u.name} for u in db.query(User).join(AuditLog,AuditLog.actor_id==User.id).distinct().order_by(User.name).all()]}
    return {"items":items,"filters":filters,"total":total,"page":page,"pages":max(1,(total+page_size-1)//page_size)}

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

@router.post("/payments/verify", tags=["payments"])
def verify_booking_payment(data: dict, _user: User = Depends(current_user)):
    if not all(data.get(key) for key in ("razorpay_order_id", "razorpay_payment_id", "razorpay_signature")):
        raise HTTPException(422, "Payment verification fields are required")
    # A payment is only marked successful after signature verification by the
    # configured provider adapter. This deployment has no such adapter.
    raise HTTPException(503, "Payment verification is not configured; payment status was not changed")

@router.post("/bookings/{booking_id}/refund-request", tags=["payments"])
def refund_request(booking_id: str, data: RefundRequestIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    booking = db.get(Booking, booking_id)
    if not booking or booking.customer_id != user.id: raise HTTPException(404, "Booking not found")
    if booking.status not in {"cancelled", "rejected"}: raise HTTPException(409, "Only cancelled or rejected bookings can request a refund")
    prior = db.query(RefundRequest).filter(RefundRequest.booking_id == booking.id,
                                           RefundRequest.customer_id == user.id).order_by(desc(RefundRequest.created_at)).first()
    if prior and prior.status in {"pending", "approved", "processing"}:
        raise HTTPException(409, "A refund request is already active for this booking")
    item = RefundRequest(booking_id=booking.id, customer_id=user.id, reason=data.reason.strip(), amount=booking.total_amount)
    db.add(item); audit(db, user.id, "booking.refund.requested", "refund_request", item.id, {"booking_id": booking.id})
    db.commit()
    return {"id": item.id, "booking_id": booking.id, "status": item.status}

@router.get("/refund-requests/mine", tags=["payments"])
def my_refund_requests(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(RefundRequest, Booking).join(Booking, RefundRequest.booking_id == Booking.id).filter(
        RefundRequest.customer_id == user.id
    ).order_by(RefundRequest.created_at.desc()).all()
    return [{"id": item.id, "booking_id": item.booking_id, "amount": float(booking.total_amount),
             "status": item.status, "reason": item.reason, "decision_note": item.decision_note,
             "created_at": item.created_at} for item, booking in rows]

@router.get("/admin/refund-requests", tags=["administration", "payments"])
def admin_refund_requests(status: str = "pending", db: Session = Depends(get_db),
                          _admin: User = Depends(require_roles("admin", "staff"))):
    query = db.query(RefundRequest, Booking, User).join(Booking, RefundRequest.booking_id == Booking.id).join(
        User, RefundRequest.customer_id == User.id)
    if status != "all": query = query.filter(RefundRequest.status == status)
    rows = query.order_by(RefundRequest.created_at.desc()).all()
    return [{"id": item.id, "booking_id": item.booking_id, "customer_id": item.customer_id,
             "customer_name": customer.name, "customer_email": customer.email,
             "amount": float(booking.total_amount), "reason": item.reason, "status": item.status,
             "decision_note": item.decision_note, "created_at": item.created_at} for item, booking, customer in rows]

@router.patch("/admin/refund-requests/{refund_id}", tags=["administration", "payments"])
def decide_refund_request(refund_id: str, data: dict, db: Session = Depends(get_db),
                          admin: User = Depends(require_roles("admin", "staff"))):
    item = db.get(RefundRequest, refund_id)
    if not item: raise HTTPException(404, "Refund request not found")
    status = data.get("status")
    note = str(data.get("decision_note") or "").strip()
    if status not in {"approved", "rejected"}: raise HTTPException(422, "Status must be approved or rejected")
    if len(note) < 3: raise HTTPException(422, "Decision note must contain at least 3 characters")
    if item.status not in {"pending", "rejected"}: raise HTTPException(409, "This refund request has already been decided")
    item.status, item.decision_note = status, note
    audit(db, admin.id, "refund_request.decided", "refund_request", item.id, {"status": status, "note": note})
    db.commit()
    return {"id": item.id, "status": item.status, "decision_note": item.decision_note}

@router.post("/admin/refund-requests/{refund_id}/process-payment", tags=["administration", "payments"])
def process_refund_payment(refund_id: str, db: Session = Depends(get_db),
                          _admin: User = Depends(require_roles("admin"))):
    item = db.get(RefundRequest, refund_id)
    if not item: raise HTTPException(404, "Refund request not found")
    if item.status != "approved": raise HTTPException(409, "Approve the refund request before processing payment")
    # Refunds are never marked paid without a real provider response.
    raise HTTPException(503, "Payment provider refund processing is not configured; no refund was issued")


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
