import random
import datetime
from app import app
from models import db, Student, ViolationType, Violation, BonusType, BonusRecord

violation_types_data = [
    {"name": "Đi học muộn", "points_deducted": 5},
    {"name": "Không thuộc bài cũ", "points_deducted": 10},
    {"name": "Sử dụng điện thoại trong lớp", "points_deducted": 15},
    {"name": "Chửi bậy, đánh nhau", "points_deducted": 30},
    {"name": "Không mặc đồng phục", "points_deducted": 5},
    {"name": "Làm ồn trong lớp", "points_deducted": 5}
]

bonus_types_data = [
    {"name": "Phát biểu xây dựng bài", "points_added": 2, "description": "Tích cực giơ tay"},
    {"name": "Đạt điểm 10", "points_added": 5, "description": "Kiểm tra được 10 điểm"},
    {"name": "Giúp đỡ bạn bè", "points_added": 5, "description": "Hỗ trợ bạn học yếu"},
    {"name": "Nhặt được của rơi", "points_added": 10, "description": "Trả lại đồ bị mất"},
    {"name": "Hoạt động phong trào", "points_added": 5, "description": "Tham gia tích cực"}
]

def run():
    with app.app_context():
        # Create ViolationTypes if not exist
        for v_data in violation_types_data:
            vt = ViolationType.query.filter_by(name=v_data['name']).first()
            if not vt:
                vt = ViolationType(name=v_data['name'], points_deducted=v_data['points_deducted'])
                db.session.add(vt)
        
        # Create BonusTypes if not exist
        for b_data in bonus_types_data:
            bt = BonusType.query.filter_by(name=b_data['name']).first()
            if not bt:
                bt = BonusType(name=b_data['name'], points_added=b_data['points_added'], description=b_data['description'])
                db.session.add(bt)
                
        db.session.commit()

        v_types = ViolationType.query.all()
        b_types = BonusType.query.all()
        students = Student.query.all()

        print(f"Bắt đầu tạo vi phạm và điểm cộng ảo cho {len(students)} học sinh...")
        
        # Optionally delete old violations and bonus records
        Violation.query.delete()
        BonusRecord.query.delete()
        
        # Reset score to 100 before applying random modifications
        for s in students:
            s.current_score = 100
            
        db.session.commit()

        v_count = 0
        b_count = 0
        
        base_date = datetime.datetime.now()
        
        for student in students:
            # 0-3 violations per student
            num_violations = random.randint(0, 3)
            for _ in range(num_violations):
                vt = random.choice(v_types)
                days_ago = random.randint(0, 21)
                v_date = base_date - datetime.timedelta(days=days_ago)
                week_no = v_date.isocalendar()[1]
                
                v = Violation(
                    student_id=student.id,
                    violation_type_name=vt.name,
                    points_deducted=vt.points_deducted,
                    date_committed=v_date,
                    week_number=week_no
                )
                db.session.add(v)
                student.current_score -= vt.points_deducted
                v_count += 1
                
            # 0-3 bonuses per student
            num_bonuses = random.randint(0, 3)
            for _ in range(num_bonuses):
                bt = random.choice(b_types)
                days_ago = random.randint(0, 21)
                b_date = base_date - datetime.timedelta(days=days_ago)
                week_no = b_date.isocalendar()[1]
                
                br = BonusRecord(
                    student_id=student.id,
                    bonus_type_name=bt.name,
                    points_added=bt.points_added,
                    reason=f"Nhận điểm cộng: {bt.name}",
                    date_awarded=b_date,
                    week_number=week_no
                )
                db.session.add(br)
                student.current_score += bt.points_added
                b_count += 1

        db.session.commit()
        print(f"Đã tạo {v_count} vi phạm và {b_count} điểm cộng. Cập nhật current_score thành công.")

if __name__ == '__main__':
    run()
