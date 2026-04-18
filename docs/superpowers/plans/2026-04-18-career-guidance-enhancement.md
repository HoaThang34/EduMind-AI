# Career Guidance Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nâng cấp module hướng nghiệp với Score Simulator, Connected Map, Comparison page, filter nâng cấp, sparkline, multi-admission-block, và lịch sử điểm chuẩn.

**Architecture:** Data-first — migration models trước, sau đó build backend API, cuối cùng là frontend. Backend dùng Flask/SQLAlchemy/SQLite. Frontend dùng Chart.js (radar, line, sparkline) và D3.js v7 (force-directed map).

**Tech Stack:** Python/Flask, SQLAlchemy, SQLite, Jinja2, Chart.js v4 (CDN), D3.js v7 (CDN), pytest + pytest-flask (testing)

---

## File Map

| File | Action | Mô tả |
|---|---|---|
| `models.py` | Modify | Thêm `admission_block`, `entry_score` vào `UniversityMajor`; thêm model `MajorEntryScore` |
| `migrate_career.py` | Create | Script migration SQLite ALTER TABLE (chạy 1 lần) |
| `seed_entry_scores.py` | Create | Seed mock data điểm chuẩn 2023-2025 + gán admission_block |
| `routes/career.py` | Modify | Fix filter bug, thêm 4 endpoints mới |
| `templates/student_career_browse.html` | Modify | Top bar filter, chip filters, grid 2 cột, sparkline, simulator button |
| `templates/student_career_compare.html` | Create | Trang so sánh: radar overlay + versus table + line chart |
| `templates/student_career_map.html` | Create | Trang connected map D3.js |
| `templates/student_career.html` | Modify | Thêm 3 nút điều hướng |
| `templates/admin_majors.html` | Modify | Thêm fields admission_block, entry_score, lịch sử điểm |
| `tests/conftest.py` | Create | pytest fixtures: Flask test client + in-memory DB |
| `tests/test_career_api.py` | Create | Tests cho tất cả career API endpoints |

---

## Task 1: Setup pytest + test fixtures

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Cài pytest**

```bash
cd "/Users/dat_macbook/Documents/2025/ý tưởng mới/Hỗ trợ Yên Bái nhận diện khuôn mặt/EduMind-AI"
pip install pytest pytest-flask
```

- [ ] **Step 2: Tạo `tests/__init__.py`**

```python
```
(file rỗng)

- [ ] **Step 3: Tạo `tests/conftest.py`**

```python
import pytest
from app import app as flask_app
from models import db as _db, UniversityMajor, MajorSubjectWeight, MajorEntryScore, Student
import datetime


@pytest.fixture(scope='session')
def app():
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    flask_app.config['WTF_CSRF_ENABLED'] = False
    with flask_app.app_context():
        _db.create_all()
        _seed_test_data()
        yield flask_app
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def student_session(client, app):
    with app.app_context():
        s = Student.query.filter_by(username='test_student').first()
        with client.session_transaction() as sess:
            sess['student_id'] = s.id
    return client


def _seed_test_data():
    from werkzeug.security import generate_password_hash
    student = Student(
        username='test_student',
        password=generate_password_hash('password'),
        full_name='Học Sinh Test',
        class_id=None,
        student_code='TS001',
    )
    _db.session.add(student)
    _db.session.flush()

    major = UniversityMajor(
        name='Trí tuệ nhân tạo', university='HUST',
        faculty='Công nghệ thông tin', major_group='Kỹ thuật',
        admission_block='A1', entry_score=28.5,
        created_at=datetime.datetime.utcnow()
    )
    _db.session.add(major)
    _db.session.flush()

    for subj, w, ms in [('Toán', 0.4, 8.5), ('Lý', 0.35, 7.5), ('Hóa', 0.25, 7.0)]:
        _db.session.add(MajorSubjectWeight(
            major_id=major.id, subject_name=subj, weight=w, min_score=ms))

    for year, score in [(2023, 27.0), (2024, 28.0), (2025, 28.5)]:
        _db.session.add(MajorEntryScore(major_id=major.id, year=year, score=score))

    _db.session.commit()
```

- [ ] **Step 4: Verify fixtures load (tests sẽ fail vì model chưa có fields mới — đó là đúng)**

```bash
pytest tests/ -v 2>&1 | head -30
```

Expected: ImportError hoặc lỗi model — bình thường, sẽ fix ở Task 2.

---

## Task 2: Cập nhật models + migration script

**Files:**
- Modify: `models.py`
- Create: `migrate_career.py`
- Create: `seed_entry_scores.py`

- [ ] **Step 1: Thêm fields vào `UniversityMajor` trong `models.py`**

Tìm class `UniversityMajor` (khoảng dòng bắt đầu với `class UniversityMajor`). Thay đổi:

```python
class UniversityMajor(db.Model):
    __tablename__ = 'university_major'
    __table_args__ = (
        db.UniqueConstraint('name', 'university', 'admission_block', name='uq_major_university_block'),
    )
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    university = db.Column(db.String(150), nullable=False)
    faculty = db.Column(db.String(150))
    major_group = db.Column(db.String(50))
    admission_block = db.Column(db.String(20))   # A1, B00, D01, ...
    entry_score = db.Column(db.Float)             # điểm chuẩn năm hiện tại
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    weights = db.relationship('MajorSubjectWeight', backref='major',
                               cascade='all, delete-orphan', lazy=True)
    pinned_by = db.relationship('StudentPinnedMajor', backref='major',
                                 cascade='all, delete-orphan', lazy=True)
    targeted_by = db.relationship('StudentTargetMajor', backref='major',
                                   cascade='all, delete-orphan', lazy=True)
    entry_scores = db.relationship('MajorEntryScore', backref='major',
                                    cascade='all, delete-orphan', lazy=True)
```

- [ ] **Step 2: Thêm model `MajorEntryScore` vào `models.py`**

Thêm sau class `StudentTargetMajor`:

```python
class MajorEntryScore(db.Model):
    __tablename__ = 'major_entry_score'
    __table_args__ = (db.UniqueConstraint('major_id', 'year', name='uq_major_year'),)
    id = db.Column(db.Integer, primary_key=True)
    major_id = db.Column(db.Integer, db.ForeignKey('university_major.id'), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float, nullable=False)
```

- [ ] **Step 3: Tạo `migrate_career.py`**

```python
"""Migration script: thêm admission_block, entry_score vào university_major;
tạo bảng major_entry_score. Chạy 1 lần trên DB hiện có."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database.db')


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Kiểm tra column đã tồn tại chưa
    cur.execute("PRAGMA table_info(university_major)")
    cols = [row[1] for row in cur.fetchall()]

    if 'admission_block' not in cols:
        cur.execute("ALTER TABLE university_major ADD COLUMN admission_block TEXT")
        print("Added admission_block")

    if 'entry_score' not in cols:
        cur.execute("ALTER TABLE university_major ADD COLUMN entry_score REAL")
        print("Added entry_score")

    # Tạo bảng major_entry_score nếu chưa có
    cur.execute("""
        CREATE TABLE IF NOT EXISTS major_entry_score (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            major_id INTEGER NOT NULL REFERENCES university_major(id) ON DELETE CASCADE,
            year INTEGER NOT NULL,
            score REAL NOT NULL,
            UNIQUE(major_id, year)
        )
    """)
    print("Created major_entry_score table")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    migrate()
```

- [ ] **Step 4: Tạo `seed_entry_scores.py`**

