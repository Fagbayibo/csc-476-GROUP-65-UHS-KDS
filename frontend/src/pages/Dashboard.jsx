import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { get, qs } from '../api.js';
import { Card, COLORS, Filters, fmt, Spinner, Stat, useLoad, Alert } from '../ui.jsx';

export default function Dashboard() {
  const [f, setF] = useState({});
  const [s, err] = useLoad(() => get(`/analytics/summary?${qs(f)}`), [JSON.stringify(f)]);
  const [t] = useLoad(() => get(`/analytics/trend?${qs({ ...f, top: 5 })}`), [JSON.stringify(f)]);
  const [cat] = useLoad(() => get(`/analytics/breakdown?${qs({ ...f, by: 'category' })}`), [JSON.stringify(f)]);
  const [alerts] = useLoad(() => get('/mining/alerts?method=historical&level=campus&weeks=8'), []);
  const rows = t ? t.periods.map((p, i) => Object.fromEntries([['period', p], ...t.series.map((x) => [x.name, x.values[i]])])) : [];
  const change = s && s.previous_30_days ? Math.round((s.last_30_days / s.previous_30_days - 1) * 100) : null;
  return (
    <>
      <div className="page-head"><h1>Ailments dashboard</h1><p className="muted">Overview of clinic visits and diagnoses.</p></div>
      <Filters value={f} onChange={setF} />
      <Alert kind="error">{err?.message}</Alert>
      {!s ? <Spinner /> : <>
        <div className="stats">
          <Stat label="clinic visits" value={fmt(s.encounters)} note={s.date_range && `${s.date_range[0]} to ${s.date_range[1]}`} />
          <Stat label="patients seen" value={fmt(s.patients)} />
          <Stat label="diagnoses recorded" value={fmt(s.diagnoses)} />
          <Stat label="average visits per day" value={s.avg_daily_visits} />
          <Stat label="visits in last 30 days" value={fmt(s.last_30_days)} note={change !== null && `${change >= 0 ? '+' : ''}${change}% on previous 30 days`} tone={change > 15 ? 'warn' : ''} />
          <Stat label="new outbreak signals (8 weeks)" value={alerts ? alerts.alerts.filter((a) => a.status === 'new').length : '…'} tone={alerts?.alerts.some((a) => a.status === 'new') ? 'warn' : ''} />
        </div>
        <div className="grid2">
          <Card title="Most common ailments">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={s.top_ailments} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" tickFormatter={(v) => (v >= 1000 ? `${v / 1000}k` : v)} />
                <YAxis dataKey="ailment" type="category" width={170} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v) => fmt(v)} /><Bar dataKey="cases" fill={COLORS[0]} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Cases by patient category">
            <table><thead><tr><th>Category</th><th>Cases</th><th>Patients</th><th>Share</th></tr></thead>
              <tbody>{cat?.rows.map((r) => <tr key={r.category}><td>{r.category}</td><td>{fmt(r.cases)}</td><td>{fmt(r.patients)}</td><td>{r.share}%</td></tr>)}</tbody></table>
            <h3 className="mt">By ailment group</h3>
            <table><tbody>{s.by_group.map((g) => <tr key={g.ailment_group}><td>{g.ailment_group}</td><td className="num">{fmt(g.cases)}</td></tr>)}</tbody></table>
          </Card>
        </div>
        <Card title="Monthly cases of the five most common ailments">
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={rows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="period" tick={{ fontSize: 11 }} minTickGap={20} />
              <YAxis /><Tooltip /><Legend />
              {t?.series.map((x, i) => <Line key={x.code} dataKey={x.name} stroke={COLORS[i]} dot={false} strokeWidth={2} />)}</LineChart>
          </ResponsiveContainer>
        </Card>
      </>}
    </>
  );
}
