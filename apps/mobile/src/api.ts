import * as SecureStore from 'expo-secure-store';
const BASE = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
export async function api(path:string, options:RequestInit={}) {
  const headers = new Headers(options.headers);
  headers.set('Content-Type','application/json');
  const token = await SecureStore.getItemAsync('elsewhere_token');
  if (token) headers.set('Authorization',`Bearer ${token}`);
  const response = await fetch(`${BASE}${path}`,{...options,headers});
  const data = await response.json().catch(()=>({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}