```python
"""Seed admission_block và điểm chuẩn lịch sử 2023-2024-2025 cho tất cả majors."""
import sys
import os
import random

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

from app import app
from models import db, UniversityMajor, MajorEntryScore

# Mapping tên ngành → khối xét tuyển phổ biến nhất
BLOCK_MAP = {
    'Kỹ thuật': 'A1',
    'Công nghệ': 'A1',
    'Kinh tế': 'A1',
    'Y dược': 'B00',
    'Xã hội': 'D01',
    'Nghệ thuật': 'C00',
}
DEFAULT_BLOCK = 'A1'
DEFAULT_SCORE_2025 = 22.0


def seed():
    with app.app_context():
        majors = UniversityMajor.query.all()
        count = 0
        for major in majors:
            # Gán admission_block nếu chưa có
            if not major.admission_block:
                major.admission_block = BLOCK_MAP.get(major.major_group, DEFAULT_BLOCK)

            # Gán entry_score 2025 nếu chưa có
            base = major.entry_score or DEFAULT_SCORE_2025
            if not major.entry_score:
                major.entry_score = round(base + random.uniform(-2, 3), 1)
                base = major.entry_score

            # Seed lịch sử 2023, 2024 nếu chưa có
            for year, delta in [(2023, -1.5), (2024, -0.75)]:
                exists = MajorEntryScore.query.filter_by(
                    major_id=major.id, year=year).first()
                if not exists:
                    db.session.add(MajorEntryScore(
                        major_id=major.id,
                        year=year,
                        score=round(base + delta + random.uniform(-0.5, 0.5), 1)
                    ))

            # Seed 2025 nếu chưa có
            exists_2025 = MajorEntryScore.query.filter_by(
                major_id=major.id, year=2025).first()
            if not exists_2025:
                db.session.add(MajorEntryScore(
                    major_id=major.id, year=2025, score=base))

            count += 1

        db.session.commit()
        print(f"Seeded {count} majors with admission_block + entry scores.")


if __name__ == '__main__':
    seed()
```

- [ ] **Step 5: Chạy migration + seed**

```bash
cd "/Users/dat_macbook/Documents/2025/ý tưởng mới/Hỗ trợ Yên Bái nhận diện khuôn mặt/EduMind-AI"
python migrate_career.py
python seed_entry_scores.py
```

Expected:
```
Added admission_block
Added entry_score
Created major_entry_score table
Migration complete.
Seeded N majors with admission_block + entry scores.
```

- [ ] **Step 6: Verify tests load**

```bash
pytest tests/conftest.py -v
```

Expected: no import errors, fixtures created.

- [ ] **Step 7: Commit**

```bash
git add models.py migrate_career.py seed_entry_scores.py tests/__init__.py tests/conftest.py
git commit -m "feat: add admission_block, entry_score, MajorEntryScore model + migration"
```

---

## Task 3: Backend API — fix filter + 4 endpoints mới

**Files:**
- Modify: `routes/career.py`
- Create: `tests/test_career_api.py`

- [ ] **Step 1: Viết failing tests**

Tạo `tests/test_career_api.py`:

```python
import json
import pytest


class TestBrowseFilter:
    def test_search_by_name(self, student_session):
        r = student_session.get('/api/student/career/browse?q=trí+tuệ')
        data = r.get_json()
        assert r.status_code == 200
        assert any('Trí tuệ nhân tạo' in m['name'] for m in data['majors'])

    def test_search_by_university(self, student_session):
        r = student_session.get('/api/student/career/browse?q=HUST')
        data = r.get_json()
        assert r.status_code == 200
        assert all('HUST' in m['university'] for m in data['majors'])

    def test_filter_by_admission_block(self, student_session):
        r = student_session.get('/api/student/career/browse?admission_block=A1')
        data = r.get_json()
        assert r.status_code == 200
        assert all(m['admission_block'] == 'A1' for m in data['majors'])

    def test_filter_by_university_param(self, student_session):
        r = student_session.get('/api/student/career/browse?university=HUST')
        data = r.get_json()
        assert r.status_code == 200
        assert all(m['university'] == 'HUST' for m in data['majors'])


class TestSimulate:
    def test_simulate_returns_fit_scores(self, student_session):
        payload = {'scores': {'Toán': 9.0, 'Lý': 8.0, 'Hóa': 7.5}}
        r = student_session.post('/api/student/career/simulate',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        data = r.get_json()
        assert r.status_code == 200
        assert 'majors' in data
        assert len(data['majors']) > 0
        assert 'fit_pct' in data['majors'][0]

    def test_simulate_sorted_by_fit(self, student_session):
        payload = {'scores': {'Toán': 9.0, 'Lý': 8.0, 'Hóa': 7.5}}
        r = student_session.post('/api/student/career/simulate',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        data = r.get_json()
        fits = [m['fit_pct'] for m in data['majors']]
        assert fits == sorted(fits, reverse=True)


class TestCompare:
    def test_compare_returns_radar_and_scores(self, student_session, app):
        with app.app_context():
            from models import UniversityMajor
            major = UniversityMajor.query.first()
            mid = major.id
        r = student_session.get(f'/api/student/career/compare?major_ids={mid}')
        data = r.get_json()
        assert r.status_code == 200
        assert 'majors' in data
        m = data['majors'][0]
        assert 'radar' in m
        assert 'entry_scores' in m
        assert 'fit_pct' in m

    def test_compare_rejects_more_than_4(self, student_session):
        r = student_session.get('/api/student/career/compare?major_ids=1,2,3,4,5')
        assert r.status_code == 400


class TestScoreHistory:
    def test_score_history_returns_3_years(self, student_session, app):
        with app.app_context():
            from models import UniversityMajor
            major = UniversityMajor.query.first()
            mid = major.id
        r = student_session.get(f'/api/student/career/score-history?major_ids={mid}')
        data = r.get_json()
        assert r.status_code == 200
        assert str(mid) in data or mid in data
        scores = list(data.values())[0]
        assert len(scores) == 3
        years = [s['year'] for s in scores]
        assert 2023 in years and 2025 in years


class TestMapData:
    def test_map_data_returns_weight_vectors(self, student_session):
        r = student_session.get('/api/student/career/map-data')
        data = r.get_json()
        assert r.status_code == 200
        assert 'majors' in data
        assert len(data['majors']) > 0
        m = data['majors'][0]
        assert 'weight_vector' in m
        assert 'entry_score' in m
```

- [ ] **Step 2: Chạy để confirm fail**

```bash
pytest tests/test_career_api.py -v 2>&1 | head -40
```

Expected: FAILED — endpoints chưa tồn tại hoặc thiếu params.

- [ ] **Step 3: Cập nhật `routes/career.py` — fix browse + thêm endpoints**

Thay thế hàm `api_browse` và thêm 4 endpoints mới. Mở `routes/career.py` và áp dụng các thay đổi sau:

**3a. Fix `api_browse`** — thay toàn bộ hàm:

```python
@career_bp.route('/api/student/career/browse')
def api_browse():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    sem, yr = _cfg()
    averages = calculate_subject_averages(student.id, sem, yr)

    group = request.args.get('group', '')
    min_fit = request.args.get('min_fit', 0, type=float)
    q = request.args.get('q', '').strip()
    university = request.args.get('university', '').strip()
    admission_block = request.args.get('admission_block', '').strip()

    from sqlalchemy import or_
    query = UniversityMajor.query
    if q:
        query = query.filter(or_(
            UniversityMajor.name.ilike(f'%{q}%'),
            UniversityMajor.university.ilike(f'%{q}%')
        ))
    if university:
        query = query.filter(UniversityMajor.university == university)
    if admission_block:
        query = query.filter(UniversityMajor.admission_block == admission_block)
    if group:
        query = query.filter(UniversityMajor.major_group == group)
    majors = query.all()

    pinned_ids = {p.major_id for p in StudentPinnedMajor.query.filter_by(student_id=student.id)}
    target = StudentTargetMajor.query.filter_by(student_id=student.id).first()
    target_id = target.major_id if target else None

    results = []
    for major in majors:
        wlist = _weights_list(major)
        if not wlist:
            continue
        fit = calculate_fit_score(averages, wlist)
        if fit['fit_pct'] < min_fit:
            continue
        labels, stu_scores, maj_scores, _ = _radar(major.id, averages)
        entry_scores_sorted = sorted(
            [{'year': es.year, 'score': es.score} for es in major.entry_scores],
            key=lambda x: x['year']
        )
        results.append({
            'id': major.id, 'name': major.name, 'university': major.university,
            'faculty': major.faculty, 'major_group': major.major_group,
            'admission_block': major.admission_block,
            'entry_score': major.entry_score,
            'fit_pct': fit['fit_pct'],
            'is_pinned': major.id in pinned_ids,
            'is_target': major.id == target_id,
            'radar': {'labels': labels, 'student_scores': stu_scores, 'major_scores': maj_scores},
            'entry_scores': entry_scores_sorted,
        })
    results.sort(key=lambda x: x['fit_pct'], reverse=True)
    return jsonify({'majors': results})
```

