export type MobileAccountRole = 'traveller' | 'vehicle_owner' | 'travel_agency';
export type AuthSession = { access_token:string; token_type:'bearer'; user?:{id:string;email:string;role:MobileAccountRole} };
export const authStorageKey = 'elsewhere.auth.session';
