# API routers

Each module owns one API domain and exposes a FastAPI `router`. `app/routers/__init__.py` composes these routers into the versioned API included by `app/main.py`.

- `auth.py`: registration, login and current-user session
- `destinations.py`: public destination search/detail and admin creation
- `itineraries.py`: itinerary draft creation and current-user itinerary list
- `vehicles.py`: public search/detail and owner vehicle management
- `bookings.py`: customer booking requests and owner booking decisions
- `reviews.py`: booking review submission
- `budget.py`: trip budget estimate endpoint
- `admin.py`: admin overview

Route implementations currently delegate to `app/legacy_routes.py` to preserve the existing API contract while the codebase is modularised. Move endpoint bodies into their respective router modules as the next refactoring step; do not create duplicate paths.