**3b. Thêm endpoint `/api/student/career/simulate`** — thêm sau `api_browse`:

```python
@career_bp.route('/api/student/career/simulate', methods=['POST'])
def api_simulate():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    scores = request.json.get('scores', {})
    if not scores:
        return jsonify({'error': 'scores required'}), 400

    majors = UniversityMajor.query.all()
    results = []
    for major in majors:
        wlist = _weights_list(major)
        if not wlist:
            continue
        fit = calculate_fit_score(scores, wlist)
        results.append({
            'id': major.id, 'name': major.name, 'university': major.university,
            'admission_block': major.admission_block,
            'entry_score': major.entry_score,
            'fit_pct': fit['fit_pct'],
            'gaps': fit['gaps'],
        })
    results.sort(key=lambda x: x['fit_pct'], reverse=True)
    return jsonify({'majors': results})
```

**3c. Thêm endpoint `/api/student/career/compare`**:

```python
@career_bp.route('/api/student/career/compare')
def api_compare():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    raw = request.args.get('major_ids', '')
    try:
        ids = [int(x) for x in raw.split(',') if x.strip()]
    except ValueError:
        return jsonify({'error': 'invalid major_ids'}), 400
    if len(ids) > 4:
        return jsonify({'error': 'max 4 majors'}), 400

    sem, yr = _cfg()
    averages = calculate_subject_averages(student.id, sem, yr)

    results = []
    for mid in ids:
        major = UniversityMajor.query.get(mid)
        if not major:
            continue
        wlist = _weights_list(major)
        fit = calculate_fit_score(averages, wlist)
        labels, stu_scores, maj_scores, _ = _radar(mid, averages)
        entry_scores_sorted = sorted(
            [{'year': es.year, 'score': es.score} for es in major.entry_scores],
            key=lambda x: x['year']
        )
        results.append({
            'id': major.id, 'name': major.name, 'university': major.university,
            'faculty': major.faculty, 'major_group': major.major_group,
            'admission_block': major.admission_block,
            'entry_score': major.entry_score,
            'fit_pct': fit['fit_pct'],
            'gaps': fit['gaps'],
            'weights': wlist,
            'radar': {'labels': labels, 'student_scores': stu_scores, 'major_scores': maj_scores},
            'entry_scores': entry_scores_sorted,
        })
    return jsonify({'majors': results, 'student_scores': averages})
```

**3d. Thêm endpoint `/api/student/career/score-history`**:

```python
@career_bp.route('/api/student/career/score-history')
def api_score_history():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    raw = request.args.get('major_ids', '')
    try:
        ids = [int(x) for x in raw.split(',') if x.strip()]
    except ValueError:
        return jsonify({'error': 'invalid major_ids'}), 400

    from models import MajorEntryScore
    result = {}
    for mid in ids:
        scores = MajorEntryScore.query.filter_by(major_id=mid).order_by(MajorEntryScore.year).all()
        result[mid] = [{'year': s.year, 'score': s.score} for s in scores]
    return jsonify(result)
```

**3e. Thêm endpoint `/api/student/career/map-data`**:

```python
@career_bp.route('/api/student/career/map-data')
def api_map_data():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    sem, yr = _cfg()
    averages = calculate_subject_averages(student.id, sem, yr)

    majors = UniversityMajor.query.all()
    result = []
    for major in majors:
        wlist = _weights_list(major)
        if not wlist:
            continue
        weight_vector = {w['subject_name']: w['weight'] for w in wlist}
        fit = calculate_fit_score(averages, wlist)
        result.append({
            'id': major.id, 'name': major.name, 'university': major.university,
            'major_group': major.major_group,
            'admission_block': major.admission_block,
            'entry_score': major.entry_score or 20.0,
            'fit_pct': fit['fit_pct'],
            'weight_vector': weight_vector,
        })
    return jsonify({'majors': result})
```

Cũng thêm import `MajorEntryScore` vào đầu `routes/career.py`:

```python
from models import db, Student, UniversityMajor, MajorSubjectWeight, StudentPinnedMajor, StudentTargetMajor, SystemConfig, MajorEntryScore
```

- [ ] **Step 4: Chạy tests**

```bash
pytest tests/test_career_api.py -v
```

Expected: tất cả PASS.

- [ ] **Step 5: Commit**

```bash
git add routes/career.py tests/test_career_api.py
git commit -m "feat: fix browse filter + add simulate/compare/score-history/map-data APIs"
```

---

## Task 4: Browse page UI — top bar filter + sparkline + simulator button

**Files:**
- Modify: `templates/student_career_browse.html`

- [ ] **Step 1: Đọc file hiện tại**

```bash
cat templates/student_career_browse.html
```

- [ ] **Step 2: Thay toàn bộ nội dung `student_career_browse.html`**

Thay thế file với template sau (giữ nguyên `{% extends 'base.html' %}` và block structure hiện có, chỉ thay phần `{% block content %}`):

