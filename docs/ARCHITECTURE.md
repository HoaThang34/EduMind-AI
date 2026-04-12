# EduMind-AI System Architecture

## Overview
EduMind-AI is a comprehensive school management system built with Flask that combines traditional school management features with modern AI capabilities. The system manages students, grades, violations, attendance, timetables, and includes AI-powered chatbot, OCR grade entry, and automated report generation.

---

## Technology Stack

### Backend
- **Framework:** Flask (Python web framework)
- **Database:** SQLite with SQLAlchemy ORM
- **Authentication:** Flask-Login
- **AI/LLM:** Ollama (local LLM server)
- **OCR:** Ollama vision models (Gemini-compatible)
- **Data Processing:** Pandas (Excel operations)
- **Security:** Werkzeug password hashing

### Frontend
- **Templates:** Jinja2 (Flask templating)
- **Styling:** Bootstrap 5 + Custom CSS
- **Charts:** Chart.js
- **Icons:** Bootstrap Icons
- **JavaScript:** Vanilla JS (ES6+)
- **QR Codes:** API-based generation (qrserver.com)

### Development Tools
- **Environment:** Python 3.x
- **Package Management:** pip + requirements.txt
- **Configuration:** python-dotenv (.env files)
- **Version Control:** Git

---

## System Architecture

### Layered Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Presentation Layer                    │
│  (HTML Templates, JavaScript, CSS, Mobile Interface)     │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                      Application Layer                     │
│  (Flask Routes, Blueprints, Business Logic, Helpers)     │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                       Data Access Layer                    │
│  (SQLAlchemy ORM, Database Models, Queries)              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                      Data Layer                            │
│  (SQLite Database, File Storage, AI Models)              │
└─────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Application Entry Point (`app.py`)
**Responsibilities:**
- Flask app initialization
- Database configuration
- Blueprint registration
- Login manager setup
- Database migration functions
- Static file serving
- Startup database creation

**Key Functions:**
- `create_database()` - Initialize DB with migrations
- `ensure_*()` functions - Schema migrations
- `load_user()` - User loader for Flask-Login

---

### 2. Database Models (`models.py`)
**Design Patterns:**
- Active Record pattern (SQLAlchemy)
- Relationships defined as attributes
- Cascade delete for related records
- Unique constraints for data integrity
- Indexes on frequently queried fields

**Model Categories:**
- **User Models:** Teacher, Student
- **Academic Models:** Subject, Grade, ClassSubject
- **Discipline Models:** Violation, ViolationType, BonusRecord, BonusType
- **Attendance Models:** AttendanceRecord, AttendanceMonitoringSession
- **Timetable Models:** TimetableSlot, LessonBookEntry, LessonBookWeek, LessonBookSlot
- **Communication Models:** Notification, GroupChatMessage, PrivateMessage, ChatConversation
- **Management Models:** ClassRoom, SystemConfig, Permission, TeacherPermission
- **Audit Models:** ChangeLog, WeeklyArchive
- **Finance Models:** ClassFundCollection, ClassFundExpense

---

### 3. Route Organization (`routes/`)
**Blueprint Pattern:**
Each module is a separate Flask Blueprint for modularity:

```
routes/
├── auth.py              → auth_bp (Authentication)
├── grades.py            → grades_bp (Grade management)
├── student.py           → student_bp (Student portal)
├── ai_engine.py         → ai_engine_bp (AI features)
├── core.py              → Direct app registration (Core features)
├── admin_mgmt.py        → Admin management
├── violations_mgmt.py   → Violation management
├── students_mgmt.py     → Student management
├── subjects_mgmt.py     → Subject management
├── rules_bonus.py       → Rules and bonuses
├── messaging.py         → Messaging system
├── lesson_book.py       → Lesson book
├── timetable.py         → Timetable
├── class_fund.py        → Class fund
├── attendance.py        → Attendance
└── class_subjects.py    → Class-subject assignments
```

