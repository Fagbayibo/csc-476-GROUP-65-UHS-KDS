"""Creates the tables, the reference data, demonstration users, and loads the synthetic dataset."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import Base, SessionLocal, engine          # noqa: E402
from app.ingest import import_csv                       # noqa: E402
from app.models import User                             # noqa: E402
from app.reference import seed_reference                # noqa: E402
from app.security import hash_password                  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / 'data' / 'uhs_encounters_synthetic.csv'
USERS = [('admin', 'System Administrator', 'admin', 'Admin@12345'),
         ('records', 'Health Records Officer (demo)', 'records_officer', 'Records@123'),
         ('analyst', 'Medical Officer / Analyst (demo)', 'analyst', 'Analyst@123')]

if __name__ == '__main__':
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_reference(db)
        for u, n, r, p in USERS:
            db.add(User(username=u, full_name=n, role=r, password_hash=hash_password(p)))
        db.commit()
        if not DATA.exists():
            sys.exit(f'{DATA} not found – run scripts/generate_synthetic.py first.')
        records = db.query(User).filter_by(username='records').one()
        b = import_csv(db, DATA.read_bytes(), DATA.name, records.id)
        print(f'Imported {b.rows_loaded} of {b.rows_read} rows ({b.rows_rejected} rejected, '
              f'{b.duplicates_removed} duplicates) in {b.duration_ms} ms.')
    print('Demo users: admin/Admin@12345, records/Records@123, analyst/Analyst@123')
