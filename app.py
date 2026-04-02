
import os
from flask import Flask
from werkzeug.security import generate_password_hash
from flask_login import LoginManager

from models import db, Teacher, SystemConfig, ViolationType
from app_helpers import register_template_extensions
from routes import register_all_routes

basedir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(basedir, "templates")

app = Flask(__name__, template_folder=template_dir)

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


def create_database():
    db.create_all()
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
