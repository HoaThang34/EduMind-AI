# Định hướng chọn ngành Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm tính năng "Định hướng chọn ngành" vào student portal — radar chart overlay so sánh điểm học sinh với yêu cầu ~150 ngành đại học, kèm pin và target tracking.

**Architecture:** 4 DB models mới (UniversityMajor, MajorSubjectWeight, StudentPinnedMajor, StudentTargetMajor) + 2 helper functions trong app_helpers.py + 1 Blueprint mới (career.py) + 2 template student + 1 template admin. Không thay đổi bảng điểm hiện có — chỉ đọc từ Grade.

**Tech Stack:** Flask, SQLAlchemy, Chart.js (CDN), Tailwind CSS (CDN), pytest

---

## File Map

| File | Action | Mục đích |
|------|--------|---------|
| `models.py` | Modify | Thêm 4 models mới |
| `app.py` | Modify | Migration + đăng ký career_bp |
| `app_helpers.py` | Modify | Thêm `calculate_subject_averages()`, `calculate_fit_score()` |
| `routes/career.py` | Create | Blueprint career — API + page routes |
| `routes/__init__.py` | Modify | Register career blueprint |
| `templates/student_career.html` | Create | Trang chính định hướng |
| `templates/student_career_browse.html` | Create | Trang duyệt ngành (chart view) |
| `templates/admin_majors.html` | Create | Quản lý ngành cho admin |
| `templates/student_dashboard.html` | Modify | Thêm tab thứ 3 |
| `data/majors_seed.json` | Create | Mock data ~150 ngành |
| `seed_majors.py` | Create | Script import seed data vào DB |
| `tests/test_career.py` | Create | Tests cho helper functions + API |

---

## Task 1: DB Models

**Files:**
- Modify: `models.py`

- [ ] **Step 1: Thêm 4 models vào cuối models.py**

Mở `models.py`, thêm vào cuối file (sau model cuối cùng hiện có):

```python
class UniversityMajor(db.Model):
    __tablename__ = 'university_major'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    university = db.Column(db.String(150), nullable=False)
    faculty = db.Column(db.String(150))
    major_group = db.Column(db.String(50))  # Kỹ thuật, Kinh tế, Y dược, Xã hội,...
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    weights = db.relationship('MajorSubjectWeight', backref='major',
                               cascade='all, delete-orphan', lazy=True)
    pinned_by = db.relationship('StudentPinnedMajor', backref='major',
                                 cascade='all, delete-orphan', lazy=True)
    targeted_by = db.relationship('StudentTargetMajor', backref='major',
                                   cascade='all, delete-orphan', lazy=True)


class MajorSubjectWeight(db.Model):
    __tablename__ = 'major_subject_weight'
    id = db.Column(db.Integer, primary_key=True)
    major_id = db.Column(db.Integer, db.ForeignKey('university_major.id'), nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)  # khớp Subject.name
    weight = db.Column(db.Float, nullable=False)   # tổng các weight của 1 ngành = 1.0
    min_score = db.Column(db.Float, nullable=False)  # điểm yêu cầu 0-10


class StudentPinnedMajor(db.Model):
    __tablename__ = 'student_pinned_major'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    major_id = db.Column(db.Integer, db.ForeignKey('university_major.id'), nullable=False)
    pinned_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'major_id'),)


class StudentTargetMajor(db.Model):
    __tablename__ = 'student_target_major'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, unique=True)
    major_id = db.Column(db.Integer, db.ForeignKey('university_major.id'), nullable=False)
    set_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
```

- [ ] **Step 2: Commit**

```bash
git add models.py
git commit -m "feat: add UniversityMajor, MajorSubjectWeight, StudentPinnedMajor, StudentTargetMajor models"
```

---

## Task 2: DB Migration

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Thêm hàm migration cho các bảng mới vào app.py**

Trong `app.py`, thêm hàm sau trước hàm `create_database()`:

```python
def ensure_career_tables():
    """Tạo bảng career nếu chưa có (SQLite migration)."""
    insp = inspect(db.engine)
    if not insp.has_table("university_major"):
        db.session.execute(text("""
            CREATE TABLE university_major (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(150) NOT NULL,
                university VARCHAR(150) NOT NULL,
                faculty VARCHAR(150),
                major_group VARCHAR(50),
                description TEXT,
                created_at DATETIME
            )
        """))
    if not insp.has_table("major_subject_weight"):
        db.session.execute(text("""
            CREATE TABLE major_subject_weight (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                major_id INTEGER NOT NULL REFERENCES university_major(id),
                subject_name VARCHAR(100) NOT NULL,
                weight FLOAT NOT NULL,
                min_score FLOAT NOT NULL
            )
        """))
    if not insp.has_table("student_pinned_major"):
        db.session.execute(text("""
            CREATE TABLE student_pinned_major (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES student(id),
                major_id INTEGER NOT NULL REFERENCES university_major(id),
                pinned_at DATETIME,
                UNIQUE(student_id, major_id)
            )
        """))
    if not insp.has_table("student_target_major"):
        db.session.execute(text("""
            CREATE TABLE student_target_major (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL UNIQUE REFERENCES student(id),
                major_id INTEGER NOT NULL REFERENCES university_major(id),
                set_at DATETIME
            )
        """))
    db.session.commit()
```

- [ ] **Step 2: Gọi `ensure_career_tables()` trong `create_database()`**

Trong hàm `create_database()` ở `app.py`, thêm dòng này ngay trước `db.session.commit()` cuối:

```python
    ensure_career_tables()
```

- [ ] **Step 3: Đăng ký career blueprint**

Trong `app.py`, thêm sau các import blueprint hiện có (khoảng dòng 52-61):

```python
from routes.career import career_bp
app.register_blueprint(career_bp)
```

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add career DB migration and register career blueprint"
```

---

## Task 3: Helper Functions

**Files:**
- Modify: `app_helpers.py`
- Create: `tests/test_career.py`

- [ ] **Step 1: Tạo thư mục tests và viết failing tests**

```bash
mkdir -p tests
touch tests/__init__.py
```

Tạo file `tests/test_career.py`:

```python
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def subject_averages_sample():
    """Điểm trung bình mẫu: {subject_name: avg_score}"""
    return {
        'Toán': 7.5,
        'Vật lý': 8.2,
        'Tiếng Anh': 8.5,
        'Hóa học': 6.1,
    }


@pytest.fixture
def weights_sample():
    """Weights mẫu cho ngành AI: [{subject_name, weight, min_score}]"""
    return [
        {'subject_name': 'Toán', 'weight': 0.4, 'min_score': 8.3},
        {'subject_name': 'Vật lý', 'weight': 0.35, 'min_score': 8.0},
        {'subject_name': 'Tiếng Anh', 'weight': 0.25, 'min_score': 8.5},
    ]


def test_calculate_fit_score_basic(subject_averages_sample, weights_sample):
    from app_helpers import calculate_fit_score
    result = calculate_fit_score(subject_averages_sample, weights_sample)
    assert 'fit_pct' in result
    assert 'gaps' in result
    # Toán: min(7.5,8.3)*0.4 = 3.0, Lý: min(8.2,8.0)*0.35 = 2.8, Anh: min(8.5,8.5)*0.25 = 2.125
    # Denominator: 8.3*0.4 + 8.0*0.35 + 8.5*0.25 = 3.32 + 2.8 + 2.125 = 8.245
    # Numerator: 3.0 + 2.8 + 2.125 = 7.925
    expected = round(7.925 / 8.245 * 100, 1)
    assert abs(result['fit_pct'] - expected) < 0.2


