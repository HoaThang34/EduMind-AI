# AI Quick Reference - EduMind-AI

Tài liệu hướng dẫn nhanh cho AI assistant làm việc với codebase EduMind-AI.

---

## Common Tasks

### 1. Adding a New Route

**Steps:**
1. Chọn file route phù hợp trong `routes/`
2. Định nghĩa route với decorators
3. Implement logic
4. Trả về response (HTML hoặc JSON)
5. Update `docs/API_ROUTES.md`

**Example:**
```python
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app_helpers import permission_required

bp = Blueprint('my_feature', __name__)

@bp.route("/my-feature")
@login_required
@permission_required('view_my_feature')
def my_feature():
    data = MyModel.query.all()
    return render_template("my_feature.html", data=data)

@bp.route("/api/my-action", methods=["POST"])
@login_required
def my_api_action():
    data = request.get_json()
    # Process data
    return jsonify({"success": True, "result": data})
```

**Register in `routes/__init__.py`:**
```python
from .my_feature import bp as my_feature_bp
# In register_all_routes(app):
app.register_blueprint(my_feature_bp)
```

---

### 2. Adding a New Database Model

**Steps:**
1. Thêm model class vào `models.py`
2. Định nghĩa fields và relationships
3. Thêm migration function vào `app.py`
4. Update `docs/DATABASE_SCHEMA.md`

**Example:**
```python
class MyModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    student = db.relationship('Student', backref='my_models')
```

**Migration in `app.py`:**
```python
def ensure_my_model_table():
    insp = inspect(db.engine)
    if not insp.has_table("my_model"):
        db.session.execute(text("""
            CREATE TABLE my_model (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                created_at DATETIME,
                student_id INTEGER,
                FOREIGN KEY (student_id) REFERENCES student(id)
            )
        """))
        db.session.commit()
```

---

### 3. Adding a New Permission

**Steps:**
1. Thêm permission vào database (seed data)
2. Apply decorator to routes
3. Update documentation

**Example:**
```python
permission = Permission(
    code='my_feature',
    name='My Feature',
    description='Access to my feature',
    category='my_category'
)
db.session.add(permission)
db.session.commit()
```

---

### 4. Querying Database

**Common Patterns:**

**Get single record:**
```python
student = db.session.get(Student, student_id)
```

**Query with filter:**
```python
students = Student.query.filter_by(student_class="12 Tin").all()
```

**Query with OR condition:**
```python
from sqlalchemy import or_
results = Student.query.filter(
    or_(
        Student.name.ilike(f"%{search}%"),
        Student.student_code.ilike(f"%{search}%")
    )
).all()
```

**Query with JOIN:**
```python
violations = db.session.query(Violation, Student)\
    .join(Student)\
    .filter(Violation.week_number == 5)\
    .all()
```

**Aggregate functions:**
```python
from sqlalchemy import func
total = db.session.query(func.sum(Violation.points_deducted))\
    .filter_by(student_id=student_id)\
    .scalar() or 0
```

**Pagination:**
```python
page = request.args.get('page', 1, type=int)
results = Student.query.paginate(page=page, per_page=20, error_out=False)
```

---

### 5. Working with Relationships

**Access related data:**
```python
student = Student.query.first()
grades = student.grades  # Backref relationship
violations = student.violations
```

**Create with relationship:**
```python
grade = Grade(
    student_id=student.id,
    subject_id=subject.id,
    score=8.5
)
db.session.add(grade)
db.session.commit()
```

**Delete cascade:**
```python
db.session.delete(student)
db.session.commit()
```

---

### 6. Using Helper Functions

**Check permissions:**
```python
from app_helpers import can_access_student, can_access_subject

if can_access_student(student_id):
    # Allow access
```

**Get accessible students:**
```python
from app_helpers import get_accessible_students

students = get_accessible_students()
if selected_class:
    students = students.filter_by(student_class=selected_class)
```

**Log changes:**
```python
from app_helpers import log_change

log_change(
    change_type='grade_update',
    description='Updated grade',
    student_id=student_id,
    student_name=student.name,
    student_class=student.student_class,
    old_value=old_score,
    new_value=new_score
)
```

**Send notification:**
```python
from app_helpers import create_notification

create_notification(
    title="New Grade Added",
    message=f"Grade added for {student.name}",
    notification_type='grade',
    target_role=student.student_class
)
```

**Calculate GPA:**
```python
from app_helpers import calculate_student_gpa

gpa = calculate_student_gpa(student_id, semester=1, school_year="2025-2026")
```

