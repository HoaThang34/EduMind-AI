import re
import os

with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# Make routes dir
os.makedirs("routes", exist_ok=True)

grades_code = """from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Student, Grade, Subject, SystemConfig, db
from app import admin_required, can_access_student, get_accessible_students, log_change

grades_bp = Blueprint('grades', __name__)

"""

# Extract routes
routes = [
    r'(@app\.route\("/manage_grades"\).*?(?=@app\.route|# ===))',
    r'(@app\.route\("/student_grades/<int:student_id>".*?(?=@app\.route|# ===))',
    r'(@app\.route\("/delete_grade/<int:grade_id>".*?(?=@app\.route|# ===))',
    r'(@app\.route\("/api/update_grade/<int:grade_id>".*?(?=@app\.route|# ===))',
    r'(@app\.route\("/student/<int:student_id>/transcript"\).*?(?=@app\.route|# ===))'
]

routes_code = ""
for pat in routes:
    match = re.search(pat, app_code, re.DOTALL)
    if match:
        route_text = match.group(1)
        route_text_mod = route_text.replace('@app.route', '@grades_bp.route')
        
        routes_code += route_text_mod + "\n\n"
        app_code = app_code.replace(match.group(1), "")

grades_code += routes_code

with open("routes/grades.py", "w", encoding="utf-8") as f:
    f.write(grades_code)

req_text = "from routes.grades import grades_bp\napp.register_blueprint(grades_bp)\n"
if req_text not in app_code:
    app_code = app_code.replace('app.register_blueprint(student_bp)', 'app.register_blueprint(student_bp)\n' + req_text)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)

print("Extracted grades routes successfully")
