import random
from app import app
from models import db, Student, Subject, Grade

subjects_data = [
    {"name": "Toán học", "code": "TOAN", "description": "Môn Toán"},
    {"name": "Vật lý", "code": "LY", "description": "Môn Lý"},
    {"name": "Hóa học", "code": "HOA", "description": "Môn Hóa"},
    {"name": "Ngữ văn", "code": "VAN", "description": "Môn Văn"},
    {"name": "Tiếng Anh", "code": "ANH", "description": "Môn Anh văn"},
    {"name": "Sinh học", "code": "SINH", "description": "Môn Sinh"},
    {"name": "Lịch sử", "code": "SU", "description": "Môn Sử"},
    {"name": "Địa lý", "code": "DIA", "description": "Môn Địa"},
    {"name": "Giáo dục công dân", "code": "GDCD", "description": "Môn GDCD"},
    {"name": "Thể dục", "code": "TD", "description": "Môn Thể dục"}
]

def run():
    with app.app_context():
        # create subjects
        for sub in subjects_data:
            subject = Subject.query.filter_by(code=sub['code']).first()
            if not subject:
                subject = Subject(
                    name=sub['name'],
                    code=sub['code'],
                    description=sub['description'],
                    num_tx_columns=3,
                    num_gk_columns=1,
                    num_hk_columns=1
                )
                db.session.add(subject)
        db.session.commit()

        subjects = Subject.query.all()
        students = Student.query.all()
        
        # Optionally, clear existing grades to avoid duplication
        Grade.query.delete()
        db.session.commit()

        print(f"Bắt đầu tạo điểm cho {len(students)} học sinh và {len(subjects)} môn học...")

        count = 0
        for student in students:
            for subject in subjects:
                # create TX (Thường xuyên)
                for i in range(subject.num_tx_columns):
                    grade = Grade(
                        student_id=student.id,
                        subject_id=subject.id,
                        grade_type="TX",
                        column_index=i+1,
                        score=round(random.uniform(4.0, 10.0), 1),
                        semester=1,
                        school_year="2025-2026"
                    )
                    db.session.add(grade)
                    count += 1
                
                # create GK (Giữa kỳ)
                for i in range(subject.num_gk_columns):
                    grade = Grade(
                        student_id=student.id,
                        subject_id=subject.id,
                        grade_type="GK",
                        column_index=i+1,
                        score=round(random.uniform(4.0, 10.0), 1),
                        semester=1,
                        school_year="2025-2026"
                    )
                    db.session.add(grade)
                    count += 1
                
                # create HK (Cuối kỳ)
                for i in range(subject.num_hk_columns):
                    grade = Grade(
                        student_id=student.id,
                        subject_id=subject.id,
                        grade_type="HK",
                        column_index=i+1,
                        score=round(random.uniform(4.0, 10.0), 1),
                        semester=1,
                        school_year="2025-2026"
                    )
                    db.session.add(grade)
                    count += 1

        db.session.commit()
        print(f"Đã tạo thành công {count} bản ghi điểm.")

if __name__ == '__main__':
    run()