def test_calculate_fit_score_no_inflation(subject_averages_sample, weights_sample):
    """Điểm vượt yêu cầu không inflate fit score."""
    from app_helpers import calculate_fit_score
    high_scores = {'Toán': 10.0, 'Vật lý': 10.0, 'Tiếng Anh': 10.0}
    result = calculate_fit_score(high_scores, weights_sample)
    assert result['fit_pct'] == 100.0


def test_calculate_fit_score_missing_subject(weights_sample):
    """Môn chưa có điểm tính = 0."""
    from app_helpers import calculate_fit_score
    no_scores = {}
    result = calculate_fit_score(no_scores, weights_sample)
    assert result['fit_pct'] == 0.0


def test_calculate_fit_score_gaps(subject_averages_sample, weights_sample):
    """Gap Toán phải là âm (thiếu điểm)."""
    from app_helpers import calculate_fit_score
    result = calculate_fit_score(subject_averages_sample, weights_sample)
    toan_gap = next(g for g in result['gaps'] if g['subject_name'] == 'Toán')
    assert toan_gap['gap'] < 0  # 7.5 - 8.3 = -0.8
    assert abs(toan_gap['gap'] - (-0.8)) < 0.01


def test_calculate_fit_score_status_tags(subject_averages_sample, weights_sample):
    from app_helpers import calculate_fit_score
    result = calculate_fit_score(subject_averages_sample, weights_sample)
    anh_gap = next(g for g in result['gaps'] if g['subject_name'] == 'Tiếng Anh')
    assert anh_gap['status'] == 'ok'   # 8.5 >= 8.5
    toan_gap = next(g for g in result['gaps'] if g['subject_name'] == 'Toán')
    assert toan_gap['status'] == 'fail'  # 7.5 < 8.3
```

- [ ] **Step 2: Chạy tests — phải FAIL vì hàm chưa tồn tại**

```bash
cd "/Users/dat_macbook/Documents/2025/ý tưởng mới/Hỗ trợ Yên Bái nhận diện khuôn mặt/EduMind-AI"
venv/bin/pytest tests/test_career.py -v
```

Expected output: `ImportError: cannot import name 'calculate_fit_score' from 'app_helpers'`

- [ ] **Step 3: Thêm helper functions vào app_helpers.py**

Thêm vào cuối `app_helpers.py`:

```python
def calculate_subject_averages(student_id, semester, school_year):
    """
    Tính điểm trung bình từng môn cho học sinh.
    Formula per subject: (avg_TX + avg_GK*2 + avg_HK*3) / 6
    Returns: dict {subject_name: avg_score} — chỉ gồm môn có đủ TX+GK+HK
    """
    from models import Grade, Subject
    grades = Grade.query.filter_by(
        student_id=student_id,
        semester=semester,
        school_year=school_year
    ).all()

    by_subject = {}
    for g in grades:
        sid = g.subject_id
        if sid not in by_subject:
            by_subject[sid] = {'TX': [], 'GK': [], 'HK': []}
        by_subject[sid][g.grade_type].append(g.score)

    result = {}
    for subject_id, data in by_subject.items():
        if data['TX'] and data['GK'] and data['HK']:
            avg_tx = sum(data['TX']) / len(data['TX'])
            avg_gk = sum(data['GK']) / len(data['GK'])
            avg_hk = sum(data['HK']) / len(data['HK'])
            avg = round((avg_tx + avg_gk * 2 + avg_hk * 3) / 6, 2)
            subject = Subject.query.get(subject_id)
            if subject:
                result[subject.name] = avg
    return result


def calculate_fit_score(subject_averages, weights):
    """
    Tính fit % của học sinh với 1 ngành.

    Args:
        subject_averages: dict {subject_name: avg_score}
        weights: list of dict [{subject_name, weight, min_score}]

    Returns:
        {
            'fit_pct': float (0-100),
            'gaps': [{subject_name, student_score, min_score, gap, status, weight}]
        }
        status: 'ok' (đạt), 'warn' (thiếu <= 1đ), 'fail' (thiếu > 1đ)
    """
    numerator = 0.0
    denominator = 0.0
    gaps = []

    for w in weights:
        name = w['subject_name']
        min_score = w['min_score']
        weight = w['weight']
        student_score = subject_averages.get(name, 0.0)

        numerator += min(student_score, min_score) * weight
        denominator += min_score * weight

        gap = round(student_score - min_score, 2)
        if gap >= 0:
            status = 'ok'
        elif gap >= -1.0:
            status = 'warn'
        else:
            status = 'fail'

        gaps.append({
            'subject_name': name,
            'student_score': student_score,
            'min_score': min_score,
            'gap': gap,
            'status': status,
            'weight': weight,
        })

    fit_pct = round(numerator / denominator * 100, 1) if denominator > 0 else 0.0
    fit_pct = min(fit_pct, 100.0)

    return {'fit_pct': fit_pct, 'gaps': gaps}
```

- [ ] **Step 4: Chạy lại tests — phải PASS**

```bash
venv/bin/pytest tests/test_career.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add app_helpers.py tests/
git commit -m "feat: add calculate_subject_averages and calculate_fit_score helpers"
```

---

## Task 4: Career Blueprint

**Files:**
- Create: `routes/career.py`
- Modify: `routes/__init__.py`

- [ ] **Step 1: Tạo routes/career.py**

```python
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from models import db, Student, UniversityMajor, MajorSubjectWeight, StudentPinnedMajor, StudentTargetMajor, SystemConfig
from app_helpers import calculate_subject_averages, calculate_fit_score
import datetime

career_bp = Blueprint('career', __name__)


def _get_current_student():
    student_id = session.get('student_id')
    if not student_id:
        return None
    return Student.query.get(student_id)


def _get_school_config():
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    return {
        'semester': int(configs.get('current_semester', '1')),
        'school_year': configs.get('school_year', '2025-2026'),
    }


def _build_major_radar_data(major_id, subject_averages):
    """Trả về labels, student_scores, major_scores cho Chart.js."""
    weights = MajorSubjectWeight.query.filter_by(major_id=major_id).all()
    labels = [w.subject_name for w in weights]
    student_scores = [subject_averages.get(w.subject_name, 0.0) for w in weights]
    major_scores = [w.min_score for w in weights]
    weights_list = [{'subject_name': w.subject_name, 'weight': w.weight, 'min_score': w.min_score}
                    for w in weights]
    return labels, student_scores, major_scores, weights_list


@career_bp.route('/student/career')
def career_main():
    student = _get_current_student()
    if not student:
        return redirect(url_for('student.student_login'))

    cfg = _get_school_config()
    subject_averages = calculate_subject_averages(student.id, cfg['semester'], cfg['school_year'])

    # Ngành mục tiêu
    target = StudentTargetMajor.query.filter_by(student_id=student.id).first()
    target_major = target.major if target else None
    target_data = None
    if target_major:
        weights = [{'subject_name': w.subject_name, 'weight': w.weight, 'min_score': w.min_score}
                   for w in target_major.weights]
        fit_result = calculate_fit_score(subject_averages, weights)
        target_data = {
            'major': target_major,
            'fit_pct': fit_result['fit_pct'],
            'gaps': fit_result['gaps'],
        }

    # Ngành đã ghim
    pins = StudentPinnedMajor.query.filter_by(student_id=student.id).all()
    pinned_data = []
    for p in pins:
        weights = [{'subject_name': w.subject_name, 'weight': w.weight, 'min_score': w.min_score}
                   for w in p.major.weights]
        fit_result = calculate_fit_score(subject_averages, weights)
        pinned_data.append({
            'major': p.major,
            'fit_pct': fit_result['fit_pct'],
        })

    # Ngành mặc định trên radar = target nếu có, không thì ngành đầu tiên
    default_major = target_major or UniversityMajor.query.first()
    radar_labels, radar_student, radar_major, _ = _build_major_radar_data(
        default_major.id, subject_averages
    ) if default_major else ([], [], [], [])

    return render_template('student_career.html',
        student=student,
        target_data=target_data,
        pinned_data=pinned_data,
        radar_labels=radar_labels,
        radar_student=radar_student,
        radar_major=radar_major,
        default_major=default_major,
        subject_averages=subject_averages,
    )


