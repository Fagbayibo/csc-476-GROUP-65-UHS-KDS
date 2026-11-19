"""
Pre-processing step of the knowledge-discovery process: reads a CSV export of clinic encounters,
cleans and validates it, pseudonymises the card numbers and loads it into the database.
"""
import io
import json
import time
from datetime import date, datetime
import pandas as pd
from sqlalchemy import insert, select
from sqlalchemy.orm import Session
from .models import (Ailment, Encounter, EncounterDiagnosis, Faculty, ImportBatch, Patient,
                     PatientCategory, Residence)
from .security import pseudonymise

REQUIRED = ['card_no', 'sex', 'birth_year', 'category', 'faculty', 'hall', 'visit_date', 'visit_type', 'diagnosis_codes']
SEX_MAP = {'M': 'M', 'MALE': 'M', 'F': 'F', 'FEMALE': 'F'}
CAT_MAP = {'STUDENT': 'Student', 'STAFF': 'Staff', 'DEPENDANT': 'Dependant', 'DEPENDENT': 'Dependant'}
ISSUE_TEXT = {
    'missing_card': 'No card number – row rejected',
    'invalid_date': 'Visit date missing or not a valid date – row rejected',
    'future_date': 'Visit date is in the future – row rejected',
    'unknown_category': 'Patient category not Student, Staff or Dependant – row rejected',
    'no_valid_diagnosis': 'No recognised ICD-10 diagnosis – row rejected',
    'unknown_code': 'Unrecognised diagnosis code removed (row kept if another code was valid)',
    'missing_sex': 'Sex missing – kept as unknown',
    'invalid_birth_year': 'Birth year missing or implausible – kept, age unknown',
    'date_reformatted': 'Date written as DD/MM/YYYY – converted',
    'duplicate': 'Exact duplicate of another visit – removed',
}


class ImportErrorMsg(Exception):
    pass


def residence_kind(name: str) -> str:
    n = name.lower()
    if 'staff' in n:
        return 'staff_quarters'
    if 'off' in n and 'campus' in n:
        return 'off_campus'
    return 'hall'


def parse_date(s: str):
    """Returns (date, reformatted?) or (None, False)."""
    s = (s or '').strip()
    for fmt, flag in (('%Y-%m-%d', False), ('%d/%m/%Y', True), ('%d-%m-%Y', True)):
        try:
            return datetime.strptime(s, fmt).date(), flag
        except ValueError:
            continue
    return None, False


def clean(df: pd.DataFrame, ailment_ids: dict, today: date | None = None):
    """Validates and normalises rows. Returns (clean records, issue counts, issue examples)."""
    today = today or date.today()
    issues, examples = {}, {}

    def note(kind, rownum):
        issues[kind] = issues.get(kind, 0) + 1
        ex = examples.setdefault(kind, [])
        if len(ex) < 5:
            ex.append(rownum)

    records, seen = [], set()
    for i, r in enumerate(df.itertuples(index=False), start=2):  # row 1 is the header
        card = (r.card_no or '').strip()
        if not card:
            note('missing_card', i); continue
        d, reformatted = parse_date(r.visit_date)
        if d is None:
            note('invalid_date', i); continue
        if reformatted:
            note('date_reformatted', i)
        if d > today:
            note('future_date', i); continue
        cat = CAT_MAP.get((r.category or '').strip().upper())
        if not cat:
            note('unknown_category', i); continue
        codes, unknown = [], False
        for c in str(r.diagnosis_codes or '').replace(',', ';').split(';'):
            c = c.strip().upper()
            if not c:
                continue
            if c in ailment_ids:
                if c not in codes:
                    codes.append(c)
            else:
                unknown = True
        if unknown:
            note('unknown_code', i)
        if not codes:
            note('no_valid_diagnosis', i); continue
        sex = SEX_MAP.get((r.sex or '').strip().upper())
        if sex is None:
            note('missing_sex', i)
        try:
            by = int(str(r.birth_year).strip())
            if not (1920 <= by <= d.year):
                raise ValueError
        except ValueError:
            by = None
            note('invalid_birth_year', i)
        vt = 'Follow-up' if (r.visit_type or '').strip().lower().startswith('follow') else 'New'
        key = pseudonymise(card)
        sig = (key, d, tuple(sorted(codes)))
        if sig in seen:
            note('duplicate', i); continue
        seen.add(sig)
        records.append({'key': key, 'sex': sex, 'birth_year': by, 'category': cat,
                        'faculty': (r.faculty or '').strip() or None, 'residence': (r.hall or '').strip() or None,
                        'visit_date': d, 'visit_type': vt, 'codes': codes})
    return records, issues, examples


