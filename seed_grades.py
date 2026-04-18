"""Inject mock grades for all students so the career feature has data to display.

Scores are realistic for a mid-performing student:
  Toán: 7.5  Văn: 7.0  Anh: 7.0  Lý: 6.5  Hóa: 6.0
  Sinh: 6.0  Sử: 6.5  Địa: 7.0  GDCD: 8.0

Run: python seed_grades.py [--student-id 1]
"""
import sys
import os
import datetime

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

from app import app
from models import db, Student, Subject, Grade, SystemConfig


SUBJECT_SCORES = {
    'Toán':  {'TX': 7.5, 'GK': 7.5, 'HK': 7.5},
    'Văn':   {'TX': 7.0, 'GK': 7.0, 'HK': 7.0},
    'Anh':   {'TX': 7.0, 'GK': 7.0, 'HK': 7.0},
    'Lý':    {'TX': 6.5, 'GK': 6.5, 'HK': 6.5},
    'Hóa':   {'TX': 6.0, 'GK': 6.0, 'HK': 6.0},
    'Sinh':  {'TX': 6.0, 'GK': 6.0, 'HK': 6.0},
    'Sử':    {'TX': 6.5, 'GK': 6.5, 'HK': 6.5},
    'Địa':   {'TX': 7.0, 'GK': 7.0, 'HK': 7.0},
    'GDCD':  {'TX': 8.0, 'GK': 8.0, 'HK': 8.0},
}


def ensure_subject(name, class_name='10A1'):
    s = Subject.query.filter_by(name=name).first()
    if not s:
        s = Subject(name=name, class_name=class_name, coefficient=1)
        db.session.add(s)
        db.session.flush()
    return s


def seed_student(student, semester, school_year):
    added = 0
    for subj_name, scores in SUBJECT_SCORES.items():
        subj = ensure_subject(subj_name, student.class_name or '10A1')
        for grade_type, score in scores.items():
            exists = Grade.query.filter_by(
                student_id=student.id, subject_id=subj.id,
                grade_type=grade_type, semester=semester, school_year=school_year
            ).first()
            if not exists:
                db.session.add(Grade(
                    student_id=student.id, subject_id=subj.id,
                    grade_type=grade_type, column_index=1,
                    score=score, semester=semester, school_year=school_year,
                    date_recorded=datetime.datetime.utcnow(),
                ))
                added += 1
    return added


def main():
    target_id = None
    if '--student-id' in sys.argv:
        idx = sys.argv.index('--student-id')
        target_id = int(sys.argv[idx + 1])

    with app.app_context():
        configs = {c.key: c.value for c in SystemConfig.query.all()}
        semester = int(configs.get('current_semester', '1'))
        school_year = configs.get('school_year', '2025-2026')

        if target_id:
            students = [Student.query.get(target_id)]
            if not students[0]:
                print(f'Student {target_id} not found.')
                return
        else:
            students = Student.query.all()
            if not students:
                print('No students in DB. Add a student first via the admin panel.')
                return

        total = 0
        for s in students:
            n = seed_student(s, semester, school_year)
            total += n
            print(f'  [{s.student_id}] {s.name}: {n} grade rows added')

        db.session.commit()
        print(f'\nDone. {total} grade records inserted (semester={semester}, year={school_year}).')


if __name__ == '__main__':
    main()
