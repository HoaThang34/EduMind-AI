import os
from app import app, db
from models import Teacher, SystemConfig, ViolationType, Subject, ClassRoom
from werkzeug.security import generate_password_hash

def rebuild():
    # Xóa database cũ
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "database.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Đã xóa database cũ.")

    with app.app_context():
        # Tạo lại các bảng theo model mới
        db.create_all()
        print("Đã tạo lại các bảng dữ liệu.")

        # 1. Thêm Admin mặc định
        admin = Teacher(
            username="admin",
            password=generate_password_hash("admin123"),
            full_name="Quản trị viên Hệ thống",
            role="admin"
        )
        db.session.add(admin)

        # 2. Thêm cấu hình hệ thống mặc định
        configs = [
            SystemConfig(key="current_week", value="1"),
            SystemConfig(key="current_semester", value="1"),
            SystemConfig(key="school_year", value="2025-2026")
        ]
        db.session.add_all(configs)

        # 3. Thêm một số môn học mẫu
        subjects = [
            Subject(name="Toán", code="TOAN"),
            Subject(name="Văn", code="VAN"),
            Subject(name="Anh", code="ANH"),
            Subject(name="Lý", code="LY"),
            Subject(name="Hóa", code="HOA"),
            Subject(name="Tin học", code="TIN")
        ]
        db.session.add_all(subjects)

        # 4. Thêm một số loại vi phạm mẫu
        rules = [
            ViolationType(name="Đi trễ", points_deducted=5),
            ViolationType(name="Không đồng phục", points_deducted=10),
            ViolationType(name="Sử dụng điện thoại", points_deducted=20),
            ViolationType(name="Nghỉ học không phép", points_deducted=30)
        ]
        db.session.add_all(rules)

        db.session.commit()
        print("Đã khởi tạo dữ liệu mẫu thành công.")
        print("Tài khoản admin: admin / admin123")

if __name__ == "__main__":
    rebuild()