@career_bp.route('/api/student/career/radar-data')
def api_radar_data():
    student = _get_current_student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401

    major_id = request.args.get('major_id', type=int)
    major = UniversityMajor.query.get_or_404(major_id)

    cfg = _get_school_config()
    subject_averages = calculate_subject_averages(student.id, cfg['semester'], cfg['school_year'])
    labels, student_scores, major_scores, weights_list = _build_major_radar_data(major_id, subject_averages)
    fit_result = calculate_fit_score(subject_averages, weights_list)

    return jsonify({
        'labels': labels,
        'student_scores': student_scores,
        'major_scores': major_scores,
        'fit_pct': fit_result['fit_pct'],
        'gaps': fit_result['gaps'],
        'major': {'id': major.id, 'name': major.name, 'university': major.university},
    })


@career_bp.route('/api/student/career/browse')
def api_browse():
    student = _get_current_student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401

    cfg = _get_school_config()
    subject_averages = calculate_subject_averages(student.id, cfg['semester'], cfg['school_year'])

    # Filters
    major_group = request.args.get('group', '')
    university = request.args.get('university', '')
    min_fit = request.args.get('min_fit', 0, type=float)
    search = request.args.get('q', '').strip().lower()

    query = UniversityMajor.query
    if major_group:
        query = query.filter_by(major_group=major_group)
    if university:
        query = query.filter(UniversityMajor.university.ilike(f'%{university}%'))

    majors = query.all()

    pinned_ids = {p.major_id for p in StudentPinnedMajor.query.filter_by(student_id=student.id).all()}
    target = StudentTargetMajor.query.filter_by(student_id=student.id).first()
    target_id = target.major_id if target else None

    results = []
    for major in majors:
        if search and search not in major.name.lower() and search not in major.university.lower():
            continue
        weights = [{'subject_name': w.subject_name, 'weight': w.weight, 'min_score': w.min_score}
                   for w in major.weights]
        if not weights:
            continue
        fit_result = calculate_fit_score(subject_averages, weights)
        if fit_result['fit_pct'] < min_fit:
            continue

        labels = [w['subject_name'] for w in weights]
        student_scores = [subject_averages.get(w['subject_name'], 0.0) for w in weights]
        major_scores = [w['min_score'] for w in weights]

        results.append({
            'id': major.id,
            'name': major.name,
            'university': major.university,
            'faculty': major.faculty,
            'major_group': major.major_group,
            'fit_pct': fit_result['fit_pct'],
            'is_pinned': major.id in pinned_ids,
            'is_target': major.id == target_id,
            'radar': {
                'labels': labels,
                'student_scores': student_scores,
                'major_scores': major_scores,
            },
        })

    results.sort(key=lambda x: x['fit_pct'], reverse=True)
    return jsonify({'majors': results})


@career_bp.route('/api/student/career/pin', methods=['POST'])
def api_pin():
    student = _get_current_student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    major_id = request.json.get('major_id')
    if not UniversityMajor.query.get(major_id):
        return jsonify({'error': 'not found'}), 404
    existing = StudentPinnedMajor.query.filter_by(student_id=student.id, major_id=major_id).first()
    if not existing:
        db.session.add(StudentPinnedMajor(student_id=student.id, major_id=major_id,
                                           pinned_at=datetime.datetime.utcnow()))
        db.session.commit()
    return jsonify({'ok': True})


@career_bp.route('/api/student/career/pin/<int:major_id>', methods=['DELETE'])
def api_unpin(major_id):
    student = _get_current_student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    pin = StudentPinnedMajor.query.filter_by(student_id=student.id, major_id=major_id).first()
    if pin:
        db.session.delete(pin)
        db.session.commit()
    return jsonify({'ok': True})


@career_bp.route('/api/student/career/target', methods=['POST'])
def api_set_target():
    student = _get_current_student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    major_id = request.json.get('major_id')
    if not UniversityMajor.query.get(major_id):
        return jsonify({'error': 'not found'}), 404
    existing = StudentTargetMajor.query.filter_by(student_id=student.id).first()
    if existing:
        existing.major_id = major_id
        existing.set_at = datetime.datetime.utcnow()
    else:
        db.session.add(StudentTargetMajor(student_id=student.id, major_id=major_id,
                                           set_at=datetime.datetime.utcnow()))
    db.session.commit()
    return jsonify({'ok': True})


@career_bp.route('/student/career/browse')
def career_browse():
    student = _get_current_student()
    if not student:
        return redirect(url_for('student.student_login'))
    groups = db.session.query(UniversityMajor.major_group).distinct().all()
    groups = [g[0] for g in groups if g[0]]
    universities = db.session.query(UniversityMajor.university).distinct().all()
    universities = [u[0] for u in universities]
    return render_template('student_career_browse.html',
        student=student, groups=groups, universities=universities)


# ---- Admin routes ----

@career_bp.route('/admin/majors')
def admin_majors():
    from flask_login import current_user
    if not current_user.is_authenticated or current_user.role != 'admin':
        return redirect(url_for('auth.login'))
    majors = UniversityMajor.query.order_by(UniversityMajor.university).all()
    return render_template('admin_majors.html', majors=majors)


@career_bp.route('/admin/majors/add', methods=['POST'])
def admin_add_major():
    from flask_login import current_user
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    data = request.json
    major = UniversityMajor(
        name=data['name'], university=data['university'],
        faculty=data.get('faculty', ''), major_group=data.get('major_group', ''),
        description=data.get('description', ''),
        created_at=datetime.datetime.utcnow()
    )
    db.session.add(major)
    db.session.flush()
    for w in data.get('weights', []):
        db.session.add(MajorSubjectWeight(
            major_id=major.id,
            subject_name=w['subject_name'],
            weight=float(w['weight']),
            min_score=float(w['min_score'])
        ))
    db.session.commit()
    return jsonify({'ok': True, 'id': major.id})


@career_bp.route('/admin/majors/<int:major_id>', methods=['DELETE'])
def admin_delete_major(major_id):
    from flask_login import current_user
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    major = UniversityMajor.query.get_or_404(major_id)
    db.session.delete(major)
    db.session.commit()
    return jsonify({'ok': True})
```

- [ ] **Step 2: Đăng ký trong routes/__init__.py**

Thêm vào cuối hàm `register_all_routes()` trong `routes/__init__.py`:

```python
    from .career import register as register_career
    register_career(app)
