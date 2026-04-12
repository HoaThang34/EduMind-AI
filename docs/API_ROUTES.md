# API Routes Documentation - EduMind-AI

## Overview
EduMind-AI uses Flask with Blueprint pattern for route organization. Routes are split across multiple files in the `routes/` directory.

## Route Files Structure

- `routes/__init__.py` - Registers all blueprints
- `routes/auth.py` - Authentication routes (Blueprint: `auth_bp`)
- `routes/grades.py` - Grade management routes (Blueprint: `grades_bp`)
- `routes/student.py` - Student portal routes (Blueprint: `student_bp`)
- `routes/ai_engine.py` - AI/Chatbot routes (Blueprint: `ai_engine_bp`)
- `routes/core.py` - Core routes registered directly on app
- `routes/admin_mgmt.py` - Admin management routes
- `routes/violations_mgmt.py` - Violation management routes
- `routes/students_mgmt.py` - Student management routes
- `routes/subjects_mgmt.py` - Subject management routes
- `routes/rules_bonus.py` - Rules and bonus point routes
- `routes/messaging.py` - Messaging routes
- `routes/lesson_book.py` - Lesson book routes
- `routes/timetable.py` - Timetable routes
- `routes/class_fund.py` - Class fund routes
- `routes/attendance.py` - Attendance routes
- `routes/class_subjects.py` - Class-subject routes

---

## Authentication Routes (`auth_bp`)

### POST `/login`
**Description:** Teacher login

**Request Body:**
- `username` (string) - Teacher username
- `password` (string) - Password

**Response:** Redirects to home on success, flashes error on failure

---

### GET `/logout`
**Description:** Teacher logout (requires login)

**Response:** Redirects to login page

---

## Grade Management Routes (`grades_bp`)

### GET `/manage_grades`
**Description:** List students for grade entry (requires login, permission: view_grades)

**Query Parameters:**
- `search` (string) - Search by name or student code
- `class_select` (string) - Filter by class

**Response:** Renders `manage_grades.html`

---

### GET|POST `/student_grades/<int:student_id>`
**Description:** View and enter grades for a student (requires login, role: subject_teacher or permission: manage_grades)

**POST Request Body:**
- `subject_id` (integer) - Subject ID
- `grade_type` (string) - TX, GK, or HK
- `column_index` (integer) - Column index (default: 1)
- `score` (float) - Score (0-10)
- `semester` (integer) - Semester (default from config)
- `school_year` (string) - School year (default from config)

**Response:** Renders `student_grades.html`

---

### POST `/delete_grade/<int:grade_id>`
**Description:** Delete a grade (requires login, role: subject_teacher or permission: manage_grades)

**Response:** Redirects to student grades page

---

### POST `/api/update_grade/<int:grade_id>`
**Description:** API endpoint to update grade inline (requires login, role: subject_teacher or permission: manage_grades)

**Request Body (JSON):**
- `score` (float) - New score (0-10)

**Response (JSON):**
```json
{
  "success": true,
  "score": 8.5
}
```

---

### GET `/student/<int:student_id>/transcript`
**Description:** View student transcript/grade report (requires login, permission: view_grades)

**Query Parameters:**
- `semester` (integer) - Semester (default from config)
- `school_year` (string) - School year (default from config)

**Response:** Renders `student_transcript.html`

---

### GET `/student/<int:student_id>/parent_report`
**Description:** Generate parent report (requires login, permission: view_grades)

**Query Parameters:**
- `semester` (integer) - Semester (default from config)
- `school_year` (string) - School year (default from config)

**Response:** Renders `parent_report.html`

---

## Student Portal Routes (`student_bp`)

### GET|POST `/student/login`
**Description:** Student login

**POST Request Body:**
- `student_code` (string) - Student code
- `student_password` (string) - Password or parent phone (fallback)

**Response:** Redirects to student dashboard on success

---

### GET `/student/logout`
**Description:** Student logout

**Response:** Redirects to student login

---

### POST `/student/api/generate_ai_advice`
**Description:** API to generate AI advice for student (requires student login)

**Response (JSON):**
```json
{
  "advice": "AI-generated advice text"
}
```

---

### GET `/student/dashboard`
**Description:** Student dashboard (requires student login)

**Response:** Renders `student_dashboard.html` with:
- Current week violations
- Current week bonuses
- Grade transcript
- Unread notifications count

---

### GET `/student/thoi-khoa-bieu`
**Description:** Student timetable (requires student login)

**Query Parameters:**
- `week_number` (integer) - ISO week (default: current week)

**Response:** Renders `student_timetable.html`

---

### GET `/student/thong-bao`
**Description:** Student notifications list (requires student login)