```html
{% extends 'base.html' %}
{% block content %}
<div class="container-fluid py-4" id="browse-app">

  <!-- TOP FILTER BAR -->
  <div class="card mb-3 shadow-sm">
    <div class="card-body py-2">
      <div class="d-flex flex-wrap gap-2 align-items-center">
        <input type="text" id="search-input" class="form-control form-control-sm" style="max-width:220px"
               placeholder="🔍 Tìm ngành hoặc trường...">
        <select id="filter-university" class="form-select form-select-sm" style="max-width:160px">
          <option value="">Tất cả trường</option>
        </select>
        <select id="filter-block" class="form-select form-select-sm" style="max-width:130px">
          <option value="">Tất cả khối</option>
          <option>A1</option><option>A00</option><option>B00</option>
          <option>D01</option><option>C00</option>
        </select>
        <select id="filter-group" class="form-select form-select-sm" style="max-width:140px">
          <option value="">Tất cả nhóm ngành</option>
          {% for g in groups %}<option>{{ g }}</option>{% endfor %}
        </select>
        <div class="d-flex align-items-center gap-1">
          <label class="small text-muted mb-0">Phù hợp ≥</label>
          <input type="range" id="filter-fit" min="0" max="100" value="0" style="width:80px">
          <span id="filter-fit-label" class="small fw-bold text-success">0%</span>
        </div>
      </div>
      <!-- Sort pills -->
      <div class="d-flex gap-2 mt-2 flex-wrap align-items-center">
        <span class="text-muted small">Sắp xếp:</span>
        <span class="badge sort-pill active" data-sort="fit">Phù hợp nhất</span>
        <span class="badge sort-pill" data-sort="score_desc">ĐC cao → thấp</span>
        <span class="badge sort-pill" data-sort="score_asc">ĐC thấp → cao</span>
        <span class="badge sort-pill" data-sort="name">Tên A-Z</span>
        <!-- Active filter chips -->
        <div id="active-chips" class="d-flex gap-1 flex-wrap ms-2"></div>
      </div>
    </div>
  </div>

  <!-- RESULTS INFO + SIMULATOR BUTTON -->
  <div class="d-flex justify-content-between align-items-center mb-3">
    <span id="result-count" class="text-muted small">Đang tải...</span>
    <div class="d-flex gap-2">
      <button class="btn btn-sm btn-outline-warning" onclick="openSimulator()">
        🎯 Mô phỏng điểm
      </button>
      <button class="btn btn-sm btn-primary d-none" id="compare-btn" onclick="goCompare()">
        So sánh (<span id="compare-count">0</span>)
      </button>
    </div>
  </div>

  <!-- MAJORS GRID -->
  <div class="row g-3" id="majors-grid"></div>
</div>

<!-- SCORE SIMULATOR MODAL -->
<div class="modal fade" id="simulatorModal" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">🎯 Nếu điểm của bạn là...</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <p class="text-muted small">Điều chỉnh điểm dự kiến — danh sách ngành sẽ cập nhật ngay</p>
        <div id="simulator-sliders" class="row g-2"></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline-secondary btn-sm" onclick="resetSimulator()">
          Reset về điểm thật
        </button>
        <button class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Đóng</button>
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script>
// State
let allMajors = [];
let simScores = {};
let realScores = {};
let compareIds = new Set(JSON.parse(sessionStorage.getItem('compare_major_ids') || '[]'));
let currentSort = 'fit';
let simTimer = null;
let sparklineCharts = {};

// Filter state
function getFilters() {
  return {
    q: document.getElementById('search-input').value.trim(),
    university: document.getElementById('filter-university').value,
    admission_block: document.getElementById('filter-block').value,
    group: document.getElementById('filter-group').value,
    min_fit: parseInt(document.getElementById('filter-fit').value),
  };
}

// Load majors
async function loadMajors() {
  const f = getFilters();
  const params = new URLSearchParams();
  if (f.q) params.set('q', f.q);
  if (f.university) params.set('university', f.university);
  if (f.admission_block) params.set('admission_block', f.admission_block);
  if (f.group) params.set('group', f.group);
  if (f.min_fit > 0) params.set('min_fit', f.min_fit);

  const r = await fetch('/api/student/career/browse?' + params);
  const data = await r.json();
  allMajors = data.majors;
  renderGrid();
  updateChips(f);
}

function renderGrid() {
  const sorted = [...allMajors].sort((a, b) => {
    if (currentSort === 'fit') return b.fit_pct - a.fit_pct;
    if (currentSort === 'score_desc') return (b.entry_score||0) - (a.entry_score||0);
    if (currentSort === 'score_asc') return (a.entry_score||0) - (b.entry_score||0);
    return a.name.localeCompare(b.name);
  });

  const grid = document.getElementById('majors-grid');
  grid.innerHTML = '';
  document.getElementById('result-count').textContent = `${sorted.length} ngành`;

  sorted.forEach(m => {
    const fitColor = m.fit_pct >= 70 ? 'success' : m.fit_pct >= 50 ? 'warning' : 'danger';
    const checked = compareIds.has(m.id) ? 'checked' : '';
    const trend = getTrend(m.entry_scores);
    const col = document.createElement('div');
    col.className = 'col-md-6 col-lg-4';
    col.innerHTML = `
      <div class="card h-100 shadow-sm major-card" data-id="${m.id}">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-start">
            <div>
              <h6 class="mb-0 fw-bold">${m.name}</h6>
              <small class="text-muted">${m.university}</small><br>
              <small class="text-secondary">${m.admission_block || ''} | ĐC: ${m.entry_score || '—'}</small>
            </div>
            <input type="checkbox" class="form-check-input compare-chk ms-2" ${checked}
                   onchange="toggleCompare(${m.id}, this.checked)">
          </div>
          <div class="mt-2 d-flex align-items-center gap-2">
            <div class="progress flex-grow-1" style="height:6px">
              <div class="progress-bar bg-${fitColor}" style="width:${m.fit_pct}%"></div>
            </div>
            <span class="fw-bold text-${fitColor} small">${Math.round(m.fit_pct)}%</span>
          </div>
          <div class="d-flex justify-content-between align-items-center mt-2">
            <small class="text-muted">Xu hướng ĐC:</small>
            <div style="width:80px;height:30px">
              <canvas id="spark-${m.id}" width="80" height="30"></canvas>
            </div>
            <small class="text-${trend.color} fw-bold">${trend.label}</small>
          </div>
        </div>
      </div>`;
    grid.appendChild(col);
    renderSparkline(m.id, m.entry_scores);
  });
}

function getTrend(scores) {
  if (!scores || scores.length < 2) return { label: '—', color: 'secondary' };
  const first = scores[0].score, last = scores[scores.length - 1].score;
  const diff = (last - first).toFixed(1);
  if (diff > 0) return { label: `↑ +${diff}`, color: 'danger' };
  if (diff < 0) return { label: `↓ ${diff}`, color: 'success' };
  return { label: '→ 0', color: 'secondary' };
}

function renderSparkline(majorId, scores) {
  const canvas = document.getElementById(`spark-${majorId}`);
  if (!canvas || !scores || scores.length === 0) return;
  if (sparklineCharts[majorId]) { sparklineCharts[majorId].destroy(); }
  sparklineCharts[majorId] = new Chart(canvas, {
    type: 'line',
    data: {
      labels: scores.map(s => s.year),
      datasets: [{ data: scores.map(s => s.score), borderColor: '#3b82f6',
                   borderWidth: 1.5, pointRadius: 2, fill: false, tension: 0.3 }]
    },
    options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } },
               animation: false, responsive: false }
  });
}

// Compare
function toggleCompare(id, checked) {
  if (checked) {
    if (compareIds.size >= 4) { alert('Tối đa 4 ngành'); return; }
    compareIds.add(id);
  } else {
    compareIds.delete(id);
  }
  sessionStorage.setItem('compare_major_ids', JSON.stringify([...compareIds]));
  const btn = document.getElementById('compare-btn');
  document.getElementById('compare-count').textContent = compareIds.size;
  btn.classList.toggle('d-none', compareIds.size < 2);
}

function goCompare() {
  window.location.href = '/student/career/compare?major_ids=' + [...compareIds].join(',');
}

// Simulator
function openSimulator() {
  loadSimulatorSliders();
  new bootstrap.Modal(document.getElementById('simulatorModal')).show();
}

async function loadSimulatorSliders() {
  const r = await fetch('/api/student/career/map-data');
  const data = await r.json();
  const subjects = new Set();
  data.majors.forEach(m => Object.keys(m.weight_vector).forEach(s => subjects.add(s)));

  const container = document.getElementById('simulator-sliders');
  container.innerHTML = '';
  subjects.forEach(subj => {
    const current = realScores[subj] || 5.0;
    const div = document.createElement('div');
    div.className = 'col-md-4';
    div.innerHTML = `
      <label class="small fw-bold">${subj}</label>
      <div class="d-flex align-items-center gap-2">
        <input type="range" class="form-range sim-slider" min="0" max="10" step="0.1"
               value="${current}" data-subj="${subj}"
               oninput="onSimSlider(this)">
        <span class="small sim-val" id="val-${subj.replace(/\s/g,'_')}">${current}</span>
      </div>`;
    container.appendChild(div);
    simScores[subj] = current;
  });
}

function onSimSlider(el) {
  const subj = el.dataset.subj;
  simScores[subj] = parseFloat(el.value);
  document.getElementById('val-' + subj.replace(/\s/g, '_')).textContent = el.value;
  clearTimeout(simTimer);
  simTimer = setTimeout(runSimulate, 300);
}

async function runSimulate() {
  const r = await fetch('/api/student/career/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scores: simScores })
  });
  const data = await r.json();
  // Cập nhật fit_pct trong allMajors
  const fitMap = {};
  data.majors.forEach(m => { fitMap[m.id] = m.fit_pct; });
  allMajors.forEach(m => { if (fitMap[m.id] !== undefined) m.fit_pct = fitMap[m.id]; });
  renderGrid();
}

function resetSimulator() {
  simScores = { ...realScores };
  document.querySelectorAll('.sim-slider').forEach(el => {
    const subj = el.dataset.subj;
    el.value = realScores[subj] || 5.0;
    document.getElementById('val-' + subj.replace(/\s/g, '_')).textContent = el.value;
  });
  runSimulate();
}

// Chips
function updateChips(f) {
  const container = document.getElementById('active-chips');
  container.innerHTML = '';
  const add = (label, clearFn) => {
    const chip = document.createElement('span');
    chip.className = 'badge bg-primary';
    chip.style.cursor = 'pointer';
    chip.textContent = label + ' ×';
    chip.onclick = clearFn;
    container.appendChild(chip);
  };
  if (f.q) add(`"${f.q}"`, () => { document.getElementById('search-input').value=''; loadMajors(); });
  if (f.university) add(f.university, () => { document.getElementById('filter-university').value=''; loadMajors(); });
  if (f.admission_block) add(`Khối: ${f.admission_block}`, () => { document.getElementById('filter-block').value=''; loadMajors(); });
  if (f.group) add(f.group, () => { document.getElementById('filter-group').value=''; loadMajors(); });
  if (f.min_fit > 0) add(`≥${f.min_fit}%`, () => { document.getElementById('filter-fit').value=0; document.getElementById('filter-fit-label').textContent='0%'; loadMajors(); });
}

// Populate university dropdown
async function populateUniversities() {
  const r = await fetch('/api/student/career/browse');
  const data = await r.json();
  const unis = [...new Set(data.majors.map(m => m.university))].sort();
  const sel = document.getElementById('filter-university');
  unis.forEach(u => sel.add(new Option(u, u)));
}

// Event listeners
let searchTimer;
document.getElementById('search-input').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadMajors, 400);
});
['filter-university','filter-block','filter-group'].forEach(id => {
  document.getElementById(id).addEventListener('change', loadMajors);
});
document.getElementById('filter-fit').addEventListener('input', function() {
  document.getElementById('filter-fit-label').textContent = this.value + '%';
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadMajors, 400);
});
document.querySelectorAll('.sort-pill').forEach(pill => {
  pill.addEventListener('click', function() {
    document.querySelectorAll('.sort-pill').forEach(p => p.classList.remove('active'));
    this.classList.add('active');
    currentSort = this.dataset.sort;
    renderGrid();
  });
});

// Init
populateUniversities();
loadMajors();
</script>
{% endblock %}
```

