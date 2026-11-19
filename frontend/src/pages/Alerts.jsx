import { useState } from 'react';
import { get, post } from '../api.js';
import { Alert, Badge, Card, Spinner, useLoad } from '../ui.jsx';

export default function Alerts() {
  const [m, setM] = useState('historical');
  const [lvl, setLvl] = useState('campus');
  const [w, setW] = useState(26);
  const [d, err, reload, loading] = useLoad(() => get(`/mining/alerts?method=${m}&level=${lvl}&weeks=${w}`), [m, lvl, w]);
  const [msg, setMsg] = useState('');
  const status = async (id, s) => { try { await post(`/mining/alerts/${id}/status`, { status: s }); reload(); } catch (e) { setMsg(e.message); } };
  return (
    <>
      <div className="page-head"><h1>Outbreak alerts</h1><p className="muted">Weeks in which cases of an ailment rose well above what is normally expected.</p></div>
      <div className="filters">
        <label>Method<select value={m} onChange={(e) => setM(e.target.value)}>
          <option value="historical">Historical limits (allows for season)</option><option value="ears_c2">EARS C2 (recent weeks)</option></select></label>
        <label>Level<select value={lvl} onChange={(e) => setLvl(e.target.value)}><option value="campus">Whole campus</option><option value="residence">Each hall</option></select></label>
        <label>Period<select value={w} onChange={(e) => setW(Number(e.target.value))}>{[8, 26, 52, 104].map((x) => <option key={x} value={x}>Last {x} weeks</option>)}</select></label>
      </div>
      <Alert kind="error" onClose={() => setMsg('')}>{err?.message || msg}</Alert>
      {loading ? <Spinner label="Scanning weekly counts…" /> : d && (
        <Card title={`${d.alerts.length} signal${d.alerts.length === 1 ? '' : 's'} since ${d.since}`}>
          {d.alerts.length === 0 ? <p className="empty">No unusual rises in this period.</p> : (
            <div className="table-wrap"><table>
              <thead><tr><th>Week starting</th><th>Ailment</th><th>Where</th><th className="num">Cases</th><th className="num">Expected</th><th className="num">Threshold</th><th>Status</th><th /></tr></thead>
              <tbody>{d.alerts.map((a) => (
                <tr key={a.id} className={a.status === 'new' ? 'row-new' : ''}><td>{a.week_start}</td><td><b>{a.ailment}</b> <span className="muted small">{a.code}</span></td>
                  <td>{a.residence || 'Whole campus'}</td><td className="num"><b>{a.observed}</b></td><td className="num">{a.expected}</td><td className="num">{a.threshold}</td>
                  <td><Badge kind={a.status === 'new' ? 'warn' : a.status === 'acknowledged' ? 'ok' : 'neutral'}>{a.status}</Badge></td>
                  <td className="nowrap">{a.status === 'new' ? <>
                    <button className="btn btn-small" onClick={() => status(a.id, 'acknowledged')}>Acknowledge</button>{' '}
                    <button className="btn btn-small btn-ghost" onClick={() => status(a.id, 'dismissed')}>Dismiss</button></>
                    : <button className="btn btn-small btn-ghost" onClick={() => status(a.id, 'new')}>Reopen</button>}</td></tr>))}
              </tbody></table></div>)}
          <p className="muted small">An alert is raised when the week’s count exceeds the threshold (expected + 2.58 SD for historical limits, + 3 SD for EARS C2) and is at least 5 cases (3 for a single hall).</p>
        </Card>)}
    </>
  );
}
