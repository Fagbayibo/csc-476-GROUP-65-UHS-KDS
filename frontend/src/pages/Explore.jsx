import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { download, get, qs } from '../api.js';
import { Card, COLORS, Filters, fmt, MONTHS, Spinner, useLoad, useReference } from '../ui.jsx';

const DIMS = [['sex', 'Sex'], ['category', 'Patient category'], ['age_group', 'Age group'], ['season', 'Season'], ['residence', 'Residence'], ['faculty', 'Faculty']];

export default function Explore() {
  const ref = useReference();
  const [f, setF] = useState({ ailment: 'B54' });
  const [dim, setDim] = useState('season');
  const key = JSON.stringify(f);
  const [t] = useLoad(() => get(`/analytics/trend?${qs({ ...f, top: 1 })}`), [key]);
  const [s] = useLoad(() => get(`/analytics/seasonality?${qs(f)}`), [key]);
  const [b] = useLoad(() => get(`/analytics/breakdown?${qs({ ...f, by: dim })}`), [key, dim]);
  const name = ref?.ailments.find((a) => a.code === f.ailment)?.name || 'All ailments';
  const series = t?.series[0];
  const trendRows = t ? t.periods.map((p, i) => ({ period: p, cases: f.ailment ? (series?.values[i] ?? 0) : t.total_visits[i] })) : [];
  const seasRows = s ? s.months.map((m, i) => ({ month: MONTHS[m - 1], index: s.index[i], average: s.average[i] })) : [];
  return (
    <>
      <div className="page-head"><h1>Explore incidence</h1><p className="muted">Look at one ailment over time, by season and by group of patients.</p></div>
      <Filters value={f} onChange={setF} />
      <div className="grid2">
        <Card title={`${name}: monthly cases`} right={<button className="btn btn-small" onClick={() => download(`/reports/export?${qs({ ...f, kind: 'monthly' })}`, 'monthly_cases.csv')}>Export CSV</button>}>
          {!t ? <Spinner /> : <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trendRows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="period" tick={{ fontSize: 11 }} minTickGap={20} /><YAxis /><Tooltip />
              <Line dataKey="cases" stroke={COLORS[0]} strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer>}
        </Card>
        <Card title="Seasonal index (1.0 = average month)">
          {!s ? <Spinner /> : <ResponsiveContainer width="100%" height={280}>
            <BarChart data={seasRows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="month" /><YAxis domain={[0, 'auto']} />
              <Tooltip formatter={(v, n) => (n === 'index' ? v : fmt(v))} /><ReferenceLine y={1} stroke="#999" strokeDasharray="4 4" />
              <Bar dataKey="index" fill={COLORS[1]} radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer>}
          {s?.years_used?.length > 0 && <p className="muted small">Based on complete years: {s.years_used.join(', ')}.</p>}
        </Card>
      </div>
      <Card title="Breakdown" right={<select value={dim} onChange={(e) => setDim(e.target.value)}>{DIMS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>}>
        {!b ? <Spinner /> : <div className="grid2">
          <ResponsiveContainer width="100%" height={Math.max(220, b.rows.length * 26)}>
            <BarChart data={b.rows} layout="vertical" margin={{ left: 30 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => (v >= 1000 ? `${v / 1000}k` : v)} /><YAxis dataKey={dim} type="category" width={150} tick={{ fontSize: 12 }} /><Tooltip formatter={(v) => fmt(v)} />
              <Bar dataKey="cases" fill={COLORS[2]} radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer>
          <table><thead><tr><th>{DIMS.find((d) => d[0] === dim)[1]}</th><th>Cases</th><th>Patients</th><th>Share</th></tr></thead>
            <tbody>{b.rows.map((r) => <tr key={r[dim]}><td>{r[dim]}</td><td>{fmt(r.cases)}</td><td>{fmt(r.patients)}</td><td>{r.share}%</td></tr>)}</tbody></table>
        </div>}
      </Card>
    </>
  );
}