```

Tuy nhiên, career dùng Blueprint nên **không** cần `register` function — blueprint đã được đăng ký trong `app.py` ở Task 2. Bỏ qua bước này.

- [ ] **Step 3: Commit**

```bash
git add routes/career.py routes/__init__.py
git commit -m "feat: add career blueprint with radar-data, browse, pin, target APIs"
```

---

## Task 5: Seed Data

**Files:**
- Create: `data/majors_seed.json`
- Create: `seed_majors.py`

- [ ] **Step 1: Tạo thư mục data và file seed JSON**

```bash
mkdir -p data
```

Tạo `data/majors_seed.json` với cấu trúc (thêm đủ ~150 ngành thực tế hoặc dùng script generate):

```json
[
  {
    "name": "Trí tuệ nhân tạo",
    "university": "ĐH Bách Khoa Hà Nội",
    "faculty": "Viện Công nghệ thông tin và Truyền thông",
    "major_group": "Kỹ thuật - Công nghệ",
    "description": "Đào tạo kỹ sư AI với nền tảng toán học, lập trình và học máy.",
    "weights": [
      {"subject_name": "Toán", "weight": 0.45, "min_score": 8.5},
      {"subject_name": "Vật lý", "weight": 0.30, "min_score": 7.5},
      {"subject_name": "Tiếng Anh", "weight": 0.25, "min_score": 7.0}
    ]
  },
  {
    "name": "Công nghệ thông tin",
    "university": "ĐH Công nghệ - ĐHQGHN",
    "faculty": "Khoa Công nghệ thông tin",
    "major_group": "Kỹ thuật - Công nghệ",
    "description": "Đào tạo kỹ sư CNTT toàn diện từ lập trình đến hệ thống.",
    "weights": [
      {"subject_name": "Toán", "weight": 0.40, "min_score": 8.0},
      {"subject_name": "Vật lý", "weight": 0.30, "min_score": 7.0},
      {"subject_name": "Tiếng Anh", "weight": 0.30, "min_score": 6.5}
    ]
  },
  {
    "name": "Marketing",
    "university": "ĐH Kinh tế Quốc dân",
    "faculty": "Viện Marketing và Quản trị",
    "major_group": "Kinh tế - Kinh doanh",
    "description": "Đào tạo chuyên gia marketing trong môi trường số.",
    "weights": [
      {"subject_name": "Ngữ văn", "weight": 0.35, "min_score": 7.0},
      {"subject_name": "Toán", "weight": 0.30, "min_score": 6.5},
      {"subject_name": "Tiếng Anh", "weight": 0.35, "min_score": 7.5}
    ]
  },
  {
    "name": "Y khoa",
    "university": "ĐH Y Hà Nội",
    "faculty": "Khoa Y",
    "major_group": "Y - Dược",
    "description": "Đào tạo bác sĩ đa khoa với nền tảng khoa học tự nhiên vững chắc.",
    "weights": [
      {"subject_name": "Hóa học", "weight": 0.40, "min_score": 8.5},
      {"subject_name": "Sinh học", "weight": 0.35, "min_score": 8.5},
      {"subject_name": "Vật lý", "weight": 0.25, "min_score": 7.0}
    ]
  },
  {
    "name": "Dược học",
    "university": "ĐH Dược Hà Nội",
    "faculty": "Khoa Dược",
    "major_group": "Y - Dược",
    "description": "Đào tạo dược sĩ với kiến thức hóa học và sinh học chuyên sâu.",
    "weights": [
      {"subject_name": "Hóa học", "weight": 0.45, "min_score": 8.0},
      {"subject_name": "Sinh học", "weight": 0.35, "min_score": 8.0},
      {"subject_name": "Toán", "weight": 0.20, "min_score": 6.5}
    ]
  },
  {
    "name": "Luật",
    "university": "ĐH Luật Hà Nội",
    "faculty": "Khoa Luật",
    "major_group": "Xã hội - Nhân văn",
    "description": "Đào tạo cử nhân luật với kỹ năng phân tích pháp lý.",
    "weights": [
      {"subject_name": "Ngữ văn", "weight": 0.40, "min_score": 7.5},
      {"subject_name": "Lịch sử", "weight": 0.30, "min_score": 7.0},
      {"subject_name": "Tiếng Anh", "weight": 0.30, "min_score": 7.0}
    ]
  },
  {
    "name": "Kiến trúc",
    "university": "ĐH Kiến trúc Hà Nội",
    "faculty": "Khoa Kiến trúc",
    "major_group": "Kỹ thuật - Công nghệ",
    "description": "Đào tạo kiến trúc sư với tư duy sáng tạo và kỹ năng kỹ thuật.",
    "weights": [
      {"subject_name": "Toán", "weight": 0.35, "min_score": 7.0},
      {"subject_name": "Vật lý", "weight": 0.25, "min_score": 7.0},
      {"subject_name": "Ngữ văn", "weight": 0.20, "min_score": 6.5},
      {"subject_name": "Tiếng Anh", "weight": 0.20, "min_score": 6.0}
    ]
  },
  {
    "name": "Tài chính - Ngân hàng",
    "university": "ĐH Kinh tế Quốc dân",
    "faculty": "Viện Ngân hàng - Tài chính",
    "major_group": "Kinh tế - Kinh doanh",
    "description": "Đào tạo chuyên gia tài chính và ngân hàng.",
    "weights": [
      {"subject_name": "Toán", "weight": 0.50, "min_score": 8.0},
      {"subject_name": "Tiếng Anh", "weight": 0.30, "min_score": 7.0},
      {"subject_name": "Ngữ văn", "weight": 0.20, "min_score": 6.5}
    ]
  }
]
```

> **Lưu ý:** File này chứa 8 ngành mẫu. Để đủ ~150 ngành, chạy script generate bằng Claude API sau (xem `seed_majors.py`).

- [ ] **Step 2: Tạo seed_majors.py**

```python
#!/usr/bin/env python3
"""
Script import majors_seed.json vào DB.
Chạy: venv/bin/python seed_majors.py
Có thể chạy nhiều lần — skip ngành đã tồn tại (cùng name + university).
"""
import json
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app import app
from models import db, UniversityMajor, MajorSubjectWeight

SEED_FILE = os.path.join(os.path.dirname(__file__), 'data', 'majors_seed.json')


def seed():
    with open(SEED_FILE, encoding='utf-8') as f:
        majors = json.load(f)

    added = 0
    skipped = 0
    with app.app_context():
        for m in majors:
            exists = UniversityMajor.query.filter_by(
                name=m['name'], university=m['university']
            ).first()
            if exists:
                skipped += 1
                continue
            major = UniversityMajor(
                name=m['name'],
                university=m['university'],
                faculty=m.get('faculty', ''),
                major_group=m.get('major_group', ''),
                description=m.get('description', ''),
                created_at=datetime.datetime.utcnow(),
            )
            db.session.add(major)
            db.session.flush()
            for w in m.get('weights', []):
                db.session.add(MajorSubjectWeight(
                    major_id=major.id,
                    subject_name=w['subject_name'],
                    weight=float(w['weight']),
                    min_score=float(w['min_score']),
                ))
            added += 1
        db.session.commit()
    print(f"Done: {added} added, {skipped} skipped.")


if __name__ == '__main__':
    seed()
