"""
Association-rule mining (Apriori). Each visit becomes a 'transaction' of items: the diagnoses made
plus the patient's sex, category, age group, residence and the season. Rules of the form
{items} -> {diagnosis} are kept when they meet the support, confidence and lift thresholds.
"""
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules


def transactions(df: pd.DataFrame, include_residence: bool = True) -> pd.DataFrame:
    enc = df.drop_duplicates('encounter_id').set_index('encounter_id')
    attrs = {'sex': 'sex', 'category': 'category', 'age': 'age_group', 'season': 'season'}
    if include_residence:
        attrs['residence'] = 'residence'
    parts = []
    for label, col in attrs.items():
        vals = enc[col].astype(str)
        vals = vals[~vals.isin(['Unknown', 'None', 'nan'])]
        parts.append(pd.get_dummies(label + '=' + vals))
    dx = pd.crosstab(df['encounter_id'], 'dx=' + df['ailment'].astype(str)).clip(upper=1)
    onehot = pd.concat(parts, axis=1).reindex(enc.index, fill_value=False)
    onehot = onehot.join(dx.astype(bool), how='left').fillna(False).astype(bool)
    return onehot


def mine(df: pd.DataFrame, min_support=0.003, min_confidence=0.2, min_lift=1.3, max_len=3, target=None, limit=200):
    if df.empty:
        return {'transactions': 0, 'itemsets': 0, 'rules': []}
    onehot = transactions(df)
    items = apriori(onehot, min_support=min_support, use_colnames=True, max_len=max_len, low_memory=True)
    if items.empty:
        return {'transactions': int(len(onehot)), 'itemsets': 0, 'rules': []}
    rules = association_rules(items, metric='confidence', min_threshold=min_confidence)
    # keep rules that predict a diagnosis, whose antecedent is not just another attribute of the consequent
    rules = rules[rules['consequents'].apply(lambda c: len(c) == 1 and next(iter(c)).startswith('dx='))]
    rules = rules[rules['lift'] >= min_lift]
    if target:
        rules = rules[rules['consequents'].apply(lambda c: next(iter(c)) == 'dx=' + target)]
    rules = rules.sort_values(['lift', 'confidence'], ascending=False).head(limit)
    out = []
    for r in rules.itertuples():
        out.append({'antecedent': sorted(r.antecedents), 'consequent': next(iter(r.consequents)).removeprefix('dx='),
                    'support': round(float(r.support), 4), 'confidence': round(float(r.confidence), 3),
                    'lift': round(float(r.lift), 2), 'count': int(round(r.support * len(onehot)))})
    return {'transactions': int(len(onehot)), 'itemsets': int(len(items)), 'rules': out}
