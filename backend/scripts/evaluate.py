"""
Evaluates the knowledge-discovery methods against the ground truth planted in the synthetic data.
Writes the results to data/evaluation_results.json. Run after scripts/seed.py.
"""
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import analytics                                                 # noqa: E402
from app.mining import associations, clustering, forecasting, surveillance  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / 'data'
truth = json.loads((DATA / 'ground_truth.json').read_text())
df = analytics.facts()
res = {'dataset': {'diagnoses': int(len(df)), 'encounters': int(df['encounter_id'].nunique()),
                   'patients': int(df['patient_id'].nunique()),
                   'period': [df['visit_date'].min().date().isoformat(), df['visit_date'].max().date().isoformat()]}}

# ---------- 1. association rules
t0 = time.perf_counter()
mined = associations.mine(df)
res_rules_time = time.perf_counter() - t0
onehot = associations.transactions(df)


def metrics(ante, cons):
    a = onehot[ante].all(axis=1)
    c = onehot[cons]
    n = len(onehot)
    sup = (a & c).sum() / n
    conf = (a & c).sum() / max(1, a.sum())
    lift = conf / (c.sum() / n)
    return {'support': round(float(sup), 4), 'confidence': round(float(conf), 3), 'lift': round(float(lift), 2)}


PLANTED = [
    (['dx=Type 2 diabetes mellitus'], 'dx=Hypertension', 'Diabetes visits also record hypertension'),
    (['dx=Malaria'], 'dx=Typhoid fever', 'Malaria diagnosed together with typhoid'),
    (['category=Staff', 'age=40–59'], 'dx=Hypertension', 'Hypertension among staff aged 40–59'),
    (['sex=F'], 'dx=Urinary tract infection', 'UTI more common in females'),
    (['sex=F', 'category=Student'], 'dx=Dysmenorrhoea', 'Dysmenorrhoea among female students'),
    (['season=Rainy'], 'dx=Malaria', 'Malaria in the rainy season'),
    (['season=Harmattan'], 'dx=Upper respiratory tract infection', 'URTI in the harmattan'),
    (['residence=Hall C'], 'dx=Malaria', 'Higher malaria risk in Hall C'),
    (['sex=M'], 'dx=Injury (unspecified)', 'Injuries more common in males'),
]
found = {(tuple(r['antecedent']), 'dx=' + r['consequent']) for r in mined['rules']}
res['association_rules'] = {
    'parameters': {'min_support': 0.003, 'min_confidence': 0.2, 'min_lift': 1.3, 'max_len': 3},
    'transactions': mined['transactions'], 'frequent_itemsets': mined['itemsets'], 'rules': len(mined['rules']),
    'seconds': round(res_rules_time, 2),
    'planted': [{'pattern': label, 'antecedent': a, 'consequent': c.removeprefix('dx='), **metrics(a, c),
                 'found_by_miner': (tuple(sorted(a)), c) in found} for a, c, label in PLANTED],
    'top_rules': mined['rules'][:12],
}

# ---------- 2. clustering
t0 = time.perf_counter()
cl = clustering.cluster(df)
res['clustering'] = {**{k: cl[k] for k in ('k', 'silhouette', 'scores', 'clusters', 'members')},
                     'seconds': round(time.perf_counter() - t0, 2)}

# ---------- 3. forecasting: train on 2022–2024, test on 2025
codes = df.groupby('code', observed=True).size().sort_values(ascending=False).head(8).index.tolist()
names = dict(zip(df['code'], df['ailment']))
fc = []
for code in codes:
    s = forecasting.monthly(df, code)[:pd.Period('2025-12', 'M')]
    bt = forecasting.backtest(s, 12)
    best = min(bt['models'], key=lambda m: bt['models'][m]['mae'])
    fc.append({'code': code, 'ailment': names[code], 'mean_monthly_2025': round(float(np.mean(bt['actual'])), 1),
               'best_model': best, **{m: {k: v for k, v in bt['models'][m].items() if k != 'predicted'} for m in bt['models']},
               'actual': bt['actual'], 'predicted_best': bt['models'][best]['predicted']})
