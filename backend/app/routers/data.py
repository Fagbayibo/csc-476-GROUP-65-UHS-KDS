import json
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..config import MAX_UPLOAD_MB
from ..db import get_db
from ..ingest import ImportErrorMsg, import_csv, REQUIRED
from ..models import (Ailment, AilmentGroup, Encounter, EncounterDiagnosis, Faculty, ImportBatch, Patient,
                      PatientCategory, Residence, User)
from ..security import ANY_ROLE, require
from .. import analytics

router = APIRouter(prefix='/api', tags=['data'])


def batch_out(b: ImportBatch, uploader: str | None = None):
    return {'id': b.id, 'filename': b.filename, 'uploaded_at': b.uploaded_at.isoformat(timespec='seconds'),
            'uploaded_by': uploader, 'rows_read': b.rows_read, 'rows_loaded': b.rows_loaded,
            'rows_rejected': b.rows_rejected, 'duplicates_removed': b.duplicates_removed,
            'duration_ms': b.duration_ms, 'issues': json.loads(b.issues_json or '{}')}


@router.post('/data/import', status_code=201)
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db),
                 user: User = Depends(require('admin', 'records_officer'))):
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(400, 'Please upload a .csv file.')
    content = await file.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f'The file is larger than {MAX_UPLOAD_MB} MB.')
    try:
        b = import_csv(db, content, file.filename, user.id)
    except ImportErrorMsg as e:
        raise HTTPException(400, str(e))
    return batch_out(b, user.full_name)


@router.get('/data/batches')
def batches(db: Session = Depends(get_db), _=Depends(require(*ANY_ROLE))):
    rows = db.query(ImportBatch, User.full_name).join(User, User.id == ImportBatch.uploaded_by) \
        .order_by(ImportBatch.id.desc()).limit(50).all()
    return [batch_out(b, n) for b, n in rows]


@router.get('/data/template')
def template(_=Depends(require(*ANY_ROLE))):
    return {'columns': REQUIRED, 'example': {
        'card_no': 'JC-000123', 'sex': 'F', 'birth_year': '2003', 'category': 'Student', 'faculty': 'Science',
        'hall': 'Hall C', 'visit_date': '2026-10-12', 'visit_type': 'New', 'diagnosis_codes': 'B54;A01.0'}}


@router.get('/data/encounters')
def encounters(page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=100), code: str | None = None,
               db: Session = Depends(get_db), _=Depends(require(*ANY_ROLE))):
    q = select(Encounter.id, Encounter.visit_date, Encounter.visit_type, Patient.patient_key, Patient.sex,
               Patient.birth_year, PatientCategory.name, Residence.name) \
        .join(Patient, Patient.id == Encounter.patient_id) \
        .join(PatientCategory, PatientCategory.id == Patient.category_id) \
        .outerjoin(Residence, Residence.id == Patient.residence_id)
    if code:
        q = q.where(Encounter.id.in_(select(EncounterDiagnosis.encounter_id).join(Ailment).where(Ailment.icd10_code == code)))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(Encounter.visit_date.desc(), Encounter.id.desc()).limit(size).offset((page - 1) * size)).all()
    ids = [r[0] for r in rows]
    dx = {}
    if ids:
        for eid, c, n in db.execute(select(EncounterDiagnosis.encounter_id, Ailment.icd10_code, Ailment.name)
                                    .join(Ailment).where(EncounterDiagnosis.encounter_id.in_(ids))):
            dx.setdefault(eid, []).append(f'{c} {n}')
    return {'total': total, 'page': page, 'size': size, 'items': [
        {'id': r[0], 'visit_date': r[1].isoformat(), 'visit_type': r[2], 'patient': r[3][:10], 'sex': r[4] or '?',
         'birth_year': r[5], 'category': r[6], 'residence': r[7], 'diagnoses': dx.get(r[0], [])} for r in rows]}


@router.get('/reference')
def reference(db: Session = Depends(get_db), _=Depends(require(*ANY_ROLE))):
    ail = db.query(Ailment, AilmentGroup.name).join(AilmentGroup).order_by(Ailment.name).all()
    dr = db.execute(select(func.min(Encounter.visit_date), func.max(Encounter.visit_date))).one()
    return {
        'ailments': [{'code': a.icd10_code, 'name': a.name, 'group': g} for a, g in ail],
        'groups': sorted({g for _, g in ail}),
        'residences': [{'name': r.name, 'kind': r.kind} for r in db.query(Residence).order_by(Residence.name)],
        'faculties': [f.name for f in db.query(Faculty).order_by(Faculty.name)],
        'categories': [c.name for c in db.query(PatientCategory).order_by(PatientCategory.name)],
        'date_range': [dr[0].isoformat() if dr[0] else None, dr[1].isoformat() if dr[1] else None],
        'age_groups': analytics.AGE_LABELS, 'seasons': ['Harmattan', 'Dry', 'Rainy'],
    }
