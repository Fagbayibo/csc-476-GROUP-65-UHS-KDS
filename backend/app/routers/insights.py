"""Descriptive analytics, knowledge-discovery endpoints and CSV export."""
import csv
import io
import json
import time
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Ailment, Alert, AnalysisRun, Residence, User
from ..security import ANY_ROLE, require
from .. import analytics
from ..mining import associations, clustering, forecasting, surveillance

router = APIRouter(prefix='/api', tags=['insights'])
FILTER_KEYS = ('date_from', 'date_to', 'ailment') + analytics.FILTERS


def params(request: Request) -> dict:
    return {k: v for k, v in request.query_params.items() if k in FILTER_KEYS and v}


def record(db, user, kind, p, summary, t0):
    db.add(AnalysisRun(kind=kind, parameters_json=json.dumps(p, default=str), summary_json=json.dumps(summary, default=str),
                       duration_ms=int((time.perf_counter() - t0) * 1000), created_by=user.id))
    db.commit()


@router.get('/analytics/summary')
def summary(request: Request, _=Depends(require(*ANY_ROLE))):
    return analytics.summary(params(request))


@router.get('/analytics/trend')
def trend(request: Request, granularity: str = 'month', top: int = Query(6, ge=1, le=16), _=Depends(require(*ANY_ROLE))):
    return analytics.trend(params(request), granularity, top)


@router.get('/analytics/breakdown')
def breakdown(request: Request, by: str = 'category', _=Depends(require(*ANY_ROLE))):
    try:
        return analytics.breakdown(params(request), by)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get('/analytics/seasonality')
def seasonality(request: Request, _=Depends(require(*ANY_ROLE))):
    return analytics.seasonality(params(request))


@router.get('/mining/rules')
def rules(request: Request, min_support: float = Query(0.003, gt=0, le=1), min_confidence: float = Query(0.2, gt=0, le=1),
          min_lift: float = Query(1.3, ge=0), target: str | None = None, db: Session = Depends(get_db),
          user: User = Depends(require('admin', 'analyst'))):
    t0 = time.perf_counter()
    p = params(request)
    res = associations.mine(analytics.filtered(p), min_support, min_confidence, min_lift, target=target)
    record(db, user, 'association_rules', {**p, 'min_support': min_support, 'min_confidence': min_confidence,
                                            'min_lift': min_lift, 'target': target},
           {'transactions': res['transactions'], 'rules': len(res['rules'])}, t0)
    return res


@router.get('/mining/clusters')
def clusters(request: Request, k: int | None = Query(None, ge=2, le=8), db: Session = Depends(get_db),
             user: User = Depends(require('admin', 'analyst'))):
    t0 = time.perf_counter()
    p = params(request)
    res = clustering.cluster(analytics.filtered(p), k)
    record(db, user, 'clustering', {**p, 'k': k}, {'k': res['k'], 'silhouette': res['silhouette']}, t0)
    return res


@router.get('/mining/forecast')
def forecast(code: str, horizon: int = Query(6, ge=1, le=12), db: Session = Depends(get_db),
             user: User = Depends(require('admin', 'analyst'))):
    t0 = time.perf_counter()
    res = forecasting.forecast(analytics.facts(), code, horizon)
    record(db, user, 'forecast', {'code': code, 'horizon': horizon}, {'best_model': res.get('best_model')}, t0)
    return res


@router.get('/mining/alerts')
def alerts(method: str = 'historical', level: str = 'campus', weeks: int = Query(12, ge=1, le=260),
           db: Session = Depends(get_db), user: User = Depends(require(*ANY_ROLE))):
    """Scans the most recent weeks for unusual rises and saves new signals as alerts."""
    if method not in surveillance.METHODS or level not in ('campus', 'residence'):
        raise HTTPException(400, 'Unknown method or level.')
    t0 = time.perf_counter()
    df = analytics.facts()
    if df.empty:
        return {'alerts': []}
    since = (df['week_start'].max() - timedelta(weeks=weeks - 1)).date().isoformat()
    signals = surveillance.scan(df, method, level, since=since)
    ail = {a.icd10_code: a.id for a in db.query(Ailment)}
    res = {r.name: r.id for r in db.query(Residence)}
    out = []
    for s in signals:
        rid = res.get(s['residence']) if s['residence'] else None
        wk = date.fromisoformat(s['week_start'])
        a = db.query(Alert).filter_by(ailment_id=ail[s['code']], residence_id=rid, week_start=wk, method=method).first()
        if not a:
            a = Alert(ailment_id=ail[s['code']], residence_id=rid, week_start=wk, method=method, observed=s['observed'],
                      expected=s['expected'], threshold=s['threshold'])
            db.add(a); db.flush()
        out.append({**s, 'id': a.id, 'status': a.status})
    db.commit()
    record(db, user, 'surveillance', {'method': method, 'level': level, 'weeks': weeks}, {'signals': len(out)}, t0)
    return {'since': since, 'alerts': out}


class AlertStatus(BaseModel):
    status: str


@router.post('/mining/alerts/{aid}/status')
def set_alert_status(aid: int, body: AlertStatus, db: Session = Depends(get_db), user: User = Depends(require(*ANY_ROLE))):
    if body.status not in ('new', 'acknowledged', 'dismissed'):
        raise HTTPException(400, 'Unknown status.')
    a = db.get(Alert, aid)
    if not a:
        raise HTTPException(404, 'Alert not found.')
    a.status = body.status
    a.acknowledged_by = user.id if body.status != 'new' else None
    db.commit()
    return {'id': a.id, 'status': a.status}


@router.get('/runs')
def runs(db: Session = Depends(get_db), _=Depends(require('admin', 'analyst'))):
    rows = db.query(AnalysisRun, User.full_name).join(User, User.id == AnalysisRun.created_by) \
        .order_by(AnalysisRun.id.desc()).limit(50).all()
    return [{'id': r.id, 'kind': r.kind, 'by': n, 'at': r.created_at.isoformat(timespec='seconds'),
             'duration_ms': r.duration_ms, 'parameters': json.loads(r.parameters_json),
             'summary': json.loads(r.summary_json)} for r, n in rows]


@router.get('/reports/export')
def export(request: Request, kind: str = 'monthly', _=Depends(require(*ANY_ROLE))):
    """CSV downloads: monthly cases per ailment, or breakdown by residence."""
    p = params(request)
    df = analytics.filtered(p)
    buf = io.StringIO()
    w = csv.writer(buf)
    if kind == 'monthly':
        tab = df.groupby(['period', 'ailment'], observed=True).size().unstack(fill_value=0)
        w.writerow(['month', *tab.columns])
        for idx, row in tab.iterrows():
            w.writerow([idx, *[int(v) for v in row]])
    elif kind == 'residence':
        tab = df.groupby(['residence', 'ailment'], observed=True).size().unstack(fill_value=0)
        w.writerow(['residence', *tab.columns])
        for idx, row in tab.iterrows():
            w.writerow([idx, *[int(v) for v in row]])
    else:
        raise HTTPException(400, 'kind must be monthly or residence.')
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type='text/csv',
                             headers={'Content-Disposition': f'attachment; filename="uhs_{kind}_cases.csv"'})
