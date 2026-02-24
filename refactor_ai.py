import re
import os

with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# Make routes dir
os.makedirs("routes", exist_ok=True)

ai_code = """from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import Student, Violation, db, Grade, SystemConfig
from app import call_ollama, get_or_create_chat_session, get_conversation_history, save_message, CHATBOT_SYSTEM_PROMPT, _call_gemini
import json
import base64

ai_engine_bp = Blueprint('ai_engine', __name__)

OLLAMA_MODEL = "gemini-3-flash-preview"

"""

# Extract routes
routes = [
    r'(@app\.route\("/chatbot"\).*?(?=@app\.route|# ===))',
    r'(@app\.route\("/api/chatbot".*?(?=@app\.route|# ===))',
    r'(@app\.route\("/api/chatbot/clear".*?(?=@app\.route|# ===))',
    r'(@app\.route\("/assistant_chatbot"\).*?(?=@app\.route|# ===))',
    r'(@app\.route\("/api/assistant_chatbot".*?(?=@app\.route|# ===))',
    r'(@app\.route\("/api/generate_report/<int:student_id>".*?(?=@app\.route|# ===))',
    r'(@app\.route\("/api/generate_parent_report/<int:student_id>".*?(?=@app\.route|# ===))'
]

routes_code = ""
for pat in routes:
    match = re.search(pat, app_code, re.DOTALL)
    if match:
        route_text = match.group(1)
        route_text_mod = route_text.replace('@app.route', '@ai_engine_bp.route')
        
        routes_code += route_text_mod + "\n\n"
        app_code = app_code.replace(match.group(1), "")

ai_code += routes_code

with open("routes/ai_engine.py", "w", encoding="utf-8") as f:
    f.write(ai_code)

req_text = "from routes.ai_engine import ai_engine_bp\napp.register_blueprint(ai_engine_bp)\n"
if req_text not in app_code:
    app_code = app_code.replace('app.register_blueprint(grades_bp)', 'app.register_blueprint(grades_bp)\n' + req_text)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)

print("Extracted ai routes successfully")