def import_csv(db: Session, content: bytes, filename: str, user_id: int, today: date | None = None) -> ImportBatch:
    t0 = time.perf_counter()
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as e:  # noqa: BLE001
        raise ImportErrorMsg(f'The file could not be read as CSV ({e}).')
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ImportErrorMsg(f'Missing column(s): {", ".join(missing)}. Expected: {", ".join(REQUIRED)}.')
    df = df[REQUIRED]

    ailment_ids = {a.icd10_code: a.id for a in db.query(Ailment).all()}
    records, issues, examples = clean(df, ailment_ids, today)

    # duplicates of visits already in the database
    existing = set()
    if records and db.query(Encounter.id).first():
        rows = db.execute(select(Encounter.id, Patient.patient_key, Encounter.visit_date, Ailment.icd10_code)
                          .join(Encounter, Encounter.patient_id == Patient.id)
                          .join(EncounterDiagnosis, EncounterDiagnosis.encounter_id == Encounter.id)
                          .join(Ailment, Ailment.id == EncounterDiagnosis.ailment_id)).all()
        tmp = {}
        for eid, k, d, c in rows:
            tmp.setdefault((eid, k, d), []).append(c)
        existing = {(k, d, tuple(sorted(cs))) for (_, k, d), cs in tmp.items()}
    fresh = []
    for rec in records:
        if (rec['key'], rec['visit_date'], tuple(sorted(rec['codes']))) in existing:
            issues['duplicate'] = issues.get('duplicate', 0) + 1
        else:
            fresh.append(rec)

    batch = ImportBatch(filename=filename[:200], uploaded_by=user_id, rows_read=len(df))
    db.add(batch)
    db.flush()

    def lookup(model, values, extra=None):
        have = {o.name: o.id for o in db.query(model).all()}
        for v in sorted(values - have.keys()):
            obj = model(name=v, **(extra(v) if extra else {}))
            db.add(obj); db.flush(); have[v] = obj.id
        return have

    cats = lookup(PatientCategory, {r['category'] for r in fresh})
    facs = lookup(Faculty, {r['faculty'] for r in fresh if r['faculty']})
    ress = lookup(Residence, {r['residence'] for r in fresh if r['residence']}, lambda v: {'kind': residence_kind(v)})

    patients = {k: pid for k, pid in db.execute(select(Patient.patient_key, Patient.id)).all()}
    new_patients = {}
    for r in fresh:
        if r['key'] not in patients and r['key'] not in new_patients:
            new_patients[r['key']] = {'patient_key': r['key'], 'sex': r['sex'], 'birth_year': r['birth_year'],
                                      'category_id': cats[r['category']], 'faculty_id': facs.get(r['faculty']),
                                      'residence_id': ress.get(r['residence'])}
    if new_patients:
        db.execute(insert(Patient), list(new_patients.values()))
        patients = {k: pid for k, pid in db.execute(select(Patient.patient_key, Patient.id)).all()}

    if fresh:
        enc_rows = [{'patient_id': patients[r['key']], 'visit_date': r['visit_date'], 'visit_type': r['visit_type'],
                     'batch_id': batch.id} for r in fresh]
        ids = db.execute(insert(Encounter).returning(Encounter.id, sort_by_parameter_order=True), enc_rows).scalars().all()
        dx = [{'encounter_id': eid, 'ailment_id': ailment_ids[c]} for eid, r in zip(ids, fresh) for c in r['codes']]
        db.execute(insert(EncounterDiagnosis), dx)

    rejected = sum(v for k, v in issues.items() if k in ('missing_card', 'invalid_date', 'future_date',
                                                         'unknown_category', 'no_valid_diagnosis'))
    batch.rows_loaded = len(fresh)
    batch.rows_rejected = rejected
    batch.duplicates_removed = issues.get('duplicate', 0)
    batch.issues_json = json.dumps({k: {'count': v, 'description': ISSUE_TEXT[k], 'example_rows': examples.get(k, [])}
                                    for k, v in sorted(issues.items(), key=lambda x: -x[1])})
    batch.duration_ms = int((time.perf_counter() - t0) * 1000)
    db.commit()
    from . import analytics
    analytics.invalidate()
    return batch
