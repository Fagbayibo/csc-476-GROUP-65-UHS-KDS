import { useState } from 'react';
import { useAuth } from '../auth.jsx';
import { Alert } from '../ui.jsx';

export default function Login() {
  const { login } = useAuth();
  const [f, setF] = useState({ username: '', password: '' });
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr('');
    try { await login(f.username, f.password); } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="login-wrap">
      <div className="login-art">
        <img src="/favicon.svg" alt="" width="56" height="56" />
        <h1>Knowledge Discovery System for Ailments Incidence</h1>
        <p>University Health Service (Jaja Clinic), University of Ibadan</p>
        <ul><li>Trends and seasonal patterns of ailments</li><li>Association rules and resident-hall clusters</li>
          <li>Monthly incidence forecasts</li><li>Early warning of unusual rises (outbreaks)</li></ul>
      </div>
      <form className="login card" onSubmit={submit}>
        <h2>Sign in</h2>
        <Alert kind="error">{err}</Alert>
        <label>Username<input value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} autoComplete="username" required /></label>
        <label>Password<input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="current-password" required /></label>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <p className="muted small">Access is restricted to authorised UHS staff. All patient identifiers are pseudonymised.</p>
      </form>
    </div>
  );
}