```

- [ ] **Step 3: Chạy seed script**

```bash
cd "/Users/dat_macbook/Documents/2025/ý tưởng mới/Hỗ trợ Yên Bái nhận diện khuôn mặt/EduMind-AI"
venv/bin/python seed_majors.py
```

Expected: `Done: 8 added, 0 skipped.`

- [ ] **Step 4: Commit**

```bash
git add data/majors_seed.json seed_majors.py
git commit -m "feat: add majors seed data and import script"
```

---

## Task 6: Template — Trang chính

**Files:**
- Create: `templates/student_career.html`

- [ ] **Step 1: Tạo student_career.html**

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Định hướng chọn ngành - EduMind AI</title>
  <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script>
    tailwind.config = { theme: { extend: { fontFamily: { sans: ['"Be Vietnam Pro"', 'system-ui'] } } } }
  </script>
  <style>
    body { background: #f5f5f5; font-family: "Be Vietnam Pro", system-ui, sans-serif; }
    .card { background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; }
    .status-ok { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; border-radius: 4px; padding: 1px 8px; font-size: 11px; font-weight: 500; }
    .status-warn { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; border-radius: 4px; padding: 1px 8px; font-size: 11px; font-weight: 500; }
    .status-fail { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; border-radius: 4px; padding: 1px 8px; font-size: 11px; font-weight: 500; }
  </style>
</head>
<body class="min-h-screen">

  <!-- Navbar -->
  <nav class="bg-white border-b border-gray-200 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <a href="{{ url_for('student.student_dashboard') }}" class="text-gray-500 hover:text-gray-800 text-sm">
          <i class="fas fa-arrow-left mr-1"></i>Quay lại
        </a>
        <span class="text-gray-300">|</span>
        <span class="font-semibold text-gray-800">Định hướng chọn ngành</span>
      </div>
      <span class="text-sm text-gray-500">{{ student.name }} · {{ student.student_class }}</span>
    </div>
  </nav>

  <div class="max-w-7xl mx-auto px-4 py-6">
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">

      <!-- LEFT: Radar panel (2/3) -->
      <div class="lg:col-span-2 card overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <span class="text-xs font-medium text-gray-400 uppercase tracking-wide">Biểu đồ năng lực</span>
          <a href="{{ url_for('career.career_browse') }}" class="text-xs text-indigo-600 hover:underline">
            Duyệt tất cả ngành <i class="fas fa-arrow-right ml-1"></i>
          </a>
        </div>

        <!-- Major selector -->
        <div class="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center gap-3">
          <span class="text-xs text-gray-400">Đang so sánh với</span>
          <select id="majorSelect" onchange="loadRadarData(this.value)"
            class="text-sm font-medium text-gray-800 bg-white border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-300">
            {% if default_major %}
            <option value="{{ default_major.id }}">{{ default_major.name }} — {{ default_major.university }}</option>
            {% endif %}
          </select>
          <button onclick="openMajorPicker()" class="text-xs text-indigo-600 hover:underline ml-auto">Đổi ngành</button>
        </div>

        <!-- Chart -->
        <div class="p-6 flex justify-center">
          <div style="max-width: 420px; width: 100%">
            <canvas id="radarChart"></canvas>
          </div>
        </div>

        <!-- Legend -->
        <div class="px-6 pb-5 flex gap-6 justify-center">
          <div class="flex items-center gap-2 text-xs text-gray-500">
            <span class="inline-block w-5 h-0.5 bg-indigo-600"></span>Điểm của bạn
          </div>
          <div class="flex items-center gap-2 text-xs text-gray-500">
            <span class="inline-block w-5 border-t-2 border-dashed border-orange-400"></span>Yêu cầu ngành
          </div>
        </div>
      </div>

      <!-- RIGHT: Sidebar (1/3) -->
      <div class="flex flex-col gap-4">

        <!-- Target major -->
        <div class="card overflow-hidden">
          <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <span class="text-xs font-medium text-gray-400 uppercase tracking-wide">Ngành mục tiêu</span>
            {% if target_data %}
            <span class="text-xs bg-indigo-50 text-indigo-600 border border-indigo-200 rounded px-2 py-0.5 font-medium">Đang theo dõi</span>
            {% endif %}
          </div>
          <div class="p-4">
            {% if target_data %}
            <div class="font-semibold text-gray-900 text-base">{{ target_data.major.name }}</div>
            <div class="text-xs text-gray-400 mt-0.5 mb-3">{{ target_data.major.university }}</div>
            <div class="flex items-baseline gap-2 mb-2">
              <span class="text-3xl font-bold text-gray-900" id="sidebarFitPct">{{ target_data.fit_pct }}</span>
              <span class="text-sm text-gray-400">% phù hợp</span>
            </div>
            <div class="h-1 bg-gray-100 rounded mb-4 overflow-hidden">
              <div class="h-full bg-indigo-500 rounded" style="width: {{ target_data.fit_pct }}%"></div>
            </div>
            <div class="flex flex-col gap-2" id="gapList">
              {% for g in target_data.gaps %}
              <div class="flex items-center justify-between bg-gray-50 border border-gray-100 rounded-md px-3 py-2">
                <span class="text-xs text-gray-500">{{ g.subject_name }}</span>
                <div class="flex items-center gap-2">
                  <span class="text-xs text-gray-800">{{ g.student_score }} <span class="text-gray-300">/ {{ g.min_score }}</span></span>
                  <span class="status-{{ g.status }}">
                    {% if g.status == 'ok' %}Đạt{% elif g.status == 'warn' %}{{ g.gap }}đ{% else %}{{ g.gap }}đ{% endif %}
                  </span>
                </div>
              </div>
              {% endfor %}
            </div>
            {% set worst = target_data.gaps | selectattr('status', 'ne', 'ok') | list %}
            {% if worst %}
            <div class="mt-3 bg-gray-50 border border-gray-100 rounded-md px-3 py-2 text-xs text-gray-500 leading-relaxed">
              Cải thiện <strong class="text-gray-800">{{ worst[0].subject_name }} thêm {{ (worst[0].gap * -1) | round(1) }} điểm</strong> để gần đạt điều kiện hơn.
            </div>
            {% endif %}
            <button onclick="openMajorPicker(true)"
              class="mt-3 w-full text-xs text-gray-400 hover:text-gray-600 border border-gray-200 rounded-md py-1.5">
              Đổi mục tiêu
            </button>
            {% else %}
            <p class="text-sm text-gray-400 text-center py-4">Chưa đặt ngành mục tiêu</p>
            <a href="{{ url_for('career.career_browse') }}"
              class="mt-2 block w-full text-center text-xs text-indigo-600 border border-indigo-200 rounded-md py-1.5 hover:bg-indigo-50">
              Chọn ngành mục tiêu
            </a>
            {% endif %}
          </div>
        </div>

        <!-- Pinned majors -->
        <div class="card overflow-hidden">
          <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <span class="text-xs font-medium text-gray-400 uppercase tracking-wide">Đã ghim</span>
            <a href="{{ url_for('career.career_browse') }}" class="text-xs text-indigo-600 hover:underline">+ Thêm ngành</a>
          </div>
          {% if pinned_data %}
          {% for p in pinned_data %}
          <div class="flex items-center justify-between px-4 py-3 border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
               onclick="loadRadarData({{ p.major.id }})">
            <div>
              <div class="text-sm font-medium text-gray-800">{{ p.major.name }}</div>
              <div class="text-xs text-gray-400">{{ p.major.university }}</div>
            </div>
            <div class="flex items-center gap-3 ml-3">
              <span class="text-sm font-semibold {% if p.fit_pct >= 80 %}text-green-600{% elif p.fit_pct >= 60 %}text-yellow-600{% else %}text-red-500{% endif %}">
                {{ p.fit_pct }}%
              </span>
              <div class="w-10 h-1 bg-gray-100 rounded overflow-hidden">
                <div class="h-full rounded {% if p.fit_pct >= 80 %}bg-green-500{% elif p.fit_pct >= 60 %}bg-yellow-500{% else %}bg-red-400{% endif %}"
                     style="width: {{ p.fit_pct }}%"></div>
              </div>
              <button onclick="event.stopPropagation(); unpinMajor({{ p.major.id }}, this)"
                class="text-gray-300 hover:text-red-400 text-xs"><i class="fas fa-times"></i></button>
            </div>
          </div>
          {% endfor %}
          {% else %}
          <div class="px-4 py-5 text-center text-sm text-gray-400">Chưa ghim ngành nào</div>
          {% endif %}
          <div class="px-4 py-3 text-center">
            <a href="{{ url_for('career.career_browse') }}" class="text-xs text-gray-400 hover:text-gray-600">
              + Duyệt 150 ngành khác
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>

<script>
const radarLabels = {{ radar_labels | tojson }};
const radarStudent = {{ radar_student | tojson }};
const radarMajor = {{ radar_major | tojson }};

const ctx = document.getElementById('radarChart').getContext('2d');
const radarChart = new Chart(ctx, {
  type: 'radar',
  data: {
    labels: radarLabels,
    datasets: [
      {
        label: 'Điểm của bạn',
        data: radarStudent,
        backgroundColor: 'rgba(79,70,229,0.12)',
        borderColor: '#4f46e5',
        borderWidth: 2,
        pointBackgroundColor: '#4f46e5',
        pointRadius: 4,
      },
      {
        label: 'Yêu cầu ngành',
        data: radarMajor,
        backgroundColor: 'rgba(249,115,22,0.07)',
        borderColor: '#f97316',
        borderWidth: 2,
        borderDash: [5, 4],
        pointBackgroundColor: '#f97316',
        pointRadius: 3,
      }
    ]
  },
  options: {
    responsive: true,
    scales: {
      r: {
        min: 0, max: 10,
        ticks: { stepSize: 2, font: { size: 10 }, color: '#9ca3af' },
        grid: { color: '#e5e7eb' },
        pointLabels: { font: { size: 12, family: 'Be Vietnam Pro' }, color: '#374151' },
        angleLines: { color: '#e5e7eb' },
      }
    },
    plugins: { legend: { display: false } }
  }
});

function loadRadarData(majorId) {
  fetch(`/api/student/career/radar-data?major_id=${majorId}`)
    .then(r => r.json())
    .then(d => {
      radarChart.data.labels = d.labels;
      radarChart.data.datasets[0].data = d.student_scores;
      radarChart.data.datasets[1].data = d.major_scores;
      radarChart.update();
    });
}

function unpinMajor(majorId, btn) {
  fetch(`/api/student/career/pin/${majorId}`, { method: 'DELETE' })
    .then(() => btn.closest('.flex.items-center.justify-between').remove());
}

function openMajorPicker(asTarget) {
  window.location.href = '{{ url_for("career.career_browse") }}' + (asTarget ? '?set_target=1' : '');
}
</script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add templates/student_career.html
git commit -m "feat: add student_career.html main page template"
```

