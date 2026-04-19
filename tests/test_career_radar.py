"""Tests for routes.career._radar() — radar labels must be union of student + major."""
import pytest
from app import app
from models import db, UniversityMajor, MajorSubjectWeight


@pytest.fixture
def sample_major():
    with app.app_context():
        m = UniversityMajor(name="Test Major Radar", university="Test Uni Radar",
                            major_group="Kỹ thuật - Công nghệ", admission_block="A01",
                            entry_score=27.0)
        db.session.add(m)
        db.session.flush()
        db.session.add_all([
            MajorSubjectWeight(major_id=m.id, subject_name="Toán", weight=0.30, min_score=9.2),
            MajorSubjectWeight(major_id=m.id, subject_name="Vật lý", weight=0.30, min_score=8.9),
            MajorSubjectWeight(major_id=m.id, subject_name="Ngoại ngữ", weight=0.30, min_score=8.9),
            MajorSubjectWeight(major_id=m.id, subject_name="Hóa học", weight=0.03, min_score=6.0),
            MajorSubjectWeight(major_id=m.id, subject_name="Ngữ văn", weight=0.0, min_score=3.5),
        ])
        db.session.commit()
        yield m
        MajorSubjectWeight.query.filter_by(major_id=m.id).delete()
        db.session.delete(m)
        db.session.commit()


def test_radar_union_includes_core_when_student_has_no_grades(sample_major):
    from routes.career import _radar
    with app.app_context():
        labels, stu, maj, _ = _radar(sample_major.id, {})
    assert set(labels) >= {"Toán", "Vật lý", "Ngoại ngữ", "Hóa học"}, f"got {labels}"
    assert "Ngữ văn" not in labels
    assert all(s == 0.0 for s in stu)


def test_radar_union_includes_student_subjects_outside_weights(sample_major):
    from routes.career import _radar
    with app.app_context():
        averages = {"Toán": 8.0, "Sinh học": 7.5, "Lịch sử": 6.0}
        labels, stu, maj, _ = _radar(sample_major.id, averages)
    assert "Sinh học" in labels
    assert "Lịch sử" in labels
    assert stu[labels.index("Sinh học")] == 7.5
    assert maj[labels.index("Sinh học")] == 0.0