res['forecasting'] = {'train': '2022-01 to 2024-12', 'test': '2025-01 to 2025-12', 'ailments': fc,
                      'best_counts': {m: sum(1 for f in fc if f['best_model'] == m) for m in forecasting.MODELS},
                      'mean_mape': {m: round(float(np.mean([f[m]['mape'] for f in fc])), 1) for m in forecasting.MODELS}}

# ---------- 4. outbreak detection
EVAL_FROM, EVAL_TO = '2024-01-01', df['week_start'].max().date().isoformat()
obs = [o for o in truth['outbreaks'] if o['start'] >= EVAL_FROM]
surv = {}
for method in surveillance.METHODS:
    surv[method] = {}
    for level in ('campus', 'residence'):
        t0 = time.perf_counter()
        sig = [s for s in surveillance.scan(df, method, level) if EVAL_FROM <= s['week_start'] <= EVAL_TO]
        secs = time.perf_counter() - t0
        targets = [o for o in obs if (o['hall'] is None) == (level == 'campus')]
        outcome, true_ids = [], set()
        for o in targets:
            start = date.fromisoformat(o['start'])
            end = start + timedelta(weeks=o['weeks'])     # one week of grace after the outbreak
            hits = [s for s in sig if s['code'] == o['code'] and (s['residence'] == o['hall'])
                    and start.isoformat() <= s['week_start'] <= end.isoformat()]
            for h in hits:
                true_ids.add(id(h))
            first = min((h['week_start'] for h in hits), default=None)
            outcome.append({'outbreak': o['id'], 'label': o['label'], 'start': o['start'], 'detected': bool(hits),
                            'delay_weeks': (date.fromisoformat(first) - start).days // 7 if first else None})
        # signals that coincide with ANY planted outbreak of that ailment (e.g. a hall outbreak seen campus-wide) are not counted as false
        def explained(s):
            for o in truth['outbreaks']:
                st = date.fromisoformat(o['start']); en = st + timedelta(weeks=o['weeks'])
                if s['code'] == o['code'] and st.isoformat() <= s['week_start'] <= en.isoformat() and \
                        (s['residence'] is None or s['residence'] == o['hall']):
                    return True
            return False
        false = [s for s in sig if not explained(s)]
        n_series = df['code'].nunique() * (1 if level == 'campus' else df.loc[df['residence_kind'] == 'hall', 'residence'].nunique())
        weeks = (date.fromisoformat(EVAL_TO) - date.fromisoformat(EVAL_FROM)).days // 7 + 1
        surv[method][level] = {
            'signals': len(sig), 'false_signals': len(false), 'series': int(n_series), 'weeks': weeks,
            'false_per_series_year': round(len(false) / n_series / (weeks / 52.18), 3),
            'specificity': round(1 - len(false) / (n_series * weeks), 4),
            'outbreaks': outcome, 'detected': sum(o['detected'] for o in outcome), 'of': len(outcome),
            'seconds': round(secs, 2),
            'false_by_ailment': pd.Series([s['ailment'] for s in false]).value_counts().head(5).to_dict() if false else {},
        }
res['surveillance'] = {'evaluation_window': [EVAL_FROM, EVAL_TO], 'methods': surv,
                       'outbreaks_in_window': [o['id'] for o in obs]}

(DATA / 'evaluation_results.json').write_text(json.dumps(res, indent=2, default=str))
print(json.dumps({'rules': res['association_rules']['rules'], 'planted': [(p['pattern'], p['lift'], p['found_by_miner']) for p in res['association_rules']['planted']],
                  'clusters': (cl['k'], cl['silhouette'], [c['residences'] for c in cl['clusters']]),
                  'forecast': (res['forecasting']['best_counts'], res['forecasting']['mean_mape']),
                  'surv': {m: {l: (v['detected'], v['of'], v['false_signals'], v['false_per_series_year'], [o['delay_weeks'] for o in v['outbreaks']]) for l, v in d.items()} for m, d in surv.items()}},
                 indent=1, default=str))
