"""
Outbreak (aberration) detection on weekly case counts.
* EARS C2 (Hutwagner et al., 2003): baseline = weeks t-9..t-3; alert if count > mean + 3 SD.
* Historical limits (Stroup et al., 1989): baseline = the same week and the 3 weeks either side in
  the two previous years; alert if count > mean + 2.58 SD. This allows for normal seasonal rises.
A minimum count avoids alerts on very small numbers, and the SD is given a floor so that a flat
baseline does not make every small rise an alert.
"""
import numpy as np
import pandas as pd

METHODS = ('ears_c2', 'historical')


def weekly(df: pd.DataFrame, code: str, residence: str | None = None, weeks_index=None) -> pd.Series:
    d = df[df['code'] == code]
    if residence:
        d = d[d['residence'] == residence]
    s = d.groupby('week_start').size()
    idx = weeks_index if weeks_index is not None else pd.date_range(df['week_start'].min(), df['week_start'].max(), freq='W-MON')
    return s.reindex(idx, fill_value=0).astype(float)


def detect(series: pd.Series, method: str, min_count: int = 5, sd_floor: float = 1.0):
    vals, idx = series.values, series.index
    out = []
    for t in range(len(vals)):
        if method == 'ears_c2':
            if t < 9:
                continue
            base = vals[t - 9:t - 2]
            z = 3.0
        else:
            base = []
            for back in (52, 104):
                lo, hi = t - back - 3, t - back + 4
                if lo >= 0:
                    base.extend(vals[lo:hi])
            if len(base) < 14:
                continue
            base = np.array(base)
            z = 2.58
        mu = float(np.mean(base))
        sd = max(float(np.std(base, ddof=1)), sd_floor, np.sqrt(max(mu, 0)) * 0.5)
        thr = mu + z * sd
        if vals[t] > thr and vals[t] >= min_count:
            out.append({'week_start': idx[t].date().isoformat(), 'observed': int(vals[t]),
                        'expected': round(mu, 1), 'threshold': round(thr, 1)})
    return out


def scan(df: pd.DataFrame, method: str = 'historical', level: str = 'campus', codes=None, since=None, min_count=5):
    """Runs detection for every ailment (and every hall if level='residence'). Returns a list of signals."""
    if method not in METHODS:
        raise ValueError('Unknown method.')
    weeks = pd.date_range(df['week_start'].min(), df['week_start'].max(), freq='W-MON')
    codes = codes or sorted(df['code'].unique().tolist())
    names = dict(zip(df['code'], df['ailment']))
    units = [None]
    if level == 'residence':
        units = sorted(df.loc[df['residence_kind'] == 'hall', 'residence'].unique().tolist())
    signals = []
    for code in codes:
        for unit in units:
            s = weekly(df, code, unit, weeks)
            for a in detect(s, method, min_count=min_count if unit is None else max(3, min_count // 2)):
                if since and a['week_start'] < since:
                    continue
                signals.append({'code': code, 'ailment': names.get(code, code), 'residence': unit, 'method': method, **a})
    signals.sort(key=lambda x: (x['week_start'], x['code']), reverse=True)
    return signals
