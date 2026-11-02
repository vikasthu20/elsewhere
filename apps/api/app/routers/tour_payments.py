"""Tour package payment reference and manual reconciliation workflow.

No card or UPI charge is made by this module. A configured gateway adapter is a
separate integration; this workflow records customer-supplied transfer references
and requires an administrator to verify settlement before marking a request paid.
"""
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, inspect
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64, hashlib, secrets
from app.db import get_db
from app.models import User, TourPackage, TourPackageRequest, TourPackagePayment, TourPackagePayout, TourPackageInvoice, TourPackageTravelOperation, TourPackageTravellerDocument, TourPackageDocumentLifecycleNotice, UserPrivacyConsent, UserPrivacyRequest, PrivacyRetentionPolicy, PrivacyRetentionRun, PrivacyProcessor, PrivacyProcessingActivity, PrivacyCrossBorderTransfer, PrivacyRiskAssessment, PrivacyRiskItem, PrivacySecurityIncident, PrivacyIncidentEvidence, PrivacyIncidentPlaybook, PrivacyIncidentReview, SecurityVulnerability, VulnerabilityRemediationEvent, Notification, AuditLog
from app.schemas import TourPackagePaymentReferenceIn, TourPackagePaymentDecisionIn, TourPackagePayoutRequestIn, TourPackagePayoutDecisionIn
from app.security import current_user, require_roles
from app.services.operations import audit

router = APIRouter()

def _payload(item, request):
    package = None
    return {"id": item.id, "request_id": item.request_id, "package_request_status": request.status,
            "amount": str(Decimal(str(item.amount)).quantize(Decimal("0.01"))),
            "currency": item.currency, "payment_method": item.payment_method,
            "payment_reference": item.payment_reference, "status": item.status,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "verified_at": item.verified_at.isoformat() if item.verified_at else None}

