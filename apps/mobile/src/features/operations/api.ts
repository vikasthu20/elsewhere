import { api } from "../../api";

export const operationsApi = {
  myTickets: () => api("/support/tickets/mine"),
  createTicket: (input: { subject: string; message: string; priority?: "low"|"normal"|"high"|"urgent" }) =>
    api("/support/tickets", { method: "POST", body: JSON.stringify(input) }),
  notifications: () => api("/notifications/mine"),
  markNotificationRead: (id: string) => api(`/notifications/${id}/read`, { method: "POST" }),
  cancelBooking: (bookingId: string) => api(`/bookings/${bookingId}/cancel`, { method: "POST" }),
  requestPasswordReset: (destination: string, purpose: "password_reset" = "password_reset") =>
    api("/auth/otp/request", { method: "POST", body: JSON.stringify({ destination, purpose }) }),
  resetPassword: (input: { destination: string; code: string; new_password: string }) =>
    api("/auth/password-reset", { method: "POST", body: JSON.stringify(input) }),
};
