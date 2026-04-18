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
