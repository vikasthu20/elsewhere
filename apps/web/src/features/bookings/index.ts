/** Booking request feature. */
export { BookingRequestPage } from '../../pages/PublicPages';
export type BookingStatus = 'requested' | 'accepted' | 'rejected' | 'cancelled' | 'completed';
export type BookingRequest = { vehicle_id:string; start_date:string; end_date:string; pickup_location:string; notes?:string };
export function isValidBookingDates(start:string,end:string) { return Boolean(start && end && new Date(end).getTime() >= new Date(start).getTime()); }
