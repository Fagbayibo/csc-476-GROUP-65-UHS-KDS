import json
from datetime import date
import pandas as pd
from app import analytics
from app.ingest import clean
from app.mining import surveillance
from app.security import pseudonymise


# ---------- authentication and roles
def test_tc01_login_and_me(client, auth):
    assert client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrong'}).status_code == 401
    r = client.get('/api/auth/me', headers=auth['analyst'])
    assert r.status_code == 200 and r.json()['role'] == 'analyst'
    assert client.get('/api/auth/me').status_code == 401


def test_tc02_roles_are_enforced(client, auth):
    f = ('x.csv', b'card_no\n1\n', 'text/csv')
    assert client.post('/api/data/import', headers=auth['analyst'], files={'file': f}).status_code == 403
    assert client.get('/api/mining/rules', headers=auth['records']).status_code == 403
    assert client.get('/api/users', headers=auth['analyst']).status_code == 403
    r = client.post('/api/users', headers=auth['admin'], json={'username': 'nurse1', 'full_name': 'Nurse One',
                                                               'password': 'Password1', 'role': 'analyst'})
    assert r.status_code == 201


# ---------- pre-processing
def test_tc03_cleaning_rules():
    rows = [
        # card, sex, birth_year, category, faculty, hall, date, type, codes
        ['JC-1', 'Female', '2003', 'student', 'Science', 'Hall C', '2025-06-02', 'New', 'B54;A01.0'],
        ['JC-1', 'F', '2003', 'Student', 'Science', 'Hall C', '2025-06-02', 'New', 'A01.0;B54'],   # duplicate (order differs)
        ['JC-2', '', '1999', 'Student', 'Arts', 'Hall A', '05/03/2025', 'Follow-up', 'J06.9'],    # missing sex, DD/MM/YYYY
        ['JC-3', 'M', '1890', 'Staff', 'Law', 'Staff Quarters', '2025-02-30', 'New', 'I10'],     # impossible date
        ['JC-4', 'M', '1980', 'Visitor', 'Law', 'Off-campus', '2025-01-10', 'New', 'I10'],       # unknown category
        ['JC-5', 'M', '1980', 'Staff', 'Law', 'Off-campus', '2025-01-10', 'New', 'XYZ;I10'],     # one unknown code
        ['JC-6', 'M', '1980', 'Staff', 'Law', 'Off-campus', '2025-01-10', 'New', 'XYZ'],         # no valid code
        ['', 'M', '1980', 'Staff', 'Law', 'Off-campus', '2025-01-10', 'New', 'I10'],             # no card
        ['JC-7', 'M', '1980', 'Staff', 'Law', 'Off-campus', '2030-01-10', 'New', 'I10'],         # future date
    ]
    df = pd.DataFrame(rows, columns=['card_no', 'sex', 'birth_year', 'category', 'faculty', 'hall', 'visit_date',
                                     'visit_type', 'diagnosis_codes'])
    ids = {'B54': 1, 'A01.0': 2, 'J06.9': 3, 'I10': 4}
    recs, issues, _ = clean(df, ids, today=date(2026, 11, 19))
    assert len(recs) == 3
    assert issues == {'duplicate': 1, 'missing_sex': 1, 'date_reformatted': 1, 'invalid_date': 1,
                      'unknown_category': 1, 'unknown_code': 2, 'no_valid_diagnosis': 1, 'missing_card': 1,
                      'future_date': 1}
    assert recs[1]['visit_date'] == date(2025, 3, 5) and recs[1]['sex'] is None
    assert recs[2]['codes'] == ['I10']


def test_tc04_pseudonymisation():
    a, b = pseudonymise('JC-000123'), pseudonymise(' jc-000123 ')
    assert a == b and len(a) == 32 and 'JC' not in a.upper()[:2] or a != 'JC-000123'
    assert pseudonymise('JC-000124') != a


def test_tc05_import_summary(loaded):
    b = loaded['batch']
    truth = json.loads(loaded['truth'].read_text())
    assert b['rows_read'] == truth['rows_written']
    assert b['rows_loaded'] + b['rows_rejected'] + b['duplicates_removed'] == b['rows_read']
    assert b['rows_rejected'] > 0 and b['duplicates_removed'] > 0


def test_tc06_reimport_is_idempotent(client, auth, loaded):
    f = loaded['csv']
    r = client.post('/api/data/import', headers=auth['records'], files={'file': (f.name, f.read_bytes(), 'text/csv')})
    assert r.status_code == 201 and r.json()['rows_loaded'] == 0