@router.post("/tour-package-requests/{request_id}/payment", tags=["tour-package-payments"])
def create_or_get_payment(request_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    request = db.query(TourPackageRequest).filter(TourPackageRequest.id == request_id, TourPackageRequest.customer_id == user.id).first()
    if not request: raise HTTPException(404, "Tour package request not found")
    if request.status != "confirmed": raise HTTPException(409, "The agency must confirm the request before payment can be submitted")
    existing = db.query(TourPackagePayment).filter(TourPackagePayment.request_id == request.id).first()
    if existing: return _payload(existing, request)
    package = db.get(TourPackage, request.package_id)
    if not package: raise HTTPException(404, "Tour package not found")
    amount = (Decimal(str(package.price_per_person)) * request.travellers).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    item = TourPackagePayment(request_id=request.id, customer_id=user.id, provider_id=request.provider_id, amount=amount, currency=(package.currency or "INR").upper()[:3])
    db.add(item); db.flush()
    audit(db, user.id, "tour_package.payment_intent_created", "tour_package_payment", item.id, {"request_id": request.id, "amount": str(amount)})
    db.commit(); db.refresh(item)
    return _payload(item, request)

@router.post("/tour-package-requests/{request_id}/payment-reference", tags=["tour-package-payments"])
def submit_payment_reference(request_id: str, data: TourPackagePaymentReferenceIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    request = db.query(TourPackageRequest).filter(TourPackageRequest.id == request_id, TourPackageRequest.customer_id == user.id).first()
    if not request: raise HTTPException(404, "Tour package request not found")
    payment = db.query(TourPackagePayment).filter(TourPackagePayment.request_id == request.id).first()
    if not payment: raise HTTPException(404, "Create the payment record first")
    if payment.status == "paid": raise HTTPException(409, "Payment has already been verified")
    if payment.status == "rejected": raise HTTPException(409, "This payment submission was rejected; contact support")
    payment.payment_reference = data.payment_reference.strip()
    payment.status = "verification_pending"
    db.add(Notification(user_id=request.provider_id, title="Tour package payment submitted", body=f"A customer submitted payment reference for request {request.id}.", channel="in_app"))
    audit(db, user.id, "tour_package.payment_reference_submitted", "tour_package_payment", payment.id)
    db.commit(); db.refresh(payment)
    return _payload(payment, request)

@router.get("/tour-package-payments/mine", tags=["tour-package-payments"])
def my_tour_package_payments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(TourPackagePayment).filter(TourPackagePayment.customer_id == user.id).order_by(TourPackagePayment.created_at.desc()).all()
    return [_payload(x, db.get(TourPackageRequest, x.request_id)) for x in rows]

@router.get("/admin/tour-package-payments", tags=["administration", "tour-package-payments"])
def admin_tour_package_payments(status: str = "", db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    query = db.query(TourPackagePayment)
    if status: query = query.filter(TourPackagePayment.status == status)
    rows = query.order_by(TourPackagePayment.created_at.desc()).all()
    return [_payload(x, db.get(TourPackageRequest, x.request_id)) for x in rows]

@router.patch("/admin/tour-package-payments/{payment_id}", tags=["administration", "tour-package-payments"])
def decide_tour_package_payment(payment_id: str, data: TourPackagePaymentDecisionIn, TourPackagePayoutRequestIn, TourPackagePayoutDecisionIn, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    payment = db.get(TourPackagePayment, payment_id)
    if not payment: raise HTTPException(404, "Payment record not found")
    request = db.get(TourPackageRequest, payment.request_id)
    if payment.status == "paid": raise HTTPException(409, "Verified payment cannot be changed")
    if payment.status != "verification_pending": raise HTTPException(409, "A customer payment reference must be submitted first")
    payment.status = data.status
    if data.status == "paid":
        payment.verified_by = admin.id; payment.verified_at = datetime.utcnow()
        request.status = "paid"
        package = db.get(TourPackage, request.package_id)
        _issue_tour_package_invoice(db, payment, request, package, admin.id)
    db.add(Notification(user_id=payment.customer_id, title="Tour package payment update", body=("Your tour package payment has been verified." if data.status == "paid" else f"Your payment reference could not be verified. {data.note}"), channel="in_app"))
    audit(db, admin.id, "tour_package.payment_reconciled", "tour_package_payment", payment.id, {"status": data.status, "note": data.note})
    db.commit(); db.refresh(payment)
    return _payload(payment, request)


@router.get("/providers/me/tour-package-revenue/dashboard", tags=["tour-package-payments"])
def provider_tour_package_revenue_dashboard(
    days: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("agency", "owner", "admin"))
):
    from datetime import timedelta
    from sqlalchemy import func
    days = min(max(days, 7), 365)
    since = datetime.utcnow() - timedelta(days=days)
    base = db.query(TourPackagePayment, TourPackageRequest, TourPackage).join(
        TourPackageRequest, TourPackageRequest.id == TourPackagePayment.request_id
    ).join(TourPackage, TourPackage.id == TourPackageRequest.package_id).filter(
        TourPackagePayment.provider_id == user.id
    )
    rows = base.order_by(TourPackagePayment.created_at.desc()).all()
    counts = {"awaiting_payment": 0, "verification_pending": 0, "paid": 0, "rejected": 0}
    revenue_by_currency = {}
    paid_count = 0
    recent_paid = []
    package_totals = {}
    for payment, request, package in rows:
        counts[payment.status] = counts.get(payment.status, 0) + 1
        if payment.status == "paid":
            paid_count += 1
            revenue_by_currency[payment.currency] = round(
                revenue_by_currency.get(payment.currency, 0) + float(payment.amount), 2
            )
            key = (package.id, package.title, package.destination, payment.currency)
            package_totals[key] = package_totals.get(key, 0) + float(payment.amount)
            if payment.verified_at and payment.verified_at >= since:
                recent_paid.append({
                    "payment_id": payment.id, "package_title": package.title,
                    "destination": package.destination, "amount": float(payment.amount),
                    "currency": payment.currency, "verified_at": payment.verified_at.isoformat(),
                    "travellers": request.travellers, "start_date": request.start_date.isoformat()
                })
    # Revenue timeline uses verified_at and keeps currencies separate.
    timeline = {}
    for item in recent_paid:
        day = item["verified_at"][:10]
        key = (day, item["currency"])
        timeline[key] = round(timeline.get(key, 0) + item["amount"], 2)
    top_packages = [
        {"package_id": key[0], "title": key[1], "destination": key[2],
         "currency": key[3], "paid_revenue": round(value, 2)}
        for key, value in sorted(package_totals.items(), key=lambda pair: pair[1], reverse=True)[:10]
    ]
    request_rows = db.query(TourPackageRequest).filter(TourPackageRequest.provider_id == user.id).all()
    request_counts = {}
    for item in request_rows:
        request_counts[item.status] = request_counts.get(item.status, 0) + 1
    return {
        "period_days": days,
        "payment_counts": counts,
        "request_counts": request_counts,
        "paid_revenue_by_currency": revenue_by_currency,
        "paid_payment_count": paid_count,
        "recent_verified_payments": recent_paid[:50],
        "revenue_timeline": [
            {"date": day, "currency": currency, "amount": amount}
            for (day, currency), amount in sorted(timeline.items())
        ],
        "top_packages": top_packages,
        "note": "Revenue includes only payments verified as paid. Amounts are grouped by currency and are not converted."
    }


def _payout_payload(item):
    return {
        "id": item.id, "provider_id": item.provider_id, "amount": str(item.amount),
        "currency": item.currency, "payout_method": item.payout_method,
        "account_holder": item.account_holder, "bank_name": item.bank_name,
        "account_last4": item.account_last4, "status": item.status,
        "provider_note": item.provider_note, "admin_note": item.admin_note,
        "payout_reference": item.payout_reference,
        "requested_at": item.requested_at.isoformat() if item.requested_at else None,
        "processed_at": item.processed_at.isoformat() if item.processed_at else None,
    }


def _provider_available_balance(db, provider_id: str, currency: str):
    paid = db.query(TourPackagePayment).filter(
        TourPackagePayment.provider_id == provider_id,
        TourPackagePayment.status == "paid",
        TourPackagePayment.currency == currency
    ).all()
    gross = sum((Decimal(str(x.amount)) for x in paid), Decimal("0.00"))
    payouts = db.query(TourPackagePayout).filter(
        TourPackagePayout.provider_id == provider_id,
        TourPackagePayout.currency == currency,
        TourPackagePayout.status.in_(["requested", "processing", "paid"])
    ).all()
    reserved = sum((Decimal(str(x.amount)) for x in payouts), Decimal("0.00"))
    return (gross - reserved).quantize(Decimal("0.01"))


@router.get("/providers/me/payouts", tags=["tour-package-payouts"])
def provider_list_payouts(db: Session = Depends(get_db), user: User = Depends(require_roles("agency", "owner", "admin"))):
    rows = db.query(TourPackagePayout).filter(TourPackagePayout.provider_id == user.id).order_by(TourPackagePayout.requested_at.desc()).all()
    return [_payout_payload(x) for x in rows]


@router.get("/providers/me/payouts/balance", tags=["tour-package-payouts"])
def provider_payout_balances(db: Session = Depends(get_db), user: User = Depends(require_roles("agency", "owner", "admin"))):
    currencies = [x[0] for x in db.query(TourPackagePayment.currency).filter(
        TourPackagePayment.provider_id == user.id, TourPackagePayment.status == "paid"
    ).distinct().all()]
    return [{"currency": code, "gross_paid": str(sum(
        (Decimal(str(x.amount)) for x in db.query(TourPackagePayment).filter(
            TourPackagePayment.provider_id == user.id, TourPackagePayment.status == "paid",
            TourPackagePayment.currency == code).all()), Decimal("0.00"))),
        "available": str(_provider_available_balance(db, user.id, code))}
        for code in currencies]


@router.post("/providers/me/payouts", tags=["tour-package-payouts"])
def provider_create_tour_package_payout(data: TourPackagePayoutRequestIn, db: Session = Depends(get_db), user: User = Depends(require_roles("agency", "owner", "admin"))):
    currency = data.currency.upper()
    available = _provider_available_balance(db, user.id, currency)
    amount = Decimal(str(data.amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount > available:
        raise HTTPException(400, f"Requested amount exceeds available {currency} balance ({available}).")
    item = TourPackagePayout(provider_id=user.id, amount=amount, currency=currency,
        account_holder=data.account_holder.strip(), bank_name=data.bank_name.strip(),
        account_last4=data.account_last4, provider_note=data.provider_note.strip(), status="requested")
    db.add(item); db.flush()
    audit(db, user.id, "tour_package.payout_requested", "tour_package_payout", item.id,
          {"amount": str(amount), "currency": currency, "account_last4": data.account_last4})
    db.add(Notification(user_id=user.id, title="Payout request submitted",
        body=f"Your payout request for {currency} {amount} has been submitted for review.", channel="in_app"))
    db.commit(); db.refresh(item)
    return _payout_payload(item)


@router.get("/admin/tour-package-payouts", tags=["administration", "tour-package-payouts"])
def admin_list_tour_package_payouts(status: str = "", q: str = "", db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    query = db.query(TourPackagePayout)
    if status and status != "all":
        query = query.filter(TourPackagePayout.status == status)
    rows = query.order_by(TourPackagePayout.requested_at.desc()).all()
    if q.strip():
        term = q.strip().lower()
        rows = [x for x in rows if term in x.account_holder.lower() or term in x.bank_name.lower()
                or term in x.currency.lower() or term in x.account_last4]
    return [_payout_payload(x) | {"provider_name": (db.get(User, x.provider_id).name if db.get(User, x.provider_id) else "Provider"),
                                  "provider_email": (db.get(User, x.provider_id).email if db.get(User, x.provider_id) else "")}
            for x in rows]


@router.patch("/admin/tour-package-payouts/{payout_id}", tags=["administration", "tour-package-payouts"])
def admin_decide_tour_package_payout(payout_id: str, data: TourPackagePayoutDecisionIn, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    item = db.get(TourPackagePayout, payout_id)
    if not item:
        raise HTTPException(404, "Payout request not found")
    if item.status in ("paid", "rejected"):
        raise HTTPException(409, "This payout request is already closed")
    if data.status == "paid" and not data.payout_reference.strip():
        raise HTTPException(400, "Enter the bank transfer reference before marking a payout paid")
    item.status = data.status
    item.payout_reference = data.payout_reference.strip()
    item.admin_note = data.admin_note.strip()
    if data.status in ("paid", "rejected"):
        item.processed_by = admin.id
        item.processed_at = datetime.utcnow()
    db.add(Notification(user_id=item.provider_id, title="Payout request updated",
        body=f"Your {item.currency} {item.amount} payout request is now {item.status}. {item.admin_note}".strip(),
        channel="in_app"))
    audit(db, admin.id, "tour_package.payout_updated", "tour_package_payout", item.id,
          {"status": item.status, "payout_reference": item.payout_reference})
    db.commit(); db.refresh(item)
    return _payout_payload(item)


def _invoice_payload(invoice):
    return {
        "id": invoice.id, "invoice_number": invoice.invoice_number,
        "payment_id": invoice.payment_id, "request_id": invoice.request_id,
        "package_title": invoice.package_title, "destination": invoice.destination,
        "customer_name": invoice.customer_name, "customer_email": invoice.customer_email,
        "provider_name": invoice.provider_name, "start_date": invoice.start_date.isoformat(),
        "travellers": invoice.travellers, "unit_price": str(invoice.unit_price),
        "subtotal": str(invoice.subtotal), "total": str(invoice.total),
        "currency": invoice.currency, "status": invoice.status,
        "issued_at": invoice.issued_at.isoformat() if invoice.issued_at else None,
    }


def _issue_tour_package_invoice(db, payment, request, package, admin_id):
    existing = db.query(TourPackageInvoice).filter(TourPackageInvoice.payment_id == payment.id).first()
    if existing:
        return existing
    from app.models import User
    customer = db.get(User, payment.customer_id)
    provider = db.get(User, payment.provider_id)
    issued = datetime.utcnow()
    invoice = TourPackageInvoice(
        invoice_number=f"ELS-TP-{issued.strftime('%Y%m%d')}-{payment.id[:8].upper()}",
        payment_id=payment.id, request_id=request.id,
        customer_id=payment.customer_id, provider_id=payment.provider_id,
        package_title=package.title if package else "Tour package",
        destination=package.destination if package else "",
        customer_name=customer.name if customer else "Traveller",
        customer_email=customer.email if customer else "",
        provider_name=provider.name if provider else "Travel partner",
        start_date=request.start_date, travellers=request.travellers,
        unit_price=payment.amount / request.travellers,
        subtotal=payment.amount, total=payment.amount, currency=payment.currency,
        status="issued", issued_at=issued
    )
    db.add(invoice)
    db.flush()
    db.add(TourPackageTravelOperation(invoice_id=invoice.id, request_id=request.id, customer_id=request.customer_id, provider_id=request.provider_id, status="confirmed", checklist_json="[]"))
    audit(db, admin_id, "tour_package.invoice_issued", "tour_package_invoice", invoice.id,
          {"invoice_number": invoice.invoice_number, "payment_id": payment.id})
    return invoice


@router.get("/tour-package-invoices/mine", tags=["tour-package-invoices"])
def my_tour_package_invoices(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(TourPackageInvoice).filter(TourPackageInvoice.customer_id == user.id).order_by(TourPackageInvoice.issued_at.desc()).all()
    return [_invoice_payload(x) for x in rows]


@router.get("/providers/me/tour-package-invoices", tags=["tour-package-invoices"])
def provider_tour_package_invoices(db: Session = Depends(get_db), user: User = Depends(require_roles("agency", "owner", "admin"))):
    rows = db.query(TourPackageInvoice).filter(TourPackageInvoice.provider_id == user.id).order_by(TourPackageInvoice.issued_at.desc()).all()
    return [_invoice_payload(x) for x in rows]


@router.get("/tour-package-invoices/{invoice_id}/pdf", tags=["tour-package-invoices"])
def download_tour_package_invoice_pdf(invoice_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    invoice = db.get(TourPackageInvoice, invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if user.id not in (invoice.customer_id, invoice.provider_id) and user.role != "admin":
        raise HTTPException(403, "You cannot access this invoice")
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="InvoiceBrand", parent=styles["Title"], textColor=colors.HexColor("#34483c"), fontSize=22, leading=26, alignment=0))
    story = [Paragraph("ELSEWHERE", styles["InvoiceBrand"]), Paragraph("TOUR PACKAGE PAYMENT RECEIPT", styles["Heading2"]), Spacer(1, 8*mm)]
    story.append(Paragraph(f"<b>Invoice:</b> {invoice.invoice_number}", styles["Normal"]))
    story.append(Paragraph(f"<b>Issued:</b> {invoice.issued_at.strftime('%d %b %Y %H:%M UTC')}", styles["Normal"]))
    story.append(Spacer(1, 6*mm))
    rows = [
        ["Traveller", invoice.customer_name],
        ["Email", invoice.customer_email],
        ["Travel partner", invoice.provider_name],
        ["Package", invoice.package_title],
        ["Destination", invoice.destination],
        ["Travel start", invoice.start_date.strftime("%d %b %Y")],
        ["Travellers", str(invoice.travellers)],
        ["Price per traveller", f"{invoice.currency} {Decimal(str(invoice.unit_price)):,.2f}"],
        ["Subtotal", f"{invoice.currency} {Decimal(str(invoice.subtotal)):,.2f}"],
        ["Total paid", f"{invoice.currency} {Decimal(str(invoice.total)):,.2f}"],
        ["Payment status", "PAID · VERIFIED"],
    ]
    table = Table(rows, colWidths=[48*mm, 112*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#f2f0e9")),
        ("TEXTCOLOR",(0,0),(0,-1),colors.HexColor("#465348")),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),9),
        ("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#ddd8ce")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),9),("RIGHTPADDING",(0,0),(-1,-1),9),
        ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
    ]))
    story += [table, Spacer(1, 12*mm), Paragraph("This receipt confirms that the payment was marked as paid after manual verification. It is not a tax invoice unless separately issued by the travel partner.", styles["Italic"])]
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"',
                 "Cache-Control": "private, no-store"})


# Replace successful admin payment verification to issue an invoice in the same transaction.


# Step 71: booking confirmation and provider travel operations.
def _travel_operation_payload(item, invoice):
    import json
    try: checklist = json.loads(item.checklist_json or "[]")
    except (TypeError, ValueError): checklist = []
    return {"id": item.id, "invoice_id": invoice.id, "invoice_number": invoice.invoice_number,
        "request_id": item.request_id, "package_title": invoice.package_title, "destination": invoice.destination,
        "customer_name": invoice.customer_name, "customer_email": invoice.customer_email,
        "start_date": invoice.start_date.isoformat(), "travellers": invoice.travellers,
        "status": item.status, "meeting_point": item.meeting_point, "pickup_time": item.pickup_time,
        "emergency_contact": item.emergency_contact, "provider_instructions": item.provider_instructions,
        "checklist": checklist, "updated_at": item.updated_at.isoformat() if item.updated_at else None}

@router.get("/tour-package-travel-operations/mine", tags=["tour-package-operations"])
def my_tour_package_travel_operations(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(TourPackageTravelOperation, TourPackageInvoice).join(TourPackageInvoice, TourPackageInvoice.id == TourPackageTravelOperation.invoice_id).filter(TourPackageTravelOperation.customer_id == user.id).order_by(TourPackageInvoice.start_date.asc()).all()
    return [_travel_operation_payload(op, inv) for op, inv in rows]

@router.get("/providers/me/tour-package-travel-operations", tags=["tour-package-operations"])
def provider_tour_package_travel_operations(db: Session = Depends(get_db), user: User = Depends(require_roles("agency", "owner", "admin"))):
    rows = db.query(TourPackageTravelOperation, TourPackageInvoice).join(TourPackageInvoice, TourPackageInvoice.id == TourPackageTravelOperation.invoice_id).filter(TourPackageTravelOperation.provider_id == user.id).order_by(TourPackageInvoice.start_date.asc()).all()
    return [_travel_operation_payload(op, inv) for op, inv in rows]

@router.patch("/providers/me/tour-package-travel-operations/{operation_id}", tags=["tour-package-operations"])
def update_tour_package_travel_operation(operation_id: str, data: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("agency", "owner", "admin"))):
    import json
    op = db.query(TourPackageTravelOperation).filter(TourPackageTravelOperation.id == operation_id, TourPackageTravelOperation.provider_id == user.id).first()
    if not op: raise HTTPException(404, "Travel operation not found")
    allowed_statuses = {"confirmed", "documents_shared", "ready", "completed", "cancelled"}
    if "status" in data:
        if data["status"] not in allowed_statuses: raise HTTPException(422, "Invalid operation status")
        op.status = data["status"]
    for key, limit in (("meeting_point",300),("pickup_time",80),("emergency_contact",80),("provider_instructions",4000)):
        if key in data: setattr(op, key, str(data[key] or "").strip()[:limit])
    if "checklist" in data:
        checklist = data["checklist"]
        if not isinstance(checklist, list) or len(checklist) > 30: raise HTTPException(422, "Checklist must be a list of up to 30 items")
        cleaned = []
        for entry in checklist:
            if not isinstance(entry, dict) or not str(entry.get("label", "")).strip(): continue
            cleaned.append({"label": str(entry["label"]).strip()[:120], "done": bool(entry.get("done", False))})
        op.checklist_json = json.dumps(cleaned)
    db.add(Notification(user_id=op.customer_id, title="Your travel details were updated", body="Your travel partner updated the meeting or preparation details for your booking.", channel="in_app"))
    audit(db, user.id, "tour_package.travel_operation_updated", "tour_package_travel_operation", op.id, {"status": op.status})
    db.commit(); db.refresh(op)
    invoice = db.get(TourPackageInvoice, op.invoice_id)
    return _travel_operation_payload(op, invoice)


# Traveller document collection. Files are stored outside the public web root.
import os, uuid, shutil, mimetypes
from pathlib import Path
from fastapi.responses import FileResponse
from sqlalchemy import or_

_DOCUMENT_ROOT = Path(os.environ.get("ELSEWHERE_PRIVATE_DOCUMENT_DIR", "/var/lib/elsewhere/private-traveller-documents"))
_ALLOWED_DOCUMENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
_MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
_DOCUMENT_RETENTION_DAYS = int(os.environ.get("ELSEWHERE_DOCUMENT_RETENTION_DAYS", "365"))

def _document_cipher():
    raw = os.environ.get("ELSEWHERE_DOCUMENT_ENCRYPTION_KEY", "")
    if not raw:
        raise HTTPException(503, "Traveller document encryption is not configured")
    try:
        key = base64.urlsafe_b64decode(raw.encode())
        if len(key) != 32: raise ValueError("key must decode to 32 bytes")
        return AESGCM(key)
    except Exception:
        raise HTTPException(503, "Traveller document encryption key is invalid")

def _encrypt_document(data: bytes) -> bytes:
    nonce = secrets.token_bytes(12)
    return b"ELS1" + nonce + _document_cipher().encrypt(nonce, data, b"elsewhere-traveller-document")

def _decrypt_document(data: bytes) -> bytes:
    if not data.startswith(b"ELS1"): return data  # legacy Step 72 files
    return _document_cipher().decrypt(data[4:16], data[16:], b"elsewhere-traveller-document")

def _encrypt_field(value: str) -> str:
    if not value: return ""
    nonce = secrets.token_bytes(12)
    encrypted = _document_cipher().encrypt(nonce, value.encode(), b"elsewhere-traveller-field")
    return "enc:v1:" + base64.urlsafe_b64encode(nonce + encrypted).decode()

def _decrypt_field(value: str) -> str:
    if not value.startswith("enc:v1:"): return value  # legacy unencrypted metadata
    raw = base64.urlsafe_b64decode(value[7:].encode())
    return _document_cipher().decrypt(raw[:12], raw[12:], b"elsewhere-traveller-field").decode()

def _traveller_document_payload(doc):
    return {"id": doc.id, "operation_id": doc.operation_id, "traveller_name": doc.traveller_name,
        "document_type": doc.document_type, "document_number": _decrypt_field(doc.document_number),
        "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
        "original_filename": doc.original_filename, "content_type": doc.content_type,
        "file_size": doc.file_size, "verification_status": doc.verification_status,
        "reviewer_note": doc.reviewer_note, "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None, "encrypted_at_rest": bool(doc.encrypted_at_rest), "retention_until": doc.retention_until.isoformat() if doc.retention_until else None}

@router.get("/tour-package-traveller-documents/mine", tags=["traveller-documents"])
def my_traveller_documents(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(TourPackageTravellerDocument).filter(TourPackageTravellerDocument.customer_id == user.id).order_by(TourPackageTravellerDocument.created_at.desc()).all()
    return [_traveller_document_payload(x) for x in rows]

@router.post("/tour-package-travel-operations/{operation_id}/traveller-documents", tags=["traveller-documents"])
async def upload_traveller_document(operation_id: str, traveller_name: str = Form(...), document_type: str = Form(...), document_number: str = Form(""), expiry_date: str = Form(""), file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    op = db.query(TourPackageTravelOperation).filter(TourPackageTravelOperation.id == operation_id, TourPackageTravelOperation.customer_id == user.id).first()
    if not op: raise HTTPException(404, "Travel booking not found")
    if document_type not in {"passport", "national_id", "visa", "other"}: raise HTTPException(422, "Unsupported document type")
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_DOCUMENT_TYPES: raise HTTPException(415, "Only PDF, JPEG and PNG documents are accepted")
    safe_name = Path(file.filename or "document").name[:255]
    stored = f"{uuid.uuid4().hex}.bin"
    cipher = _document_cipher()  # fail closed before accepting sensitive data
    _DOCUMENT_ROOT.mkdir(parents=True, exist_ok=True)
    target = _DOCUMENT_ROOT / stored
    size = 0
    try:
        chunks = []
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk: break
            size += len(chunk)
            if size > _MAX_DOCUMENT_BYTES: raise HTTPException(413, "Document exceeds 10 MB")
            chunks.append(chunk)
        target.write_bytes(_encrypt_document(b"".join(chunks)))
    except Exception:
        target.unlink(missing_ok=True); raise
    finally:
        await file.close()
    exp = None
    if expiry_date:
        try: exp = date.fromisoformat(expiry_date)
        except ValueError:
            target.unlink(missing_ok=True); raise HTTPException(422, "Expiry date must use YYYY-MM-DD")
    doc = TourPackageTravellerDocument(operation_id=op.id, customer_id=user.id, provider_id=op.provider_id,
        traveller_name=traveller_name.strip()[:160], document_type=document_type,
        expiry_date=exp, original_filename=safe_name, stored_filename=stored, content_type=content_type, file_size=size,
        document_number=_encrypt_field(document_number.strip()[:100]), encrypted_at_rest=True,
        retention_until=date.today() + timedelta(days=_DOCUMENT_RETENTION_DAYS))
    db.add(doc); db.commit(); db.refresh(doc)
    db.add(Notification(user_id=op.provider_id, title="Traveller document submitted", body="A customer submitted a document for booking verification.", channel="in_app")); db.commit()
    return _traveller_document_payload(doc)

@router.get("/providers/me/tour-package-traveller-documents", tags=["traveller-documents"])
def provider_traveller_documents(db: Session = Depends(get_db), user: User = Depends(require_roles("agency", "owner", "admin"))):
    rows = db.query(TourPackageTravellerDocument).filter(TourPackageTravellerDocument.provider_id == user.id).order_by(TourPackageTravellerDocument.created_at.desc()).all()
    return [_traveller_document_payload(x) for x in rows]

@router.patch("/providers/me/tour-package-traveller-documents/{document_id}", tags=["traveller-documents"])
def review_traveller_document(document_id: str, data: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("agency", "owner", "admin"))):
    doc = db.query(TourPackageTravellerDocument).filter(TourPackageTravellerDocument.id == document_id, TourPackageTravellerDocument.provider_id == user.id).first()
    if not doc: raise HTTPException(404, "Traveller document not found")
    status = data.get("verification_status")
    if status not in {"verified", "rejected", "pending"}: raise HTTPException(422, "Invalid verification status")
    doc.verification_status = status; doc.reviewer_note = str(data.get("reviewer_note", "")).strip()[:1000]; doc.reviewed_at = datetime.utcnow()
    db.add(Notification(user_id=doc.customer_id, title="Traveller document reviewed", body=f"Your {doc.document_type.replace('_',' ')} document was marked {status}.", channel="in_app"))
    audit(db, user.id, "tour_package.traveller_document_reviewed", "tour_package_traveller_document", doc.id, {"status": status})
    db.commit(); db.refresh(doc); return _traveller_document_payload(doc)

@router.get("/tour-package-traveller-documents/{document_id}/download", tags=["traveller-documents"])
def download_traveller_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = db.query(TourPackageTravellerDocument).filter(TourPackageTravellerDocument.id == document_id).first()
    if not doc or user.id not in {doc.customer_id, doc.provider_id} and getattr(user.role, "value", user.role) != "admin": raise HTTPException(404, "Document not found")
    path = _DOCUMENT_ROOT / doc.stored_filename
    if not path.is_file(): raise HTTPException(404, "Stored document is unavailable")
    try:
        payload = _decrypt_document(path.read_bytes())
    except Exception:
        raise HTTPException(500, "Document decryption failed; check the configured encryption key")
    return Response(payload, media_type=doc.content_type, headers={
        "Content-Disposition": f'attachment; filename="{doc.original_filename.replace(chr(34), "")}"',
        "Cache-Control":"private, no-store", "Pragma":"no-cache", "X-Content-Type-Options":"nosniff"})

@router.get("/providers/me/tour-package-traveller-documents/expiry-alerts", tags=["traveller-documents"])
def provider_document_expiry_alerts(days: int = 90, db: Session = Depends(get_db), user: User = Depends(require_roles("agency", "owner", "admin"))):
    if days < 1 or days > 365: raise HTTPException(422, "days must be between 1 and 365")
    today = date.today()
    rows = db.query(TourPackageTravellerDocument).filter(
        TourPackageTravellerDocument.provider_id == user.id,
        TourPackageTravellerDocument.expiry_date.is_not(None),
        TourPackageTravellerDocument.expiry_date <= today + timedelta(days=days)
    ).order_by(TourPackageTravellerDocument.expiry_date.asc()).all()
    return [{"id": x.id, "traveller_name": x.traveller_name, "document_type": x.document_type,
        "expiry_date": x.expiry_date.isoformat(), "expired": x.expiry_date < today,
        "days_remaining": (x.expiry_date - today).days, "verification_status": x.verification_status}
        for x in rows]

@router.delete("/providers/me/tour-package-traveller-documents/{document_id}", tags=["traveller-documents"])
def delete_traveller_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("agency", "owner", "admin"))):
    doc = db.query(TourPackageTravellerDocument).filter(
        TourPackageTravellerDocument.id == document_id, TourPackageTravellerDocument.provider_id == user.id).first()
    if not doc: raise HTTPException(404, "Traveller document not found")
    path = _DOCUMENT_ROOT / doc.stored_filename
    path.unlink(missing_ok=True)
    audit(db, user.id, "tour_package.traveller_document_deleted", "tour_package_traveller_document", doc.id, {"reason": "retention_or_manual_deletion"})
    db.delete(doc); db.commit()
    return {"deleted": True}


@router.get("/admin/tour-package-traveller-document-compliance", tags=["traveller-documents"])
def admin_traveller_document_compliance(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    today = date.today()
    rows = db.query(TourPackageTravellerDocument).order_by(TourPackageTravellerDocument.created_at.desc()).all()
    notices = db.query(TourPackageDocumentLifecycleNotice).count()
    result = []
    for doc in rows:
        remaining = (doc.expiry_date - today).days if doc.expiry_date else None
        result.append({
            "id": doc.id, "traveller_name": doc.traveller_name, "document_type": doc.document_type,
            "provider_id": doc.provider_id, "customer_id": doc.customer_id,
            "verification_status": doc.verification_status,
            "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
            "days_remaining": remaining, "retention_until": doc.retention_until.isoformat() if doc.retention_until else None,
            "encrypted_at_rest": bool(doc.encrypted_at_rest), "created_at": doc.created_at.isoformat(),
        })
    return {
        "summary": {
            "total_documents": len(rows),
            "pending": sum(x.verification_status == "pending" for x in rows),
            "verified": sum(x.verification_status == "verified" for x in rows),
            "rejected": sum(x.verification_status == "rejected" for x in rows),
            "expired": sum(bool(x.expiry_date and x.expiry_date < today) for x in rows),
            "expiring_90_days": sum(bool(x.expiry_date and today <= x.expiry_date <= today + timedelta(days=90)) for x in rows),
            "unencrypted_legacy": sum(not x.encrypted_at_rest for x in rows),
            "lifecycle_notices_recorded": notices,
        },
        "documents": result,
    }

@router.get("/admin/tour-package-traveller-document-compliance/export", tags=["traveller-documents"])
def export_traveller_document_compliance(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    import csv, io
    payload = admin_traveller_document_compliance(db=db, user=user)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=["id","traveller_name","document_type","provider_id","customer_id","verification_status","expiry_date","days_remaining","retention_until","encrypted_at_rest","created_at"])
    writer.writeheader()
    writer.writerows(payload["documents"])
    return Response(stream.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="elsewhere-document-compliance.csv"',
        "Cache-Control": "private, no-store"
    })


# Account privacy controls and data-subject request workflow.
@router.get("/privacy/consent", tags=["privacy"])
def get_privacy_consent(db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.query(UserPrivacyConsent).filter_by(user_id=user.id).first()
    if not row:
        return {"essential_acknowledged": True, "analytics_enabled": False, "marketing_enabled": False}
    return {"essential_acknowledged": row.essential_acknowledged,
        "analytics_enabled": row.analytics_enabled, "marketing_enabled": row.marketing_enabled,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None}

@router.put("/privacy/consent", tags=["privacy"])
def update_privacy_consent(data: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.query(UserPrivacyConsent).filter_by(user_id=user.id).first()
    if not row:
        row = UserPrivacyConsent(user_id=user.id)
        db.add(row)
    row.essential_acknowledged = True
    row.analytics_enabled = bool(data.get("analytics_enabled", False))
    row.marketing_enabled = bool(data.get("marketing_enabled", False))
    db.commit(); db.refresh(row)
    audit(db, user.id, "privacy.consent_updated", "user_privacy_consent", row.id,
          {"analytics_enabled": row.analytics_enabled, "marketing_enabled": row.marketing_enabled})
    db.commit()
    return {"analytics_enabled": row.analytics_enabled, "marketing_enabled": row.marketing_enabled,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None}

@router.get("/privacy/requests/mine", tags=["privacy"])
def my_privacy_requests(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(UserPrivacyRequest).filter_by(user_id=user.id).order_by(UserPrivacyRequest.created_at.desc()).all()
    return [{"id": x.id, "request_type": x.request_type, "details": x.details, "status": x.status,
             "admin_note": x.admin_note, "created_at": x.created_at.isoformat(), "updated_at": x.updated_at.isoformat()}
            for x in rows]

@router.post("/privacy/requests", tags=["privacy"])
def create_privacy_request(data: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    kind = str(data.get("request_type", "")).strip().lower()
    if kind not in {"data_export", "account_deletion", "data_correction"}:
        raise HTTPException(422, "Unsupported privacy request type")
    details = str(data.get("details", "")).strip()
    if len(details) > 2000: raise HTTPException(422, "Details must be 2,000 characters or fewer")
    row = UserPrivacyRequest(user_id=user.id, request_type=kind, details=details)
    db.add(row)
    db.add(Notification(user_id=user.id, title="Privacy request received",
        body=f"Your {kind.replace('_', ' ')} request has been submitted for review.", channel="in_app"))
    db.commit(); db.refresh(row)
    audit(db, user.id, "privacy.request_created", "user_privacy_request", row.id, {"request_type": kind})
    db.commit()
    return {"id": row.id, "request_type": row.request_type, "status": row.status}

@router.get("/privacy/data-export", tags=["privacy"])
def privacy_data_export(db: Session = Depends(get_db), user: User = Depends(current_user)):
    consent = db.query(UserPrivacyConsent).filter_by(user_id=user.id).first()
    # Deliberately limited to account profile and consent data; booking and payment exports
    # require a separate verified data inventory before being represented as a complete export.
    return {
        "export_scope": "account_profile_and_privacy_consent",
        "user": {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone,
                 "role": getattr(user.role, "value", user.role), "created_at": user.created_at.isoformat()},
        "consent": {"essential_acknowledged": consent.essential_acknowledged,
                    "analytics_enabled": consent.analytics_enabled, "marketing_enabled": consent.marketing_enabled,
                    "updated_at": consent.updated_at.isoformat() if consent.updated_at else None} if consent else
                   {"essential_acknowledged": True, "analytics_enabled": False, "marketing_enabled": False},
    }

@router.get("/admin/privacy/requests", tags=["privacy"])
def admin_privacy_requests(status: str = "all", db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    q = db.query(UserPrivacyRequest)
    if status != "all":
        if status not in {"submitted", "in_review", "completed", "rejected"}: raise HTTPException(422, "Invalid status filter")
        q = q.filter(UserPrivacyRequest.status == status)
    rows = q.order_by(UserPrivacyRequest.created_at.asc()).all()
    return [{"id": x.id, "user_id": x.user_id, "request_type": x.request_type, "details": x.details,
             "status": x.status, "admin_note": x.admin_note, "created_at": x.created_at.isoformat(),
             "updated_at": x.updated_at.isoformat()} for x in rows]

@router.patch("/admin/privacy/requests/{request_id}", tags=["privacy"])
def review_privacy_request(request_id: str, data: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    row = db.query(UserPrivacyRequest).filter_by(id=request_id).first()
    if not row: raise HTTPException(404, "Privacy request not found")
    status = str(data.get("status", "")).strip().lower()
    if status not in {"in_review", "completed", "rejected"}: raise HTTPException(422, "Invalid request status")
    note = str(data.get("admin_note", "")).strip()
    if len(note) > 2000: raise HTTPException(422, "Admin note is too long")
    row.status = status; row.admin_note = note
    db.add(Notification(user_id=row.user_id, title="Privacy request updated",
        body=f"Your privacy request status is now {status.replace('_', ' ')}.", channel="in_app"))
    audit(db, user.id, "privacy.request_reviewed", "user_privacy_request", row.id,
          {"status": status, "request_type": row.request_type})
    db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/privacy/data-export/full", tags=["privacy"])
def full_privacy_data_export(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Export application rows directly associated with the authenticated account."""
    from app.db import Base
    from datetime import date as _date, datetime as _datetime
    from decimal import Decimal
    excluded = {"password_hash", "document_number", "stored_filename", "file_path", "content",
                "access_token", "refresh_token", "secret", "api_key"}
    related_keys = {"user_id", "customer_id", "provider_id", "owner_id", "actor_id",
                    "assigned_to", "processed_by", "assigned_by"}
    export = {}
    for table in Base.metadata.sorted_tables:
        keys = [c for c in table.columns if c.name in related_keys]
        if not keys:
            continue
        predicate = or_(*[c == user.id for c in keys])
        rows = db.execute(select(table).where(predicate)).mappings().all()
        if not rows:
            continue
        safe_rows = []
        for row in rows:
            item = {}
            for key, value in row.items():
                if key.lower() in excluded or any(token in key.lower() for token in ("password", "token", "secret", "document_number", "stored_filename")):
                    continue
                if isinstance(value, (_date, _datetime)): value = value.isoformat()
                elif isinstance(value, Decimal): value = str(value)
                elif isinstance(value, bytes): continue
                elif hasattr(value, "value"): value = value.value
                item[key] = value
            safe_rows.append(item)
        export[table.name] = safe_rows
    return {"export_scope": "records directly associated with this account; credentials and private document contents excluded",
            "generated_at": datetime.utcnow().isoformat(), "tables": export}

@router.post("/admin/privacy/requests/{request_id}/execute-deletion", tags=["privacy"])
def execute_account_deletion(request_id: str, data: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    """Close account and anonymize core identity after explicit admin confirmation."""
    if data.get("confirm") is not True:
        raise HTTPException(422, "Explicit confirmation is required")
    req = db.query(UserPrivacyRequest).filter_by(id=request_id, request_type="account_deletion").first()
    if not req: raise HTTPException(404, "Account deletion request not found")
    target = db.query(User).filter_by(id=req.user_id).first()
    if not target: raise HTTPException(404, "Account not found")
    if getattr(target.role, "value", target.role) == "admin":
        raise HTTPException(409, "Administrator accounts cannot be deleted through this workflow")
    if target.id == user.id:
        raise HTTPException(409, "An administrator cannot execute deletion of their own account")
    # Purge traveller document files and metadata linked to this account. Keep the
    # lifecycle ledger for audit; it contains no document bytes or identity fields.
    docs = db.query(TourPackageTravellerDocument).filter(
        or_(TourPackageTravellerDocument.customer_id == target.id,
            TourPackageTravellerDocument.provider_id == target.id)).all()
    for doc in docs:
        (_DOCUMENT_ROOT / doc.stored_filename).unlink(missing_ok=True)
        db.delete(doc)
    db.query(Notification).filter(Notification.user_id == target.id).delete(synchronize_session=False)
    consent = db.query(UserPrivacyConsent).filter_by(user_id=target.id).first()
    if consent: db.delete(consent)
    # Preserve the stable FK identity for financial, booking and audit records.
    target.name = "Deleted User"
    target.email = f"deleted+{target.id}@privacy.invalid"
    target.phone = None
    target.password_hash = secrets.token_urlsafe(48)
    target.is_active = False
    req.details = ""
    req.admin_note = "Account closed and core profile anonymized. Financial and booking records retained per applicable retention policy."
    req.status = "completed"
    audit(db, user.id, "privacy.account_anonymized", "user", target.id,
          {"privacy_request_id": req.id, "traveller_documents_purged": len(docs)})
    db.commit()
    return {"request_id": req.id, "status": "completed", "account_deactivated": True,
            "core_profile_anonymized": True, "traveller_documents_purged": len(docs),
            "financial_and_booking_records_retained": True}


@router.get("/admin/privacy/retention-policies", tags=["privacy"])
def list_retention_policies(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    rows = db.query(PrivacyRetentionPolicy).order_by(PrivacyRetentionPolicy.data_category.asc()).all()
    return [{"id": x.id, "data_category": x.data_category, "retention_days": x.retention_days,
        "enabled": x.enabled, "legal_basis_note": x.legal_basis_note,
        "updated_at": x.updated_at.isoformat() if x.updated_at else None} for x in rows]

@router.put("/admin/privacy/retention-policies/{category}", tags=["privacy"])
def save_retention_policy(category: str, data: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    if category != "support_ticket_content": raise HTTPException(422, "Only support_ticket_content is currently supported")
    days = data.get("retention_days")
    if days is not None and (not isinstance(days, int) or days < 30 or days > 3650):
        raise HTTPException(422, "retention_days must be between 30 and 3650")
    note = str(data.get("legal_basis_note", "")).strip()
    if len(note) > 1000: raise HTTPException(422, "Legal basis note is too long")
    row = db.query(PrivacyRetentionPolicy).filter_by(data_category=category).first()
    if not row:
        row = PrivacyRetentionPolicy(data_category=category); db.add(row)
    row.retention_days = days
    row.enabled = bool(data.get("enabled", False)) and days is not None
    row.legal_basis_note = note
    row.updated_by = user.id
    db.commit(); db.refresh(row)
    audit(db, user.id, "privacy.retention_policy_updated", "privacy_retention_policy", row.id,
          {"category": category, "enabled": row.enabled, "retention_days": row.retention_days})
    db.commit()
    return {"data_category": row.data_category, "retention_days": row.retention_days,
            "enabled": row.enabled, "legal_basis_note": row.legal_basis_note}

@router.post("/admin/privacy/retention/run", tags=["privacy"])
def run_retention_job(data: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    from app.services.privacy_retention import run_privacy_retention
    category = str(data.get("category", "support_ticket_content"))
    apply = data.get("apply") is True
    try:
        return run_privacy_retention(db, category=category, apply=apply, run_by=user.id)
    except ValueError as exc:
        raise HTTPException(409, str(exc))

@router.get("/admin/privacy/retention/runs", tags=["privacy"])
def retention_run_history(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    rows = db.query(PrivacyRetentionRun).order_by(PrivacyRetentionRun.created_at.desc()).limit(100).all()
    return [{"id": x.id, "category": x.data_category, "mode": x.run_mode,
        "candidates": x.candidates, "anonymized": x.anonymized, "details": x.details,
        "created_at": x.created_at.isoformat()} for x in rows]


@router.get("/admin/privacy/data-inventory", tags=["privacy"])
def privacy_data_inventory(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    """Metadata-only inventory; never returns row values or document contents."""
    from app.db import Base
    sensitive_terms = ("password", "token", "secret", "document_number", "stored_filename", "file_path", "content")
    items = []
    for table in sorted(Base.metadata.sorted_tables, key=lambda t: t.name):
        columns = []
        for column in table.columns:
            columns.append({"name": column.name, "type": str(column.type), "nullable": column.nullable,
                            "classification": "restricted" if any(term in column.name.lower() for term in sensitive_terms) else "standard"})
        items.append({"table": table.name, "columns": columns,
                      "personal_data_indicator": any(c.name in {"user_id", "customer_id", "provider_id", "email", "phone", "name"} for c in table.columns)})
    return {"generated_at": datetime.utcnow().isoformat(), "table_count": len(items), "tables": items,
            "scope_note": "Schema metadata only. This inventory does not prove operational data flows, processors, hosting locations or legal basis."}


@router.get("/admin/privacy/consent-audit", tags=["privacy"])
def privacy_consent_audit(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    limit = max(1, min(limit, 500))
    rows = db.query(AuditLog).filter(AuditLog.action == "privacy.consent_updated").order_by(AuditLog.created_at.desc()).limit(limit).all()
    import json
    return [{"id": x.id, "actor_id": x.actor_id, "resource_id": x.resource_id,
             "action": x.action, "details": json.loads(x.details_json or "{}"),
             "occurred_at": x.created_at.isoformat() if x.created_at else None} for x in rows]


@router.get("/admin/privacy/compliance-evidence", tags=["privacy"])
def privacy_compliance_evidence(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    """A point-in-time evidence summary assembled from currently available records."""
    from app.db import Base
    inventory_tables = len(Base.metadata.tables)
    consent_total = db.query(UserPrivacyConsent).count()
    analytics_opt_in = db.query(UserPrivacyConsent).filter_by(analytics_enabled=True).count()
    marketing_opt_in = db.query(UserPrivacyConsent).filter_by(marketing_enabled=True).count()
    requests = {status: db.query(UserPrivacyRequest).filter_by(status=status).count()
                for status in ("submitted", "in_review", "completed", "rejected")}
    policies = db.query(PrivacyRetentionPolicy).all()
    retention_runs = db.query(PrivacyRetentionRun).count()
    consent_events = db.query(AuditLog).filter(AuditLog.action == "privacy.consent_updated").count()
    return {"generated_at": datetime.utcnow().isoformat(), "evidence_type": "point_in_time_application_report",
            "inventory_table_count": inventory_tables, "consent": {"accounts_with_saved_preferences": consent_total,
            "analytics_opt_in": analytics_opt_in, "marketing_opt_in": marketing_opt_in,
            "recorded_consent_update_events": consent_events}, "privacy_requests_by_status": requests,
            "retention": {"configured_policies": len(policies), "enabled_policies": sum(1 for p in policies if p.enabled),
            "recorded_runs": retention_runs},
            "limitations": ["Not an independent compliance certification or legal opinion.",
            "Consent event history exists only from the point this audit action was introduced; earlier changes are not reconstructed.",
            "Schema inventory does not establish all external processors, data transfers, purposes or lawful bases."]}


# Privacy processing register, processors and international transfer records.
def _privacy_text(value, limit=1000):
    return str(value or "").strip()[:limit]

@router.get("/admin/privacy/processors", tags=["privacy"])
def list_privacy_processors(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    return [{"id": x.id, "name": x.name, "service_description": x.service_description,
             "data_categories": x.data_categories, "processing_purpose": x.processing_purpose,
             "country": x.country, "subprocessors": x.subprocessors,
             "contract_reference": x.contract_reference, "active": x.active,
             "updated_at": x.updated_at.isoformat() if x.updated_at else None}
            for x in db.query(PrivacyProcessor).order_by(PrivacyProcessor.name).all()]

@router.post("/admin/privacy/processors", tags=["privacy"])
def create_privacy_processor(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    name = _privacy_text(payload.get("name"), 180)
    if not name: raise HTTPException(422, "Processor name is required")
    item = PrivacyProcessor(name=name, service_description=_privacy_text(payload.get("service_description")),
        data_categories=_privacy_text(payload.get("data_categories")), processing_purpose=_privacy_text(payload.get("processing_purpose")),
        country=_privacy_text(payload.get("country"),120), subprocessors=_privacy_text(payload.get("subprocessors")),
        contract_reference=_privacy_text(payload.get("contract_reference"),250), active=bool(payload.get("active", True)), created_by=user.id)
    db.add(item); db.flush(); audit(db,user.id,"privacy.processor_created","privacy_processor",item.id,{"name":item.name}); db.commit(); db.refresh(item)
    return {"id":item.id,"name":item.name,"active":item.active}

@router.put("/admin/privacy/processors/{item_id}", tags=["privacy"])
def update_privacy_processor(item_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    item=db.get(PrivacyProcessor,item_id)
    if not item: raise HTTPException(404,"Processor not found")
    for key,limit in (("name",180),("service_description",1000),("data_categories",1000),("processing_purpose",1000),("country",120),("subprocessors",1000),("contract_reference",250)):
        if key in payload: setattr(item,key,_privacy_text(payload[key],limit))
    if "active" in payload: item.active=bool(payload["active"])
    audit(db,user.id,"privacy.processor_updated","privacy_processor",item.id,{"active":item.active}); db.commit()
    return {"id":item.id,"name":item.name,"active":item.active}

@router.get("/admin/privacy/processing-register", tags=["privacy"])
def list_processing_register(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    return [{"id":x.id,"activity_name":x.activity_name,"purpose":x.purpose,"data_subjects":x.data_subjects,"data_categories":x.data_categories,"lawful_basis":x.lawful_basis,"retention_rule":x.retention_rule,"security_measures":x.security_measures,"processor_ids":x.processor_ids,"owner_department":x.owner_department,"active":x.active} for x in db.query(PrivacyProcessingActivity).order_by(PrivacyProcessingActivity.activity_name).all()]

@router.post("/admin/privacy/processing-register", tags=["privacy"])
def create_processing_activity(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    name=_privacy_text(payload.get("activity_name"),180)
    if not name: raise HTTPException(422,"Activity name is required")
    item=PrivacyProcessingActivity(activity_name=name,purpose=_privacy_text(payload.get("purpose")),data_subjects=_privacy_text(payload.get("data_subjects"),500),data_categories=_privacy_text(payload.get("data_categories")),lawful_basis=_privacy_text(payload.get("lawful_basis"),250),retention_rule=_privacy_text(payload.get("retention_rule"),500),security_measures=_privacy_text(payload.get("security_measures")),processor_ids=_privacy_text(payload.get("processor_ids"),2000),owner_department=_privacy_text(payload.get("owner_department"),160),active=bool(payload.get("active",True)),created_by=user.id)
    db.add(item); db.flush(); audit(db,user.id,"privacy.processing_activity_created","privacy_processing_activity",item.id,{"activity_name":name}); db.commit(); db.refresh(item)
    return {"id":item.id,"activity_name":item.activity_name}

@router.get("/admin/privacy/cross-border-transfers", tags=["privacy"])
def list_cross_border_transfers(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    return [{"id":x.id,"processor_id":x.processor_id,"origin_country":x.origin_country,"destination_country":x.destination_country,"data_categories":x.data_categories,"transfer_purpose":x.transfer_purpose,"transfer_mechanism":x.transfer_mechanism,"safeguards_note":x.safeguards_note,"reviewed_at":x.reviewed_at.isoformat() if x.reviewed_at else None,"active":x.active} for x in db.query(PrivacyCrossBorderTransfer).order_by(PrivacyCrossBorderTransfer.updated_at.desc()).all()]

@router.post("/admin/privacy/cross-border-transfers", tags=["privacy"])
def create_cross_border_transfer(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    origin=_privacy_text(payload.get("origin_country"),120); destination=_privacy_text(payload.get("destination_country"),120)
    if not origin or not destination: raise HTTPException(422,"Origin and destination countries are required")
    processor_id=payload.get("processor_id") or None
    if processor_id and not db.get(PrivacyProcessor,processor_id): raise HTTPException(404,"Processor not found")
    item=PrivacyCrossBorderTransfer(processor_id=processor_id,origin_country=origin,destination_country=destination,data_categories=_privacy_text(payload.get("data_categories")),transfer_purpose=_privacy_text(payload.get("transfer_purpose")),transfer_mechanism=_privacy_text(payload.get("transfer_mechanism"),500),safeguards_note=_privacy_text(payload.get("safeguards_note"),1500),active=bool(payload.get("active",True)),created_by=user.id)
    db.add(item); db.flush(); audit(db,user.id,"privacy.cross_border_transfer_created","privacy_cross_border_transfer",item.id,{"origin":origin,"destination":destination}); db.commit(); db.refresh(item)
    return {"id":item.id,"origin_country":origin,"destination_country":destination}

@router.get("/admin/privacy/processing-evidence", tags=["privacy"])
def processing_evidence(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    processors=db.query(PrivacyProcessor).all(); activities=db.query(PrivacyProcessingActivity).all(); transfers=db.query(PrivacyCrossBorderTransfer).all()
    return {"generated_at":datetime.utcnow().isoformat(),"processors_total":len(processors),"processors_active":sum(x.active for x in processors),"processing_activities_total":len(activities),"processing_activities_active":sum(x.active for x in activities),"cross_border_transfers_total":len(transfers),"cross_border_transfers_active":sum(x.active for x in transfers),"unreviewed_transfers":sum(x.reviewed_at is None for x in transfers),"limitations":["Register contents are administrator-entered declarations and are not independently verified.","A recorded transfer mechanism or safeguard is not a legal determination that a transfer is lawful.","This report does not discover processors or data flows automatically."]}


# DPIA / privacy risk assessments and mitigation register.
def _risk_score(likelihood, impact):
    return max(1, min(5, int(likelihood))) * max(1, min(5, int(impact)))

def _risk_item_json(x):
    return {"id":x.id,"assessment_id":x.assessment_id,"risk_description":x.risk_description,"affected_people":x.affected_people,"likelihood":x.likelihood,"impact":x.impact,"inherent_score":_risk_score(x.likelihood,x.impact),"mitigation":x.mitigation,"mitigation_owner":x.mitigation_owner,"due_date":x.due_date.isoformat() if x.due_date else None,"mitigation_status":x.mitigation_status,"residual_likelihood":x.residual_likelihood,"residual_impact":x.residual_impact,"residual_score":_risk_score(x.residual_likelihood,x.residual_impact) if x.residual_likelihood and x.residual_impact else None}

@router.get("/admin/privacy/risk-assessments", tags=["privacy-risk"] )
def list_privacy_risk_assessments(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    rows=db.query(PrivacyRiskAssessment).order_by(PrivacyRiskAssessment.updated_at.desc()).all()
    return [{"id":a.id,"title":a.title,"processing_activity_id":a.processing_activity_id,"assessment_type":a.assessment_type,"scope":a.scope,"necessity_proportionality":a.necessity_proportionality,"consultation_notes":a.consultation_notes,"status":a.status,"owner":a.owner,"reviewed_at":a.reviewed_at.isoformat() if a.reviewed_at else None,"risks":[_risk_item_json(r) for r in db.query(PrivacyRiskItem).filter_by(assessment_id=a.id).all()]} for a in rows]

@router.post("/admin/privacy/risk-assessments", tags=["privacy-risk"])
def create_privacy_risk_assessment(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    title=_privacy_text(payload.get("title"),180)
    if not title: raise HTTPException(422,"Assessment title is required")
    activity_id=payload.get("processing_activity_id") or None
    if activity_id and not db.get(PrivacyProcessingActivity,activity_id): raise HTTPException(404,"Processing activity not found")
    item=PrivacyRiskAssessment(title=title,processing_activity_id=activity_id,assessment_type=_privacy_text(payload.get("assessment_type","DPIA"),40),scope=_privacy_text(payload.get("scope"),5000),necessity_proportionality=_privacy_text(payload.get("necessity_proportionality"),5000),consultation_notes=_privacy_text(payload.get("consultation_notes"),5000),owner=_privacy_text(payload.get("owner"),160),created_by=user.id)
    db.add(item); db.flush(); audit(db,user.id,"privacy.risk_assessment_created","privacy_risk_assessment",item.id,{"title":title}); db.commit(); return {"id":item.id,"title":item.title,"status":item.status}

@router.post("/admin/privacy/risk-assessments/{assessment_id}/risks", tags=["privacy-risk"])
def create_privacy_risk_item(assessment_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    if not db.get(PrivacyRiskAssessment,assessment_id): raise HTTPException(404,"Assessment not found")
    description=_privacy_text(payload.get("risk_description"),5000)
    if not description: raise HTTPException(422,"Risk description is required")
    likelihood=max(1,min(5,int(payload.get("likelihood",3)))); impact=max(1,min(5,int(payload.get("impact",3))))
    due=None
    if payload.get("due_date"):
        try: due=date.fromisoformat(payload["due_date"])
        except (TypeError,ValueError): raise HTTPException(422,"due_date must be YYYY-MM-DD")
    item=PrivacyRiskItem(assessment_id=assessment_id,risk_description=description,affected_people=_privacy_text(payload.get("affected_people"),500),likelihood=likelihood,impact=impact,mitigation=_privacy_text(payload.get("mitigation"),5000),mitigation_owner=_privacy_text(payload.get("mitigation_owner"),160),due_date=due,mitigation_status="open")
    db.add(item); db.flush(); audit(db,user.id,"privacy.risk_item_created","privacy_risk_item",item.id,{"assessment_id":assessment_id,"inherent_score":_risk_score(likelihood,impact)}); db.commit(); db.refresh(item); return _risk_item_json(item)

@router.patch("/admin/privacy/risk-items/{risk_id}", tags=["privacy-risk"])
def update_privacy_risk_item(risk_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    item=db.get(PrivacyRiskItem,risk_id)
    if not item: raise HTTPException(404,"Risk item not found")
    if "mitigation" in payload: item.mitigation=_privacy_text(payload["mitigation"],5000)
    if "mitigation_owner" in payload: item.mitigation_owner=_privacy_text(payload["mitigation_owner"],160)
    if "mitigation_status" in payload:
        status=str(payload["mitigation_status"])
        if status not in {"open","in_progress","mitigated","accepted"}: raise HTTPException(422,"Invalid mitigation status")
        item.mitigation_status=status
    for key in ("residual_likelihood","residual_impact"):
        if key in payload:
            value=payload[key]; setattr(item,key,None if value is None else max(1,min(5,int(value))))
    if "due_date" in payload:
        try: item.due_date=date.fromisoformat(payload["due_date"]) if payload["due_date"] else None
        except (TypeError,ValueError): raise HTTPException(422,"due_date must be YYYY-MM-DD")
    audit(db,user.id,"privacy.risk_item_updated","privacy_risk_item",item.id,{"status":item.mitigation_status}); db.commit(); db.refresh(item); return _risk_item_json(item)

@router.post("/admin/privacy/risk-assessments/{assessment_id}/review", tags=["privacy-risk"])
def review_privacy_risk_assessment(assessment_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    item=db.get(PrivacyRiskAssessment,assessment_id)
    if not item: raise HTTPException(404,"Assessment not found")
    status=str(payload.get("status","reviewed"))
    if status not in {"reviewed","requires_changes","approved"}: raise HTTPException(422,"Invalid review status")
    item.status=status; item.reviewed_at=datetime.utcnow(); audit(db,user.id,"privacy.risk_assessment_reviewed","privacy_risk_assessment",item.id,{"status":status}); db.commit(); return {"id":item.id,"status":item.status,"reviewed_at":item.reviewed_at.isoformat()}

@router.get("/admin/privacy/risk-evidence", tags=["privacy-risk"])
def privacy_risk_evidence(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    assessments=db.query(PrivacyRiskAssessment).all(); risks=db.query(PrivacyRiskItem).all()
    return {"generated_at":datetime.utcnow().isoformat(),"assessments_total":len(assessments),"draft_assessments":sum(a.status=="draft" for a in assessments),"reviewed_assessments":sum(a.status in {"reviewed","approved"} for a in assessments),"risks_total":len(risks),"open_mitigations":sum(r.mitigation_status in {"open","in_progress"} for r in risks),"high_inherent_risks":sum(_risk_score(r.likelihood,r.impact)>=15 for r in risks),"overdue_mitigations":sum(bool(r.due_date and r.due_date<date.today() and r.mitigation_status not in {"mitigated","accepted"}) for r in risks),"limitations":["Risk scores are a simple 1–5 likelihood multiplied by 1–5 impact; configure and validate the scale with your privacy governance process.","This register does not determine whether a DPIA is legally required or whether residual risk is acceptable.","Assessment and mitigation content is administrator-entered and requires qualified review."]}


# Security incident and personal-data breach register. This records decisions; it does not send statutory notices.
def _incident_json(x, db):
    return {"id":x.id,"reference":x.reference,"title":x.title,"description":x.description,"discovered_at":x.discovered_at.isoformat() if x.discovered_at else None,"occurred_at":x.occurred_at.isoformat() if x.occurred_at else None,"severity":x.severity,"status":x.status,"personal_data_involved":x.personal_data_involved,"data_categories":x.data_categories,"affected_people_estimate":x.affected_people_estimate,"jurisdictions":x.jurisdictions,"containment_actions":x.containment_actions,"notification_assessment":x.notification_assessment,"notification_due_at":x.notification_due_at.isoformat() if x.notification_due_at else None,"notification_decision":x.notification_decision,"closed_at":x.closed_at.isoformat() if x.closed_at else None,"evidence":[{"id":e.id,"evidence_type":e.evidence_type,"summary":e.summary,"reference_uri":e.reference_uri,"recorded_at":e.recorded_at.isoformat()} for e in db.query(PrivacyIncidentEvidence).filter_by(incident_id=x.id).order_by(PrivacyIncidentEvidence.recorded_at.desc()).all()]}

def _incident_datetime(value, field):
    if not value: return None
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError: raise HTTPException(422, f"{field} must be an ISO-8601 datetime")

@router.get("/admin/privacy/incidents", tags=["privacy-incidents"])
def list_privacy_incidents(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    rows=db.query(PrivacySecurityIncident).order_by(PrivacySecurityIncident.discovered_at.desc()).all()
    return [_incident_json(x,db) for x in rows]

@router.post("/admin/privacy/incidents", tags=["privacy-incidents"])
def create_privacy_incident(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    title=_privacy_text(payload.get("title"),180)
    if not title: raise HTTPException(422,"Incident title is required")
    severity=str(payload.get("severity","medium"))
    if severity not in {"low","medium","high","critical"}: raise HTTPException(422,"Invalid severity")
    estimate=payload.get("affected_people_estimate")
    if estimate is not None and (int(estimate)<0 or int(estimate)>100000000): raise HTTPException(422,"Invalid affected people estimate")
    import secrets
    incident=PrivacySecurityIncident(reference="INC-"+secrets.token_hex(5).upper(),title=title,description=_privacy_text(payload.get("description"),10000),discovered_at=_incident_datetime(payload.get("discovered_at"),"discovered_at") or datetime.utcnow(),occurred_at=_incident_datetime(payload.get("occurred_at"),"occurred_at"),severity=severity,personal_data_involved=bool(payload.get("personal_data_involved",False)),data_categories=_privacy_text(payload.get("data_categories"),3000),affected_people_estimate=int(estimate) if estimate is not None else None,jurisdictions=_privacy_text(payload.get("jurisdictions"),1000),created_by=user.id)
    db.add(incident); db.flush(); audit(db,user.id,"privacy.incident_reported","privacy_security_incident",incident.id,{"reference":incident.reference,"severity":severity}); db.commit(); db.refresh(incident); return _incident_json(incident,db)

@router.patch("/admin/privacy/incidents/{incident_id}", tags=["privacy-incidents"])
def update_privacy_incident(incident_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    incident=db.get(PrivacySecurityIncident,incident_id)
    if not incident: raise HTTPException(404,"Incident not found")
    allowed={"reported","investigating","contained","notification_review","resolved","closed"}
    if "status" in payload:
        if payload["status"] not in allowed: raise HTTPException(422,"Invalid incident status")
        incident.status=payload["status"]; incident.closed_at=datetime.utcnow() if incident.status=="closed" else None
    if "severity" in payload:
        if payload["severity"] not in {"low","medium","high","critical"}: raise HTTPException(422,"Invalid severity")
        incident.severity=payload["severity"]
    for key,limit in (("containment_actions",5000),("notification_decision",5000),("data_categories",3000),("jurisdictions",1000)):
        if key in payload: setattr(incident,key,_privacy_text(payload[key],limit))
    if "notification_assessment" in payload:
        if payload["notification_assessment"] not in {"pending","required","not_required","under_review"}: raise HTTPException(422,"Invalid notification assessment")
        incident.notification_assessment=payload["notification_assessment"]
    if "notification_due_at" in payload: incident.notification_due_at=_incident_datetime(payload["notification_due_at"],"notification_due_at")
    if "affected_people_estimate" in payload: incident.affected_people_estimate=int(payload["affected_people_estimate"]) if payload["affected_people_estimate"] is not None else None
    audit(db,user.id,"privacy.incident_updated","privacy_security_incident",incident.id,{"status":incident.status,"notification_assessment":incident.notification_assessment}); db.commit(); db.refresh(incident); return _incident_json(incident,db)

@router.post("/admin/privacy/incidents/{incident_id}/evidence", tags=["privacy-incidents"])
def add_privacy_incident_evidence(incident_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    incident=db.get(PrivacySecurityIncident,incident_id)
    if not incident: raise HTTPException(404,"Incident not found")
    kind=_privacy_text(payload.get("evidence_type"),60); summary=_privacy_text(payload.get("summary"),5000)
    if not kind or not summary: raise HTTPException(422,"Evidence type and summary are required")
    uri=_privacy_text(payload.get("reference_uri"),500) or None
    if uri and not uri.startswith(("https://","s3://","gs://","file://")): raise HTTPException(422,"Evidence reference must use an approved secure URI scheme")
    item=PrivacyIncidentEvidence(incident_id=incident.id,evidence_type=kind,summary=summary,reference_uri=uri,recorded_by=user.id)
    db.add(item); db.flush(); audit(db,user.id,"privacy.incident_evidence_recorded","privacy_incident_evidence",item.id,{"incident_id":incident.id,"evidence_type":kind}); db.commit(); return {"id":item.id,"recorded_at":item.recorded_at.isoformat()}

@router.get("/admin/privacy/incidents/evidence-report", tags=["privacy-incidents"])
def privacy_incident_evidence_report(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    rows=db.query(PrivacySecurityIncident).all()
    return {"generated_at":datetime.utcnow().isoformat(),"total_incidents":len(rows),"open_incidents":sum(x.status not in {"resolved","closed"} for x in rows),"personal_data_incidents":sum(x.personal_data_involved for x in rows),"notification_pending":sum(x.notification_assessment in {"pending","under_review"} for x in rows),"notification_required":sum(x.notification_assessment=="required" for x in rows),"critical_incidents":sum(x.severity=="critical" for x in rows),"evidence_entries":db.query(PrivacyIncidentEvidence).count(),"disclaimer":"This is an internal evidence register, not a legal notification or determination. Assess applicable jurisdictional deadlines and obligations with qualified counsel and the relevant authority."}


# Incident response playbooks and post-incident learning records.
def _playbook_json(x):
    return {"id":x.id,"name":x.name,"incident_type":x.incident_type,"severity":x.severity,"response_steps":x.response_steps,"escalation_roles":x.escalation_roles,"enabled":x.enabled,"updated_at":x.updated_at.isoformat() if x.updated_at else None}

def _incident_review_json(x):
    return {"id":x.id,"incident_id":x.incident_id,"root_cause":x.root_cause,"impact_summary":x.impact_summary,"response_effectiveness":x.response_effectiveness,"lessons_learned":x.lessons_learned,"corrective_actions":x.corrective_actions,"owner":x.owner,"due_date":x.due_date.isoformat() if x.due_date else None,"status":x.status,"reviewed_at":x.reviewed_at.isoformat() if x.reviewed_at else None}

@router.get("/admin/privacy/incident-playbooks", tags=["privacy-incidents"])
def list_privacy_incident_playbooks(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    return [_playbook_json(x) for x in db.query(PrivacyIncidentPlaybook).order_by(PrivacyIncidentPlaybook.name).all()]

@router.post("/admin/privacy/incident-playbooks", tags=["privacy-incidents"])
def create_privacy_incident_playbook(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    name=_privacy_text(payload.get("name"),180)
    if not name: raise HTTPException(422,"Playbook name is required")
    if db.query(PrivacyIncidentPlaybook).filter_by(name=name).first(): raise HTTPException(409,"A playbook with this name already exists")
    severity=str(payload.get("severity","medium"))
    if severity not in {"low","medium","high","critical"}: raise HTTPException(422,"Invalid severity")
    item=PrivacyIncidentPlaybook(name=name,incident_type=_privacy_text(payload.get("incident_type"),80) or "general",severity=severity,response_steps=_privacy_text(payload.get("response_steps"),12000),escalation_roles=_privacy_text(payload.get("escalation_roles"),3000),enabled=bool(payload.get("enabled",True)),created_by=user.id)
    db.add(item); db.flush(); audit(db,user.id,"privacy.incident_playbook_created","privacy_incident_playbook",item.id,{"severity":severity}); db.commit(); db.refresh(item); return _playbook_json(item)

@router.patch("/admin/privacy/incident-playbooks/{playbook_id}", tags=["privacy-incidents"])
def update_privacy_incident_playbook(playbook_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    item=db.get(PrivacyIncidentPlaybook,playbook_id)
    if not item: raise HTTPException(404,"Playbook not found")
    for key,limit in (("name",180),("incident_type",80),("response_steps",12000),("escalation_roles",3000)):
        if key in payload:
            value=_privacy_text(payload[key],limit)
            if key=="name" and not value: raise HTTPException(422,"Playbook name is required")
            setattr(item,key,value)
    if "severity" in payload:
        if payload["severity"] not in {"low","medium","high","critical"}: raise HTTPException(422,"Invalid severity")
        item.severity=payload["severity"]
    if "enabled" in payload: item.enabled=bool(payload["enabled"])
    audit(db,user.id,"privacy.incident_playbook_updated","privacy_incident_playbook",item.id,{"enabled":item.enabled}); db.commit(); db.refresh(item); return _playbook_json(item)

@router.get("/admin/privacy/incidents/{incident_id}/post-incident-review", tags=["privacy-incidents"])
def get_privacy_post_incident_review(incident_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    if not db.get(PrivacySecurityIncident,incident_id): raise HTTPException(404,"Incident not found")
    rows=db.query(PrivacyIncidentReview).filter_by(incident_id=incident_id).order_by(PrivacyIncidentReview.reviewed_at.desc()).all()
    return [_incident_review_json(x) for x in rows]

@router.post("/admin/privacy/incidents/{incident_id}/post-incident-review", tags=["privacy-incidents"])
def create_privacy_post_incident_review(incident_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    if not db.get(PrivacySecurityIncident,incident_id): raise HTTPException(404,"Incident not found")
    status=str(payload.get("status","open"))
    if status not in {"open","in_progress","completed","accepted"}: raise HTTPException(422,"Invalid review status")
    due=None
    if payload.get("due_date"):
        try: due=date.fromisoformat(payload["due_date"])
        except (TypeError,ValueError): raise HTTPException(422,"due_date must be YYYY-MM-DD")
    item=PrivacyIncidentReview(incident_id=incident_id,root_cause=_privacy_text(payload.get("root_cause"),10000),impact_summary=_privacy_text(payload.get("impact_summary"),10000),response_effectiveness=_privacy_text(payload.get("response_effectiveness"),10000),lessons_learned=_privacy_text(payload.get("lessons_learned"),10000),corrective_actions=_privacy_text(payload.get("corrective_actions"),10000),owner=_privacy_text(payload.get("owner"),160),due_date=due,status=status,reviewed_by=user.id)
    db.add(item); db.flush(); audit(db,user.id,"privacy.incident_post_review_created","privacy_incident_review",item.id,{"incident_id":incident_id,"status":status}); db.commit(); db.refresh(item); return _incident_review_json(item)

@router.patch("/admin/privacy/incident-reviews/{review_id}", tags=["privacy-incidents"])
def update_privacy_post_incident_review(review_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    item=db.get(PrivacyIncidentReview,review_id)
    if not item: raise HTTPException(404,"Review not found")
    for key,limit in (("root_cause",10000),("impact_summary",10000),("response_effectiveness",10000),("lessons_learned",10000),("corrective_actions",10000),("owner",160)):
        if key in payload: setattr(item,key,_privacy_text(payload[key],limit))
    if "status" in payload:
        if payload["status"] not in {"open","in_progress","completed","accepted"}: raise HTTPException(422,"Invalid review status")
        item.status=payload["status"]
    if "due_date" in payload:
        try: item.due_date=date.fromisoformat(payload["due_date"]) if payload["due_date"] else None
        except (TypeError,ValueError): raise HTTPException(422,"due_date must be YYYY-MM-DD")
    audit(db,user.id,"privacy.incident_post_review_updated","privacy_incident_review",item.id,{"status":item.status}); db.commit(); db.refresh(item); return _incident_review_json(item)

@router.get("/admin/privacy/incident-response-evidence", tags=["privacy-incidents"])
def privacy_incident_response_evidence(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    incidents=db.query(PrivacySecurityIncident).all(); reviews=db.query(PrivacyIncidentReview).all(); playbooks=db.query(PrivacyIncidentPlaybook).all()
    return {"generated_at":datetime.utcnow().isoformat(),"playbooks_total":len(playbooks),"enabled_playbooks":sum(x.enabled for x in playbooks),"incidents_total":len(incidents),"incidents_without_review":sum(not any(r.incident_id==i.id for r in reviews) for i in incidents),"open_corrective_actions":sum(r.status in {"open","in_progress"} for r in reviews),"overdue_corrective_actions":sum(bool(r.due_date and r.due_date<date.today() and r.status not in {"completed","accepted"}) for r in reviews),"completed_reviews":sum(r.status=="completed" for r in reviews),"note":"Evidence is administrator-entered. Playbooks do not automatically page responders or execute technical containment."}


# Security vulnerability register and patch remediation
def _vulnerability_json(item, events=None):
    return {"id":item.id,"reference":item.reference,"title":item.title,"description":item.description,
            "source":item.source,"affected_component":item.affected_component,"affected_version":item.affected_version,
            "cve_id":item.cve_id,"severity":item.severity,"cvss_score":item.cvss_score,"status":item.status,
            "discovered_at":item.discovered_at.isoformat() if item.discovered_at else None,
            "due_date":item.due_date.isoformat() if item.due_date else None,"remediation_summary":item.remediation_summary,
            "workaround":item.workaround,"assigned_to":item.assigned_to,
            "resolved_at":item.resolved_at.isoformat() if item.resolved_at else None,
            "events":[{"id":e.id,"event_type":e.event_type,"summary":e.summary,"evidence_reference":e.evidence_reference,
                       "created_at":e.created_at.isoformat() if e.created_at else None} for e in (events or [])]}

@router.get("/admin/security/vulnerabilities", tags=["security-vulnerabilities"])
def list_security_vulnerabilities(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    items=db.query(SecurityVulnerability).order_by(SecurityVulnerability.discovered_at.desc()).all()
    return [_vulnerability_json(x, db.query(VulnerabilityRemediationEvent).filter(VulnerabilityRemediationEvent.vulnerability_id==x.id).order_by(VulnerabilityRemediationEvent.created_at.desc()).all()) for x in items]

@router.post("/admin/security/vulnerabilities", tags=["security-vulnerabilities"])
def create_security_vulnerability(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    title=_privacy_text(payload.get("title"),200)
    if not title: raise HTTPException(422,"title is required")
    severity=payload.get("severity","medium")
    if severity not in {"critical","high","medium","low","informational"}: raise HTTPException(422,"Invalid severity")
    score=payload.get("cvss_score")
    if score is not None and (not isinstance(score,(int,float)) or score<0 or score>10): raise HTTPException(422,"CVSS score must be between 0 and 10")
    due=None
    try: due=date.fromisoformat(payload["due_date"]) if payload.get("due_date") else None
    except (TypeError,ValueError): raise HTTPException(422,"due_date must be YYYY-MM-DD")
    item=SecurityVulnerability(reference="VUL-"+secrets.token_hex(5).upper(),title=title,description=_privacy_text(payload.get("description"),10000),source=_privacy_text(payload.get("source","manual"),80),affected_component=_privacy_text(payload.get("affected_component"),180),affected_version=_privacy_text(payload.get("affected_version"),100),cve_id=_privacy_text(payload.get("cve_id"),30) or None,severity=severity,cvss_score=score,status="identified",due_date=due,remediation_summary=_privacy_text(payload.get("remediation_summary"),10000),workaround=_privacy_text(payload.get("workaround"),10000),assigned_to=_privacy_text(payload.get("assigned_to"),160),created_by=user.id)
    db.add(item); db.flush()
    ev=VulnerabilityRemediationEvent(vulnerability_id=item.id,event_type="identified",summary="Vulnerability entered in register",created_by=user.id); db.add(ev)
    audit(db,user.id,"security.vulnerability_created","security_vulnerability",item.id,{"severity":severity,"component":item.affected_component})
    db.commit(); db.refresh(item); return _vulnerability_json(item,[ev])

@router.patch("/admin/security/vulnerabilities/{vulnerability_id}", tags=["security-vulnerabilities"])
def update_security_vulnerability(vulnerability_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    item=db.get(SecurityVulnerability,vulnerability_id)
    if not item: raise HTTPException(404,"Vulnerability not found")
    allowed={"title":200,"description":10000,"source":80,"affected_component":180,"affected_version":100,"cve_id":30,"remediation_summary":10000,"workaround":10000,"assigned_to":160}
    for key,limit in allowed.items():
        if key in payload: setattr(item,key,_privacy_text(payload[key],limit))
    if "severity" in payload:
        if payload["severity"] not in {"critical","high","medium","low","informational"}: raise HTTPException(422,"Invalid severity")
        item.severity=payload["severity"]
    if "cvss_score" in payload:
        score=payload["cvss_score"]
        if score is not None and (not isinstance(score,(int,float)) or score<0 or score>10): raise HTTPException(422,"CVSS score must be between 0 and 10")
        item.cvss_score=score
    if "due_date" in payload:
        try: item.due_date=date.fromisoformat(payload["due_date"]) if payload["due_date"] else None
        except (TypeError,ValueError): raise HTTPException(422,"due_date must be YYYY-MM-DD")
    if "status" in payload:
        if payload["status"] not in {"identified","triaged","in_progress","mitigated","resolved","accepted","false_positive"}: raise HTTPException(422,"Invalid status")
        item.status=payload["status"]
        if item.status=="resolved": item.resolved_at=datetime.utcnow()
        elif item.status!="resolved": item.resolved_at=None
    db.add(VulnerabilityRemediationEvent(vulnerability_id=item.id,event_type="status_or_record_updated",summary=_privacy_text(payload.get("event_summary","Vulnerability record updated"),2000),evidence_reference=_privacy_text(payload.get("evidence_reference"),500) or None,created_by=user.id))
    audit(db,user.id,"security.vulnerability_updated","security_vulnerability",item.id,{"status":item.status,"severity":item.severity})
    db.commit(); db.refresh(item)
    events=db.query(VulnerabilityRemediationEvent).filter(VulnerabilityRemediationEvent.vulnerability_id==item.id).order_by(VulnerabilityRemediationEvent.created_at.desc()).all()
    return _vulnerability_json(item,events)

@router.post("/admin/security/vulnerabilities/{vulnerability_id}/events", tags=["security-vulnerabilities"])
def add_vulnerability_remediation_event(vulnerability_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    item=db.get(SecurityVulnerability,vulnerability_id)
    if not item: raise HTTPException(404,"Vulnerability not found")
    event_type=payload.get("event_type","remediation")
    if event_type not in {"triage","patch_planned","patch_applied","verification","rollback","exception","remediation","note"}: raise HTTPException(422,"Invalid event type")
    summary=_privacy_text(payload.get("summary"),5000)
    if not summary: raise HTTPException(422,"summary is required")
    ev=VulnerabilityRemediationEvent(vulnerability_id=item.id,event_type=event_type,summary=summary,evidence_reference=_privacy_text(payload.get("evidence_reference"),500) or None,created_by=user.id)
    db.add(ev); audit(db,user.id,"security.vulnerability_event_added","security_vulnerability",item.id,{"event_type":event_type}); db.commit(); db.refresh(ev)
    return {"id":ev.id,"event_type":ev.event_type,"summary":ev.summary,"evidence_reference":ev.evidence_reference,"created_at":ev.created_at.isoformat() if ev.created_at else None}

@router.get("/admin/security/vulnerability-report", tags=["security-vulnerabilities"])
def security_vulnerability_report(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    items=db.query(SecurityVulnerability).all(); today=date.today()
    return {"generated_at":datetime.utcnow().isoformat(),"total":len(items),
            "by_severity":{s:sum(x.severity==s for x in items) for s in ["critical","high","medium","low","informational"]},
            "by_status":{s:sum(x.status==s for x in items) for s in ["identified","triaged","in_progress","mitigated","resolved","accepted","false_positive"]},
            "overdue":sum(bool(x.due_date and x.due_date<today and x.status not in {"resolved","accepted","false_positive"}) for x in items),
            "unassigned":sum(not x.assigned_to for x in items),
            "note":"Manually maintained register. No automated scanning, dependency analysis, patch deployment or verification is performed."}
