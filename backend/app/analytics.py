"""
Builds an analysis table (one row per diagnosis made at a visit) from the database and provides
the descriptive statistics used by the dashboard. The table is cached and rebuilt after each import.
"""
import threading
import pandas as pd
from sqlalchemy import text
from .db import engine

_lock = threading.Lock()
_cache: dict = {'facts': None}

AGE_BINS = [-1, 15, 24, 39, 59, 200]
AGE_LABELS = ['0–15', '16–24', '25–39', '40–59', '60+']
SEASONS = {12: 'Harmattan', 1: 'Harmattan', 2: 'Harmattan', 3: 'Dry', 11: 'Dry'}


def season_of(month: int) -> str:
    return SEASONS.get(month, 'Rainy')


def invalidate():
    with _lock:
        _cache['facts'] = None


SQL = text("""
SELECT e.id AS encounter_id, e.visit_date, e.visit_type, p.id AS patient_id, p.sex, p.birth_year,
       pc.name AS category, f.name AS faculty, r.name AS residence, r.kind AS residence_kind,
       a.icd10_code AS code, a.name AS ailment, g.name AS ailment_group
  FROM encounters e
  JOIN patients p ON p.id = e.patient_id
  JOIN patient_categories pc ON pc.id = p.category_id
  LEFT JOIN faculties f ON f.id = p.faculty_id
  LEFT JOIN residences r ON r.id = p.residence_id
  JOIN encounter_diagnoses ed ON ed.encounter_id = e.id
  JOIN ailments a ON a.id = ed.ailment_id
  JOIN ailment_groups g ON g.id = a.group_id
""")


def facts() -> pd.DataFrame:
    with _lock:
        if _cache['facts'] is not None:
            return _cache['facts']
    with engine.connect() as conn:
        df = pd.read_sql(SQL, conn)
    df['visit_date'] = pd.to_datetime(df['visit_date'])
    df['year'] = df['visit_date'].dt.year
    df['month'] = df['visit_date'].dt.month
    df['period'] = df['visit_date'].dt.to_period('M').astype(str)
    df['week_start'] = (df['visit_date'] - pd.to_timedelta(df['visit_date'].dt.weekday, unit='D')).dt.normalize()
    df['season'] = df['month'].map(season_of)
    df['age'] = df['year'] - df['birth_year']
    df['age_group'] = pd.cut(df['age'], bins=AGE_BINS, labels=AGE_LABELS).astype(str).replace('nan', 'Unknown')
    df['sex'] = df['sex'].fillna('Unknown')
    df['faculty'] = df['faculty'].fillna('None')
    df['residence'] = df['residence'].fillna('Unknown')
    for c in ('category', 'ailment', 'code', 'ailment_group', 'season', 'age_group', 'residence', 'faculty', 'sex'):
        df[c] = df[c].astype('category')
    with _lock:
        _cache['facts'] = df
    return df


FILTERS = ('category', 'sex', 'residence', 'faculty', 'ailment_group', 'age_group', 'season')


def filtered(params: dict) -> pd.DataFrame:
    df = facts()
    if params.get('date_from'):
        df = df[df['visit_date'] >= pd.Timestamp(params['date_from'])]
    if params.get('date_to'):
        df = df[df['visit_date'] <= pd.Timestamp(params['date_to'])]
    for k in FILTERS:
        if params.get(k):
            df = df[df[k] == params[k]]
    if params.get('ailment'):
        df = df[df['code'] == params['ailment']]
    return df


def summary(params: dict) -> dict:
    df = filtered(params)
    if df.empty:
        return {'encounters': 0, 'diagnoses': 0, 'patients': 0, 'top_ailments': [], 'by_group': [], 'date_range': None}
    enc = df['encounter_id'].nunique()
    top = (df.groupby(['code', 'ailment'], observed=True).size().sort_values(ascending=False).head(10)
           .reset_index(name='cases'))
    top['share'] = (top['cases'] / len(df) * 100).round(1)
    by_group = df.groupby('ailment_group', observed=True).size().sort_values(ascending=False).reset_index(name='cases')
    last = df['visit_date'].max()
    last30 = df[df['visit_date'] > last - pd.Timedelta(days=30)]
    prev30 = df[(df['visit_date'] <= last - pd.Timedelta(days=30)) & (df['visit_date'] > last - pd.Timedelta(days=60))]
    return {
        'encounters': int(enc), 'diagnoses': int(len(df)), 'patients': int(df['patient_id'].nunique()),
        'date_range': [df['visit_date'].min().date().isoformat(), last.date().isoformat()],
        'avg_daily_visits': round(enc / max(1, (last - df['visit_date'].min()).days + 1), 1),
        'last_30_days': int(last30['encounter_id'].nunique()), 'previous_30_days': int(prev30['encounter_id'].nunique()),
        'top_ailments': top.to_dict('records'), 'by_group': by_group.to_dict('records'),
    }


def trend(params: dict, granularity: str = 'month', top: int = 6) -> dict:
    df = filtered(params)
    key = 'period' if granularity == 'month' else 'week_start'
    if df.empty:
        return {'periods': [], 'series': []}
    codes = [params['ailment']] if params.get('ailment') else (
        df.groupby('code', observed=True).size().sort_values(ascending=False).head(top).index.tolist())
    names = dict(zip(df['code'], df['ailment']))
    tab = df[df['code'].isin(codes)].groupby([key, 'code'], observed=True).size().unstack(fill_value=0)
    if granularity != 'month':
        tab.index = tab.index.strftime('%Y-%m-%d')
    total = df.groupby(key, observed=True)['encounter_id'].nunique()
    if granularity != 'month':
        total.index = total.index.strftime('%Y-%m-%d')
    periods = sorted(set(tab.index) | set(total.index))
    tab = tab.reindex(periods, fill_value=0)
    return {'periods': periods,
            'series': [{'code': c, 'name': names[c], 'values': [int(v) for v in tab[c]]} for c in codes if c in tab],
            'total_visits': [int(total.get(p, 0)) for p in periods]}


def breakdown(params: dict, by: str) -> dict:
    if by not in ('sex', 'category', 'age_group', 'residence', 'faculty', 'season', 'ailment_group', 'ailment'):
        raise ValueError('Unsupported breakdown.')
    df = filtered(params)
    tab = df.groupby(by, observed=True).agg(cases=('encounter_id', 'size'), patients=('patient_id', 'nunique'))
    tab = tab.sort_values('cases', ascending=False).reset_index()
    tab['share'] = (tab['cases'] / max(1, tab['cases'].sum()) * 100).round(1)
    return {'by': by, 'rows': tab.astype({by: str}).to_dict('records')}


def seasonality(params: dict) -> dict:
    """Average cases per calendar month across complete years, with a seasonal index (1.0 = average)."""
    df = filtered(params)
    if df.empty:
        return {'months': [], 'average': [], 'index': []}
    full = df.groupby(['year', 'month'], observed=True).size()
    yrs = df.groupby('year')['month'].nunique()
    complete = yrs[yrs == 12].index
    full = full[full.index.get_level_values(0).isin(complete)] if len(complete) else full
    avg = full.groupby(level=1).mean().reindex(range(1, 13), fill_value=0)
    idx = (avg / avg.mean()).round(2) if avg.mean() else avg
    return {'months': list(range(1, 13)), 'average': [round(float(v), 1) for v in avg], 'index': [float(v) for v in idx],
            'years_used': [int(y) for y in complete]}