**Response:** Renders `student_notifications.html`

---

### POST `/student/thong-bao/<int:nid>/doc`
**Description:** Mark notification as read (requires student login)

**Response:** Redirects to notifications list

---

### GET `/student/the-hoc-sinh`
**Description:** Student ID card with QR codes (requires student login)

**Response:** Renders `student_id_card.html` with:
- Verification QR (90-day expiry)
- Attendance QR (no expiry)

---

### GET `/student/the-hoc-sinh/xac-minh/<token>`
**Description:** Public route to verify student ID card via QR

**Response:** Renders `student_id_card_verify.html`

---

### GET `/student/qr-diem-danh/<int:student_id>`
**Description:** Attendance QR page for student (public)

**Response:** Renders `student_qr_attendance.html`

---

### GET `/student/diem-danh-qr`
**Description:** Quick attendance QR from dashboard (requires student login)

**Response:** Renders `student_qr_attendance.html`

---

## AI Engine Routes (`ai_engine_bp`)

### GET `/chatbot`
**Description:** Chatbot interface (requires login)

**Response:** Renders `chatbot.html`

---

### POST `/api/chatbot`
**Description:** Context-aware chatbot API (requires login)

**Request Body (JSON):**
- `message` (string) - User message

**Response (JSON):**
```json
{
  "response": "AI response",
  "buttons": [
    {"label": "Button text", "payload": "payload"}
  ]
}
```

**Features:**
- Student search by name/code
- Class detection from message
- Grade and violation data retrieval
- Action buttons for quick navigation

---

### POST `/api/chatbot/clear`
**Description:** Clear chat session (requires login)

**Response (JSON):**
```json
{
  "status": "success",
  "message": "Chat đã được làm mới"
}
```

---

### GET `/assistant_chatbot`
**Description:** Multi-purpose assistant chatbot (requires login)

**Response:** Renders `assistant_chatbot.html`

---

### POST `/api/generate_report/<int:student_id>`
**Description:** Generate AI report for student (requires login)

**Request Body (JSON):**
- `week` (integer, optional) - Specific week

**Response (JSON):**
```json
{
  "report": "AI-generated report text"
}
```

---

### POST `/api/generate_parent_report/<int:student_id>`
**Description:** Generate parent report with AI (requires login)

**Request Body (JSON):**
- `semester` (integer) - Semester
- `school_year` (string) - School year

**Response (JSON):**
```json
{
  "report": "AI-generated parent report"
}
```

---

### POST `/api/generate_chart_comments/<int:student_id>`
**Description:** Generate AI comments for charts (requires login)

**Request Body (JSON):**
- `gpa` (float) - GPA
- `avg_score` (float) - Average score
- `highest_score` (float) - Highest score
- `lowest_score` (float) - Lowest score
- `strong_subjects` (array) - Strong subjects
- `weak_subjects` (array) - Weak subjects
- `total_subjects` (integer) - Total subjects
- `conduct_score` (float) - Conduct score
- `total_violations` (integer) - Total violations
- `semester` (integer) - Semester

**Response (JSON):**
```json
{
  "comments": "AI-generated chart comments"
}
```

---

### POST `/api/assistant_chatbot`
**Description:** Multi-purpose assistant API with intent detection (requires login)

**Request Body (JSON):**
- `message` (string) - User message

**Response (JSON):**
```json
{
  "response": "AI response",
  "category": "nội quy|ứng xử|trợ giúp GV|general"
}
```

**Intent Categories:**
- Nội quy: school rules, violations, discipline
- Ứng xử: behavior, situations, skills
- Trợ giúp GV: teacher assistance, comments, methods
- General: fallback

---

### GET `/ocr-grades`
**Description:** OCR grade entry interface (requires login)

**Response:** Renders `ocr_grades.html`

---

### POST `/api/ocr-grades`
**Description:** Process grade image with OCR (requires login)

**Request Body (multipart/form-data):**
- `image` (file) - Image file

**Response (JSON):**
```json
{
  "results": [
    {
      "rowId": "1",
      "student_code": "12345",
      "student_name": "Nguyễn Văn A",
      "date_of_birth": "15/08/2008",
      "roll_number": "1",
      "score": "8.5",
      "grade_type": "TX"
    }
  ],
  "metadata": {
    "total_detected": 10
  }
}
```

---

### POST `/api/confirm-ocr-grades`
**Description:** Save OCR-confirmed grades to database (requires login)

**Request Body (JSON):**
- `subject_id` (integer) - Subject ID
- `class_filter` (string, optional) - Class filter
- `semester` (integer) - Semester
- `grades` (array) - Array of grade objects

**Response (JSON):**
```json
{
  "success": true,
  "success_count": 10,
  "errors": [],
  "item_results": []
}
```

