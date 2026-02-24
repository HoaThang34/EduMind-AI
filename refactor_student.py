import re
import os

with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# Make routes dir
os.makedirs("routes", exist_ok=True)

student_code = """from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import Student, Violation, BonusRecord, Grade, Subject, SystemConfig, db
from app import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa
import base64
import json
import ollama

student_bp = Blueprint('student', __name__)

OLLAMA_MODEL = "gemini-3-flash-preview"

# We might need to copy `student_required`, `get_student_ai_advice`, `_student_chat_call_ollama` and `ALLOWED_CHAT_EXTENSIONS` here.
# Let's extract them:
"""

# Extract helpers
to_extract = [
    r'(def student_required\(f\):.*?(?=@app\.route|def get_student_ai_advice))',
    r'(def get_student_ai_advice\(student\):.*?(?=@app\.route|@student_required|def _student_chat))',
    r'(ALLOWED_CHAT_EXTENSIONS = \{.*?\}\n)',
    r'(def _student_chat_call_ollama\(system_prompt, history, user_message, image_base64=None\):.*?(?=@app\.route))'
]

extracted_helpers = ""
for pat in to_extract:
    match = re.search(pat, app_code, re.DOTALL)
    if match:
        extracted_helpers += match.group(1) + "\n\n"
        app_code = app_code.replace(match.group(1), "")

student_code += extracted_helpers

# Extract routes
routes = [
    r'(@app\.route\("/student/login".*?(?=@app\.route|# ===|def get_student_ai_advice|@student_required))',
    r'(@app\.route\("/student/logout"\).*?(?=@app\.route|# ===|def get_student_ai_advice))',
    r'(@app\.route\("/student/dashboard"\).*?(?=@app\.route|# ===|ALLOWED_CHAT_EXTENSIONS))',
    r'(@app\.route\("/api/student/chat".*?(?=@app\.route|# ===))'
]

routes_code = ""
for pat in routes:
    match = re.search(pat, app_code, re.DOTALL)
    if match:
        route_text = match.group(1)
        route_text_mod = route_text.replace('@app.route', '@student_bp.route')
        
        routes_code += route_text_mod + "\n\n"
        app_code = app_code.replace(match.group(1), "")

student_code += routes_code

with open("routes/student.py", "w", encoding="utf-8") as f:
    f.write(student_code)

req_text = "from routes.student import student_bp\napp.register_blueprint(student_bp)\n"
if req_text not in app_code:
    app_code = app_code.replace('app.register_blueprint(auth_bp)', 'app.register_blueprint(auth_bp)\n' + req_text)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)

print("Extracted student routes successfully")