- [ ] **Step 3: Kiểm tra trong browser**

```bash
cd "/Users/dat_macbook/Documents/2025/ý tưởng mới/Hỗ trợ Yên Bái nhận diện khuôn mặt/EduMind-AI"
python app.py
```

Mở `http://localhost:5000/student/career/browse`, đăng nhập học sinh, kiểm tra:
- [ ] Search theo tên ngành hoạt động
- [ ] Dropdown lọc theo trường hoạt động
- [ ] Sort pills hoạt động
- [ ] Sparkline hiện trong cards
- [ ] Nút "Mô phỏng điểm" mở modal
- [ ] Sliders trong modal cập nhật fit% realtime
- [ ] Checkbox chọn ≥2 ngành → nút "So sánh" xuất hiện

- [ ] **Step 4: Commit**

```bash
git add templates/student_career_browse.html
git commit -m "feat: browse page top bar filter, sparkline, score simulator modal"
```

---

## Task 5: Comparison page

**Files:**
- Create: `templates/student_career_compare.html`
- Modify: `routes/career.py` (thêm route `/student/career/compare`)

- [ ] **Step 1: Thêm route vào `routes/career.py`**

Thêm sau `career_browse`:

```python
@career_bp.route('/student/career/compare')
def career_compare():
    student = _student()
    if not student:
        return redirect(url_for('student.student_login'))
    major_ids = request.args.get('major_ids', '')
    return render_template('student_career_compare.html',
                           student=student, major_ids=major_ids)
```

- [ ] **Step 2: Tạo `templates/student_career_compare.html`**

```html
{% extends 'base.html' %}
{% block content %}
<div class="container-fluid py-4" id="compare-app">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h4 class="mb-0">So sánh ngành</h4>
    <a href="/student/career/browse" class="btn btn-sm btn-outline-secondary">← Quay lại</a>
  </div>

  <!-- MAJOR SELECTOR -->
  <div class="card mb-3 shadow-sm">
    <div class="card-body">
      <div class="d-flex flex-wrap gap-2 align-items-center" id="selected-majors">
        <!-- chips filled by JS -->
      </div>
      <div class="mt-2 d-flex gap-2">
        <input type="text" id="add-search" class="form-control form-control-sm" style="max-width:250px"
               placeholder="+ Thêm ngành (gõ để tìm)...">
        <div id="add-dropdown" class="dropdown-menu show d-none"
             style="position:absolute;max-height:200px;overflow-y:auto;z-index:1000"></div>
      </div>
    </div>
  </div>

  <!-- RADAR OVERLAY -->
  <div class="card mb-3 shadow-sm">
    <div class="card-header fw-bold">Radar so sánh môn học</div>
    <div class="card-body d-flex justify-content-center">
      <canvas id="radar-chart" width="500" height="400"></canvas>
    </div>
  </div>

  <!-- LINE CHART: lịch sử điểm chuẩn -->
  <div class="card mb-3 shadow-sm">
    <div class="card-header fw-bold">Xu hướng điểm chuẩn (2023–2025)</div>
    <div class="card-body">
      <canvas id="line-chart" height="120"></canvas>
    </div>
  </div>

  <!-- VERSUS TABLE -->
  <div class="card shadow-sm">
    <div class="card-header fw-bold">So sánh chi tiết</div>
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-bordered table-hover mb-0" id="versus-table">
          <thead id="versus-thead"></thead>
          <tbody id="versus-tbody"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script>
const COLORS = ['#3b82f6','#f59e0b','#10b981','#a78bfa'];
let compareIds = new Set(JSON.parse(sessionStorage.getItem('compare_major_ids') || '[]'));
let currentData = null;
let radarChart = null, lineChart = null;
let allMajorsCache = null;

// Init from URL
const urlIds = new URLSearchParams(location.search).get('major_ids') || '';
if (urlIds) {
  urlIds.split(',').filter(Boolean).forEach(id => compareIds.add(parseInt(id)));
  sessionStorage.setItem('compare_major_ids', JSON.stringify([...compareIds]));
}

async function loadAndRender() {
  if (compareIds.size === 0) { clearCharts(); return; }
  const r = await fetch('/api/student/career/compare?major_ids=' + [...compareIds].join(','));
  currentData = await r.json();
  renderSelectedChips();
  renderRadar(currentData);
  renderLineChart(currentData);
  renderVersusTable(currentData);
}

function renderSelectedChips() {
  const container = document.getElementById('selected-majors');
  container.innerHTML = '';
  if (!currentData) return;
  currentData.majors.forEach((m, i) => {
    const chip = document.createElement('span');
    chip.className = 'badge d-flex align-items-center gap-1';
    chip.style.cssText = `background:${COLORS[i]};font-size:0.85rem;padding:6px 10px`;
    chip.innerHTML = `${m.name} — ${m.university}
      <button class="btn-close btn-close-white btn-sm ms-1" style="font-size:0.6rem"
              onclick="removeMajor(${m.id})"></button>`;
    container.appendChild(chip);
  });
}

function removeMajor(id) {
  compareIds.delete(id);
  sessionStorage.setItem('compare_major_ids', JSON.stringify([...compareIds]));
  loadAndRender();
}

function renderRadar(data) {
  if (radarChart) radarChart.destroy();
  if (!data.majors.length) return;
  const allLabels = [...new Set(data.majors.flatMap(m => m.radar.labels))];
  const datasets = data.majors.map((m, i) => ({
    label: `${m.name} (${m.university})`,
    data: allLabels.map(l => {
      const idx = m.radar.labels.indexOf(l);
      return idx >= 0 ? m.radar.major_scores[idx] : 0;
    }),
    borderColor: COLORS[i], backgroundColor: COLORS[i] + '33', borderWidth: 2
  }));
  // Student dataset
  if (data.majors[0] && data.student_scores) {
    datasets.push({
      label: 'Điểm của bạn',
      data: allLabels.map(l => data.student_scores[l] || 0),
      borderColor: '#ffffff', backgroundColor: '#ffffff22',
      borderWidth: 2, borderDash: [5,3]
    });
  }
  radarChart = new Chart(document.getElementById('radar-chart'), {
    type: 'radar',
    data: { labels: allLabels, datasets },
    options: { scales: { r: { min: 0, max: 10, ticks: { stepSize: 2 } } },
               plugins: { legend: { position: 'bottom' } } }
  });
}

function renderLineChart(data) {
  if (lineChart) lineChart.destroy();
  const datasets = data.majors.map((m, i) => ({
    label: `${m.name}`,
    data: m.entry_scores.map(s => ({ x: s.year, y: s.score })),
    borderColor: COLORS[i], backgroundColor: COLORS[i] + '22',
    borderWidth: 2, pointRadius: 4, tension: 0.3
  }));
  // Student score line (horizontal)
  if (data.student_scores) {
    const totalScore = Object.values(data.student_scores).reduce((a,b) => a+b, 0);
    const avg = Object.keys(data.student_scores).length > 0
      ? totalScore / Object.keys(data.student_scores).length * 3 : null;
    // Chỉ vẽ nếu có điểm
  }
  lineChart = new Chart(document.getElementById('line-chart'), {
    type: 'line',
    data: { datasets },
    options: {
      scales: {
        x: { type: 'linear', min: 2022, max: 2026, ticks: { stepSize: 1,
              callback: v => Number.isInteger(v) ? v : '' } },
        y: { min: 15, title: { display: true, text: 'Điểm chuẩn' } }
      },
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

function renderVersusTable(data) {
  const thead = document.getElementById('versus-thead');
  const tbody = document.getElementById('versus-tbody');
  thead.innerHTML = '';
  tbody.innerHTML = '';
  if (!data.majors.length) return;

  // Header
  const headerRow = document.createElement('tr');
  headerRow.innerHTML = '<th style="width:160px">Tiêu chí</th>';
  data.majors.forEach((m, i) => {
    headerRow.innerHTML += `<th style="color:${COLORS[i]}">${m.name}<br><small>${m.university}</small></th>`;
  });
  thead.appendChild(headerRow);

  // Rows
  const rows = [
    { label: '% Phù hợp', fn: m => `<strong class="${m.fit_pct>=70?'text-success':m.fit_pct>=50?'text-warning':'text-danger'}">${Math.round(m.fit_pct)}%</strong>`, higher_better: true, numeric: m => m.fit_pct },
    { label: 'Điểm chuẩn 2025', fn: m => m.entry_score || '—', higher_better: false, numeric: m => m.entry_score || 0 },
    { label: 'Khối xét tuyển', fn: m => m.admission_block || '—', higher_better: null },
    { label: 'Xu hướng ĐC', fn: m => {
        const s = m.entry_scores;
        if (!s || s.length < 2) return '—';
        const diff = (s[s.length-1].score - s[0].score).toFixed(1);
        return diff > 0 ? `<span class="text-danger">↑ +${diff}</span>` : diff < 0 ? `<span class="text-success">↓ ${diff}</span>` : '→ 0';
      }, higher_better: null },
  ];

  // Subject rows from weights
  const allSubjects = [...new Set(data.majors.flatMap(m => m.weights.map(w => w.subject_name)))];
  allSubjects.forEach(subj => {
    rows.push({
      label: `Yêu cầu ${subj}`,
      fn: (m, studentScores) => {
        const w = m.weights.find(x => x.subject_name === subj);
        const req = w ? w.min_score : '—';
        const stu = studentScores[subj];
        if (!w || stu === undefined) return `${req}`;
        const ok = stu >= w.min_score;
        return `<span class="${ok?'text-success':'text-danger'}">${req} ${ok?'✓':'✗'}</span>`;
      },
      higher_better: null,
      numeric: m => { const w = m.weights.find(x => x.subject_name === subj); return w ? w.min_score : 0; }
    });
  });

  rows.forEach(rowDef => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td class="fw-bold text-muted small">${rowDef.label}</td>`;
    const vals = rowDef.numeric ? data.majors.map(m => rowDef.numeric(m)) : null;
    const best = vals ? (rowDef.higher_better === false ? Math.min(...vals) : Math.max(...vals)) : null;
    data.majors.forEach((m, i) => {
      const cellVal = rowDef.fn(m, data.student_scores || {});
      const isBest = vals && vals[i] === best && rowDef.higher_better !== null;
      tr.innerHTML += `<td ${isBest ? 'style="background:#d1fae522"' : ''}>${cellVal}</td>`;
    });
    tbody.appendChild(tr);
  });
}

