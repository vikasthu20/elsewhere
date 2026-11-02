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

## Important limitations — not production complete

The current source implements a functional foundation and key flows, but does not yet implement every one of the 100+ planned screen surfaces or every requirement in the master brief. In particular:
- Real geocoding, route directions, live visiting hours and map licensing/API integration are not configured.
- OTP/email/SMS delivery and password-reset token delivery are not configured; the forgot-password screen is informational only.
- OAuth Google/Apple sign-in buttons are intentionally not active until provider credentials and callback flows are configured.
- Payment gateway, refund and signed webhook integration are not implemented.
- Private document upload, malware scanning and official vehicle-document verification are not implemented.
- Admin/agency dashboards are initial operational shells; moderation, full role/permission management, audit history and package management still need work.
- Booking concurrency needs a PostgreSQL exclusion constraint or equivalent transaction/locking strategy and dedicated concurrency tests before accepting live bookings.
- Sample destination and vehicle imagery/content are illustrative. Do not present sample prices, ratings, availability or generated itineraries as verified live facts.

Run the test suite with `pytest apps/api/tests`. Verify production builds and simulator/device behaviour in the target development environment before deployment.