def test_tc07_bad_file_rejected(client, auth):
    r = client.post('/api/data/import', headers=auth['records'], files={'file': ('a.csv', b'name,age\nx,1\n', 'text/csv')})
    assert r.status_code == 400 and 'Missing column' in r.json()['detail']


def test_tc08_no_card_numbers_stored(client, auth, loaded):
    r = client.get('/api/data/encounters?size=50', headers=auth['analyst'])
    assert r.status_code == 200
    assert all(not i['patient'].startswith('JC-') for i in r.json()['items'])


# ---------- descriptive analytics
def test_tc09_summary_and_top_ailment(client, auth, loaded):
    s = client.get('/api/analytics/summary', headers=auth['analyst']).json()
    assert s['encounters'] == loaded['batch']['rows_loaded']
    assert s['top_ailments'][0]['name' if 'name' in s['top_ailments'][0] else 'ailment'] == 'Malaria'


def test_tc10_malaria_seasonality(client, auth, loaded):
    s = client.get('/api/analytics/seasonality?ailment=B54', headers=auth['analyst']).json()
    idx = dict(zip(s['months'], s['index']))
    assert idx[7] > 1.3 and idx[2] < 0.75     # rainy-season peak, dry-season low


def test_tc11_filters(client, auth, loaded):
    f = client.get('/api/analytics/breakdown?by=sex&ailment=N94.6', headers=auth['analyst']).json()
    sexes = {r['sex'] for r in f['rows']}
    assert sexes <= {'F', 'Unknown'}           # dysmenorrhoea only in females


# ---------- knowledge discovery
def test_tc12_association_rules_recover_planted_patterns(client, auth, loaded):
    r = client.get('/api/mining/rules?min_support=0.003&min_confidence=0.2&min_lift=1.3', headers=auth['analyst']).json()
    rules = {(tuple(x['antecedent']), x['consequent']): x for x in r['rules']}
    dm = rules[(('dx=Type 2 diabetes mellitus',), 'Hypertension')]
    assert dm['confidence'] > 0.5 and dm['lift'] > 5
    r2 = client.get('/api/mining/rules?target=Typhoid%20fever&min_lift=1.3', headers=auth['analyst']).json()
    assert any(x['antecedent'] == ['dx=Malaria'] for x in r2['rules'])


def test_tc13_clusters_separate_high_malaria_halls(client, auth, loaded):
    c = client.get('/api/mining/clusters', headers=auth['analyst']).json()
    lab = {m['residence']: m['cluster'] for m in c['members']}
    assert lab['Hall C'] == lab['Hall G']
    assert sum(1 for v in lab.values() if v == lab['Hall C']) <= 3


def test_tc14_forecast(client, auth, loaded):
    f = client.get('/api/mining/forecast?code=B54&horizon=6', headers=auth['analyst']).json()
    assert len(f['forecast']) == 6 and f['best_model'] in f['backtest']['models']
    assert f['backtest']['models'][f['best_model']]['mape'] < 15


def test_tc15_outbreak_detection_finds_planted_outbreaks(loaded):
    df = analytics.facts()
    camp = surveillance.scan(df, 'historical', 'campus', codes=['J06.9'])
    assert any('2024-01-15' <= a['week_start'] <= '2024-02-05' for a in camp)     # OB2
    halls = surveillance.scan(df, 'ears_c2', 'residence', codes=['A09'])
    assert any(a['residence'] == 'Hall F' and '2024-05-06' <= a['week_start'] <= '2024-05-20' for a in halls)  # OB3


def test_tc16_alerts_saved_and_acknowledged(client, auth, loaded):
    r = client.get('/api/mining/alerts?method=ears_c2&level=residence&weeks=40', headers=auth['analyst']).json()
    assert r['alerts'], 'expected at least one signal in the last 40 weeks'
    aid = r['alerts'][0]['id']
    assert client.post(f'/api/mining/alerts/{aid}/status', headers=auth['analyst'], json={'status': 'acknowledged'}).json()['status'] == 'acknowledged'
    again = client.get('/api/mining/alerts?method=ears_c2&level=residence&weeks=40', headers=auth['analyst']).json()
    assert next(a for a in again['alerts'] if a['id'] == aid)['status'] == 'acknowledged'


def test_tc17_export_and_audit(client, auth, loaded):
    r = client.get('/api/reports/export?kind=monthly', headers=auth['analyst'])
    assert r.status_code == 200 and r.text.startswith('month,')
    runs = client.get('/api/runs', headers=auth['analyst']).json()
    assert {x['kind'] for x in runs} >= {'association_rules', 'clustering', 'forecast', 'surveillance'}
