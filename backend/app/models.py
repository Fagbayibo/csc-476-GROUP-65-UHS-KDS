"""
Database model, normalised to Third Normal Form.
* Look-up values (patient categories, faculties, residences, ailment groups, ailments) are stored once
  and referenced by key.
* A patient's age and the season of a visit are not stored: they are derived from birth_year and
  visit_date, so they can never disagree with them.
* An encounter can have several diagnoses, held in ENCOUNTER_DIAGNOSES (one row per diagnosis).
"""
from datetime import datetime, date
from sqlalchemy import (String, Integer, Date, DateTime, Boolean, Float, ForeignKey, Text,
                        UniqueConstraint, CheckConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (CheckConstraint("role IN ('admin','records_officer','analyst')", name='ck_user_role'),)


class PatientCategory(Base):
    __tablename__ = 'patient_categories'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)


class Faculty(Base):
    __tablename__ = 'faculties'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class Residence(Base):
    __tablename__ = 'residences'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(String(20))   # hall | staff_quarters | off_campus
    __table_args__ = (CheckConstraint("kind IN ('hall','staff_quarters','off_campus')", name='ck_res_kind'),)


class AilmentGroup(Base):
    __tablename__ = 'ailment_groups'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)


class Ailment(Base):
    __tablename__ = 'ailments'
    id: Mapped[int] = mapped_column(primary_key=True)
    icd10_code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    group_id: Mapped[int] = mapped_column(ForeignKey('ailment_groups.id'))
    group: Mapped[AilmentGroup] = relationship()


class Patient(Base):
    __tablename__ = 'patients'
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_key: Mapped[str] = mapped_column(String(32), unique=True)   # pseudonym, never the card number
    sex: Mapped[str | None] = mapped_column(String(1))
    birth_year: Mapped[int | None] = mapped_column(Integer)
    category_id: Mapped[int] = mapped_column(ForeignKey('patient_categories.id'))
    faculty_id: Mapped[int | None] = mapped_column(ForeignKey('faculties.id'))
    residence_id: Mapped[int | None] = mapped_column(ForeignKey('residences.id'))
    __table_args__ = (CheckConstraint("sex IN ('M','F') OR sex IS NULL", name='ck_patient_sex'),)


class ImportBatch(Base):
    __tablename__ = 'import_batches'
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(200))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, default=0)
    issues_json: Mapped[str] = mapped_column(Text, default='{}')
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)


class Encounter(Base):
    __tablename__ = 'encounters'
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'))
    visit_date: Mapped[date] = mapped_column(Date)
    visit_type: Mapped[str] = mapped_column(String(10))
    batch_id: Mapped[int] = mapped_column(ForeignKey('import_batches.id'))
    __table_args__ = (Index('ix_encounters_date', 'visit_date'), Index('ix_encounters_patient', 'patient_id'),
                      CheckConstraint("visit_type IN ('New','Follow-up')", name='ck_visit_type'))


class EncounterDiagnosis(Base):
    __tablename__ = 'encounter_diagnoses'
    encounter_id: Mapped[int] = mapped_column(ForeignKey('encounters.id', ondelete='CASCADE'), primary_key=True)
    ailment_id: Mapped[int] = mapped_column(ForeignKey('ailments.id'), primary_key=True)
    __table_args__ = (Index('ix_dx_ailment', 'ailment_id'),)


class AnalysisRun(Base):
    __tablename__ = 'analysis_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    parameters_json: Mapped[str] = mapped_column(Text, default='{}')
    summary_json: Mapped[str] = mapped_column(Text, default='{}')
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = 'alerts'
    id: Mapped[int] = mapped_column(primary_key=True)
    ailment_id: Mapped[int] = mapped_column(ForeignKey('ailments.id'))
    residence_id: Mapped[int | None] = mapped_column(ForeignKey('residences.id'))  # empty = whole campus
    week_start: Mapped[date] = mapped_column(Date)
    method: Mapped[str] = mapped_column(String(20))
    observed: Mapped[int] = mapped_column(Integer)
    expected: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(15), default='new')
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('ailment_id', 'residence_id', 'week_start', 'method', name='uq_alert'),
                      CheckConstraint("status IN ('new','acknowledged','dismissed')", name='ck_alert_status'))
