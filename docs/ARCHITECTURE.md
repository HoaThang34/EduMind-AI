# Kiến Trúc Hệ Thống EduMind-AI

## Tổng Quan

EduMind-AI là hệ thống quản lý trường học toàn diện, kết hợp các tính năng quản lý truyền thống với khả năng AI hiện đại. Hệ thống quản lý học sinh, điểm số, vi phạm, điểm danh, thời khóa biểu, sổ đầu bài và tích hợp chatbot AI.

---

## Tech Stack

### Backend
- **Framework:** Flask 3.1 (Python)
- **Database:** SQLite + SQLAlchemy ORM 2.0
- **Authentication:** Flask-Login
- **AI/LLM:** Ollama (local LLM server)
- **OCR/Vision:** Ollama vision models
- **Face Recognition:** ArcFace ONNX + OpenCV DNN
- **Data Processing:** Pandas (Excel operations)
- **Security:** Werkzeug password hashing

### Frontend
- **Templates:** Jinja2 (Flask templating)
- **Styling:** Bootstrap 5 + Custom CSS
- **Charts:** Chart.js
- **Icons:** Bootstrap Icons
- **JavaScript:** Vanilla JS (ES6+)
- **QR Codes:** API-based generation

### Development Tools
- **Environment:** Python 3.x
- **Package Management:** pip + requirements.txt
- **Configuration:** python-dotenv (.env files)
- **Version Control:** Git

---

