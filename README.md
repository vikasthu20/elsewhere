# Elsewhere — Travel, thoughtfully discovered.

A responsive travel discovery and vehicle booking monorepo. This package contains real application source files, not only a folder skeleton.

## Workspace

```text
elsewhere-platform/
├── apps/
│   ├── web/                 # React + TypeScript + Vite website
│   │   ├── public/images/   # Included Elsewhere design board
│   │   └── src/             # Routes, pages, reusable layout, API client and styles
│   ├── mobile/              # Expo + React Native iOS / Android app
│   │   ├── App.tsx
│   │   └── src/api.ts
│   └── api/                 # FastAPI + SQLAlchemy + Alembic
│       ├── app/             # Models, schemas, auth, routers and settings
│       ├── migrations/      # Alembic migration
│       └── tests/
├── docs/                    # Architecture, security, screen catalogue, design refs
└── docker-compose.yml       # PostgreSQL + API + web
```

## Features implemented in this source package

### React web
- Premium Elsewhere editorial design system: Mineral Ivory, Deep Ink, Alpine Green, DM Serif Display and Manrope.
- Responsive desktop and mobile navigation with mobile bottom tabs.
- Homepage, destination discovery, destination detail, trip planner, vehicle marketplace, vehicle detail, budget calculator, booking request, login, registration, password recovery, account entry, owner dashboard, agency dashboard and protected admin overview.
- Destination and vehicle sample imagery; the design board is included under `apps/web/public/images/`.
- API client with bearer-token support and user-friendly request errors.

### React Native
- Expo app for iOS and Android.
- Explore, destination discovery, trip planning, ride listings, budget entry and profile tabs.
- Login and registration with Traveller, Vehicle Owner and Travel Agency account selection.
- Secure token/user storage with Expo SecureStore.
- Responsive safe-area layout and Elsewhere visual tokens.

### FastAPI + PostgreSQL
- Registration, login and current-user endpoint with password hashing and JWT access tokens.
- Destination search and detail, itinerary draft creation, vehicle listing/search, owner vehicle listing, booking request and owner booking status update, completed-trip review, budget estimate and protected admin overview endpoints.
- SQLAlchemy models, Alembic migration, Pydantic validation, CORS allowlist and Docker service definitions.
- Idempotent destination seed script and budget formula tests.

## Run with Docker

1. Install Docker Desktop / Docker Engine and Docker Compose v2.
2. Copy `apps/api/.env.example` to `apps/api/.env` and replace the development secret.
3. From this directory run:

```bash
docker compose up --build
```

4. Open:
   - Web: http://localhost:5173
   - API health: http://localhost:8000/health
   - OpenAPI docs: http://localhost:8000/docs
   - PostgreSQL: localhost:5432

The API container runs Alembic migrations before starting FastAPI.

## Local development

### API

```bash
cd apps/api
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python scripts_seed.py
uvicorn app.main:app --reload
```

### Web

```bash
cd apps/web
npm install
npm run dev
npm run build
```

### Mobile

```bash
cd apps/mobile
npm install
npx expo install --fix
npx expo start
```

Set `EXPO_PUBLIC_API_URL` to a reachable API URL. Android emulator commonly uses `http://10.0.2.2:8000/api/v1`; iOS simulator can use `http://localhost:8000/api/v1`; physical devices need your computer's LAN IP. Do not use localhost from a physical phone.

## Environment

See `apps/api/.env.example`. Do not commit real credentials. For production, use a managed secret store, HTTPS, strict CORS, secure session/token rotation, rate limits, MFA for privileged users and encrypted private object storage.

## Continuation implementation

The continuation adds persistent support tickets, staff ticket management, in-app notification inbox/read state, owner driver records and assignments, vehicle maintenance history, audit events, admin vehicle verification, OTP-based password reset in local development mode, document metadata registration, booking cancellation, and payment/refund request boundaries. API clients for these operations are provided for web and mobile.

Run `alembic upgrade head` before starting the API. The API no longer silently creates production schema at startup; Alembic is the schema authority.

## Integration boundaries and remaining work

- OTP challenge generation, expiry and hashed storage are implemented. `OTP_DELIVERY_MODE=console` returns a development code only; production SMS/email delivery still needs a provider adapter and credentials.
- Password reset is implemented for an email address after OTP verification. Contact verification, OAuth and account recovery email delivery still need provider flows.
- Payment intent contract is present but returns an explicit provider-not-configured response until a gateway adapter, credentials and signed webhook handler are added. Refund requests enter manual support review; no money is transferred.
- Document metadata validation is implemented. Binary upload to private object storage, signed downloads, malware scanning and official document checks require configured providers.
- Audit logs, support tickets, drivers, assignments and maintenance records are persisted. Notification inbox/read endpoints are present; event-driven notification creation and push/email/SMS delivery remain to be wired into all business events.
- Fixed-precision money fields are used for vehicle rates and booking totals. PostgreSQL migration adds an exclusion constraint to reject overlapping active bookings. SQLite local development does not provide that production concurrency guarantee.
- Live maps, geocoding, directions, opening hours, full review moderation, full agency/admin workflows, all 100+ planned screens, analytics, monitoring, load testing and production security review remain future work.

See `docs/IMPLEMENTATION_STATUS.md` and `docs/OPERATIONS_API.md` for the exact current boundary. Never treat provider stubs or development OTP codes as production integrations.


## Latest continuation update

The web Support page and Expo mobile app now connect to the persisted support-ticket and in-app notification APIs. Signed-in users can create support requests, review ticket status, load notifications and mark notifications as read. See `docs/IMPLEMENTATION_STATUS.md` for implementation boundaries and verification status.