**Registration Flow:**
1. Blueprints defined in individual files
2. Registered in `routes/__init__.py`
3. Called from `app.py` during initialization

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
- `get_ollama_client()` - Ollama client instance
- `get_ollama_model()` - Get configured model
- `_call_gemini()` - Vision and JSON support (legacy name)
- `_parse_llm_json_response()` - Parse AI JSON responses

**Data Processing:**
- `parse_excel_file()` - Excel parsing with pandas
- `import_violations_to_db()` - Bulk import
- `calculate_student_gpa()` - GPA calculation
- `calculate_week_from_date()` - Week number from date
- `normalize_student_code()` - Student code normalization
- `normalize_parent_phone_for_login()` - Phone normalization

**Chatbot Memory:**
- `get_or_create_chat_session()` - Session management
- `get_conversation_history()` - Retrieve chat history
- `save_message()` - Save chat message

**Notifications & Logging:**
- `create_notification()` - Create system notification
- `broadcast_timetable_update()` - Broadcast timetable changes
- `log_change()` - Audit logging

**Timetable Helpers:**
- `timetable_class_variants_for_filter()` - Class name matching
- `resolve_class_name_for_timetable()` - Class name resolution
- `resolve_subject_for_timetable()` - Subject resolution

**Student Status:**
- `update_student_conduct()` - Auto-update conduct status
- `is_reset_needed()` - Check if weekly reset needed

---

### 5. AI/Prompt System (`prompts.py` & `prompts/`)
**Architecture:**
- Centralized prompt definitions
- JSON-based prompt storage
- Prompt templates with placeholders
- Intent detection for multi-purpose chatbot

**Prompt Categories:**
- Chatbot system prompts
- Student learning prompts
- School rules prompts
- Behavior guide prompts
- Teacher assistant prompts
- OCR grade prompts
- Vision prompts

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

### 6. Template System (`templates/`)
**Template Hierarchy:**
```
templates/
├── base.html                    → Base layout with navigation
├── login.html                   → Login page
├── welcome.html                 → Welcome/login selection
├── home.html                    → Home page
├── dashboard.html               → Main dashboard
├── student_dashboard.html       → Student portal dashboard
├── chatbot.html                 → AI chatbot interface
├── assistant_chatbot.html       → Multi-purpose assistant
├── manage_grades.html           → Grade management
├── student_grades.html          → Individual student grades
├── student_transcript.html      → Student transcript
├── parent_report.html           → Parent report
├── ocr_grades.html              → OCR grade entry
├── attendance/                  → Attendance templates
├── messaging/                   → Messaging templates
└── ...                          → Other feature templates
```

**Template Features:**
- Jinja2 inheritance (extends base.html)
- Flask-Login integration (current_user)
- Flash message display
- CSRF protection
- Mobile-responsive design
- Bootstrap components

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

### 5. Attendance Flow
```
Teacher → Open monitoring session → AttendanceMonitoringSession
→ Capture face/scan QR → POST /api/attendance/checkin
→ Face recognition/QR validation → AttendanceRecord
→ Mark violations → SessionViolationRecord
→ Confirm session → Convert to official Violation
→ Update student scores
```

---

## Security Architecture

### Authentication
- **Password Hashing:** Werkzeug security (hash with salt)
- **Session Management:** Flask-Login with secure cookies
- **Session Storage:** Server-side Flask sessions
- **Login Persistence:** Remember me functionality

### Authorization
- **Role-Based Access Control (RBAC):**
  - 6 user roles: admin, homeroom_teacher, subject_teacher, both, discipline_officer, parent_student
- **Permission-Based Access Control (PBAC):**
  - Granular permissions in Permission table
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
- **File Upload Validation:** Extension and size checks
- **Input Validation:** Server-side validation for all inputs

### Audit Trail
- **ChangeLog Table:** Records all database changes
- **Automatic Logging:** `log_change()` helper for tracking
- **Change Types:** grade, grade_update, grade_delete, violation, bonus, etc.

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
   - Action buttons for navigation