---

## Task 7: Template — Browse page

**Files:**
- Create: `templates/student_career_browse.html`

- [ ] **Step 1: Tạo student_career_browse.html**

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Duyệt ngành - EduMind AI</title>
  <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script>tailwind.config = { theme: { extend: { fontFamily: { sans: ['"Be Vietnam Pro"', 'system-ui'] } } } }</script>
  <style>
    body { background: #f5f5f5; font-family: "Be Vietnam Pro", system-ui, sans-serif; }
    .card { background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; overflow: hidden; }
    .major-card { cursor: pointer; transition: border-color 0.15s; }
    .major-card:hover { border-color: #a5b4fc; }
    .major-card.is-target { border-color: #6366f1; }
  </style>
</head>
<body class="min-h-screen">

  <nav class="bg-white border-b border-gray-200 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 h-14 flex items-center gap-3">
      <a href="{{ url_for('career.career_main') }}" class="text-gray-500 hover:text-gray-800 text-sm">
        <i class="fas fa-arrow-left mr-1"></i>Quay lại
      </a>
      <span class="text-gray-300">|</span>
      <span class="font-semibold text-gray-800">Duyệt tất cả ngành</span>
    </div>
  </nav>

  <div class="max-w-7xl mx-auto px-4 py-5">

    <!-- Filter bar -->
    <div class="card px-4 py-3 mb-5 flex flex-wrap gap-3 items-center">
      <input id="searchInput" type="text" placeholder="Tìm ngành, trường..."
        class="flex-1 min-w-48 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-300"
        oninput="debounceLoad()">
      <select id="groupFilter" onchange="loadMajors()"
        class="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none">
        <option value="">Tất cả nhóm ngành</option>
        {% for g in groups %}<option>{{ g }}</option>{% endfor %}
      </select>
      <select id="fitFilter" onchange="loadMajors()"
        class="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none">
        <option value="0">Mọi mức fit</option>
        <option value="60">&gt; 60%</option>
        <option value="70">&gt; 70%</option>
        <option value="80">&gt; 80%</option>
      </select>
      <span id="resultCount" class="text-xs text-gray-400 ml-auto"></span>
    </div>

    <!-- Cards grid -->
    <div id="cardsGrid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      <div class="col-span-full text-center py-12 text-gray-400 text-sm">Đang tải...</div>
    </div>
  </div>

<script>
const setTarget = new URLSearchParams(window.location.search).get('set_target') === '1';
let debounceTimer;
let chartInstances = {};

function debounceLoad() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadMajors, 350);
}

function loadMajors() {
  const q = document.getElementById('searchInput').value;
  const group = document.getElementById('groupFilter').value;
  const minFit = document.getElementById('fitFilter').value;
  const url = `/api/student/career/browse?q=${encodeURIComponent(q)}&group=${encodeURIComponent(group)}&min_fit=${minFit}`;

  fetch(url).then(r => r.json()).then(data => {
    const grid = document.getElementById('cardsGrid');
    document.getElementById('resultCount').textContent = `${data.majors.length} ngành`;

    if (data.majors.length === 0) {
      grid.innerHTML = '<div class="col-span-full text-center py-12 text-gray-400 text-sm">Không tìm thấy ngành phù hợp</div>';
      return;
    }

    // Destroy old charts
    Object.values(chartInstances).forEach(c => c.destroy());
    chartInstances = {};

    grid.innerHTML = data.majors.map(m => `
      <div class="card major-card ${m.is_target ? 'is-target' : ''}" id="card-${m.id}">
        <div class="p-4 pb-2">
          <div class="flex items-start justify-between gap-2 mb-1">
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-gray-900 text-sm truncate">${m.name}</div>
              <div class="text-xs text-gray-400 truncate">${m.university}</div>
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-lg font-bold ${m.fit_pct >= 80 ? 'text-green-600' : m.fit_pct >= 60 ? 'text-yellow-600' : 'text-red-500'}">${m.fit_pct}%</div>
              <div class="text-xs text-gray-300">${m.major_group || ''}</div>
            </div>
          </div>
        </div>
        <div class="px-4 pb-1" style="height:160px">
          <canvas id="chart-${m.id}"></canvas>
        </div>
        <div class="px-3 pb-3 flex gap-2 mt-1">
          <button onclick="pinMajor(${m.id}, this)" data-pinned="${m.is_pinned}"
            class="flex-1 text-xs py-1.5 rounded-md border ${m.is_pinned ? 'bg-indigo-50 text-indigo-600 border-indigo-200' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}">
            <i class="fas fa-thumbtack mr-1"></i>${m.is_pinned ? 'Đã ghim' : 'Ghim'}
          </button>
          <button onclick="setTargetMajor(${m.id}, this)" data-target="${m.is_target}"
            class="flex-1 text-xs py-1.5 rounded-md border ${m.is_target ? 'bg-indigo-600 text-white border-indigo-600' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}">
            <i class="fas fa-crosshairs mr-1"></i>${m.is_target ? 'Mục tiêu' : 'Đặt mục tiêu'}
          </button>
        </div>
      </div>
    `).join('');

    // Render mini radars
    data.majors.forEach(m => {
      const canvas = document.getElementById(`chart-${m.id}`);
      if (!canvas) return;
      chartInstances[m.id] = new Chart(canvas.getContext('2d'), {
        type: 'radar',
        data: {
          labels: m.radar.labels,
          datasets: [
            { data: m.radar.student_scores, backgroundColor: 'rgba(79,70,229,0.15)', borderColor: '#4f46e5', borderWidth: 1.5, pointRadius: 2 },
            { data: m.radar.major_scores, backgroundColor: 'rgba(249,115,22,0.07)', borderColor: '#f97316', borderWidth: 1.5, borderDash: [4,3], pointRadius: 2 }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: { r: { min: 0, max: 10, ticks: { display: false }, grid: { color: '#e5e7eb' }, pointLabels: { font: { size: 9 }, color: '#9ca3af' }, angleLines: { color: '#e5e7eb' } } },
          plugins: { legend: { display: false } }
        }
      });
    });
  });
}

function pinMajor(majorId, btn) {
  const isPinned = btn.dataset.pinned === 'true';
  if (isPinned) {
    fetch(`/api/student/career/pin/${majorId}`, { method: 'DELETE' })
      .then(() => { btn.dataset.pinned = 'false'; btn.className = 'flex-1 text-xs py-1.5 rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50'; btn.innerHTML = '<i class="fas fa-thumbtack mr-1"></i>Ghim'; });
  } else {
    fetch('/api/student/career/pin', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({major_id: majorId}) })
      .then(() => { btn.dataset.pinned = 'true'; btn.className = 'flex-1 text-xs py-1.5 rounded-md border bg-indigo-50 text-indigo-600 border-indigo-200'; btn.innerHTML = '<i class="fas fa-thumbtack mr-1"></i>Đã ghim'; });
  }
}

function setTargetMajor(majorId, btn) {
  fetch('/api/student/career/target', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({major_id: majorId}) })
    .then(() => {
      document.querySelectorAll('[data-target="true"]').forEach(b => {
        b.dataset.target = 'false';
        b.className = 'flex-1 text-xs py-1.5 rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50';
        b.innerHTML = '<i class="fas fa-crosshairs mr-1"></i>Đặt mục tiêu';
      });
      btn.dataset.target = 'true';
      btn.className = 'flex-1 text-xs py-1.5 rounded-md border bg-indigo-600 text-white border-indigo-600';
      btn.innerHTML = '<i class="fas fa-crosshairs mr-1"></i>Mục tiêu';
      if (setTarget) window.location.href = '{{ url_for("career.career_main") }}';
    });
}

