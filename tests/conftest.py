import os
# CRITICAL: force :memory: DB BEFORE importing app. app.py reads EDUMIND_DB_URI
# from env at module load. Previously conftest mutated config AFTER app loaded,
# so the Flask-SQLAlchemy engine stayed bound to production database.db and
# drop_all() at teardown wiped real data.
os.environ['EDUMIND_DB_URI'] = 'sqlite:///:memory:'

import pytest
from app import app as flask_app
from models import db as _db, UniversityMajor, MajorSubjectWeight, MajorEntryScore, Student
import datetime


def _assert_memory_db():
    url = str(_db.engine.url)
    if ':memory:' not in url:
        raise RuntimeError(
            f"REFUSING to run tests against non-memory DB: {url}. "
            "Set EDUMIND_DB_URI=sqlite:///:memory: before importing app."
        )


@pytest.fixture(scope='session')
def app():
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    with flask_app.app_context():
        _assert_memory_db()
        _db.create_all()
        _seed_test_data()
        yield flask_app
        _assert_memory_db()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def student_session(client, app):
    with app.app_context():
        s = Student.query.filter_by(student_code='TS001').first()
        with client.session_transaction() as sess:
            sess['student_id'] = s.id
    return client


def _seed_test_data():
    from werkzeug.security import generate_password_hash
    student = Student(
        name='Học Sinh Test',
        student_code='TS001',
        student_class='12A1',
        password=generate_password_hash('password'),
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
