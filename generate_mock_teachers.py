from app import app
from models import db, Teacher, ClassRoom, Subject

def run():
    with app.app_context():
        # Kiểm tra và tạo Admin
        admin = Teacher.query.filter_by(username='admin').first()
        if not admin:
            admin = Teacher(username='admin', full_name='Trần Quản Trị', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            print("Đã tạo tài khoản admin: admin / admin123")
        
        classes = ClassRoom.query.all()
        subjects = Subject.query.all()
        
        count_gvcn = 0
        count_gvbm = 0
        
        # Tạo Giáo viên chủ nhiệm (mỗi lớp 1 GVCN)
        for c in classes:
            # Ví dụ: lớp 12A1 -> gvcn_12a1
            username = f'gvcn_{c.name.lower().replace(" ", "").replace("-", "")}'
            gv = Teacher.query.filter_by(username=username).first()
            if not gv:
                gv = Teacher(
                    username=username,
                    full_name=f'GVCN {c.name}',
                    role='homeroom_teacher',
                    assigned_class=c.name
                )
                gv.set_password('123456')
                db.session.add(gv)
                count_gvcn += 1
                
        # Tạo Giáo viên bộ môn (mỗi môn 3 GVBM)
        for s in subjects:
            for i in range(1, 4):
                username = f'gvbm_{s.code.lower()}_{i}'
                gv = Teacher.query.filter_by(username=username).first()
                if not gv:
                    gv = Teacher(
                        username=username,
                        full_name=f'Giáo viên {s.name} {i}',
                        role='subject_teacher',
                        assigned_subject_id=s.id
                    )
                    gv.set_password('123456')
                    db.session.add(gv)
                    count_gvbm += 1

        db.session.commit()
        print(f"Bổ sung thành công {count_gvcn} tài khoản GVCN và {count_gvbm} tài khoản GVBM.")
        print("Mật khẩu mặc định cho GVCN và GVBM là: 123456")

if __name__ == '__main__':
    run()
