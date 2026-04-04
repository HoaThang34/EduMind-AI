
import os
from flask import Flask, send_from_directory
from werkzeug.security import generate_password_hash
from flask_login import LoginManager

from sqlalchemy import inspect, text

from models import db, Teacher, SystemConfig, ViolationType
from app_helpers import register_template_extensions
from routes import register_all_routes

basedir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(basedir, "templates")

app = Flask(__name__, template_folder=template_dir)


@app.route("/logo/<path:filename>")
def logo_file(filename):
    return send_from_directory(os.path.join(basedir, "logo"), filename)


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


def create_database():
    db.create_all()
    ensure_student_parent_columns()
    ensure_student_portrait_column()
    ensure_student_date_of_birth_column()
    ensure_lesson_book_timetable_column()
    ensure_violation_lesson_book_column()
    if not Teacher.query.first():
        hashed_pwd = generate_password_hash("admin")
        db.session.add(Teacher(username="admin", password=hashed_pwd, full_name="Admin", role="admin"))
    if not SystemConfig.query.first():
        db.session.add(SystemConfig(key="current_week", value="1"))
    if not ViolationType.query.first():
        db.session.add(ViolationType(name="Đi muộn", points_deducted=2))
    db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        create_database()
    app.run(debug=True)
