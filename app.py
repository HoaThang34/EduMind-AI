import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

from flask import Flask, send_from_directory
from werkzeug.security import generate_password_hash
from flask_login import LoginManager

from sqlalchemy import inspect, text

from models import db, Teacher, SystemConfig, ViolationType, ConductSetting, AttendanceRecord
from app_helpers import register_template_extensions
from routes import register_all_routes

template_dir = os.path.join(basedir, "templates")

app = Flask(__name__, template_folder=template_dir)


@app.route("/logo/<path:filename>")
def logo_file(filename):
    return send_from_directory(os.path.join(basedir, "logo"), filename)


@app.route("/musics/<path:filename>")
def musics_file(filename):
    return send_from_directory(os.path.join(basedir, "musics"), filename)


app.config["SECRET_KEY"] = "chia-khoa-bi-mat-cua-ban-ne-123456"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Vui lòng đăng nhập hệ thống."
login_manager.login_message_category = "error"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Teacher, int(user_id))


register_template_extensions(app)

from routes.auth import auth_bp
app.register_blueprint(auth_bp)
from routes.student import student_bp
app.register_blueprint(student_bp)
from routes.grades import grades_bp
app.register_blueprint(grades_bp)
from routes.ai_engine import ai_engine_bp
app.register_blueprint(ai_engine_bp)

register_all_routes(app)


def ensure_student_parent_columns():
    """Thêm cột phụ huynh cho DB SQLite cũ (ALTER TABLE)."""
    insp = inspect(db.engine)
    if not insp.has_table("student"):
        return
    cols = {c["name"] for c in insp.get_columns("student")}
    if "parent_name" not in cols:
        db.session.execute(text("ALTER TABLE student ADD COLUMN parent_name VARCHAR(150)"))
    if "parent_phone" not in cols:
        db.session.execute(text("ALTER TABLE student ADD COLUMN parent_phone VARCHAR(20)"))
    db.session.commit()


def ensure_student_portrait_column():
    insp = inspect(db.engine)
    if not insp.has_table("student"):
        return
    cols = {c["name"] for c in insp.get_columns("student")}
    if "portrait_filename" not in cols:
        db.session.execute(text("ALTER TABLE student ADD COLUMN portrait_filename VARCHAR(255)"))
    db.session.commit()


def ensure_student_date_of_birth_column():
    insp = inspect(db.engine)
    if not insp.has_table("student"):
        return
    cols = {c["name"] for c in insp.get_columns("student")}
    if "date_of_birth" not in cols:
        db.session.execute(text("ALTER TABLE student ADD COLUMN date_of_birth VARCHAR(30)"))
    db.session.commit()


def ensure_student_position_column():
    insp = inspect(db.engine)
    if not insp.has_table("student"):
        return
    cols = {c["name"] for c in insp.get_columns("student")}
    if "position" not in cols:
        db.session.execute(text("ALTER TABLE student ADD COLUMN position VARCHAR(50)"))
    db.session.commit()


def ensure_lesson_book_timetable_column():
    insp = inspect(db.engine)
    if not insp.has_table("lesson_book_entry"):
        return
    cols = {c["name"] for c in insp.get_columns("lesson_book_entry")}
    if "timetable_slot_id" not in cols:
        db.session.execute(text("ALTER TABLE lesson_book_entry ADD COLUMN timetable_slot_id INTEGER"))
    db.session.commit()


def ensure_violation_lesson_book_column():
    insp = inspect(db.engine)
    if not insp.has_table("violation"):
        return
    cols = {c["name"] for c in insp.get_columns("violation")}
    if "lesson_book_entry_id" not in cols:
        db.session.execute(text("ALTER TABLE violation ADD COLUMN lesson_book_entry_id INTEGER"))
    db.session.commit()


