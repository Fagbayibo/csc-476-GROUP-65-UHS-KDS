import { useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './auth.jsx';
import { Spinner } from './ui.jsx';
import Login from './pages/Login.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Explore from './pages/Explore.jsx';
import Patterns from './pages/Patterns.jsx';
import Clusters from './pages/Clusters.jsx';
import Forecast from './pages/Forecast.jsx';
import Alerts from './pages/Alerts.jsx';
import Data from './pages/Data.jsx';
import Users from './pages/Users.jsx';

const NAV = [
  ['/', 'Dashboard', null], ['/explore', 'Explore', null], ['/patterns', 'Patterns', ['admin', 'analyst']],
  ['/clusters', 'Clusters', ['admin', 'analyst']], ['/forecast', 'Forecast', ['admin', 'analyst']],
  ['/alerts', 'Outbreak alerts', null], ['/data', 'Data', null], ['/users', 'Users', ['admin']],
];
const ROLE = { admin: 'Administrator', records_officer: 'Records officer', analyst: 'Analyst' };

function Guard({ roles, children }) {
  const { can } = useAuth();
  return !roles || can(...roles) ? children : <p className="empty">Your role does not give access to this page.</p>;
}

export default function App() {
  const { user, ready, logout, can } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  if (!ready) return <Spinner />;
  if (!user) return <Routes><Route path="*" element={<Login />} /></Routes>;
  return (
    <div className="layout">
      <aside className={open ? 'side open' : 'side'}>
        <div className="brand"><img src="/favicon.svg" alt="" width="34" height="34" />
          <div><strong>UHS Knowledge Discovery</strong><small>University Health Service, Jaja</small></div></div>
        <nav>{NAV.filter(([, , r]) => !r || can(...r)).map(([to, label]) => <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>)}</nav>
        <div className="who"><span>{user.full_name}</span><small>{ROLE[user.role]}</small>
          <button className="btn btn-ghost btn-small" onClick={logout}>Sign out</button></div>
      </aside>
      <div className="main">
        <header className="topbar"><button className="menu" onClick={() => setOpen(!open)} aria-label="Menu">☰</button>
          <span className="synthetic">Demonstration data: synthetic records, not real patients</span></header>
        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/explore" element={<Explore />} />
            <Route path="/patterns" element={<Guard roles={['admin', 'analyst']}><Patterns /></Guard>} />
            <Route path="/clusters" element={<Guard roles={['admin', 'analyst']}><Clusters /></Guard>} />
            <Route path="/forecast" element={<Guard roles={['admin', 'analyst']}><Forecast /></Guard>} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/data" element={<Data />} />
            <Route path="/users" element={<Guard roles={['admin']}><Users /></Guard>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