---

## Core Routes (registered on app)

### GET `/`
**Description:** Welcome page with login form

**POST Request Body:**
- `login_type` (string) - "staff" or "student"
- `username` (string) - Staff username (if staff)
- `password` (string) - Password (if staff)
- `student_code` (string) - Student code (if student)
- `student_password` (string) - Student password (if student)

**Response:** Renders `welcome.html` or redirects to home/dashboard

---

### GET `/admin`
**Description:** Redirect to login

**Response:** Redirects to `/login`

---

### GET `/home`
**Description:** Home page (requires login)

**Response:** Renders `home.html`

---

### GET `/docs`
**Description:** Documentation page

**Response:** Renders `docs.html`

---

### GET `/terms`
**Description:** Terms of service

**Response:** Renders `terms.html`

---

### GET `/privacy`
**Description:** Privacy policy

**Response:** Renders `privacy.html`

---

### GET `/scoreboard`
**Description:** Student scoreboard (requires login)

**Query Parameters:**
- `search` (string) - Search by name/code
- `class_select` (string) - Filter by class
- `warning_level` (string) - Filter by warning level
- `academic_warning` (string) - Filter by academic warning

**Response:** Renders `index.html`

---

### GET `/dashboard`
**Description:** Main dashboard (requires login)

**Query Parameters:**
- `class_select` (string) - Filter by class

**Response:** Renders `dashboard.html` with:
- Total students count
- Score distribution (Good/Fair/Average)
- Average score
- Total violations (current week)
- Total classes
- Top violations chart
- Pie chart data

---

### GET `/profile`
**Description:** User profile (requires login)

**Response:** Renders `profile.html`

---

### GET|POST `/edit_profile`
**Description:** Edit profile (requires login, admin only)

**Response:** Renders `edit_profile.html`

---

### GET `/history`
**Description:** Violation history by week (requires login)

**Query Parameters:**
- `week` (integer) - Week number
- `class_select` (string) - Filter by class

**Response:** Renders `history.html` with:
- Violation list
- Class rankings
- Pie chart data
- Bar chart data

---

### GET `/export_history`
**Description:** Export history to Excel (requires login)

**Query Parameters:**
- `week` (integer) - Week number
- `class_select` (string) - Filter by class

**Response:** Excel file download

---

### GET `/weekly_report`
**Description:** Weekly violation report (requires login)

**Query Parameters:**
- `week` (integer) - Week number

**Response:** Renders `weekly_report.html`

---

### GET `/export_report`
**Description:** Export weekly report to Excel (requires login)

**Query Parameters:**
- `week` (integer) - Week number

**Response:** Excel file download

---

### GET `/student/<int:student_id>`
**Description:** Student detail page (requires login, access control)

**Query Parameters:**
- `week` (integer) - Week number (default: current week)

**Response:** Renders `student_detail.html` with:
- Student info
- Week violations
- Week bonuses
- Score chart
- Warning if score low

---

### GET `/violation_history`
**Description:** Paginated violation history (requires login)

**Query Parameters:**
- `page` (integer) - Page number (default: 1)
- `per_page` (integer) - Items per page (default: 20)
- `week` (integer) - Filter by week
- `class_select` (string) - Filter by class

**Response:** Renders `violation_history.html`

---

### POST `/api/analyze_class_stats`
**Description:** API to analyze class statistics with AI (requires login)

**Request Body (JSON):**
- `class_name` (string) - Class name
- `weeks` (array) - Array of week numbers

**Response (JSON):**
```json
{
  "analysis": "AI-generated analysis text"
}
```

---

## Static File Routes

### GET `/logo/<path:filename>`
**Description:** Serve logo files

**Response:** File from `logo/` directory

---

### GET `/musics/<path:filename>`
**Description:** Serve music files

**Response:** File from `musics/` directory

---

## Permission Decorators

### `@login_required`
Requires user to be logged in (Flask-Login)

### `@admin_required`
Requires user role to be 'admin'

### `@permission_required(permission_code)`
Requires user to have specific permission code

### `@role_or_permission_required(role, permission_code)`
Allows access if user has specific role OR permission

### `@student_required`
Requires student session (student portal)

---

## Access Control

### Role-Based Access
- **admin**: Full access to all features
- **homeroom_teacher**: Access to assigned class students
- **subject_teacher**: Access to assigned subject grades and assigned classes
- **both**: Both homeroom and subject teacher privileges
- **discipline_officer**: Access to violation management
- **parent_student**: Student/parent portal access

### Permission-Based Access
Granular permissions defined in `Permission` table:
- `view_grades` - View student grades
- `manage_grades` - Enter/edit grades
- `manage_students` - Manage student records
- `manage_violations` - Manage violations
- `manage_subjects` - Manage subjects
- etc.