def ensure_timetable_slot_week_number_column():
    """SQLite cũ: đổi cột semester -> week_number (thời khóa biểu theo tuần ISO)."""
    insp = inspect(db.engine)
    if not insp.has_table("timetable_slot"):
        return
    cols = {c["name"] for c in insp.get_columns("timetable_slot")}
    if "week_number" in cols:
        return
    if "semester" in cols:
        try:
            db.session.execute(text("ALTER TABLE timetable_slot RENAME COLUMN semester TO week_number"))
            db.session.commit()
            return
        except Exception:
            db.session.rollback()
        db.session.execute(
            text("ALTER TABLE timetable_slot ADD COLUMN week_number INTEGER NOT NULL DEFAULT 1")
        )
        db.session.execute(text("UPDATE timetable_slot SET week_number = semester"))
    else:
        db.session.execute(
            text("ALTER TABLE timetable_slot ADD COLUMN week_number INTEGER NOT NULL DEFAULT 1")
        )
    db.session.commit()


def ensure_student_notification_sender_column():
    """Thêm cột sender_id cho bảng student_notification (SQLite cũ)."""
    insp = inspect(db.engine)
    if not insp.has_table("student_notification"):
        return
    cols = {c["name"] for c in insp.get_columns("student_notification")}
    if "sender_id" not in cols:
        db.session.execute(text("ALTER TABLE student_notification ADD COLUMN sender_id INTEGER"))
    db.session.commit()


def ensure_student_conduct_columns():
    insp = inspect(db.engine)
    if not insp.has_table("student"):
        return
    cols = {c["name"] for c in insp.get_columns("student")}
    if "conduct" not in cols:
        db.session.execute(text("ALTER TABLE student ADD COLUMN conduct VARCHAR(20) DEFAULT 'Tốt'"))
    if "warning_level" not in cols:
        db.session.execute(text("ALTER TABLE student ADD COLUMN warning_level VARCHAR(20) DEFAULT 'Xanh'"))
    if "academic_rank" not in cols:
        db.session.execute(text("ALTER TABLE student ADD COLUMN academic_rank VARCHAR(20) DEFAULT 'Khá'"))
    if "academic_warning_level" not in cols:
        db.session.execute(text("ALTER TABLE student ADD COLUMN academic_warning_level VARCHAR(20) DEFAULT 'Xanh'"))
    
    # Check ConductSetting table
    if insp.has_table("conduct_setting"):
        c_cols = {c["name"] for c in insp.get_columns("conduct_setting")}
        if "academic_yellow_threshold" not in c_cols:
            db.session.execute(text("ALTER TABLE conduct_setting ADD COLUMN academic_yellow_threshold FLOAT DEFAULT 6.5"))
        if "academic_red_threshold" not in c_cols:
            db.session.execute(text("ALTER TABLE conduct_setting ADD COLUMN academic_red_threshold FLOAT DEFAULT 5.0"))
            
    db.session.commit()


def ensure_attendance_qr_columns():
    """Thêm cột attendance_mode và qr_scan_method cho bảng attendance_record (SQLite cũ)."""
    insp = inspect(db.engine)
    if not insp.has_table("attendance_record"):
        return
    cols = {c["name"] for c in insp.get_columns("attendance_record")}
    if "attendance_mode" not in cols:
        db.session.execute(text("ALTER TABLE attendance_record ADD COLUMN attendance_mode VARCHAR(20) DEFAULT 'face'"))
    if "qr_scan_method" not in cols:
        db.session.execute(text("ALTER TABLE attendance_record ADD COLUMN qr_scan_method VARCHAR(30)"))
    db.session.commit()


def ensure_attendance_monitoring_session_column():
    """Liên kết điểm danh với phiên theo dõi — cột monitoring_session_id (SQLite cũ chưa có)."""
    insp = inspect(db.engine)
    if not insp.has_table("attendance_record"):
        return
    cols = {c["name"] for c in insp.get_columns("attendance_record")}
    if "monitoring_session_id" not in cols:
        db.session.execute(
            text("ALTER TABLE attendance_record ADD COLUMN monitoring_session_id INTEGER")
        )
    db.session.commit()