loadMajors();
</script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add templates/student_career_browse.html
git commit -m "feat: add student_career_browse.html chart-view browse template"
```

---

## Task 8: Dashboard Navigation — Tab thứ 3

**Files:**
- Modify: `templates/student_dashboard.html`

- [ ] **Step 1: Thêm tab thứ 3 vào navigation (dòng ~197-204)**

Tìm đoạn:
```html
<div class="flex gap-2 mb-4">
    <button onclick="switchTab('pills-home')" id="pills-home-tab" class="flex-1 px-4 py-2.5 ...">
        <i class="fas fa-chart-line mr-2"></i>Học Tập & Rèn Luyện
    </button>
    <button onclick="switchTab('pills-chat')" id="pills-chat-tab" class="flex-1 px-4 py-2.5 ...">
        <i class="fas fa-comments mr-2"></i>Trợ lý AI & Chatbot
    </button>
</div>
```

Thêm nút thứ 3 sau nút Chatbot:

```html
    <a href="{{ url_for('career.career_main') }}"
       class="flex-1 px-4 py-2.5 text-sm font-medium rounded-lg transition-all bg-white text-slate-600 hover:bg-slate-50 border border-slate-200 text-center">
        <i class="fas fa-compass mr-2"></i>Định hướng chọn ngành
    </a>
```

> Dùng `<a>` thay `<button>` vì đây là link sang trang riêng.

- [ ] **Step 2: Commit**

```bash
git add templates/student_dashboard.html
git commit -m "feat: add career guidance nav button to student dashboard"
```

---

## Task 9: Admin Template

**Files:**
- Create: `templates/admin_majors.html`

- [ ] **Step 1: Tạo admin_majors.html**

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>Quản lý ngành - Admin</title>
  <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script>tailwind.config = { theme: { extend: { fontFamily: { sans: ['"Be Vietnam Pro"', 'system-ui'] } } } }</script>
</head>
<body class="bg-gray-50 font-sans min-h-screen p-6">
  <div class="max-w-5xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-semibold text-gray-900">Quản lý ngành đại học</h1>
      <button onclick="document.getElementById('addModal').classList.remove('hidden')"
        class="bg-indigo-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-indigo-700">
        + Thêm ngành
      </button>
    </div>

    <div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b border-gray-200">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ngành</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trường</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Nhóm</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Số môn</th>
            <th class="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          {% for m in majors %}
          <tr>
            <td class="px-4 py-3 font-medium text-gray-900">{{ m.name }}</td>
            <td class="px-4 py-3 text-gray-500">{{ m.university }}</td>
            <td class="px-4 py-3 text-gray-500">{{ m.major_group or '—' }}</td>
            <td class="px-4 py-3 text-gray-500">{{ m.weights | length }}</td>
            <td class="px-4 py-3 text-right">
              <button onclick="deleteMajor({{ m.id }}, this)"
                class="text-xs text-red-500 hover:text-red-700 border border-red-200 rounded px-2 py-1">
                Xóa
              </button>
            </td>
          </tr>
          {% else %}
          <tr><td colspan="5" class="px-4 py-8 text-center text-gray-400">Chưa có ngành nào. Chạy seed_majors.py để import dữ liệu.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Add modal -->
  <div id="addModal" class="hidden fixed inset-0 bg-black/40 flex items-center justify-center z-50">
    <div class="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
      <h2 class="font-semibold text-gray-900 mb-4">Thêm ngành mới</h2>
      <div class="flex flex-col gap-3">
        <input id="mName" placeholder="Tên ngành *" class="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
        <input id="mUniversity" placeholder="Trường *" class="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
        <input id="mFaculty" placeholder="Khoa/Viện" class="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
        <input id="mGroup" placeholder="Nhóm ngành (VD: Kỹ thuật - Công nghệ)" class="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
        <div>
          <div class="text-xs font-medium text-gray-500 mb-2">Môn học & Trọng số</div>
          <div id="weightRows" class="flex flex-col gap-2">
            <div class="flex gap-2">
              <input placeholder="Tên môn" class="w-name flex-1 border border-gray-200 rounded px-2 py-1.5 text-xs">
              <input placeholder="Trọng số (0-1)" class="w-weight w-24 border border-gray-200 rounded px-2 py-1.5 text-xs">
              <input placeholder="Điểm yêu cầu" class="w-score w-28 border border-gray-200 rounded px-2 py-1.5 text-xs">
            </div>
          </div>
          <button onclick="addWeightRow()" class="mt-2 text-xs text-indigo-600 hover:underline">+ Thêm môn</button>
        </div>
      </div>
      <div class="flex gap-3 mt-5">
        <button onclick="document.getElementById('addModal').classList.add('hidden')"
          class="flex-1 text-sm text-gray-500 border border-gray-200 rounded-lg py-2 hover:bg-gray-50">Hủy</button>
        <button onclick="submitMajor()"
          class="flex-1 text-sm bg-indigo-600 text-white rounded-lg py-2 hover:bg-indigo-700">Lưu</button>
      </div>
    </div>
  </div>

<script>
function addWeightRow() {
  const row = document.createElement('div');
  row.className = 'flex gap-2';
  row.innerHTML = `
    <input placeholder="Tên môn" class="w-name flex-1 border border-gray-200 rounded px-2 py-1.5 text-xs">
    <input placeholder="Trọng số (0-1)" class="w-weight w-24 border border-gray-200 rounded px-2 py-1.5 text-xs">
    <input placeholder="Điểm yêu cầu" class="w-score w-28 border border-gray-200 rounded px-2 py-1.5 text-xs">
  `;
  document.getElementById('weightRows').appendChild(row);
}

function submitMajor() {
  const weights = [];
  document.querySelectorAll('#weightRows .flex').forEach(row => {
    const name = row.querySelector('.w-name').value.trim();
    const weight = parseFloat(row.querySelector('.w-weight').value);
    const score = parseFloat(row.querySelector('.w-score').value);
    if (name && !isNaN(weight) && !isNaN(score)) weights.push({ subject_name: name, weight, min_score: score });
  });
  fetch('/admin/majors/add', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      name: document.getElementById('mName').value,
      university: document.getElementById('mUniversity').value,
      faculty: document.getElementById('mFaculty').value,
      major_group: document.getElementById('mGroup').value,
      weights
    })
  }).then(() => window.location.reload());
}

function deleteMajor(id, btn) {
  if (!confirm('Xóa ngành này?')) return;
  fetch(`/admin/majors/${id}`, { method: 'DELETE' }).then(() => btn.closest('tr').remove());
}
</script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add templates/admin_majors.html
git commit -m "feat: add admin_majors.html management template"
```

