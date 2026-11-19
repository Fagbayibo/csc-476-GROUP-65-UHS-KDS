import { useState } from 'react';
import { get, qs } from '../api.js';
import { Alert, Card, Filters, fmt, Spinner, useLoad, useReference } from '../ui.jsx';

const chip = (item) => {
  const [k, v] = item.split('=');
  const label = { dx: 'Diagnosis', sex: 'Sex', category: 'Category', age: 'Age', season: 'Season', residence: 'Residence' }[k] || k;
  return <span key={item} className={`chip chip-${k}`}>{label}: <b>{v === 'F' ? 'Female' : v === 'M' ? 'Male' : v}</b></span>;
};

export default function Patterns() {
  const ref = useReference();
  const [f, setF] = useState({});
  const [p, setP] = useState({ min_support: 0.003, min_confidence: 0.2, min_lift: 1.3, target: '' });
  const [run, setRun] = useState(0);
  const [all, setAll] = useState(false);
  const [data, err, , loading] = useLoad(() => get(`/mining/rules?${qs({ ...f, ...p })}`), [run, JSON.stringify(f)]);
  const set = (k) => (e) => setP({ ...p, [k]: e.target.value });
  return (
    <>
      <div className="page-head"><h1>Association patterns</h1>
        <p className="muted">Rules of the form “visits with these features are more likely to have this diagnosis”, found with the Apriori algorithm.</p></div>
      <Filters value={f} onChange={setF} show={['date', 'category', 'sex', 'residence']} />
      <Card title="Mining settings">
        <div className="filters">
          <label>Minimum support<input type="number" step="0.001" min="0.001" max="1" value={p.min_support} onChange={set('min_support')} /></label>
          <label>Minimum confidence<input type="number" step="0.05" min="0.01" max="1" value={p.min_confidence} onChange={set('min_confidence')} /></label>
          <label>Minimum lift<input type="number" step="0.1" min="0" value={p.min_lift} onChange={set('min_lift')} /></label>
          <label>Predicting<select value={p.target} onChange={set('target')}><option value="">Any diagnosis</option>
            {ref?.ailments.map((a) => <option key={a.code} value={a.name}>{a.name}</option>)}</select></label>
          <button className="btn btn-primary" onClick={() => setRun(run + 1)} disabled={loading}>{loading ? 'Mining…' : 'Find patterns'}</button>
        </div>
        <p className="muted small"><b>Support</b> = share of all visits that contain the whole rule. <b>Confidence</b> = how often the diagnosis follows when the features are present. <b>Lift</b> = how many times more likely the diagnosis is than usual (above 1 means a positive association).</p>
      </Card>
      <Alert kind="error">{err?.message}</Alert>
      {loading && !data ? <Spinner label="Mining patterns…" /> : data && (
        <Card title={`${data.rules.length} rules from ${fmt(data.transactions)} visits`} right={<span className="muted small">{fmt(data.itemsets)} frequent itemsets</span>}>
          {data.rules.length === 0 ? <p className="empty">No rules meet these thresholds. Try lowering them.</p> : (
            <div className="table-wrap"><table>
              <thead><tr><th>If the visit has…</th><th>…then diagnosis</th><th className="num">Visits</th><th className="num">Support</th><th className="num">Confidence</th><th className="num">Lift</th></tr></thead>
              <tbody>{(all ? data.rules : data.rules.slice(0, 30)).map((r, i) => (
                <tr key={i}><td className="chips">{r.antecedent.map(chip)}</td><td><b>{r.consequent}</b></td>
                  <td className="num">{fmt(r.count)}</td><td className="num">{(r.support * 100).toFixed(2)}%</td>
                  <td className="num">{(r.confidence * 100).toFixed(1)}%</td><td className="num"><span className="lift" style={{ '--w': `${Math.min(100, r.lift * 10)}%` }}>{r.lift.toFixed(2)}</span></td></tr>))}
              </tbody></table></div>)}
          {data.rules.length > 30 && <div className="pager"><button className="btn btn-small" onClick={() => setAll(!all)}>{all ? 'Show top 30 only' : `Show all ${data.rules.length} rules`}</button></div>}
        </Card>)}
    </>
  );
}
