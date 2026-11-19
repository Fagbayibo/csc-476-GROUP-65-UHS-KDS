import os
import sys
import tempfile
from pathlib import Path
import pytest

TMP = Path(tempfile.mkdtemp(prefix='uhs_test_'))
os.environ['DATABASE_URL'] = f"sqlite:///{TMP / 'test.db'}"
os.environ['JWT_SECRET'] = 'test-secret-that-is-long-enough-for-hs256-signing'
os.environ['PSEUDONYM_SALT'] = 'test-salt'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient            # noqa: E402
from app.main import app                             # noqa: E402
from app.db import SessionLocal                      # noqa: E402
from app.models import User                          # noqa: E402
from app.security import hash_password               # noqa: E402
from scripts.generate_synthetic import generate      # noqa: E402


@pytest.fixture(scope='session')
def client():
    with TestClient(app) as c:      # runs startup: creates tables, reference data and admin
        with SessionLocal() as db:
            db.add_all([User(username='records', full_name='Records Officer', role='records_officer',
                             password_hash=hash_password('Records@123')),
                        User(username='analyst', full_name='Analyst', role='analyst',
                             password_hash=hash_password('Analyst@123'))])
            db.commit()
        yield c


def token(client, u, p):
    r = client.post('/api/auth/login', json={'username': u, 'password': p})
    assert r.status_code == 200, r.text
    return {'Authorization': f"Bearer {r.json()['token']}"}


@pytest.fixture(scope='session')
def auth(client):
    return {'admin': token(client, 'admin', 'Admin@12345'), 'records': token(client, 'records', 'Records@123'),
            'analyst': token(client, 'analyst', 'Analyst@123')}


@pytest.fixture(scope='session')
def loaded(client, auth):
    """Generates the full synthetic dataset and imports it through the API."""
    out = TMP / 'data'
    generate(out, 2026)
    f = out / 'uhs_encounters_synthetic.csv'
    r = client.post('/api/data/import', headers=auth['records'],
                    files={'file': (f.name, f.read_bytes(), 'text/csv')})
    assert r.status_code == 201, r.text
    return {'batch': r.json(), 'csv': f, 'truth': out / 'ground_truth.json'}