function clearCharts() {
  if (radarChart) radarChart.destroy();
  if (lineChart) lineChart.destroy();
}

// Add major search
let addTimer;
document.getElementById('add-search').addEventListener('input', async function() {
  clearTimeout(addTimer);
  addTimer = setTimeout(async () => {
    const q = this.value.trim();
    if (!q) { document.getElementById('add-dropdown').classList.add('d-none'); return; }
    if (!allMajorsCache) {
      const r = await fetch('/api/student/career/browse');
      allMajorsCache = (await r.json()).majors;
    }
    const filtered = allMajorsCache.filter(m =>
      (m.name + m.university).toLowerCase().includes(q.toLowerCase()) &&
      !compareIds.has(m.id)
    ).slice(0, 8);
    const dd = document.getElementById('add-dropdown');
    dd.innerHTML = '';
    filtered.forEach(m => {
      const item = document.createElement('a');
      item.className = 'dropdown-item small';
      item.textContent = `${m.name} — ${m.university}`;
      item.onclick = () => {
        if (compareIds.size >= 4) { alert('Tối đa 4 ngành'); return; }
        compareIds.add(m.id);
        sessionStorage.setItem('compare_major_ids', JSON.stringify([...compareIds]));
        document.getElementById('add-search').value = '';
        dd.classList.add('d-none');
        loadAndRender();
      };
      dd.appendChild(item);
    });
    dd.classList.toggle('d-none', filtered.length === 0);
  }, 300);
});

document.addEventListener('click', e => {
  if (!e.target.closest('#add-search')) {
    document.getElementById('add-dropdown').classList.add('d-none');
  }
});

loadAndRender();
</script>
{% endblock %}
```

- [ ] **Step 3: Kiểm tra trong browser**

```bash
python app.py
```

Mở `http://localhost:5000/student/career/browse`, chọn 2+ ngành, click "So sánh". Kiểm tra:
- [ ] Radar overlay hiện tất cả ngành
- [ ] Line chart hiện xu hướng 3 năm
- [ ] Versus table highlight ô tốt nhất
- [ ] Thêm/xóa ngành hoạt động

- [ ] **Step 4: Commit**

```bash
git add templates/student_career_compare.html routes/career.py
git commit -m "feat: add comparison page with radar overlay, line chart, versus table"
```

---

## Task 6: Connected Map page

**Files:**
- Create: `templates/student_career_map.html`
- Modify: `routes/career.py` (thêm route `/student/career/map`)

- [ ] **Step 1: Thêm route vào `routes/career.py`**

```python
@career_bp.route('/student/career/map')
def career_map():
    student = _student()
    if not student:
        return redirect(url_for('student.student_login'))
    return render_template('student_career_map.html', student=student)
```

- [ ] **Step 2: Tạo `templates/student_career_map.html`**

