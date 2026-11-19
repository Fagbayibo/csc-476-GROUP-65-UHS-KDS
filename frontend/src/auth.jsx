import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { get, post, setToken, getToken } from './api.js';

const Ctx = createContext(null);
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const logout = useCallback(() => { setToken(null); setUser(null); }, []);
  useEffect(() => {
    if (!getToken()) { setReady(true); return; }
    get('/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
  }, []);
  useEffect(() => {
    const f = () => logout();
    window.addEventListener('uhs:unauthorized', f);
    return () => window.removeEventListener('uhs:unauthorized', f);
  }, [logout]);
  const login = async (username, password) => {
    const r = await post('/auth/login', { username, password });
    setToken(r.token); setUser(r.user); return r.user;
  };
  const can = (...roles) => !!user && roles.includes(user.role);
  return <Ctx.Provider value={{ user, ready, login, logout, can }}>{children}</Ctx.Provider>;
}
export const useAuth = () => useContext(Ctx);