---

### 7. AI Integration

**Simple text chat:**
```python
from app_helpers import call_ollama

response, error = call_ollama("Your prompt here")
if error:
    return error_message
return response
```

**Vision (image processing):**
```python
from app_helpers import _call_gemini

results, error = _call_gemini(
    prompt="Extract grades from this image",
    image_path="/path/to/image.jpg",
    is_json=True
)
```

**Vision with multiple images:**
```python
results, error = _call_gemini(
    prompt="Extract timetable data",
    image_paths=["/path/img1.jpg", "/path/img2.jpg"],
    is_json=True
)
```

**Chatbot with memory:**
```python
from app_helpers import (
    get_or_create_chat_session,
    get_conversation_history,
    save_message,
    call_ollama
)

session_id = get_or_create_chat_session()
history = get_conversation_history(session_id, limit=10)

save_message(session_id, current_user.id, "user", user_message)
response, error = call_ollama(prompt)
save_message(session_id, current_user.id, "assistant", response)
```

---

### 8. Face Recognition Integration

**Get FaceEngine singleton:**
```python
from routes.face_engine import get_engine

engine = get_engine()
```

**Detect faces:**
```python
faces = engine.detect_faces(img_bgr)
for face in faces:
    box = face['box']  # (x, y, w, h)
    crop = face['face']  # cropped BGR image
```

**Extract embedding:**
```python
embedding, box = engine.extract_embedding(img_bgr)
if embedding is not None:
    # 512-dim vector
```

**Find in database:**
```python
results, box = engine.find(
    img_bgr,
    db_embeddings=[e1, e2, ...],
    db_ids=[1, 2, ...],
    top_n=1
)
for (student_id, similarity, box) in results:
    print(f"Matched: {student_id}, similarity: {similarity}")
```

---

### 9. Form Handling

**GET with query parameters:**
```python
search = request.args.get('search', '').strip()
selected_class = request.args.get('class_select', '').strip()
week = request.args.get('week', type=int)
```

**POST form data:**
```python
username = request.form.get('username')
password = request.form.get('password')
```

**POST JSON data:**
```python
data = request.get_json() or {}
message = data.get('message', '')
score = data.get('score', 0)
```

**File upload:**
```python
if 'file' in request.files:
    file = request.files['file']
    if file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
```

---

### 10. Response Patterns

**HTML response:**
```python
return render_template("template.html", data=data, title="Page Title")
```

**JSON response (success):**
```python
return jsonify({
    "success": True,
    "data": result,
    "message": "Operation successful"
})
```

**JSON response (error):**
```python
return jsonify({
    "success": False,
    "error": "Error message"
}), 400
```

**Redirect:**
```python
return redirect(url_for('route_name'))
return redirect(url_for('route_name', param=value))
```

**Flash message + redirect:**
```python
flash("Success message", "success")
return redirect(url_for('dashboard'))
```

---

### 11. Error Handling

**Try-catch for database:**
```python
try:
    db.session.add(record)
    db.session.commit()
except Exception as e:
    db.session.rollback()
    flash(f"Error: {str(e)}", "error")
    return redirect(url_for('some_route'))
```

**Try-catch for AI:**
```python
response, error = call_ollama(prompt)
if error:
    flash(f"AI Error: {error}", "error")
    return redirect(url_for('some_route'))
```

**Validation:**
```python
if not all([field1, field2, field3]):
    flash("Vui lòng điền đầy đủ thông tin!", "error")
    return redirect(url_for('some_route'))
```

---

### 12. Student Status Updates

**Update conduct status:**
```python
from app_helpers import update_student_conduct

update_student_conduct(student_id)
```

**Update academic status:**
```python
from app_helpers import update_student_academic_status

update_student_academic_status(student_id)
```

---

### 13. Timetable Helpers

**Resolve class name:**
```python
from app_helpers import resolve_class_name_for_timetable

resolved = resolve_class_name_for_timetable("12TIN")
# Returns "12 Tin" if that's the canonical name
```

**Get class variants:**
```python
from app_helpers import timetable_class_variants_for_filter

variants = timetable_class_variants_for_filter("12 Tin")
# Returns all matching class_name values in DB
```

**Resolve subject:**
```python
from app_helpers import resolve_subject_for_timetable

subject_id, override = resolve_subject_for_timetable("Toán")
```

---

### 14. Bulk Import

