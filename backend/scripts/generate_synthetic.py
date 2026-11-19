"""
Generates a SYNTHETIC dataset of clinic encounters for testing the Knowledge Discovery System.

No real patient data is used. The records are made up, but their patterns follow published
findings on Nigerian university clinics: malaria peaks in the rainy season, respiratory
complaints rise in the harmattan, malaria and typhoid are often diagnosed together, and
hypertension and diabetes affect older staff. Known outbreaks and patterns are planted so that
the mining results can be checked against a ground truth (written to ground_truth.json).

Usage:  python scripts/generate_synthetic.py [--out data] [--seed 2026]
"""
import argparse
import csv
import json
import math
import random
from itertools import accumulate
from datetime import date, timedelta
from pathlib import Path

START, END = date(2022, 1, 1), date(2026, 10, 31)

FACULTIES = ['Arts', 'Science', 'Social Sciences', 'Education', 'Technology', 'Agriculture', 'Law',
             'Pharmacy', 'Clinical Sciences', 'Basic Medical Sciences', 'Veterinary Medicine',
             'Economics and Management Sciences']
HALLS = [f'Hall {c}' for c in 'ABCDEFGHIJ']  # neutral names: these are not real halls

# ICD-10 code, name, group, base cases per weekday, monthly seasonal multipliers (Jan..Dec)
AILMENTS = [
    ('B54', 'Malaria', 'Infectious and parasitic', 30.0, [0.6, 0.5, 0.7, 1.0, 1.3, 1.6, 1.8, 1.8, 1.6, 1.3, 0.9, 0.7]),
    ('A01.0', 'Typhoid fever', 'Infectious and parasitic', 4.0, [0.8, 0.8, 0.9, 1.0, 1.1, 1.2, 1.2, 1.2, 1.1, 1.0, 0.9, 0.8]),
    ('A09', 'Gastroenteritis', 'Infectious and parasitic', 7.0, [0.8, 0.8, 0.9, 1.1, 1.3, 1.3, 1.2, 1.1, 1.1, 1.0, 0.9, 0.8]),
    ('B36.9', 'Superficial fungal skin infection', 'Skin', 4.0, [1.0, 1.3, 1.6, 1.5, 1.1, 0.9, 0.8, 0.8, 0.8, 0.9, 1.0, 1.0]),
    ('J06.9', 'Upper respiratory tract infection', 'Respiratory', 18.0, [1.8, 1.6, 1.1, 0.8, 0.7, 0.8, 1.0, 1.1, 0.9, 0.8, 1.0, 1.6]),
    ('J45.9', 'Asthma', 'Respiratory', 2.5, [1.9, 1.7, 1.2, 0.9, 0.8, 0.8, 0.9, 0.9, 0.8, 0.8, 1.1, 1.7]),
    ('J30.4', 'Allergic rhinitis', 'Respiratory', 2.0, [1.8, 1.6, 1.2, 0.9, 0.8, 0.8, 0.8, 0.8, 0.8, 0.9, 1.1, 1.7]),
    ('H10.9', 'Conjunctivitis', 'Eye', 2.0, [1.1, 1.1, 1.0, 1.0, 0.9, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1]),
    ('K29.7', 'Gastritis / peptic ulcer disease', 'Digestive', 6.0, [1.0] * 12),
    ('K02.9', 'Dental caries', 'Digestive', 3.0, [1.0] * 12),
    ('N39.0', 'Urinary tract infection', 'Genitourinary', 5.0, [1.0, 1.0, 1.1, 1.1, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
    ('N94.6', 'Dysmenorrhoea', 'Genitourinary', 3.5, [1.0] * 12),
    ('I10', 'Hypertension', 'Circulatory and metabolic', 6.0, [1.15, 1.1, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.05, 1.15]),
    ('E11.9', 'Type 2 diabetes mellitus', 'Circulatory and metabolic', 2.5, [1.0] * 12),
    ('F41.9', 'Anxiety / stress-related disorder', 'Mental and behavioural', 2.0, [1.0] * 12),
    ('T14.9', 'Injury (unspecified)', 'Injury', 4.0, [1.0] * 12),
]
EXAM_MONTHS = {2, 7}           # synthetic academic calendar: exams in February and July
BREAK_MONTHS = {8, 9}          # long vacation: fewer students on campus
OUTBREAKS = [                  # planted outbreaks (ground truth for the surveillance evaluation)
    {'id': 'OB1', 'code': 'H10.9', 'hall': None, 'start': '2023-10-16', 'weeks': 3, 'extra_per_week': 45, 'label': 'Campus-wide conjunctivitis outbreak'},
    {'id': 'OB2', 'code': 'J06.9', 'hall': None, 'start': '2024-01-15', 'weeks': 3, 'extra_per_week': 60, 'label': 'Influenza-like respiratory outbreak'},
    {'id': 'OB3', 'code': 'A09', 'hall': 'Hall F', 'start': '2024-05-06', 'weeks': 2, 'extra_per_week': 28, 'label': 'Gastroenteritis cluster in Hall F'},
    {'id': 'OB4', 'code': 'A01.0', 'hall': 'Hall D', 'start': '2025-03-10', 'weeks': 2, 'extra_per_week': 16, 'label': 'Typhoid cluster in Hall D'},
    {'id': 'OB5', 'code': 'A09', 'hall': 'Hall B', 'start': '2025-09-15', 'weeks': 2, 'extra_per_week': 22, 'label': 'Gastroenteritis cluster in Hall B'},
    {'id': 'OB6', 'code': 'H10.9', 'hall': 'Hall H', 'start': '2026-06-08', 'weeks': 2, 'extra_per_week': 14, 'label': 'Conjunctivitis cluster in Hall H'},
]


def season(d: date) -> str:
    if d.month in (12, 1, 2):
        return 'Harmattan'
    if 4 <= d.month <= 10:
        return 'Rainy'
    return 'Dry'


class Person:
    __slots__ = ('card', 'sex', 'birth_year', 'category', 'faculty', 'hall')

    def __init__(self, card, sex, birth_year, category, faculty, hall):
        self.card, self.sex, self.birth_year = card, sex, birth_year
        self.category, self.faculty, self.hall = category, faculty, hall

    def age(self, year):
        return year - self.birth_year


def make_population(rng):
    people, n = [], 0
    def card():
        nonlocal n
        n += 1
        return f'JC-{n:06d}'
    for _ in range(9000):
        sex = 'M' if rng.random() < 0.52 else 'F'
        by = 2022 - min(34, max(16, int(rng.gauss(21.5, 2.8))))
        hall = rng.choices(HALLS + ['Off-campus'], weights=[7] * 10 + [30])[0]
        people.append(Person(card(), sex, by, 'Student', rng.choice(FACULTIES), hall))
    for _ in range(1500):
        sex = 'M' if rng.random() < 0.55 else 'F'
        by = 2022 - rng.randint(25, 64)
        people.append(Person(card(), sex, by, 'Staff', rng.choice(FACULTIES + ['Administration'] * 4),
                             rng.choice(['Staff Quarters', 'Off-campus'])))
    for _ in range(500):
        sex = 'M' if rng.random() < 0.5 else 'F'
        people.append(Person(card(), sex, 2022 - rng.randint(0, 15), 'Dependant', '', rng.choice(['Staff Quarters', 'Off-campus'])))
    return people


def risk(code, p: Person, year):
    """Relative chance that this person is the patient for an ailment (planted patterns)."""
    a = p.age(year)
    w = 1.0
    if code == 'B54':
        w *= {'Hall C': 1.9, 'Hall G': 1.4}.get(p.hall, 1.0)
    elif code == 'A09':
        w *= {'Hall F': 1.3}.get(p.hall, 1.0)
    elif code == 'N39.0':
        w *= 3.0 if p.sex == 'F' else 0.4
    elif code == 'N94.6':
        w *= 1.0 if (p.sex == 'F' and p.category == 'Student') else 0.0
    elif code == 'I10':
        w *= (6.0 if a >= 40 else 0.15) * (1.0 if p.category == 'Staff' else 0.2)
    elif code == 'E11.9':
        w *= (7.0 if a >= 45 else 0.1) * (1.0 if p.category == 'Staff' else 0.1)
    elif code == 'T14.9':
        w *= 2.2 if p.sex == 'M' else 0.7
    elif code in ('K29.7', 'F41.9'):
        w *= 1.4 if p.category == 'Student' else 0.6
    if p.category == 'Dependant' and code in ('I10', 'E11.9', 'N94.6', 'F41.9'):
        w = 0.0
    if p.category == 'Dependant' and code in ('B54', 'J06.9', 'A09'):
        w *= 1.5
    return w


def poisson(rng, lam):
    if lam <= 0:
        return 0
    if lam > 30:  # normal approximation for speed
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def generate(out: Path, seed: int):
    rng = random.Random(seed)
    people = make_population(rng)
    by_hall = {}
    for p in people:
        by_hall.setdefault(p.hall, []).append(p)
    outbreaks = []
    for ob in OUTBREAKS:
        s = date.fromisoformat(ob['start'])
        outbreaks.append({**ob, 'start_d': s, 'end_d': s + timedelta(days=7 * ob['weeks'] - 1)})

    # pre-compute weights per ailment per year (populations are fixed)
    weights = {}
    for year in range(START.year, END.year + 1):
        for code, *_ in AILMENTS:
            weights[(code, year)] = [risk(code, p, year) for p in people]

    rows, d, cum = [], START, {}
    while d <= END:
        dow = d.weekday()
        day_factor = 1.0 if dow < 5 else (0.45 if dow == 5 else 0.3)
        trend = 1 + 0.03 * (d.year - START.year)
        student_factor = 0.35 if d.month in BREAK_MONTHS else (0.5 if (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 5) else 1.0)
        for code, name, group, base, seas in AILMENTS:
            lam = base * seas[d.month - 1] * day_factor * trend
            if code in ('K29.7', 'F41.9') and d.month in EXAM_MONTHS:
                lam *= 1.8
            # mix of student and non-student patients; students thin out in vacations
            lam_students = lam * 0.8 * student_factor
            lam_others = lam * 0.2
            n_cases = poisson(rng, lam_students + lam_others)
            if n_cases == 0:
                continue
            key = (code, d.year, student_factor)
            if key not in cum:
                w = weights[(code, d.year)]
                if student_factor < 1:
                    w = [x * (student_factor if p.category == 'Student' else 1.0) for x, p in zip(w, people)]
                cum[key] = list(accumulate(w))
            for p in rng.choices(people, cum_weights=cum[key], k=n_cases):
                rows.append(make_row(rng, p, d, code))
        # planted outbreaks
        for ob in outbreaks:
            if ob['start_d'] <= d <= ob['end_d']:
                per_day = ob['extra_per_week'] / 7 * (1.3 if dow < 5 else 0.3)
                pool = by_hall[ob['hall']] if ob['hall'] else [p for p in people if p.category != 'Dependant']
                for p in rng.sample(pool, poisson(rng, per_day)):
                    rows.append(make_row(rng, p, d, ob['code'], outbreak=ob['id']))
        d += timedelta(days=1)

    rows.sort(key=lambda r: (r['visit_date'], r['card_no']))
    clean_count = len(rows)
    rows = add_dirty_rows(rng, rows)
    out.mkdir(parents=True, exist_ok=True)
    cols = ['card_no', 'sex', 'birth_year', 'category', 'faculty', 'hall', 'visit_date', 'visit_type', 'diagnosis_codes']
    with open(out / 'uhs_encounters_synthetic.csv', 'w', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        wr.writeheader()
        wr.writerows(rows)
    truth = {
        'note': 'SYNTHETIC DATA – generated for testing; no real patients.',
        'seed': seed, 'period': [START.isoformat(), END.isoformat()],
        'clean_encounters': clean_count, 'rows_written': len(rows),
        'patients': len(people),
        'outbreaks': [{k: v for k, v in ob.items() if not k.endswith('_d')} for ob in outbreaks],
        'planted_patterns': [
            'Malaria peaks in the rainy season (June–September)',
            'Upper respiratory infection, asthma and allergic rhinitis peak in the harmattan (December–February)',
            'About 25% of malaria diagnoses are accompanied by typhoid fever ("typhomalaria")',
            'About 60% of diabetes visits also record hypertension',
            'Hypertension and diabetes are concentrated among staff aged 40+ / 45+',
            'Urinary tract infection is about 7 times more likely in females; dysmenorrhoea in female students only',
            'Hall C (x1.9) and Hall G (x1.4) have higher malaria risk',
            'Gastritis and anxiety rise in exam months (February, July)',
            'Injuries are about 3 times more common in males',
        ],
        'academic_calendar': {'exam_months': sorted(EXAM_MONTHS), 'break_months': sorted(BREAK_MONTHS)},
    }
    (out / 'ground_truth.json').write_text(json.dumps(truth, indent=2))
    print(f'{clean_count} clean encounters + dirty rows = {len(rows)} rows; {len(people)} synthetic patients -> {out}')


def make_row(rng, p, d, code, outbreak=None):
    codes = [code]
    if code == 'B54' and rng.random() < 0.25:
        codes.append('A01.0')
    if code == 'E11.9' and rng.random() < 0.6:
        codes.append('I10')
    if code == 'J06.9' and rng.random() < 0.06:
        codes.append('J45.9')
    sex = p.sex if rng.random() < 0.85 else {'M': 'Male', 'F': 'Female'}[p.sex]
    return {'card_no': p.card, 'sex': sex, 'birth_year': p.birth_year, 'category': p.category,
            'faculty': p.faculty, 'hall': p.hall, 'visit_date': d.isoformat(),
            'visit_type': 'New' if rng.random() < 0.82 else 'Follow-up',
            'diagnosis_codes': ';'.join(codes)}


def add_dirty_rows(rng, rows):
    """Adds realistic data-quality problems (about 1.5% of rows) for the cleaning step to handle."""
    out = list(rows)
    n = len(rows)
    for _ in range(int(n * 0.004)):                       # exact duplicates
        out.append(dict(rng.choice(rows)))
    for _ in range(int(n * 0.003)):                       # dates typed as DD/MM/YYYY
        r = dict(rng.choice(rows)); y, m, dd = r['visit_date'].split('-'); r['visit_date'] = f'{dd}/{m}/{y}'
        out.append(r)
    for _ in range(int(n * 0.002)):                       # missing sex
        r = dict(rng.choice(rows)); r['sex'] = ''; out.append(r)
    for _ in range(int(n * 0.002)):                       # unknown diagnosis code
        r = dict(rng.choice(rows)); r['diagnosis_codes'] = rng.choice(['XYZ', 'Z99.9', 'R50']); out.append(r)
    for _ in range(int(n * 0.001)):                       # blank diagnosis
        r = dict(rng.choice(rows)); r['diagnosis_codes'] = ''; out.append(r)
    for _ in range(int(n * 0.001)):                       # impossible dates
        r = dict(rng.choice(rows)); r['visit_date'] = rng.choice(['2031-02-30', 'not recorded', '2027-13-01']); out.append(r)
    for _ in range(int(n * 0.002)):                       # implausible birth year
        r = dict(rng.choice(rows)); r['birth_year'] = rng.choice(['1890', '2030', '']); out.append(r)
    rng.shuffle(out)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(Path(__file__).resolve().parents[1] / 'data'))
    ap.add_argument('--seed', type=int, default=2026)
    a = ap.parse_args()
    generate(Path(a.out), a.seed)
