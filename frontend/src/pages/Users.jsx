import { useState } from 'react';
import { get, patch, post } from '../api.js';
import { useAuth } from '../auth.jsx';
import { Alert, Badge, Card, Spinner, useLoad } from '../ui.jsx';

const ROLES = { admin: 'Administrator', records_officer: 'Records officer', analyst: 'Analyst' };

export default function Users() {
  const { user } = useAuth();
  const [users, , reload] = useLoad(() => get('/users'), []);
  const [runs] = useLoad(() => get('/runs'), []);
  const [f, setF] = useState({ username: '', full_name: '', email: '', password: '', role: 'analyst' });
  const [msg, setMsg] = useState(null);
  const create = async (e) => {
    e.preventDefault();
    try { await post('/users', { ...f, email: f.email || null }); setMsg({ kind: 'success', text: 'Account created.' }); setF({ ...f, username: '', full_name: '', email: '', password: '' }); reload(); }
    catch (x) { setMsg({ kind: 'error', text: x.message }); }
  };
  const change = async (u, body) => { try { await patch(`/users/${u.id}`, body); reload(); } catch (x) { setMsg({ kind: 'error', text: x.message }); } };
  return (
    <>
      <div className="page-head"><h1>Users and activity</h1></div>
      <Alert kind={msg?.kind} onClose={() => setMsg(null)}>{msg?.text}</Alert>
      <div className="grid2">
        <Card title="Accounts">{!users ? <Spinner /> : <table><thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Status</th></tr></thead>
          <tbody>{users.map((u) => <tr key={u.id}><td>{u.full_name}</td><td>{u.username}</td>
            <td><select value={u.role} disabled={u.id === user.id} onChange={(e) => change(u, { role: e.target.value })}>{Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></td>
            <td><button className="btn btn-small btn-ghost" disabled={u.id === user.id} onClick={() => change(u, { is_active: !u.is_active })}>
              <Badge kind={u.is_active ? 'ok' : 'neutral'}>{u.is_active ? 'active' : 'inactive'}</Badge></button></td></tr>)}</tbody></table>}</Card>
        <Card title="New account"><form className="form" onSubmit={create}>
          <label>Full name<input required value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></label>
          <label>Username<input required minLength={3} value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} /></label>
          <label>Email (optional)<input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
          <label>Temporary password<input required minLength={8} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></label>
          <label>Role<select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <button className="btn btn-primary">Create account</button></form></Card>
      </div>
      <Card title="Analysis activity log">{!runs ? <Spinner /> : <div className="table-wrap"><table><thead><tr><th>When</th><th>Analysis</th><th>By</th><th className="num">Time (ms)</th><th>Result</th></tr></thead>
        <tbody>{runs.map((r) => <tr key={r.id}><td>{r.at.replace('T', ' ')}</td><td>{r.kind.replace('_', ' ')}</td><td>{r.by}</td><td className="num">{r.duration_ms}</td>
          <td className="small muted">{Object.entries(r.summary).map(([k, v]) => `${k}: ${v}`).join(', ')}</td></tr>)}</tbody></table></div>}</Card>
    </>
  );
}
