"""Reference list of ailments (ICD-10) tracked by the system, and helpers to seed it."""
from sqlalchemy.orm import Session
from .models import Ailment, AilmentGroup, PatientCategory

AILMENTS = [
    ('B54', 'Malaria', 'Infectious and parasitic'),
    ('A01.0', 'Typhoid fever', 'Infectious and parasitic'),
    ('A09', 'Gastroenteritis', 'Infectious and parasitic'),
    ('B36.9', 'Superficial fungal skin infection', 'Skin'),
    ('J06.9', 'Upper respiratory tract infection', 'Respiratory'),
    ('J45.9', 'Asthma', 'Respiratory'),
    ('J30.4', 'Allergic rhinitis', 'Respiratory'),
    ('H10.9', 'Conjunctivitis', 'Eye'),
    ('K29.7', 'Gastritis / peptic ulcer disease', 'Digestive'),
    ('K02.9', 'Dental caries', 'Digestive'),
    ('N39.0', 'Urinary tract infection', 'Genitourinary'),
    ('N94.6', 'Dysmenorrhoea', 'Genitourinary'),
    ('I10', 'Hypertension', 'Circulatory and metabolic'),
    ('E11.9', 'Type 2 diabetes mellitus', 'Circulatory and metabolic'),
    ('F41.9', 'Anxiety / stress-related disorder', 'Mental and behavioural'),
    ('T14.9', 'Injury (unspecified)', 'Injury'),
]
CATEGORIES = ['Student', 'Staff', 'Dependant']


def seed_reference(db: Session):
    groups = {g.name: g for g in db.query(AilmentGroup).all()}
    existing = {a.icd10_code for a in db.query(Ailment).all()}
    for code, name, group in AILMENTS:
        if group not in groups:
            groups[group] = AilmentGroup(name=group)
            db.add(groups[group])
            db.flush()
        if code not in existing:
            db.add(Ailment(icd10_code=code, name=name, group_id=groups[group].id))
    cats = {c.name for c in db.query(PatientCategory).all()}
    for c in CATEGORIES:
        if c not in cats:
            db.add(PatientCategory(name=c))
    db.commit()
