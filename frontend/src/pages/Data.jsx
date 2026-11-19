import { useState } from 'react';
import { api, get } from '../api.js';
import { useAuth } from '../auth.jsx';
import { Alert, Card, clearReference, fmt, Spinner, useLoad } from '../ui.jsx';

export default function Data() {
  const { can } = useAuth();
  const [batches, , reload] = useLoad(() => get('/data/batches'), []);
  const [tpl] = useLoad(() => get('/data/template'), []);
  const [page, setPage] = useState(1);
  const [enc, , reloadEnc] = useLoad(() => get(`/data/encounters?page=${page}&size=12`), [page]);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const upload = async (e) => {
    e.preventDefault(); if (!file) return;
    setBusy(true); setMsg(null);
    const form = new FormData(); form.append('file', file);
    try {
      const b = await api('/data/import', { method: 'POST', form });
      setMsg({ kind: 'success', text: `Loaded ${fmt(b.rows_loaded)} of ${fmt(b.rows_read)} rows in ${(b.duration_ms / 1000).toFixed(1)} s – ${fmt(b.rows_rejected)} rejected, ${fmt(b.duplicates_removed)} duplicates removed.` });
      clearReference(); reload(); setPage(1); reloadEnc();
    } catch (x) { setMsg({ kind: 'error', text: x.message }); } finally { setBusy(false); }
  };
  return (
    <>
      <div className="page-head"><h1>Clinic data</h1><p className="muted">Import encounter records exported from the medical records unit, and check their quality.</p></div>
      {can('admin', 'records_officer') && (
        <Card title="Import a CSV file">
          <form onSubmit={upload} className="filters">
            <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0])} />
            <button className="btn btn-primary" disabled={!file || busy}>{busy ? 'Importing…' : 'Import'}</button>
          </form>
          <Alert kind={msg?.kind}>{msg?.text}</Alert>
          {tpl && <p className="muted small">Required columns: <code>{tpl.columns.join(', ')}</code>. Diagnoses are ICD-10 codes separated by “;”.
            Card numbers are replaced by a keyed pseudonym on import and are never stored.</p>}
        </Card>)}
      <Card title="Import history and data-quality report">
        {!batches ? <Spinner /> : batches.length === 0 ? <p className="empty">No data imported yet.</p> : batches.map((b) => (
          <div key={b.id} className="batch">
            <div className="batch-head"><b>{b.filename}</b><span className="muted small">{String(b.uploaded_at).replace('T', ' ').slice(0, 16)} by {b.uploaded_by} · {(b.duration_ms / 1000).toFixed(1)} s</span></div>
            <div className="stats small-stats">
              <div className="stat"><span className="stat-v">{fmt(b.rows_read)}</span><span className="stat-l">rows read</span></div>
              <div className="stat"><span className="stat-v">{fmt(b.rows_loaded)}</span><span className="stat-l">visits loaded</span></div>
              <div className="stat warn"><span className="stat-v">{fmt(b.rows_rejected)}</span><span className="stat-l">rejected</span></div>
              <div className="stat"><span className="stat-v">{fmt(b.duplicates_removed)}</span><span className="stat-l">duplicates removed</span></div>
            </div>
            {Object.keys(b.issues).length > 0 && <table><thead><tr><th>Issue</th><th className="num">Rows</th><th>Example rows</th></tr></thead>
              <tbody>{Object.entries(b.issues).map(([k, v]) => <tr key={k}><td>{v.description}</td><td className="num">{fmt(v.count)}</td><td className="muted small">{v.example_rows.join(', ')}</td></tr>)}</tbody></table>}
          </div>))}
      </Card>
      <Card title="Most recent visits (pseudonymised)">
        {!enc ? <Spinner /> : <>
          <div className="table-wrap"><table><thead><tr><th>Date</th><th>Patient key</th><th>Sex</th><th>Birth year</th><th>Category</th><th>Residence</th><th>Visit</th><th>Diagnoses</th></tr></thead>
            <tbody>{enc.items.map((r) => <tr key={r.id}><td>{r.visit_date}</td><td><code>{r.patient}…</code></td><td>{r.sex}</td><td>{r.birth_year ?? '—'}</td><td>{r.category}</td><td>{r.residence}</td><td>{r.visit_type}</td><td className="small">{r.diagnoses.join('; ')}</td></tr>)}</tbody></table></div>
          <div className="pager"><button className="btn btn-small" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
            <span className="muted small">Page {page} of {fmt(Math.ceil(enc.total / enc.size))} ({fmt(enc.total)} visits)</span>
            <button className="btn btn-small" onClick={() => setPage(page + 1)} disabled={page * enc.size >= enc.total}>Next</button></div>
        </>}
      </Card>
    </>
  );
}
