const BASE = import.meta.env.VITE_API_URL || '/api';
let token = null;
try { token = localStorage.getItem('uhs_token'); } catch { /* ignore */ }

export function setToken(t) {
  token = t;
  try { t ? localStorage.setItem('uhs_token', t) : localStorage.removeItem('uhs_token'); } catch { /* ignore */ }
}
export const getToken = () => token;

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetch(BASE + path, { method, headers, body: form || (body !== undefined ? JSON.stringify(body) : undefined) });
  const isJson = (res.headers.get('content-type') || '').includes('json');
  const data = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const msg = typeof data === 'object' ? (Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join('; ') : data.detail) : data;
    if (res.status === 401 && token) window.dispatchEvent(new Event('uhs:unauthorized'));
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return data;
}
export const get = (p) => api(p);
export const post = (p, body = {}) => api(p, { method: 'POST', body });
export const patch = (p, body) => api(p, { method: 'PATCH', body });
export const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== '' && v !== undefined && v !== null)).toString();

export async function download(path, filename) {
  const res = await fetch(BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  URL.revokeObjectURL(a.href);
}