def ensure_lesson_book_week_and_slot_tables():
    """Tạo bảng lesson_book_week và lesson_book_slot (SQLite cũ chưa có)."""
    insp = inspect(db.engine)
    if not insp.has_table("lesson_book_week"):
        db.session.execute(text("""
            CREATE TABLE lesson_book_week (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                class_name VARCHAR(50) NOT NULL,
                week_number INTEGER NOT NULL,
                school_year VARCHAR(20) NOT NULL,
                semester INTEGER DEFAULT 1,
                teacher_notes TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (teacher_id) REFERENCES teacher(id),
                UNIQUE (teacher_id, class_name, week_number)
            )
        """))
    insp = inspect(db.engine)  # refresh after first create
    if not insp.has_table("lesson_book_slot"):
        db.session.execute(text("""
            CREATE TABLE lesson_book_slot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                period_number INTEGER NOT NULL DEFAULT 1,
                subject_name VARCHAR(100),
                topic TEXT,
                objectives TEXT,
                teaching_method TEXT,
                evaluation TEXT,
                homework TEXT,
                notes TEXT,
                attendance_present INTEGER,
                attendance_absent INTEGER,
                lesson_date DATE,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (week_id) REFERENCES lesson_book_week(id),
                UNIQUE (week_id, day_of_week, period_number)
            )
        """))
    db.session.commit()


def ensure_lesson_book_slot_lesson_date_column():
    """Thêm cột lesson_date cho lesson_book_slot (SQLite cũ)."""
    insp = inspect(db.engine)
    if not insp.has_table("lesson_book_slot"):
        return
    cols = {c["name"] for c in insp.get_columns("lesson_book_slot")}
    if "lesson_date" not in cols:
        db.session.execute(text("ALTER TABLE lesson_book_slot ADD COLUMN lesson_date DATE"))
    db.session.commit()


def ensure_subject_is_pass_fail_column():
    """Thêm cột is_pass_fail cho bảng subject (SQLite cũ)."""
    insp = inspect(db.engine)
    if not insp.has_table("subject"):
        return
    cols = {c["name"] for c in insp.get_columns("subject")}
    if "is_pass_fail" not in cols:
        db.session.execute(text("ALTER TABLE subject ADD COLUMN is_pass_fail BOOLEAN DEFAULT 0"))
    db.session.commit()


def ensure_teacher_class_assignment_table():
    """Tạo bảng teacher_class_assignment (SQLite cũ chưa có)."""
    insp = inspect(db.engine)
    if not insp.has_table("teacher_class_assignment"):
        db.session.execute(text("""
            CREATE TABLE teacher_class_assignment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                class_name VARCHAR(50) NOT NULL,
                subject_id INTEGER,
                school_year VARCHAR(20) NOT NULL DEFAULT '2025-2026',
                created_at DATETIME,
                created_by INTEGER,
                FOREIGN KEY (teacher_id) REFERENCES teacher(id),
                FOREIGN KEY (subject_id) REFERENCES subject(id),
                FOREIGN KEY (created_by) REFERENCES teacher(id),
                UNIQUE (teacher_id, class_name)
            )
        """))
        db.session.commit()


def create_database():
    db.create_all()
    insp = inspect(db.engine)
    ensure_student_parent_columns()
    ensure_student_portrait_column()
    ensure_student_date_of_birth_column()
    ensure_student_position_column()
    ensure_lesson_book_timetable_column()
    ensure_violation_lesson_book_column()
    ensure_timetable_slot_week_number_column()
    ensure_student_notification_sender_column()
    ensure_student_conduct_columns()
    ensure_attendance_qr_columns()
    ensure_attendance_monitoring_session_column()
    ensure_lesson_book_week_and_slot_tables()
    ensure_lesson_book_slot_lesson_date_column()
    ensure_subject_is_pass_fail_column()
    ensure_teacher_class_assignment_table()
    # AttendanceRecord table is auto-created by db.create_all()
    if not Teacher.query.first():
        hashed_pwd = generate_password_hash("admin")
        db.session.add(Teacher(username="admin", password=hashed_pwd, full_name="Admin", role="admin"))
    if not SystemConfig.query.first():
        db.session.add(SystemConfig(key="current_week", value="1"))
    if not ViolationType.query.first():
        db.session.add(ViolationType(name="Đi muộn", points_deducted=2))
    if not ConductSetting.query.first():
        db.session.add(ConductSetting())
    db.session.commit()


# Migration nhẹ khi khởi động (flask run / import app — không chỉ python app.py)
with app.app_context():
    create_database()

if __name__ == "__main__":
    app.run(debug=True)
