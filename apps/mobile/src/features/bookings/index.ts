export type MobileBookingStatus = 'requested'|'accepted'|'rejected'|'cancelled'|'completed';
export type MobileBooking = { id:string; vehicle_id:string; start_date:string; end_date:string; pickup_location:string; status:MobileBookingStatus };
