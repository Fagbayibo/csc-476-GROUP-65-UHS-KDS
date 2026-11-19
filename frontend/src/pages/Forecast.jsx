import { useState } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { get } from '../api.js';
import { Alert, Card, COLORS, Spinner, useLoad, useReference } from '../ui.jsx';

export default function Forecast() {
  const ref = useReference();
  const [code, setCode] = useState('B54');
  const [h, setH] = useState(6);
  const [f, err, , loading] = useLoad(() => get(`/mining/forecast?code=${encodeURIComponent(code)}&horizon=${h}`), [code, h]);
  const rows = [];
  if (f && !f.error) {
    f.history_periods.forEach((p, i) => rows.push({ period: p, actual: f.history[i] }));
    const bt = f.backtest;
    if (bt?.test_periods) bt.test_periods.forEach((p, i) => { const r = rows.find((x) => x.period === p); if (r) r.backtest = bt.models[f.best_model].predicted[i]; });
    if (rows.length) rows[rows.length - 1].forecast = rows[rows.length - 1].actual;
    f.forecast_periods.forEach((p, i) => rows.push({ period: p, forecast: f.forecast[i] }));
  }
  return (
    <>
      <div className="page-head"><h1>Incidence forecast</h1><p className="muted">Monthly cases expected in the coming months, to help plan drugs and staff.</p></div>
      <div className="filters">
        <label>Ailment<select value={code} onChange={(e) => setCode(e.target.value)}>{ref?.ailments.map((a) => <option key={a.code} value={a.code}>{a.name}</option>)}</select></label>
        <label>Months ahead<select value={h} onChange={(e) => setH(Number(e.target.value))}>{[3, 6, 9, 12].map((x) => <option key={x}>{x}</option>)}</select></label>
      </div>
      <Alert kind="error">{err?.message || f?.error}</Alert>
      {loading && !f ? <Spinner /> : f && !f.error && <>
        <Card title={`History and forecast (${f.best_model})`}>
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={rows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="period" tick={{ fontSize: 11 }} minTickGap={20} /><YAxis /><Tooltip /><Legend />
              <Line dataKey="actual" name="Recorded cases" stroke={COLORS[0]} dot={false} strokeWidth={2} />
              <Line dataKey="backtest" name="Back-test prediction (last 12 months)" stroke={COLORS[2]} strokeDasharray="4 3" dot={false} />
              <Line dataKey="forecast" name="Forecast" stroke={COLORS[1]} strokeWidth={2.5} strokeDasharray="6 3" dot /></LineChart>
          </ResponsiveContainer>
        </Card>
        <div className="grid2">
          <Card title="Forecast">
            <table><thead><tr><th>Month</th><th className="num">Expected cases</th></tr></thead>
              <tbody>{f.forecast_periods.map((p, i) => <tr key={p}><td>{p}</td><td className="num">{Math.round(f.forecast[i])}</td></tr>)}</tbody></table>
          </Card>
          <Card title="Accuracy on the last 12 months (back-test)">
            <table><thead><tr><th>Model</th><th className="num">MAE</th><th className="num">RMSE</th><th className="num">MAPE</th></tr></thead>
              <tbody>{Object.entries(f.backtest.models).map(([m, v]) => <tr key={m} className={m === f.best_model ? 'best' : ''}><td>{m}{m === f.best_model && ' ✓'}</td>
                <td className="num">{v.mae}</td><td className="num">{v.rmse}</td><td className="num">{v.mape}%</td></tr>)}</tbody></table>
            <p className="muted small">The model with the lowest mean absolute error (MAE) is used for the forecast.</p>
          </Card>
        </div>
      </>}
    </>
  );
}
