"""
Monthly incidence forecasting for each ailment. Three models are compared on a hold-out year:
seasonal naive (same month last year), the mean of the same month in earlier years, and additive
Holt-Winters exponential smoothing. The model with the lowest mean absolute error is used to forecast.
"""
import warnings
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


def monthly(df: pd.DataFrame, code: str) -> pd.Series:
    d = df[df['code'] == code]
    s = d.groupby(d['visit_date'].dt.to_period('M')).size()
    if s.empty:
        return s
    full = pd.period_range(df['visit_date'].min().to_period('M'), df['visit_date'].max().to_period('M'), freq='M')
    s = s.reindex(full, fill_value=0)
    last_day = df['visit_date'].max()
    if last_day.day < last_day.days_in_month:      # drop an incomplete final month
        s = s.iloc[:-1]
    return s.astype(float)


def _seasonal_naive(train, h):
    return np.array([train.iloc[-12 + (i % 12)] for i in range(h)])


def _seasonal_mean(train, h):
    by_month = train.groupby(train.index.month).mean()
    start = train.index[-1] + 1
    return np.array([by_month[(start + i).month] for i in range(h)])


def _holt_winters(train, h):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        m = ExponentialSmoothing(train.values, trend='add', seasonal='add', seasonal_periods=12,
                                 initialization_method='estimated').fit(optimized=True)
    return np.clip(m.forecast(h), 0, None)


MODELS = {'Seasonal naive': _seasonal_naive, 'Seasonal mean': _seasonal_mean, 'Holt-Winters': _holt_winters}


def errors(actual, pred):
    actual, pred = np.asarray(actual, float), np.asarray(pred, float)
    mae = float(np.mean(np.abs(actual - pred)))
    rmse = float(np.sqrt(np.mean((actual - pred) ** 2)))
    nz = actual > 0
    mape = float(np.mean(np.abs((actual[nz] - pred[nz]) / actual[nz])) * 100) if nz.any() else None
    return {'mae': round(mae, 2), 'rmse': round(rmse, 2), 'mape': None if mape is None else round(mape, 1)}


def backtest(series: pd.Series, test_months: int = 12) -> dict:
    if len(series) < 24 + test_months:
        return {}
    train, test = series.iloc[:-test_months], series.iloc[-test_months:]
    out = {}
    for name, fn in MODELS.items():
        pred = fn(train, test_months)
        out[name] = {**errors(test.values, pred), 'predicted': [round(float(v), 1) for v in pred]}
    return {'test_periods': [str(p) for p in test.index], 'actual': [int(v) for v in test.values], 'models': out}


def forecast(df: pd.DataFrame, code: str, horizon: int = 6, test_end: str | None = None) -> dict:
    s = monthly(df, code)
    if len(s) < 36:
        return {'code': code, 'error': 'At least 36 complete months of data are needed.'}
    bt_series = s[:pd.Period(test_end, 'M')] if test_end else s
    bt = backtest(bt_series)
    best = min(bt['models'], key=lambda m: bt['models'][m]['mae']) if bt else 'Holt-Winters'
    future = MODELS[best](s, horizon)
    start = s.index[-1] + 1
    return {'code': code, 'history_periods': [str(p) for p in s.index], 'history': [int(v) for v in s.values],
            'backtest': bt, 'best_model': best,
            'forecast_periods': [str(start + i) for i in range(horizon)],
            'forecast': [round(float(v), 1) for v in future]}
