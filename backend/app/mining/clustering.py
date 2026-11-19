"""
k-means clustering of halls of residence by their ailment profile (cases per 100 resident patients
per year for each ailment, standardised). The number of clusters is chosen by the silhouette score.
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


def profiles(df: pd.DataFrame, kinds=('hall',)) -> pd.DataFrame:
    d = df[df['residence_kind'].isin(kinds)]
    years = max(1.0, (d['visit_date'].max() - d['visit_date'].min()).days / 365.25)
    residents = d.groupby('residence', observed=True)['patient_id'].nunique()
    counts = d.groupby(['residence', 'ailment'], observed=True).size().unstack(fill_value=0)
    rates = counts.div(residents, axis=0) * 100 / years
    return rates[(residents >= 20).reindex(rates.index, fill_value=False)]


def cluster(df: pd.DataFrame, k: int | None = None, seed: int = 42) -> dict:
    rates = profiles(df)
    if len(rates) < 3:
        return {'k': 0, 'silhouette': None, 'members': [], 'clusters': [], 'scores': []}
    X = StandardScaler().fit_transform(rates.values)
    candidates = [k] if k else list(range(2, min(6, len(rates) - 1) + 1))
    scores, best = [], None
    for kk in candidates:
        km = KMeans(n_clusters=kk, n_init=20, random_state=seed).fit(X)
        s = float(silhouette_score(X, km.labels_)) if kk > 1 else 0.0
        scores.append({'k': kk, 'silhouette': round(s, 3)})
        if best is None or s > best[0]:
            best = (s, kk, km)
    s, kk, km = best
    xy = PCA(n_components=2, random_state=seed).fit_transform(X)
    overall = rates.mean()
    members, clusters = [], []
    for i, name in enumerate(rates.index):
        members.append({'residence': str(name), 'cluster': int(km.labels_[i]), 'x': round(float(xy[i, 0]), 3),
                        'y': round(float(xy[i, 1]), 3)})
    for c in range(kk):
        idx = np.where(km.labels_ == c)[0]
        mean_rates = rates.iloc[idx].mean()
        ratio = (mean_rates / overall.replace(0, np.nan)).sort_values(ascending=False)
        clusters.append({'cluster': c, 'size': int(len(idx)), 'residences': [str(rates.index[j]) for j in idx],
                         'distinctive': [{'ailment': a, 'rate': round(float(mean_rates[a]), 2), 'ratio_to_average': round(float(v), 2)}
                                         for a, v in ratio.head(3).items()]})
    table = rates.round(2)
    return {'k': int(kk), 'silhouette': round(s, 3), 'scores': scores, 'members': members, 'clusters': clusters,
            'ailments': [str(c) for c in table.columns],
            'rates': [{'residence': str(r), **{str(c): float(table.loc[r, c]) for c in table.columns}} for r in table.index]}