2. **OCR Grade Entry**
   - Vision model for image processing
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

### AI Model Configuration
- **Primary Model:** OLLAMA_MODEL in .env
- **Fallback Model:** OLLAMA_FALLBACK_MODEL in .env
- **Host:** OLLAMA_HOST in .env (default: localhost:11434)
- **Vision Support:** Models with vision capabilities (llava, qwen2.5-vl)

### Error Handling
- Graceful degradation on AI failures
- Fallback responses
- User-friendly error messages
- Retry logic with fallback model

---

## Mobile Architecture

### Responsive Design
- **Breakpoint:** max-width: 1023px for mobile
- **Framework:** Bootstrap 5 responsive grid
- **Touch Targets:** Minimum 56px height
- **Safe Area:** Support for notched phones

### Mobile Navigation
- **Bottom Navigation Bar:** Fixed position, thumb-accessible
- **Hamburger Menu:** Slide-in sidebar
- **Swipe Gestures:** Right swipe to open, left swipe to close
- **Touch Events:** Native touch event handling

### Mobile Features
- **QR Code Scanning:** Camera-based QR scanning
- **Face Recognition:** Mobile camera integration
- **Offline Support:** Service worker (planned)
- **Push Notifications:** Web Push API (planned)

---

## Performance Considerations

### Database Optimization
- **Indexes:** On frequently queried fields
- **Lazy Loading:** SQLAlchemy relationships
- **Eager Loading:** `joinedload()` for N+1 prevention
- **Pagination:** For large datasets

### Caching Strategy
- **Session Caching:** Flask session storage
- **Static Files:** Cached by browser
- **AI Responses:** Could add Redis caching (future)

### Frontend Optimization
- **Lazy Loading:** Images and components
- **Debouncing:** Search and resize events
- **Minification:** CSS/JS (future)
- **Bundle Splitting:** Code splitting (future)

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
- **Scaling:** Horizontal scaling with shared session store

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
GEMINI_API_KEY=your-gemini-key (if using Gemini)
```

---

## Integration Points

### External Services
1. **Ollama API** - Local LLM server
2. **QR Code API** - qrserver.com for QR generation
3. **Gemini API** - Optional cloud AI backup

### File System
- **uploads/** - User uploads (OCR images, photos)
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
- **Logging:** Console and file logging

### AI Errors
- **Fallback Responses:** When AI fails
- **Error Messages:** Clear user communication
- **Retry Logic:** With fallback model
- **Graceful Degradation:** Continue without AI

### Frontend Errors
- **Fetch Error Handling:** Network failures
- **Validation Errors:** Client-side validation
- **User Feedback:** Toast notifications
- **Console Logging:** Debug information

---

## Testing Strategy (Planned)

### Unit Tests
- Model tests
- Helper function tests
- Route tests

### Integration Tests
- API endpoint tests
- Database operation tests
- AI integration tests

### End-to-End Tests
- User flow tests
- Mobile responsive tests
- Cross-browser tests

---

## Monitoring & Logging

### Application Logging
- **Console Logging:** Development
- **File Logging:** Production (planned)
- **Error Tracking:** Sentry (planned)

### Database Monitoring
- **Query Performance:** Slow query logging
- **Connection Pool:** Monitor connections
- **Backup Strategy:** Regular backups

### AI Monitoring
- **Response Times:** AI call duration
- **Error Rates:** AI failure tracking
- **Model Performance:** Response quality metrics

---

## Future Enhancements

### Short Term
1. WebSocket for real-time updates
2. Redis for session caching
3. PostgreSQL migration
4. API versioning
5. Rate limiting

### Medium Term
1. Mobile app (React Native)
2. Parent portal improvements
3. Advanced analytics dashboard
4. Email notifications
5. SMS integration

### Long Term
1. Multi-school support
2. Cloud deployment
3. Advanced AI features
4. Integration with external systems
5. Mobile push notifications

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
- Ensure accessibility
