/** Authentication feature entry points. */
export { LoginPage, RegisterPage, ForgotPasswordPage } from '../../pages/AuthPages';
export const authRoutes = ['/login', '/register', '/forgot-password'] as const;
export type AccountRole = 'traveller' | 'vehicle_owner' | 'travel_agency' | 'support' | 'admin';
