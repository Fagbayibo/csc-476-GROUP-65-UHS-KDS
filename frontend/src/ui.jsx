import { useEffect, useState } from 'react';
import { get } from './api.js';

export const COLORS = ['#0f5f5c', '#f08a5d', '#3d84a8', '#b83b5e', '#6a994e', '#8d6cab', '#e0a800', '#5c677d'];
export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const fmt = (n) => Number(n ?? 0).toLocaleString('en-GB');

export function useLoad(fn, deps = []) {
  const [s, set] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    set((x) => ({ ...x, loading: true }));
    fn().then((data) => alive && set({ data, error: null, loading: false }))
      .catch((error) => alive && set({ data: null, error, loading: false }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return [s.data, s.error, () => setTick((t) => t + 1), s.loading];
}

let refCache = null;
export function useReference() {
  const [ref, setRef] = useState(refCache);
  useEffect(() => { if (!refCache) get('/reference').then((r) => { refCache = r; setRef(r); }).catch(() => {}); }, []);
  return ref;
}
export const clearReference = () => { refCache = null; };

export const Alert = ({ kind = 'info', children, onClose }) => children ? (
  <div className={`alert alert-${kind}`}><span>{children}</span>{onClose && <button className="x" onClick={onClose}>×</button>}</div>
) : null;
export const Spinner = ({ label }) => <div className="spin-wrap"><div className="spinner" />{label && <span>{label}</span>}</div>;
export const Badge = ({ kind = 'neutral', children }) => <span className={`badge badge-${kind}`}>{children}</span>;
export const Card = ({ title, children, right, className = '' }) => (
  <section className={`card ${className}`}>
    {(title || right) && <div className="card-head"><h2>{title}</h2>{right}</div>}
    {children}
  </section>
);
export const Stat = ({ label, value, note, tone }) => (
  <div className={`stat ${tone || ''}`}><span className="stat-v">{value}</span><span className="stat-l">{label}</span>{note && <span className="stat-n">{note}</span>}</div>
);

/** Shared filter bar used on the analysis pages. */
export function Filters({ value, onChange, show = ['date', 'category', 'sex', 'residence', 'ailment'] }) {
  const ref = useReference();
  if (!ref) return null;
  const set = (k) => (e) => onChange({ ...value, [k]: e.target.value });
  return (
    <div className="filters">
      {show.includes('date') && <>
        <label>From<input type="date" value={value.date_from || ''} onChange={set('date_from')} min={ref.date_range[0]} max={ref.date_range[1]} /></label>
        <label>To<input type="date" value={value.date_to || ''} onChange={set('date_to')} min={ref.date_range[0]} max={ref.date_range[1]} /></label>
      </>}
      {show.includes('category') && <label>Patients<select value={value.category || ''} onChange={set('category')}>
        <option value="">All</option>{ref.categories.map((c) => <option key={c}>{c}</option>)}</select></label>}
      {show.includes('sex') && <label>Sex<select value={value.sex || ''} onChange={set('sex')}>
        <option value="">All</option><option value="F">Female</option><option value="M">Male</option></select></label>}
      {show.includes('residence') && <label>Residence<select value={value.residence || ''} onChange={set('residence')}>
        <option value="">All</option>{ref.residences.map((r) => <option key={r.name}>{r.name}</option>)}</select></label>}
      {show.includes('ailment') && <label>Ailment<select value={value.ailment || ''} onChange={set('ailment')}>
        <option value="">All</option>{ref.ailments.map((a) => <option key={a.code} value={a.code}>{a.name} ({a.code})</option>)}</select></label>}
      {Object.values(value).some(Boolean) && <button className="btn btn-ghost" onClick={() => onChange({})}>Clear</button>}
    </div>
  );
}
