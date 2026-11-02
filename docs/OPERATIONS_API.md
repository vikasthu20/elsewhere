# Operations API

All paths are relative to `/api/v1`.

| Method | Path | Access |
|---|---|---|
| POST | `/support/tickets` | Authenticated user |
| GET | `/support/tickets/mine` | Authenticated user |
| GET | `/admin/support/tickets` | Admin/staff |
| PATCH | `/admin/support/tickets/{ticket_id}` | Admin/staff |
| GET | `/notifications/mine` | Authenticated user |
| POST | `/notifications/{notification_id}/read` | Notification owner |
| POST | `/owner/drivers` | Owner/agency/admin |
| GET | `/owner/drivers` | Owner/agency/admin |
| POST | `/owner/bookings/{booking_id}/driver` | Booking vehicle owner |
| POST | `/owner/vehicles/{vehicle_id}/maintenance` | Vehicle owner |
| GET | `/owner/vehicles/{vehicle_id}/maintenance` | Vehicle owner |
| PATCH | `/admin/vehicles/{vehicle_id}/verification` | Admin |
| GET | `/admin/audit-logs` | Admin |
| POST | `/auth/otp/request` | Public; development code only in console mode |
| POST | `/auth/password-reset` | Public; requires valid OTP |
| POST | `/documents/metadata` | Authenticated user |
| POST | `/bookings/{booking_id}/cancel` | Booking owner |
| POST | `/bookings/{booking_id}/payment-intent` | Booking owner; provider required |
| POST | `/bookings/{booking_id}/refund-request` | Booking owner; creates manual review ticket |

Document metadata is not a binary upload. Payment intents and refunds are not live money movement until a gateway adapter and signed webhook verification are configured.