---

## Task 10: Inject Mock Student Grades

**Files:**
- Create: `seed_grades.py`

- [ ] **Step 1: Tạo seed_grades.py để inject điểm test**

```python
#!/usr/bin/env python3
"""
Inject mock grades vào DB cho 1 học sinh test.
Chạy: venv/bin/python seed_grades.py <student_id>
VD:   venv/bin/python seed_grades.py 1
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from app import app
from models import db, Grade, Subject, SystemConfig
import datetime

MOCK_SCORES = {
    # subject_name: (avg_TX, avg_GK, avg_HK)
    'Toán':        (7.0, 7.5, 7.8),
    'Vật lý':      (8.0, 8.2, 8.5),
    'Hóa học':     (6.0, 6.2, 6.5),
    'Sinh học':    (5.5, 5.8, 6.0),
    'Ngữ văn':     (7.5, 7.0, 7.2),
    'Tiếng Anh':   (8.5, 8.3, 8.8),
    'Lịch sử':     (7.0, 7.0, 7.5),
    'Địa lý':      (7.2, 7.0, 7.3),
    'GDCD':        (8.0, 8.0, 8.5),
}


def seed_grades(student_id):
    with app.app_context():
        configs = {c.key: c.value for c in SystemConfig.query.all()}
        semester = int(configs.get('current_semester', '1'))
        school_year = configs.get('school_year', '2025-2026')

        for subject_name, (tx, gk, hk) in MOCK_SCORES.items():
            subject = Subject.query.filter_by(name=subject_name).first()
            if not subject:
                print(f"  Skip (subject not found): {subject_name}")
                continue

            # Skip if already has grades
            existing = Grade.query.filter_by(
                student_id=student_id, subject_id=subject.id,
                semester=semester, school_year=school_year
            ).first()
            if existing:
                print(f"  Skip (already exists): {subject_name}")
                continue

            for grade_type, score in [('TX', tx), ('GK', gk), ('HK', hk)]:
                db.session.add(Grade(
                    student_id=student_id,
                    subject_id=subject.id,
                    grade_type=grade_type,
                    column_index=1,
                    score=score,
                    semester=semester,
                    school_year=school_year,
                    date_recorded=datetime.datetime.utcnow(),
                ))
            print(f"  Added: {subject_name} TX={tx} GK={gk} HK={hk}")

        db.session.commit()
        print("Done.")


if __name__ == '__main__':
    sid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    seed_grades(sid)
```

- [ ] **Step 2: Xem student_id hiện có**

```bash
cd "/Users/dat_macbook/Documents/2025/ý tưởng mới/Hỗ trợ Yên Bái nhận diện khuôn mặt/EduMind-AI"
venv/bin/python -c "from app import app; from models import Student
with app.app_context():
    students = Student.query.limit(5).all()
    [print(s.id, s.name, s.student_class) for s in students]"
```

- [ ] **Step 3: Chạy seed grades**

```bash
venv/bin/python seed_grades.py <student_id_từ_bước_trên>
```

Expected: mỗi môn in `Added: <tên môn> TX=... GK=... HK=...`

- [ ] **Step 4: Commit**

```bash
git add seed_grades.py
git commit -m "feat: add seed_grades.py for injecting test student grades"
```

---

## Task 11: Smoke Test End-to-End

- [ ] **Step 1: Chạy toàn bộ unit tests**

```bash
cd "/Users/dat_macbook/Documents/2025/ý tưởng mới/Hỗ trợ Yên Bái nhận diện khuôn mặt/EduMind-AI"
venv/bin/pytest tests/test_career.py -v
```

Expected: `4 passed`

- [ ] **Step 2: Khởi động app**

```bash
FLASK_APP=app.py venv/bin/flask run --port 5001
```

- [ ] **Step 3: Kiểm tra các URLs**

Mở browser:
- `http://localhost:5001/student/login` → đăng nhập bằng tài khoản học sinh test
- `http://localhost:5001/student/career` → trang chính: phải hiện radar + sidebar
- `http://localhost:5001/student/career/browse` → duyệt ngành: cards với mini radar
- `http://localhost:5001/admin/majors` → (đăng nhập admin) danh sách ngành

- [ ] **Step 4: Test API thủ công**

```bash
# Cần có session cookie — dùng curl với session sau khi login qua browser
# Hoặc dùng browser DevTools để gọi:
# GET /api/student/career/browse → phải trả JSON với majors array
# GET /api/student/career/radar-data?major_id=1 → labels, student_scores, major_scores
```

- [ ] **Step 5: Commit tổng kết**

```bash
git add .
git commit -m "feat: career guidance feature complete — radar chart, browse, pin, target"
```

---

## Checklist spec coverage

| Spec section | Task |
|---|---|
| Navigation — tab thứ 3 | Task 8 |
| Trang `/student/career` split layout | Task 6 |
| Radar overlay 2 lớp | Task 6 (Chart.js) |
| Dropdown đổi ngành realtime | Task 6 (JS loadRadarData) |
| Sidebar target: gap analysis + state banner | Task 6 |
| Sidebar pinned: list + click load radar | Task 6 |
| Trang browse — chart view only | Task 7 |
| Browse: sort fit %, filter, search | Task 7 + Task 4 API |
| Browse: nút Ghim + Đặt mục tiêu | Task 7 |
| Fit % formula capped | Task 3 (calculate_fit_score) |
| 4 DB models mới | Task 1 |
| Migration | Task 2 |
| Seed 150 ngành | Task 5 |
| Mock grades inject | Task 10 |
| Admin `/admin/majors` | Task 4 + Task 9 |
| 6 API endpoints | Task 4 |