## Kiến Trúc Hệ Thống

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│        (HTML Templates, JavaScript, CSS, Mobile UI)         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│     (Flask Routes, Blueprints, Business Logic, Helpers)      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Data Access Layer                        │
│        (SQLAlchemy ORM, Database Models, Queries)            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                       Data Layer                            │
│        (SQLite Database, File Storage, AI Models)           │
└─────────────────────────────────────────────────────────────┘
```

---

## Kiến Trúc Component

### 1. Application Entry Point (`app.py`)

**Trách nhiệm:**
- Khởi tạo Flask app
- Cấu hình database
- Đăng ký blueprints
- Setup Login manager
- Migration functions
- Static file serving
- Khởi tạo database khi startup

**Key Functions:**
- `create_database()` - Khởi tạo DB với migrations
- `ensure_*()` functions - 16 schema migrations
- `load_user()` - User loader cho Flask-Login

---

### 2. Database Models (`models.py`)

**Design Patterns:**
- Active Record pattern (SQLAlchemy)
- Relationships defined as attributes
- Cascade delete cho related records
- Unique constraints cho data integrity
- Indexes trên frequently queried fields

**Model Categories (31 models total):**

**User Models:**
- `Teacher` - Tài khoản giáo viên với RBAC
- `Student` - Hồ sơ học sinh

**Academic Models:**
- `Subject` - Môn học
- `Grade` - Điểm số
- `ClassSubject` - Phân công môn học cho lớp
- `TimetableSlot` - Ô thời khóa biểu

**Discipline Models:**
- `ViolationType` - Loại vi phạm
- `Violation` - Bản ghi vi phạm
- `BonusType` - Loại điểm cộng
- `BonusRecord` - Bản ghi điểm cộng
- `ConductSetting` - Cấu hình ngưỡng hạnh kiểm

**Attendance Models:**
- `AttendanceRecord` - Bản ghi điểm danh
- `AttendanceMonitoringSession` - Phiên theo dõi điểm danh
- `SessionViolationRecord` - Vi phạm trong phiên

**Lesson Book Models:**
- `LessonBookEntry` - Sổ đầu bài (theo entry)
- `LessonBookWeek` - Meta tuần sổ đầu bài
- `LessonBookSlot` - Ô slot trong grid tuần

**Communication Models:**
- `Notification` - Thông báo giáo viên
- `StudentNotification` - Thông báo học sinh
- `GroupChatMessage` - Tin nhắn nhóm
- `PrivateMessage` - Tin nhắn riêng
- `ChatConversation` - Lịch sử chatbot

**Management Models:**
- `ClassRoom` - Lớp học
- `SystemConfig` - Cấu hình hệ thống
- `Permission` - Định nghĩa quyền
- `TeacherPermission` - Gán quyền cho giáo viên
- `TeacherClassAssignment` - Phân công giáo viên dạy lớp

**Finance Models:**
- `ClassFundCollection` - Thu tiền quỹ lớp
- `ClassFundExpense` - Chi tiêu quỹ lớp

**Audit Models:**
- `ChangeLog` - Lịch sử thay đổi
- `WeeklyArchive` - Lưu trữ tuần

---

### 3. Route Organization (`routes/`)

**Blueprint Pattern:**
Mỗi module là một Flask Blueprint riêng biệt:

```
routes/
├── auth.py              → auth_bp (Đăng nhập/đăng xuất)
├── grades.py            → grades_bp (Quản lý điểm)
├── student.py           → student_bp (Cổng học sinh)
├── ai_engine.py         → ai_engine_bp (AI features)
├── core.py              → Direct app registration (Core features)
├── admin_mgmt.py        → admin_bp (Quản lý admin)
├── violations_mgmt.py   → violations_bp (Quản lý vi phạm)
├── students_mgmt.py     → students_bp (Quản lý học sinh)
├── subjects_mgmt.py     → subjects_bp (Quản lý môn học)
├── rules_bonus.py       → rules_bonus_bp (Rules & bonuses)
├── messaging.py         → messaging_bp (Nhắn tin)
├── lesson_book.py      → lesson_book_bp (Sổ đầu bài)
├── timetable.py         → timetable_bp (Thời khóa biểu)
├── class_fund.py       → class_fund_bp (Quỹ lớp)
├── attendance.py        → attendance_bp (Điểm danh)
├── class_subjects.py    → class_subjects_bp (Class subjects)
└── face_engine.py       → (Engine, không phải route)
```

**Registration Flow:**
1. Blueprints định nghĩa trong individual files
2. Đăng ký trong `routes/__init__.py`
3. Gọi từ `app.py` trong initialization

---

### 4. Helper Functions (`app_helpers.py`)

**Categories:**

**Authentication & Authorization:**
- `admin_required()` - Admin-only decorator
- `permission_required()` - Permission check decorator
- `role_or_permission_required()` - Role OR permission check
- `get_accessible_students()` - Role-based student query
- `can_access_student()` - Student access check
- `can_access_subject()` - Subject access check

**AI Integration:**
- `call_ollama()` - Ollama chat API
- `_call_gemini()` - Vision và JSON support (legacy name, dùng Ollama)
- `_parse_llm_json_response()` - Parse AI JSON responses
- `get_ollama_client()` - Ollama client instance
- `get_ollama_model()` - Get configured model

**Face Recognition:**
- `get_engine()` - Get FaceEngine singleton

**Data Processing:**
- `parse_excel_file()` - Excel parsing với pandas
- `import_violations_to_db()` - Bulk import
- `calculate_student_gpa()` - GPA calculation
- `normalize_student_code()` - Student code normalization
- `normalize_parent_phone_for_login()` - Phone normalization

**Student Status:**
- `update_student_conduct()` - Auto-update conduct status
- `update_student_academic_status()` - Auto-update academic status
- `is_reset_needed()` - Check if weekly reset needed

**Notifications & Logging:**
- `create_notification()` - Create system notification
- `log_change()` - Audit logging
- `broadcast_timetable_update()` - Broadcast timetable changes

**Timetable Helpers:**
- `timetable_class_variants_for_filter()` - Class name matching
- `resolve_class_name_for_timetable()` - Class name resolution
- `resolve_subject_for_timetable()` - Subject resolution

**Chatbot Memory:**
- `get_or_create_chat_session()` - Session management
- `get_conversation_history()` - Retrieve chat history
- `save_message()` - Save chat message

---

### 5. AI/Prompt System (`prompts.py`)

**Architecture:**
- Centralized prompt definitions
- JSON-based prompt storage
- Prompt templates với placeholders
- Intent detection cho multi-purpose chatbot

**Usage Pattern:**
```python
import prompts
prompt = prompts.STUDENT_ANALYSIS_PROMPT.format(
    name=student.name,
    score=student.current_score,
    ...
)
response, error = call_ollama(prompt)
```

---

### 6. Face Recognition Engine (`routes/face_engine.py`)

**Architecture (DeepFace-style):**
```
1. Face Detection  → OpenCV DNN ResNet-SSD (or Haar Cascade fallback)
2. Face Alignment  → 5-point landmark → affine transform
3. Embedding       → ArcFace ONNX (InsightFace buffalo_l)
4. Similarity      → Cosine distance between 512-dim embeddings
```

**Key Components:**
- `FaceDetector` - Face detection (DNN or Haar)
- `ArcFaceExtractor` - ONNX embedding extraction
- `FaceEngine` - High-level API (find, extract_embedding, detect_faces)
- `ONNXModel` - ONNX Runtime wrapper với lazy loading

**Model Files:**
- ArcFace ONNX: `uploads/face_models/.onnx/w600k_r50.onnx`
- ResNet Prototxt: `uploads/face_models/.onnx/deploy.prototxt`
- ResNet Model: `uploads/face_models/.onnx/res10_300x300_ssd_iter_140000.caffemodel`

---

### 7. Template System (`templates/`)

**Template Hierarchy:**
```
templates/
├── base.html                    → Base layout với navigation
├── login.html                   → Login page
├── welcome.html                 → Welcome/login selection
├── home.html                    → Home page
├── dashboard.html               → Main dashboard
├── student_dashboard.html       → Student portal dashboard
├── chatbot.html                 → AI chatbot interface
├── manage_grades.html           → Grade management
├── student_grades.html          → Individual student grades
├── student_transcript.html      → Student transcript
├── parent_report.html           → Parent report
├── ocr_grades.html             → OCR grade entry
├── attendance/                  → Attendance templates
├── messaging/                   → Messaging templates
└── ...                          → Other feature templates
```

---

## Data Flow

### 1. Authentication Flow
```
User → Login Form → POST /login
→ Validate credentials → Flask-Login session
→ Redirect to home/dashboard
→ Subsequent requests use current_user
```

### 2. Grade Entry Flow
```
Teacher → Select student → View grades
→ Enter/Edit grade → POST /student_grades/<id>
→ Validate permission → Update database
→ Log change → Send notification
→ Update student academic status
→ Redirect to grades page
```

### 3. AI Chatbot Flow
```
User → Enter message → POST /api/chatbot
→ Get/create session → Load conversation history
→ Save user message → Search student DB
→ Build context → Call Ollama API
→ Save AI response → Return JSON
→ Frontend displays response + buttons
```

### 4. OCR Grade Entry Flow
```
Teacher → Upload image → POST /api/ocr-grades
→ Save temp file → Call Ollama Vision
→ Parse JSON response → Display editable table
→ Teacher edits → POST /api/confirm-ocr-grades
→ Validate and save → Update database
→ Log changes → Send notifications
```

### 5. Face Recognition Attendance Flow
```
Teacher → Open monitoring session
→ Capture face → POST /api/attendance/face_checkin
→ FaceEngine.detect_faces() → FaceDetector
→ FaceEngine.extract_embedding() → ArcFaceExtractor
→ Cosine similarity vs DB embeddings
→ Match found → AttendanceRecord created
→ Mark violations → SessionViolationRecord
→ Confirm session → Convert to official Violation
```

---

## Security Architecture

### Authentication
- **Password Hashing:** Werkzeug security (hash với salt)
- **Session Management:** Flask-Login với secure cookies
- **Session Storage:** Server-side Flask sessions
- **Login Persistence:** Remember me functionality

### Authorization
- **Role-Based Access Control (RBAC):**
  - 6 user roles: admin, homeroom_teacher, subject_teacher, both, discipline_officer, parent_student
- **Permission-Based Access Control (PBAC):**
  - Granular permissions trong Permission table
  - TeacherPermission assigns permissions to teachers
- **Decorators:**
  - `@login_required` - Authentication check
  - `@admin_required` - Admin-only access
  - `@permission_required(code)` - Permission check
  - `@role_or_permission_required(role, code)` - Flexible access

### Data Protection
- **SQL Injection Prevention:** SQLAlchemy ORM (parameterized queries)
- **XSS Prevention:** Jinja2 auto-escaping
- **CSRF Protection:** Flask-WTF (when enabled)
- **File Upload Validation:** Extension và size checks
- **Input Validation:** Server-side validation cho all inputs

### Audit Trail
- **ChangeLog Table:** Records all database changes
- **Automatic Logging:** `log_change()` helper cho tracking
- **Change Types:** grade, grade_update, grade_delete, violation, bonus, score_reset, bulk_violation, etc.

---

## AI Integration Architecture

### Ollama Integration
```
Application → app_helpers.py
→ get_ollama_client() → ollama.Client(host=OLLAMA_HOST)
→ call_ollama(prompt) → client.chat(model=OLLAMA_MODEL)
→ Response → Process and return
```

### AI Features
1. **Context-Aware Chatbot**
   - Conversation memory in database
   - Student search integration
   - Action buttons cho navigation

2. **OCR Grade Entry**
   - Vision model cho image processing
   - JSON response parsing
   - Student matching algorithms

3. **Report Generation**
   - Student conduct reports
   - Parent reports
   - Chart comments
   - Class statistics analysis

4. **Timetable Generation**
   - Image-to-timetable conversion
   - Structured JSON output
   - Week-based scheduling

5. **Face Recognition**
   - ArcFace embeddings
   - 1:N identification
   - Real-time camera processing

### AI Model Configuration
- **Primary Model:** OLLAMA_MODEL in .env
- **Fallback Model:** OLLAMA_FALLBACK_MODEL in .env
- **Host:** OLLAMA_HOST in .env (default: localhost:11434)
- **Vision Support:** Models với vision capabilities

### Error Handling
- Graceful degradation on AI failures
- Fallback responses
- User-friendly error messages
- Retry logic với fallback model

---

## Mobile Architecture

### Responsive Design
- **Breakpoint:** max-width: 1023px for mobile
- **Framework:** Bootstrap 5 responsive grid
- **Touch Targets:** Minimum 56px height
- **Safe Area:** Support cho notched phones

### Mobile Navigation
- **Bottom Navigation Bar:** Fixed position, thumb-accessible
- **Hamburger Menu:** Slide-in sidebar
- **Swipe Gestures:** Right swipe to open, left swipe to close
- **Touch Events:** Native touch event handling

### Mobile Features
- **QR Code Scanning:** Camera-based QR scanning
- **Face Recognition:** Mobile camera integration

---

## Performance Considerations

### Database Optimization
- **Indexes:** On frequently queried fields
- **Lazy Loading:** SQLAlchemy relationships
- **Eager Loading:** `joinedload()` cho N+1 prevention
- **Pagination:** For large datasets

### Caching Strategy
- **Session Caching:** Flask session storage
- **Static Files:** Cached by browser
- **AI Responses:** Could add Redis caching (future)

### Frontend Optimization
- **Lazy Loading:** Images and components
- **Debouncing:** Search and resize events

---

## Scalability Considerations

### Database Scaling
- **Current:** SQLite (single file, no external server)
- **Future:** PostgreSQL or MySQL for multi-user
- **Migration:** SQLAlchemy supports multiple databases

### AI Scaling
- **Current:** Local Ollama instance
- **Future:** Cloud-based AI services
- **Load Balancing:** Multiple Ollama instances

### Session Storage
- **Current:** Flask session (server-side)
- **Future:** Redis for distributed sessions
- **Scaling:** Horizontal scaling với shared session store

---

## Deployment Architecture

### Development Environment
```
Developer Machine → Local Flask Server
→ SQLite Database → Local Ollama
→ File System (uploads/)
```

### Production Environment (Recommended)
```
Web Server (Nginx) → WSGI Server (Gunicorn)
→ Flask Application → PostgreSQL Database
→ Redis (sessions/cache) → Ollama Server (AI)
→ Object Storage (S3) for uploads
```

### Environment Variables
```env
SECRET_KEY=your-secret-key
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_FALLBACK_MODEL=llama3.2
```

---

## Integration Points

### External Services
1. **Ollama API** - Local LLM server
2. **QR Code API** - qrserver.com for QR generation

### File System
- **uploads/** - User uploads (OCR images, photos)
- **uploads/face_models/.onnx/** - ArcFace ONNX models
- **logo/** - School logo
- **musics/** - Audio files
- **database.db** - SQLite database

### Database
- **SQLite** - Primary data store
- **Migration functions** - Schema updates

---

## Error Handling Strategy

### Backend Errors
- **Try-Catch Blocks:** Around critical operations
- **Database Rollback:** On transaction errors
- **Flash Messages:** User-friendly error display

### AI Errors
- **Fallback Responses:** When AI fails
- **Error Messages:** Clear user communication
- **Retry Logic:** With fallback model
- **Graceful Degradation:** Continue without AI

### Frontend Errors
- **Fetch Error Handling:** Network failures
- **Validation Errors:** Client-side validation
- **User Feedback:** Toast notifications

---

## Design Principles

1. **Simplicity:** Keep code simple and readable
2. **Modularity:** Separate concerns into modules
3. **Scalability:** Design for future growth
4. **Security:** Security-first approach
5. **User Experience:** Intuitive and responsive
6. **Maintainability:** Easy to understand and modify
7. **Performance:** Optimize for speed
8. **Flexibility:** Adaptable to changing requirements

---

## Development Guidelines

### Code Style
- Follow PEP 8 for Python
- Use meaningful variable names
- Add docstrings for functions
- Comment complex logic
- Keep functions focused and small

### Database Operations
- Use SQLAlchemy ORM
- Always commit transactions
- Handle exceptions with rollback
- Log important changes
- Use indexes for performance

### API Design
- RESTful conventions
- Consistent response formats
- Proper HTTP status codes
- Input validation
- Error handling

### Frontend Code
- Use vanilla JavaScript (no frameworks)
- Follow mobile-first approach
- Test responsive design
- Optimize for performance
