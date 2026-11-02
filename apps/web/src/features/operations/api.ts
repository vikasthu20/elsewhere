import { api } from "../../api";

export const operationsApi = {
  myTickets: () => api("/support/tickets/mine"),
  createTicket: (input: { subject: string; message: string; priority?: "low"|"normal"|"high"|"urgent" }) =>
    api("/support/tickets", { method: "POST", body: JSON.stringify(input) }),
  notifications: () => api("/notifications/mine"),
  markNotificationRead: (id: string) => api(`/notifications/${id}/read`, { method: "POST" }),
  ownerDrivers: () => api("/owner/drivers"),
  createDriver: (input: { name: string; phone: string; licence_number: string; licence_expiry?: string }) =>
    api("/owner/drivers", { method: "POST", body: JSON.stringify(input) }),
  assignDriver: (bookingId: string, driverId: string) =>
    api(`/owner/bookings/${bookingId}/driver`, { method: "POST", body: JSON.stringify({ driver_id: driverId }) }),
  maintenance: (vehicleId: string) => api(`/owner/vehicles/${vehicleId}/maintenance`),
  createMaintenance: (vehicleId: string, input: { description: string; service_date: string; next_service_date?: string; cost?: number; status?: string }) =>
    api(`/owner/vehicles/${vehicleId}/maintenance`, { method: "POST", body: JSON.stringify(input) }),
  auditLogs: () => api("/admin/audit-logs"),
  supportQueue: (status?: string) => api(`/admin/support/tickets${status ? `?status=${encodeURIComponent(status)}` : ""}`),
};
