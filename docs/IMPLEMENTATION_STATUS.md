# Implementation status — continuation build

## Existing application preserved
- React web application, Expo React Native application and FastAPI API remain the base project.
- Existing authentication, destination, itinerary, vehicle, booking, review and budget routes are retained.
- Existing screens and design catalogue are retained; the catalogue is still a roadmap and is not a claim that 100+ screens have been implemented.

## Added in this continuation
- Connected the web Support page to the persisted support-ticket and notification APIs. Travellers can submit requests, view their support history, refresh the inbox and mark notifications as read.
- Added a Support & Updates screen to the Expo mobile app using the same authenticated APIs, including support request creation, ticket history and notification read status.
- Persisted support tickets with traveller creation/listing and staff/admin queue/update endpoints.
- Persisted in-app notifications and per-user read status.
- Owner/agency driver records and booking-to-driver assignment.
- Vehicle maintenance schedule and service history.
- Persistent audit event records for the new operational actions.
- Admin vehicle verification endpoint.
- OTP challenge generation with hashed codes, expiry and attempt limits; development mode can return a code for local testing. Production SMS/email delivery is not configured.
- Password reset using a valid OTP challenge.
- Private-document metadata registration with MIME/extension/size allowlisting. Binary private storage, malware scanning and official document verification are not implemented without provider adapters.
- Payment intent provider contract and explicit unconfigured-provider response. No live charge or refund is performed until a payment gateway is configured.
- Refund requests create a support ticket for manual review; they do not transfer money.
- Monetary columns changed to fixed precision Numeric in the ORM and migration. PostgreSQL migration adds an exclusion constraint to prevent overlapping active bookings for the same vehicle; SQLite does not provide the same concurrency guarantee.
- Added service tests for money rounding, document allowlisting and OTP hashing.

## Still requiring provider configuration or further implementation
- Live maps, geocoding, directions, opening hours and place search.
- Production email/SMS OTP delivery, OAuth providers and password-reset email/SMS delivery.
- Payment gateway checkout, signed webhooks, captures, settlements and actual refunds.
- Private object storage, signed download URLs, malware scanner and authorised document verification.
- Push/email/SMS notification delivery.
- Full owner/agency/admin dashboards and all 100+ catalogue screens.
- Advanced analytics, moderation workflows, driver availability calendars and maintenance-based vehicle blocking. Security notification SLA escalation is implemented; its delivery depends on an operations webhook.
- Production-grade rate limiting, secret management, monitoring, backups, security review and load testing.

## Verification
- API suite: `pytest -q` from `apps/api` — 40 passed, including existing-database migration recovery and positive/negative expense ownership, amount validation and CORS preflight cases.
- Web: `npm run build` and `npm run test` from `apps/web` — build passed and 12 tests passed.
- Mobile: exact dependency pins, `npx tsc --noEmit`, and `npx expo export --platform all` passed. Expo's local dependency check passed; its online version check was unavailable.
- Migrations: a clean SQLite database upgraded through `0057_email_retry_worker_leases`; PostgreSQL offline SQL generation also completed. A live PostgreSQL upgrade was not run because the Docker daemon is unavailable.
- Native Android/iOS compilation, live payment/S3/provider integrations, backup restore, monitoring, security review and load testing remain unverified. Payment and S3 actions still require configured providers and credentials.
- PostgreSQL-only exclusion constraint is installed by migration 0002. Use PostgreSQL for production booking concurrency.