**Parse Excel violations:**
```python
from app_helpers import parse_excel_file, import_violations_to_db

violations = parse_excel_file(file)
errors, count = import_violations_to_db(violations)
```

**Normalize student code:**
```python
from app_helpers import normalize_student_code

normalized = normalize_student_code("34 TOÁN - 001035")
# Returns: "34 TOAN - 001035"
```

---

### 15. Template Context

**Pass data to template:**
```python
return render_template("template.html",
    students=students,
    search_query=search,
    selected_class=class_name,
    current_week=week
)
```

**Access in template:**
```html
{% for student in students %}
    <p>{{ student.name }} - {{ student.student_class }}</p>
{% endfor %}
```

**Use current_user:**
```html
{% if current_user.is_authenticated %}
    <p>Welcome, {{ current_user.full_name }}</p>
{% endif %}
```

---

### 16. Common Import Patterns

**Standard imports:**
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Student, Teacher, Grade, Subject
from sqlalchemy import or_, and_, func, desc
import datetime
import os
```

**Helper imports:**
```python
from app_helpers import (
    admin_required, permission_required, role_or_permission_required,
    get_accessible_students, can_access_student, can_access_subject,
    log_change, create_notification, call_ollama, _call_gemini,
    calculate_student_gpa, update_student_conduct, update_student_academic_status,
    get_or_create_chat_session, save_message, get_conversation_history,
    normalize_student_code, UPLOAD_FOLDER
)
```

**Face engine imports:**
```python
from routes.face_engine import get_engine, cosine_similarity
```

---

### 17. Common Mistakes to Avoid

1. **Forgot to commit:**
   ```python
   db.session.add(record)
   db.session.commit()  # Don't forget!
   ```

2. **Not handling exceptions:**
   ```python
   try:
       db.session.commit()
   except Exception as e:
       db.session.rollback()
   ```

3. **Missing imports:**
   ```python
   from models import Student, Grade
   from app_helpers import log_change
   ```

4. **Not checking permissions:**
   ```python
   @login_required
   @permission_required('required_permission')
   def my_route():
   ```

5. **SQL injection risk:**
   ```python
   # BAD:
   query = f"SELECT * FROM student WHERE name = '{name}'"
   # GOOD:
   student = Student.query.filter_by(name=name).first()
   ```

6. **Hardcoding values:**
   ```python
   # BAD:
   school_year = "2025-2026"
   # GOOD:
   configs = {c.key: c.value for c in SystemConfig.query.all()}
   school_year = configs.get("school_year", "2025-2026")
   ```

---

## Quick Command Reference

**Run Flask app:**
```bash
python app.py
```

**Create/rebuild database:**
```bash
python rebuild_db.py
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Check Ollama models:**
```bash
ollama list
```

**Pull Ollama model:**
```bash
ollama pull llama3.2
```

---

## Environment Variables

**Required in `.env`:**
```env
SECRET_KEY=your-secret-key-here
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_FALLBACK_MODEL=llama3.2
```

**Optional:**
```env
GEMINI_API_KEY=your-gemini-api-key
```

---

## File Locations

**Key files:**
- `app.py` - Main application
- `models.py` - Database models (31 models)
- `app_helpers.py` - Helper functions, decorators
- `prompts.py` - AI prompts
- `routes/` - Route blueprints
- `routes/face_engine.py` - Face recognition engine
- `templates/` - HTML templates
- `uploads/` - User uploads
- `database.db` - SQLite database

**Documentation:**
- `docs/README.md` - Project overview
- `docs/DATABASE_SCHEMA.md` - Database documentation (31 models)
- `docs/API_ROUTES.md` - API documentation
- `docs/FRONTEND_API_ROUTES.md` - Frontend API documentation
- `docs/ARCHITECTURE.md` - System architecture
- `docs/AI_QUICK_REFERENCE.md` - This file

---

## Getting Help

1. **Check documentation first** - Most answers are in docs/
2. **Review similar code** - Look at existing routes for patterns
3. **Use helper functions** - Don't reinvent the wheel
4. **Test incrementally** - Test small changes before large ones
5. **Log errors** - Add print statements for debugging

---

## Best Practices

1. **Always use decorators** for authentication/authorization
2. **Log changes** with `log_change()` for audit trail
3. **Send notifications** for important events
4. **Validate inputs** before processing
5. **Handle exceptions** gracefully
6. **Use relationships** instead of raw IDs
7. **Keep functions focused** and small
8. **Add comments** for complex logic
9. **Update documentation** when making changes
10. **Test with different user roles**