### Student Access Control
- `can_access_student(student_id)` - Check if current user can access specific student
- `get_accessible_students()` - Get query of accessible students based on role

---

## Response Formats

### HTML Responses
Most GET routes return HTML templates

### JSON Responses
API endpoints return JSON with standard format:
```json
{
  "success": true/false,
  "data": {},
  "error": "Error message if any"
}
```

### File Downloads
Export routes return file downloads (Excel, etc.)

---

## Error Handling

### Flash Messages
Success/error messages stored in Flask flash:
- `flash("Message", "success")`
- `flash("Message", "error")`

### Redirect on Error
Unauthorized access redirects to dashboard or login

### JSON Error Responses
```json
{
  "error": "Error description"
}
```

---

## Session Management

### Teacher Session
- Stored via Flask-Login
- `current_user` available in routes

### Student Session
- Stored in Flask session
- `session['student_id']`
- `session['student_name']`

### Chat Session
- `session['chat_session_id']` for chatbot context

---

## Common Query Patterns

### Search and Filter
```python
search = request.args.get('search', '').strip()
selected_class = request.args.get('class_select', '').strip()
```

### Pagination
```python
page = request.args.get('page', 1, type=int)
per_page = 20
results = query.paginate(page=page, per_page=per_page, error_out=False)
```

### JSON Request
```python
data = request.get_json() or {}
```

### Form Data
```python
value = request.form.get('field_name')
```

---

## Database Operations

### Common Patterns
```python
# Get single record
student = db.session.get(Student, student_id)

# Query with filters
students = Student.query.filter_by(student_class=class_name).all()

# Create new record
record = Model(field=value)
db.session.add(record)
db.session.commit()

# Update record
record.field = new_value
db.session.commit()

# Delete record
db.session.delete(record)
db.session.commit()
```

---

## Logging Changes

Use `log_change()` helper to track database changes:
```python
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

---

## Notifications

Use `create_notification()` to send notifications:
```python
create_notification(
    title="Notification title",
    message="Notification message",
    notification_type='grade',
    target_role='all'  # or specific class/role
)
```

---

## AI Integration

### Ollama Integration
- Uses local Ollama server (configurable via `OLLAMA_HOST` and `OLLAMA_MODEL` in .env)
- `call_ollama(prompt)` - Simple text chat
- `_call_gemini(prompt, image_path, is_json)` - Vision and JSON support (legacy name, uses Ollama)

### Prompt Files
Prompts stored in `prompts/` directory:
- `chatbot_system.json` - Chatbot system prompt
- `behavior_guide.json` - Behavior guide prompt
- `school_rules.json` - School rules prompt
- etc.

---

## File Uploads

### Upload Folder
- Configured in `UPLOAD_FOLDER` (default: `uploads/`)
- Used for OCR images, student photos, etc.

### File Handling
```python
from app_helpers import UPLOAD_FOLDER
filename = f"prefix_{uuid.uuid4().hex}_{original_filename}"
filepath = os.path.join(UPLOAD_FOLDER, filename)
file.save(filepath)
```

---

## Date/Time Handling

### Current Week
```python
week_cfg = SystemConfig.query.filter_by(key="current_week").first()
current_week = int(week_cfg.value) if week_cfg else 1
```

### ISO Week Calculation
```python
from datetime import datetime
_, week_num, _ = datetime.now().isocalendar()
```

---

## Mobile Support

### Mobile Navigation
- Bottom navigation bar (mobile only, max-width: 1023px)
- Swipe gestures for sidebar
- Responsive templates

### Mobile Routes
All routes support mobile responsive design via:
- Responsive CSS in templates
- Touch-friendly UI components
- Mobile-specific navigation

---

## Security

### Password Hashing
- Uses `werkzeug.security.generate_password_hash()`
- Supports legacy plain text for backward compatibility

### CSRF Protection
- Flask-WTF CSRF protection (if enabled)

### SQL Injection Prevention
- Uses SQLAlchemy ORM (parameterized queries)

### Session Security
- Flask-Login secure session management
- SECRET_KEY in app config

---

## Performance Considerations

### Database Queries
- Use indexing on frequently queried fields
- Lazy loading with SQLAlchemy relationships
- Pagination for large datasets

### Caching
- Consider adding Redis for session caching (future)

### Async Operations
- Long-running AI calls should be async (future enhancement)

---

## Future Enhancements

### Planned Features
- WebSocket for real-time updates
- API versioning
- Rate limiting
- Request validation with schemas
- Async task queue for heavy operations
- More comprehensive API documentation with OpenAPI/Swagger
