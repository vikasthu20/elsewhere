# Domain services

Business rules and serialization helpers shared by API endpoints live here. Routers should validate HTTP input, call a service, and translate domain errors into HTTP responses.

- `auth.py`: email normalization and public user serialization
- `budget.py`: Decimal-based INR budget estimation
- `bookings.py`: booking date validation, overlap detection and quote calculation
- `destinations.py`: destination serialization and query filtering helper
- `itineraries.py`: clearly labelled draft itinerary stop generation (not a live route provider)
- `vehicles.py`: vehicle serialization and booking eligibility
- `reviews.py`: rating and comment validation helpers

External route/maps, payment, OTP and official document verification integrations are not configured in this package; do not represent estimates or uploaded documents as confirmed provider data.
