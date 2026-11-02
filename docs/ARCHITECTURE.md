# Architecture

```text
Web (React/Vite) ─┐
Mobile (Expo/RN) ─┼─ HTTPS REST /api/v1 ─ FastAPI ─ SQLAlchemy ─ PostgreSQL
                  └─ Maps / geocoding provider (server-keyed integration)
                                      └─ private object storage for documents
```

## Design system
- Mineral Ivory `#F5F1E8`, Deep Ink `#242820`, Oxidized Persimmon `#C45A3C`, Alpine Green `#58745B`, Limestone `#DCD2C2`, Surface `#FFFCF6`.
- Display: DM Serif Display. UI: Manrope. Mobile falls back to Georgia/system sans until font assets are bundled.
- Editorial destination photography, restrained motion, generous whitespace, clear focus states and mobile-first layouts.
- Functional statuses use semantic success/warning/error colours; never encode status by colour alone.

## API domains
Authentication, profiles, destinations, itinerary, budget, vehicles, availability, bookings, reviews and administration. API version prefix: `/api/v1`.


## Operational API modules (continuation)
`app/routers/operations.py` adds support, notifications, owner driver/maintenance operations, admin audit and vehicle verification, OTP/password reset development flows, document metadata and payment/refund request endpoints. Domain helpers live in `app/services/operations.py`. The migration `0002_operations.py` adds persistent tables and fixed-precision money columns. PostgreSQL receives a GiST exclusion constraint for overlapping active vehicle bookings; SQLite is for local development and does not guarantee cross-process booking exclusion.
