const BASE = import.meta.env?.VITE_API_URL || 'http://localhost:8000/api/v1';
export const token = () => (typeof localStorage !== 'undefined' ? localStorage.getItem('elsewhere_token') || '' : '');
export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (token()) headers.set('Authorization', `Bearer ${token()}`);
  const response = await fetch(`${BASE}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload as T;
}
