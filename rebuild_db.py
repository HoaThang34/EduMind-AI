"""
XÓA TOÀN BỘ DATABASE và tạo lại từ đầu.
CHỈ dùng khi setup lần đầu trên máy mới — KHÔNG dùng để migrate.
Để thêm bảng/cột mới: dùng migrate.py

Bắt buộc truyền --force để chạy:
    python rebuild_db.py --force
"""
import sys
import os
from app import app, db
from models import Teacher, SystemConfig, ViolationType, Subject, ClassRoom, ClassSubject
from werkzeug.security import generate_password_hash
from seed_majors import seed as seed_majors
from seed_entry_scores import seed as seed_entry_scores
from seed_major_weights import seed as seed_major_weights

def rebuild():
    if "--force" not in sys.argv:
        print("⛔  rebuild_db.py XÓA TOÀN BỘ DATA. Truyền --force nếu thực sự muốn chạy.")
        print("    Để migrate an toàn: python migrate.py")
        sys.exit(1)

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

        # 3. Thêm đầy đủ các môn học THPT tại Việt Nam
        subjects = [
            # Môn học cốt lõi
            Subject(name="Toán", code="TOAN", description="Môn Toán học", num_tx_columns=5, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Văn", code="VAN", description="Môn Ngữ văn", num_tx_columns=5, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Tiếng Anh", code="ANH", description="Môn Tiếng Anh", num_tx_columns=5, num_gk_columns=1, num_hk_columns=1),
            
            # Môn Khoa học tự nhiên
            Subject(name="Vật lý", code="LY", description="Môn Vật lý", num_tx_columns=5, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Hóa học", code="HOA", description="Môn Hóa học", num_tx_columns=5, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Sinh học", code="SINH", description="Môn Sinh học", num_tx_columns=5, num_gk_columns=1, num_hk_columns=1),
            
            # Môn Khoa học xã hội
            Subject(name="Lịch sử", code="SU", description="Môn Lịch sử", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Địa lý", code="DIA", description="Môn Địa lý", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Giáo dục công dân", code="GDCD", description="Môn Giáo dục công dân", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            
            # Môn Công nghệ và Tin học
            Subject(name="Tin học", code="TIN", description="Môn Tin học", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Công nghệ", code="CN", description="Môn Công nghệ", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            
            # Môn Ngoại ngữ 2
            Subject(name="Tiếng Đức", code="DUC", description="Môn Tiếng Đức", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Tiếng Trung", code="TRUNG", description="Môn Tiếng Trung", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            
            # Môn Giáo dục thể chất và Quốc phòng
            Subject(name="Giáo dục thể chất", code="GDTC", description="Môn Giáo dục thể chất", num_tx_columns=2, num_gk_columns=1, num_hk_columns=1, is_pass_fail=True),
            Subject(name="Giáo dục quốc phòng - An ninh", code="GDPQ", description="Môn Giáo dục quốc phòng - An ninh", num_tx_columns=2, num_gk_columns=1, num_hk_columns=1, is_pass_fail=True),
            
            # Môn Hoạt động trải nghiệm, hướng nghiệp
            Subject(name="Hoạt động trải nghiệm, hướng nghiệp", code="HTHN", description="Hoạt động trải nghiệm, hướng nghiệp", num_tx_columns=2, num_gk_columns=1, num_hk_columns=1, is_pass_fail=True),
            
            # Môn học bổ trợ (tùy chọn theo chuyên ngành)
            Subject(name="Khoa học tự nhiên", code="KHTN", description="Môn Khoa học tự nhiên (Lý-Hóa-Sinh)", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Khoa học xã hội", code="KHXH", description="Môn Khoa học xã hội (Sử-Địa-GDCD)", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            
            # Các môn chuyên đề khác
            Subject(name="Hội họa", code="HH", description="Môn Hội họa", num_tx_columns=2, num_gk_columns=1, num_hk_columns=1, is_pass_fail=True),
            Subject(name="Âm nhạc", code="AM", description="Môn Âm nhạc", num_tx_columns=2, num_gk_columns=1, num_hk_columns=1, is_pass_fail=True),
            Subject(name="Tư pháp", code="TP", description="Môn Tư pháp", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Triết học", code="TH", description="Môn Triết học", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
            Subject(name="Kinh tế chính trị", code="KTCT", description="Môn Kinh tế chính trị", num_tx_columns=3, num_gk_columns=1, num_hk_columns=1),
        ]
        db.session.add_all(subjects)

        # 3.5. Thêm một số lớp mẫu
        classrooms = [
            ClassRoom(name="10A"),
            ClassRoom(name="10A1"),
            ClassRoom(name="10 Hóa"),
            ClassRoom(name="11A"),
            ClassRoom(name="11 Tin"),
            ClassRoom(name="12A")
        ]
        db.session.add_all(classrooms)

        # 3.6. Thêm phân công môn học theo lớp (ví dụ: 10 Hóa không học Tin, 11 Tin học Tin)
        # Lấy ID của các môn học
        subject_map = {s.code: s.id for s in Subject.query.all()}
        
        class_subjects = [
            # Lớp 10 Hóa - không học Tin học
            ClassSubject(class_name="10 Hóa", subject_id=subject_map["TOAN"], school_year="2025-2026", periods_per_week=5),
            ClassSubject(class_name="10 Hóa", subject_id=subject_map["VAN"], school_year="2025-2026", periods_per_week=5),
            ClassSubject(class_name="10 Hóa", subject_id=subject_map["ANH"], school_year="2025-2026", periods_per_week=4),
            ClassSubject(class_name="10 Hóa", subject_id=subject_map["LY"], school_year="2025-2026", periods_per_week=3),
            ClassSubject(class_name="10 Hóa", subject_id=subject_map["HOA"], school_year="2025-2026", periods_per_week=4),
            ClassSubject(class_name="10 Hóa", subject_id=subject_map["SINH"], school_year="2025-2026", periods_per_week=3),
            ClassSubject(class_name="10 Hóa", subject_id=subject_map["SU"], school_year="2025-2026", periods_per_week=2),
            ClassSubject(class_name="10 Hóa", subject_id=subject_map["DIA"], school_year="2025-2026", periods_per_week=2),
            ClassSubject(class_name="10 Hóa", subject_id=subject_map["GDCD"], school_year="2025-2026", periods_per_week=1),
            ClassSubject(class_name="10 Hóa", subject_id=subject_map["GDTC"], school_year="2025-2026", periods_per_week=2),
            # Không có Tin học cho 10 Hóa
            
            # Lớp 11 Tin - có học Tin học
            ClassSubject(class_name="11 Tin", subject_id=subject_map["TOAN"], school_year="2025-2026", periods_per_week=5),
            ClassSubject(class_name="11 Tin", subject_id=subject_map["VAN"], school_year="2025-2026", periods_per_week=5),
            ClassSubject(class_name="11 Tin", subject_id=subject_map["ANH"], school_year="2025-2026", periods_per_week=4),
            ClassSubject(class_name="11 Tin", subject_id=subject_map["LY"], school_year="2025-2026", periods_per_week=3),
            ClassSubject(class_name="11 Tin", subject_id=subject_map["HOA"], school_year="2025-2026", periods_per_week=3),
            ClassSubject(class_name="11 Tin", subject_id=subject_map["SINH"], school_year="2025-2026", periods_per_week=3),
            ClassSubject(class_name="11 Tin", subject_id=subject_map["TIN"], school_year="2025-2026", periods_per_week=4),  # Có Tin học
            ClassSubject(class_name="11 Tin", subject_id=subject_map["SU"], school_year="2025-2026", periods_per_week=2),
            ClassSubject(class_name="11 Tin", subject_id=subject_map["DIA"], school_year="2025-2026", periods_per_week=2),
            ClassSubject(class_name="11 Tin", subject_id=subject_map["GDCD"], school_year="2025-2026", periods_per_week=1),
            ClassSubject(class_name="11 Tin", subject_id=subject_map["GDTC"], school_year="2025-2026", periods_per_week=2),
            
            # Lớp 10A - lớp thường
            ClassSubject(class_name="10A", subject_id=subject_map["TOAN"], school_year="2025-2026", periods_per_week=5),
            ClassSubject(class_name="10A", subject_id=subject_map["VAN"], school_year="2025-2026", periods_per_week=5),
            ClassSubject(class_name="10A", subject_id=subject_map["ANH"], school_year="2025-2026", periods_per_week=4),
            ClassSubject(class_name="10A", subject_id=subject_map["LY"], school_year="2025-2026", periods_per_week=2),
            ClassSubject(class_name="10A", subject_id=subject_map["HOA"], school_year="2025-2026", periods_per_week=2),
            ClassSubject(class_name="10A", subject_id=subject_map["SINH"], school_year="2025-2026", periods_per_week=2),
            ClassSubject(class_name="10A", subject_id=subject_map["TIN"], school_year="2025-2026", periods_per_week=2),
            ClassSubject(class_name="10A", subject_id=subject_map["SU"], school_year="2025-2026", periods_per_week=2),
            ClassSubject(class_name="10A", subject_id=subject_map["DIA"], school_year="2025-2026", periods_per_week=2),
            ClassSubject(class_name="10A", subject_id=subject_map["GDCD"], school_year="2025-2026", periods_per_week=1),
            ClassSubject(class_name="10A", subject_id=subject_map["GDTC"], school_year="2025-2026", periods_per_week=2),
        ]
        db.session.add_all(class_subjects)

        # 4. Thêm một số loại vi phạm mẫu
        rules = [
            ViolationType(name="Đi trễ", points_deducted=5),
            ViolationType(name="Không đồng phục", points_deducted=10),
            ViolationType(name="Sử dụng điện thoại", points_deducted=20),
            ViolationType(name="Nghỉ học không phép", points_deducted=30)
        ]
        db.session.add_all(rules)

        db.session.commit()

        # 5. Seed university majors + entry scores + weights
        print("Seeding university majors...")
        seed_majors()
        print("Seeding entry scores...")
        seed_entry_scores()
        print("Seeding major weights (real scores + block distribution)...")
        seed_major_weights()

        print("Đã khởi tạo dữ liệu mẫu thành công.")
        print("Tài khoản admin: admin / admin123")

if __name__ == "__main__":
    rebuild()