```html
{% extends 'base.html' %}
{% block content %}
<div style="position:relative;height:85vh;overflow:hidden" id="map-app">

  <!-- Controls overlay -->
  <div style="position:absolute;top:12px;left:12px;z-index:100;display:flex;flex-direction:column;gap:8px;width:220px">
    <input type="text" id="map-search" class="form-control form-control-sm"
           placeholder="🔍 Tìm ngành...">
    <div id="group-filters" class="d-flex flex-wrap gap-1"></div>
    <div class="form-check form-switch">
      <input class="form-check-input" type="checkbox" id="filter-fit-only">
      <label class="form-check-label small text-white" for="filter-fit-only">Chỉ ngành phù hợp (>50%)</label>
    </div>
    <div class="d-flex gap-1">
      <button class="btn btn-sm btn-dark" onclick="zoom(1.3)">＋</button>
      <button class="btn btn-sm btn-dark" onclick="zoom(0.7)">－</button>
      <button class="btn btn-sm btn-dark" onclick="resetZoom()">↺</button>
    </div>
  </div>

  <!-- Detail panel -->
  <div id="detail-panel" style="position:absolute;right:0;top:0;bottom:0;width:280px;
       background:rgba(15,23,42,0.95);border-left:1px solid #334155;
       padding:16px;z-index:100;display:none;overflow-y:auto">
    <button class="btn-close btn-close-white float-end" onclick="closePanel()"></button>
    <h6 id="dp-name" class="fw-bold text-primary mb-0"></h6>
    <small id="dp-university" class="text-muted"></small>
    <div class="mt-2">
      <span class="badge bg-secondary" id="dp-block"></span>
      <span class="badge bg-dark ms-1" id="dp-group"></span>
    </div>
    <div class="mt-2">
      <span class="text-success fw-bold fs-5" id="dp-fit"></span>
      <small class="text-muted"> phù hợp</small>
    </div>
    <div class="mt-2">
      <div class="text-muted small mb-1">ĐC 2025: <strong id="dp-score" class="text-white"></strong></div>
    </div>
    <hr class="border-secondary my-2">
    <div class="small text-muted mb-1">Top môn yêu cầu:</div>
    <div id="dp-subjects"></div>
    <div class="mt-3 d-flex flex-column gap-2">
      <button class="btn btn-sm btn-outline-warning" onclick="addToCompare()">+ So sánh</button>
      <a id="dp-detail-link" class="btn btn-sm btn-outline-primary" href="#">Xem chi tiết</a>
    </div>
  </div>

  <!-- SVG canvas -->
  <svg id="map-svg" width="100%" height="100%"
       style="background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%)">
    <defs>
      <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
        <path d="M0,0 L6,3 L0,6 Z" fill="#475569" opacity="0.4"/>
      </marker>
    </defs>
    <g id="map-g"></g>
  </svg>
</div>

<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script>
const GROUP_COLORS = {
  'Kỹ thuật': '#3b82f6', 'Công nghệ': '#60a5fa', 'Kinh tế': '#f59e0b',
  'Y dược': '#10b981', 'Xã hội': '#a78bfa', 'Nghệ thuật': '#f43f5e',
  'Khoa học': '#06b6d4', 'Nông lâm': '#84cc16'
};
const DEFAULT_COLOR = '#94a3b8';

let simulation, svg, g, nodes, links, allData;
let zoomBehavior;
let currentNode = null;
let compareIds = new Set(JSON.parse(sessionStorage.getItem('compare_major_ids') || '[]'));

function cosineSim(a, b, subjects) {
  let dot = 0, normA = 0, normB = 0;
  subjects.forEach(k => {
    dot += (a[k]||0) * (b[k]||0);
    normA += (a[k]||0) ** 2;
    normB += (b[k]||0) ** 2;
  });
  return normA && normB ? dot / (Math.sqrt(normA) * Math.sqrt(normB)) : 0;
}

async function init() {
  const r = await fetch('/api/student/career/map-data');
  const data = await r.json();
  allData = data.majors;
  renderMap(allData);
  buildGroupFilters(allData);
}

function renderMap(majors) {
  const subjects = [...new Set(majors.flatMap(m => Object.keys(m.weight_vector)))];
  const SIM_THRESHOLD = 0.7;

  const nodesData = majors.map(m => ({ ...m }));
  const linksData = [];
  for (let i = 0; i < nodesData.length; i++) {
    for (let j = i + 1; j < nodesData.length; j++) {
      const sim = cosineSim(nodesData[i].weight_vector, nodesData[j].weight_vector, subjects);
      if (sim > SIM_THRESHOLD) {
        linksData.push({ source: nodesData[i].id, target: nodesData[j].id, strength: sim });
      }
    }
  }

  const width = document.getElementById('map-svg').clientWidth;
  const height = document.getElementById('map-svg').clientHeight;

  svg = d3.select('#map-svg');
  g = d3.select('#map-g');
  g.selectAll('*').remove();

  zoomBehavior = d3.zoom().scaleExtent([0.2, 4]).on('zoom', e => g.attr('transform', e.transform));
  svg.call(zoomBehavior);

  const radiusScale = d3.scaleLinear()
    .domain([15, 30]).range([8, 22]).clamp(true);

  simulation = d3.forceSimulation(nodesData)
    .force('link', d3.forceLink(linksData).id(d => d.id).distance(80).strength(d => d.strength * 0.5))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide(d => radiusScale(d.entry_score || 20) + 10));

  const link = g.append('g').selectAll('line').data(linksData).enter().append('line')
    .attr('stroke', '#475569').attr('stroke-opacity', d => d.strength * 0.5)
    .attr('stroke-width', d => d.strength * 2);

  const node = g.append('g').selectAll('g').data(nodesData).enter().append('g')
    .style('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
      .on('drag', (e, d) => { d.fx=e.x; d.fy=e.y; })
      .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; }))
    .on('click', (e, d) => showDetail(d));

  node.append('circle')
    .attr('r', d => radiusScale(d.entry_score || 20))
    .attr('fill', d => GROUP_COLORS[d.major_group] || DEFAULT_COLOR)
    .attr('fill-opacity', 0.85)
    .attr('stroke', '#1e293b').attr('stroke-width', 1.5);

  node.append('text')
    .text(d => d.name.length > 12 ? d.name.slice(0, 12) + '…' : d.name)
    .attr('text-anchor', 'middle').attr('dy', '0.35em')
    .attr('font-size', '8px').attr('fill', 'white').attr('pointer-events', 'none');

  simulation.on('tick', () => {
    link.attr('x1', d=>d.source.x).attr('y1', d=>d.source.y)
        .attr('x2', d=>d.target.x).attr('y2', d=>d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
}

function showDetail(d) {
  currentNode = d;
  document.getElementById('dp-name').textContent = d.name;
  document.getElementById('dp-university').textContent = d.university;
  document.getElementById('dp-block').textContent = d.admission_block || '—';
  document.getElementById('dp-group').textContent = d.major_group || '—';
  document.getElementById('dp-fit').textContent = Math.round(d.fit_pct) + '%';
  document.getElementById('dp-score').textContent = d.entry_score || '—';
  document.getElementById('dp-detail-link').href = '/student/career';

  const subjDiv = document.getElementById('dp-subjects');
  subjDiv.innerHTML = '';
  const top3 = Object.entries(d.weight_vector).sort((a,b)=>b[1]-a[1]).slice(0,3);
  top3.forEach(([subj, w]) => {
    const span = document.createElement('div');
    span.className = 'small text-light mb-1';
    span.innerHTML = `<span class="text-muted">${subj}:</span> trọng số ${(w*100).toFixed(0)}%`;
    subjDiv.appendChild(span);
  });

  document.getElementById('detail-panel').style.display = 'block';
}

function closePanel() {
  document.getElementById('detail-panel').style.display = 'none';
  currentNode = null;
}

function addToCompare() {
  if (!currentNode) return;
  if (compareIds.size >= 4) { alert('Tối đa 4 ngành'); return; }
  compareIds.add(currentNode.id);
  sessionStorage.setItem('compare_major_ids', JSON.stringify([...compareIds]));
  alert(`Đã thêm "${currentNode.name}" vào danh sách so sánh`);
}

function buildGroupFilters(majors) {
  const groups = [...new Set(majors.map(m => m.major_group).filter(Boolean))];
  const container = document.getElementById('group-filters');
  groups.forEach(g => {
    const btn = document.createElement('span');
    btn.className = 'badge';
    btn.style.cssText = `background:${GROUP_COLORS[g]||DEFAULT_COLOR};cursor:pointer`;
    btn.textContent = g;
    btn.onclick = () => filterByGroup(g, btn);
    container.appendChild(btn);
  });
}

let activeGroups = new Set();
function filterByGroup(group, btn) {
  if (activeGroups.has(group)) {
    activeGroups.delete(group);
    btn.style.opacity = '1';
  } else {
    activeGroups.add(group);
    btn.style.opacity = '0.4';
  }
  applyFilters();
}

function applyFilters() {
  let filtered = allData;
  const q = document.getElementById('map-search').value.toLowerCase();
  if (q) filtered = filtered.filter(m => (m.name+m.university).toLowerCase().includes(q));
  if (document.getElementById('filter-fit-only').checked)
    filtered = filtered.filter(m => m.fit_pct > 50);
  if (activeGroups.size > 0)
    filtered = filtered.filter(m => !activeGroups.has(m.major_group));
  renderMap(filtered);
}

let searchTimer;
document.getElementById('map-search').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(applyFilters, 400);
});
document.getElementById('filter-fit-only').addEventListener('change', applyFilters);

function zoom(factor) {
  svg.transition().duration(300).call(zoomBehavior.scaleBy, factor);
}
function resetZoom() {
  svg.transition().duration(300).call(zoomBehavior.transform, d3.zoomIdentity);
}

init();
</script>
{% endblock %}
```

