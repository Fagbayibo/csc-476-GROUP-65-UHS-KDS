import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, LabelList } from 'recharts';
import { get } from '../api.js';
import { Card, COLORS, Spinner, useLoad, Alert } from '../ui.jsx';

export default function Clusters() {
  const [c, err] = useLoad(() => get('/mining/clusters'), []);
  if (err) return <Alert kind="error">{err.message}</Alert>;
  if (!c) return <Spinner label="Clustering halls…" />;
  const max = Object.fromEntries(c.ailments.map((a) => [a, Math.max(...c.rates.map((r) => r[a]))]));
  const clusterOf = Object.fromEntries(c.members.map((m) => [m.residence, m.cluster]));
  return (
    <>
      <div className="page-head"><h1>Halls with similar ailment profiles</h1>
        <p className="muted">k-means clustering of halls of residence by their rate of each ailment (cases per 100 resident patients per year).</p></div>
      <div className="grid2">
        <Card title={`${c.k} clusters (silhouette ${c.silhouette})`}>
          {c.clusters.map((cl) => (
            <div key={cl.cluster} className="cluster" style={{ borderColor: COLORS[cl.cluster] }}>
              <strong style={{ color: COLORS[cl.cluster] }}>Cluster {cl.cluster + 1}</strong> – {cl.residences.join(', ')}
              <div className="muted small">Most distinctive: {cl.distinctive.map((d) => `${d.ailment} (${d.ratio_to_average}× average)`).join('; ')}</div>
            </div>))}
          <p className="muted small">Number of clusters chosen by silhouette score: {c.scores.map((s) => `k=${s.k}: ${s.silhouette}`).join(', ')}.</p>
        </Card>
        <Card title="Halls plotted by their two main components">
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 10, right: 30, bottom: 10, left: 0 }}><CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" type="number" name="PC1" tick={{ fontSize: 11 }} domain={["dataMin - 1", "dataMax + 1"]} tickFormatter={(v) => v.toFixed(0)} label={{ value: "Component 1", position: "insideBottom", offset: -4, fontSize: 11 }} /><YAxis dataKey="y" type="number" name="PC2" tick={{ fontSize: 11 }} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v) => v.toFixed(2)} />
              {c.clusters.map((cl) => <Scatter key={cl.cluster} data={c.members.filter((m) => m.cluster === cl.cluster)} fill={COLORS[cl.cluster]} isAnimationActive={false}>
                <LabelList dataKey="residence" position="top" style={{ fontSize: 11 }} /></Scatter>)}
            </ScatterChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <Card title="Rate per 100 resident patients per year">
        <div className="table-wrap"><table className="heat"><thead><tr><th>Hall</th>{c.ailments.map((a) => <th key={a} className="rot"><span>{a}</span></th>)}</tr></thead>
          <tbody>{c.rates.map((r) => <tr key={r.residence}><td><span className="dot" style={{ background: COLORS[clusterOf[r.residence]] }} />{r.residence}</td>
            {c.ailments.map((a) => <td key={a} className="num" style={{ background: `rgba(15,95,92,${(r[a] / (max[a] || 1)) * 0.55})` }}>{r[a].toFixed(1)}</td>)}</tr>)}</tbody></table></div>
      </Card>
    </>
  );
}
