from fastapi import APIRouter
from . import auth, destinations, itineraries, vehicles, bookings, reviews, budget, admin, operations, tour_payments, security_monitoring, audit_integrity, audit_evidence, audit_archive, audit_archive_jobs, audit_compliance, content, admin_workspace, email_admin, provider_catalog
api = APIRouter()
for module in (auth, destinations, itineraries, vehicles, bookings, reviews, budget, admin, operations, tour_payments, security_monitoring, audit_integrity, audit_evidence, audit_archive, audit_archive_jobs, audit_compliance, content, admin_workspace, email_admin, provider_catalog):
    api.include_router(module.router)
__all__ = ['api']
