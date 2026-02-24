import re
import os

with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# Make routes dir
os.makedirs("routes", exist_ok=True)
if not os.path.exists("routes/__init__.py"):
    with open("routes/__init__.py", "w") as f:
        pass

# Extract login route
login_pattern = re.compile(r'@app\.route\("/login", methods=\["GET", "POST"\]\)\ndef login\(\):.*?(?=@app\.route|def |# ===)', re.DOTALL)
login_match = login_pattern.search(app_code)

# Extract logout
logout_pattern = re.compile(r'@app\.route\("/logout"\)\n@login_required\ndef logout\(\):.*?(?=@app\.route|def |# ===)', re.DOTALL)
logout_match = logout_pattern.search(app_code)

if login_match and logout_match:
    auth_code = """from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from models import Teacher

auth_bp = Blueprint('auth', __name__)

"""
    login_func = login_match.group(0).replace('@app.route', '@auth_bp.route')
    logout_func = logout_match.group(0).replace('@app.route', '@auth_bp.route')
    
    auth_code += login_func + "\n" + logout_func
    
    with open("routes/auth.py", "w", encoding="utf-8") as f:
        f.write(auth_code)
        
    # Remove from app.py
    app_code = app_code.replace(login_match.group(0), "")
    app_code = app_code.replace(logout_match.group(0), "")
    
    # Add blueprint registration
    reg_str = "app.register_blueprint(auth_bp)\n"
    if reg_str not in app_code:
        # insert after app configuration
        insert_marker = 'login_manager.init_app(app)'
        if insert_marker in app_code:
            app_code = app_code.replace(insert_marker, insert_marker + "\n\nfrom routes.auth import auth_bp\n" + reg_str)
            
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(app_code)
        
    print("Extracted auth.py successfully!")
else:
    print("Could not find login or logout routes. Regex match failed.")
