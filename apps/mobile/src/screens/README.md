# React Native screens

Screens are implemented as independent React Native components and are wired into the native-stack navigator in `App.tsx`.

| Screen | File | Main interaction |
|---|---|---|
| Explore | `ExploreScreen.tsx` | Destination discovery and navigation to planning |
| Login | `LoginScreen.tsx` | API login and secure token persistence |
| Registration | `RegisterScreen.tsx` | Customer, vehicle owner and agency registration |
| Forgot password | `ForgotPasswordScreen.tsx` | Password recovery request |
| Destinations | `DestinationsScreen.tsx` | Search and select destinations |
| Trip planner | `TripPlannerScreen.tsx` | Create an itinerary draft through the API |
| Vehicles | `VehiclesScreen.tsx` | Browse sample vehicle listings |
| Booking | `BookingScreen.tsx` | Submit a vehicle booking request |
| Budget | `BudgetScreen.tsx` | Editable trip cost estimate |
| Profile | `ProfileScreen.tsx` | Account summary and sign out |
| Itinerary | `ItineraryScreen.tsx` | Day timeline presentation |

The photography URLs and vehicle prices in the mobile catalogue are illustrative sample content. Replace them with API data and approved image assets before production. API paths depend on the FastAPI routes available in the backend.