- [ ] **Step 3: Kiểm tra trong browser**

Mở `http://localhost:5000/student/career/map`. Kiểm tra:
- [ ] Nodes hiện với màu theo major_group
- [ ] Nodes "tương đồng" (cosine sim > 0.7) có đường nối
- [ ] Click node → detail panel bên phải hiện
- [ ] Drag node hoạt động
- [ ] Search highlight/filter nodes
- [ ] Nút zoom +/- hoạt động
- [ ] "Thêm vào so sánh" lưu vào sessionStorage

- [ ] **Step 4: Commit**

```bash
git add templates/student_career_map.html routes/career.py
git commit -m "feat: add connected map page with D3.js force simulation"
```

---

## Task 7: Admin page cập nhật

**Files:**
- Modify: `templates/admin_majors.html`
- Modify: `routes/career.py` (thêm 2 admin API endpoints)

- [ ] **Step 1: Thêm admin API endpoints vào `routes/career.py`**

```python
@career_bp.route('/admin/majors/<int:major_id>', methods=['PATCH'])
def admin_update_major(major_id):
    from flask_login import current_user
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    major = UniversityMajor.query.get_or_404(major_id)
    data = request.json
    if 'admission_block' in data:
        major.admission_block = data['admission_block']
    if 'entry_score' in data:
        major.entry_score = float(data['entry_score']) if data['entry_score'] else None
    db.session.commit()
    return jsonify({'ok': True})


@career_bp.route('/admin/majors/<int:major_id>/entry-scores', methods=['POST'])
def admin_add_entry_score(major_id):
    from flask_login import current_user
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    UniversityMajor.query.get_or_404(major_id)
    data = request.json
    year = int(data['year'])
    score = float(data['score'])
    existing = MajorEntryScore.query.filter_by(major_id=major_id, year=year).first()
    if existing:
        existing.score = score
    else:
        db.session.add(MajorEntryScore(major_id=major_id, year=year, score=score))
    db.session.commit()
    return jsonify({'ok': True})
```

- [ ] **Step 2: Cập nhật `templates/admin_majors.html`**

Tìm phần table header trong admin_majors.html và thêm columns. Tìm `<th>` headers của bảng majors và thêm 2 cột sau cột "Ngành":

```html
<th>Khối XT</th>
<th>ĐC 2025</th>
```

Tìm mỗi `<tr>` trong tbody và thêm 2 cells:

```html
<td>
  <input type="text" class="form-control form-control-sm" style="width:70px"
         value="{{ major.admission_block or '' }}"
         onchange="updateMajorField({{ major.id }}, 'admission_block', this.value)">
</td>
<td>
  <input type="number" class="form-control form-control-sm" style="width:80px"
         step="0.1" value="{{ major.entry_score or '' }}"
         onchange="updateMajorField({{ major.id }}, 'entry_score', this.value)">
</td>
```

Thêm JS vào cuối template (trước `{% endblock %}`):

```html
<script>
async function updateMajorField(id, field, value) {
  await fetch(`/admin/majors/${id}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({[field]: value})
  });
}

async function addEntryScore(majorId) {
  const year = document.getElementById(`year-${majorId}`).value;
  const score = document.getElementById(`score-${majorId}`).value;
  if (!year || !score) return;
  await fetch(`/admin/majors/${majorId}/entry-scores`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({year: parseInt(year), score: parseFloat(score)})
  });
  alert('Đã lưu điểm chuẩn');
}
</script>
```

- [ ] **Step 3: Kiểm tra admin page**

Đăng nhập admin, vào `/admin/majors`, kiểm tra:
- [ ] Cột "Khối XT" và "ĐC 2025" hiện đúng
- [ ] Sửa inline và blur → lưu qua PATCH API

- [ ] **Step 4: Commit**

```bash
git add templates/admin_majors.html routes/career.py
git commit -m "feat: admin majors page - admission_block, entry_score, historical scores"
```

---

## Task 8: Navigation integration

**Files:**
- Modify: `templates/student_career.html`

- [ ] **Step 1: Thêm 3 nút điều hướng vào `student_career.html`**

Tìm phần đầu của `{% block content %}` trong `student_career.html`. Thêm ngay sau thẻ mở container:

```html
<!-- Navigation cards -->
<div class="row g-3 mb-4">
  <div class="col-md-4">
    <a href="/student/career/browse" class="card text-center text-decoration-none h-100 shadow-sm border-primary">
      <div class="card-body py-3">
        <div class="fs-2">🔍</div>
        <div class="fw-bold text-primary">Khám phá ngành</div>
        <small class="text-muted">Tìm kiếm và lọc tất cả ngành học</small>
      </div>
    </a>
  </div>
  <div class="col-md-4">
    <a href="/student/career/map" class="card text-center text-decoration-none h-100 shadow-sm border-success">
      <div class="card-body py-3">
        <div class="fs-2">🗺️</div>
        <div class="fw-bold text-success">Bản đồ ngành</div>
        <small class="text-muted">Xem sơ đồ liên kết các ngành học</small>
      </div>
    </a>
  </div>
  <div class="col-md-4">
    <a href="/student/career/compare" class="card text-center text-decoration-none h-100 shadow-sm border-warning">
      <div class="card-body py-3">
        <div class="fs-2">⚖️</div>
        <div class="fw-bold text-warning">So sánh ngành</div>
        <small class="text-muted">So sánh chi tiết các ngành quan tâm</small>
      </div>
    </a>
  </div>
</div>
```

- [ ] **Step 2: Kiểm tra navigation**

Mở `/student/career`, kiểm tra:
- [ ] 3 cards hiện đúng
- [ ] Click "Khám phá ngành" → `/student/career/browse`
- [ ] Click "Bản đồ ngành" → `/student/career/map`
- [ ] Click "So sánh ngành" → `/student/career/compare`

- [ ] **Step 3: Commit final**

```bash
git add templates/student_career.html
git commit -m "feat: add navigation cards on career main page"
```

---

## Self-Review

**Spec coverage check:**
- [x] Score Simulator → Task 3 (API) + Task 4 (modal UI)
- [x] Connected Map force-directed + detail panel → Task 6
- [x] Comparison: radar overlay + versus table + line chart → Task 5
- [x] Filter top bar + chip filters + fix bug → Task 3 (API) + Task 4 (UI)
- [x] Sparkline trong browse cards → Task 4
- [x] Multi-admission-block → Task 2 (models)
- [x] MajorEntryScore table → Task 2 (models + seed)
- [x] Admin page cập nhật → Task 7
- [x] Navigation integration → Task 8

**Placeholder scan:** Không có TBD hay TODO trong plan.

**Type consistency:**
- `MajorEntryScore` được định nghĩa Task 2, dùng nhất quán trong Task 3 (import đã thêm vào models import line)
- `compare_major_ids` sessionStorage key dùng nhất quán Task 4, 5, 6
- `COLORS` array 4 màu dùng nhất quán Task 5 và 6
- `/api/student/career/simulate` POST endpoint dùng đúng trong Task 3 define + Task 4 call
- `admission_block` field name nhất quán toàn bộ plan
