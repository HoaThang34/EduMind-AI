# EduMind-AI Documentation

This directory contains comprehensive documentation for the EduMind-AI school management system.

## Documentation Files

### 1. [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)
Complete database schema documentation including:
- All 31 database models with field descriptions
- Relationships between models
- Indexes and constraints
- Migration notes
- Default data

**Purpose:** Help AI understand the data structure and relationships when working with database operations.

---

### 2. [API_ROUTES.md](./API_ROUTES.md)
Backend API routes documentation including:
- All Flask routes organized by module
- Request/response formats
- Authentication and authorization
- Permission decorators
- Common patterns

**Purpose:** Help AI understand the backend API structure, endpoints, and how to implement new routes or modify existing ones.

---

### 3. [FRONTEND_API_ROUTES.md](./FRONTEND_API_ROUTES.md)
Frontend API integration documentation including:
- JavaScript API calls from templates
- AJAX request patterns
- Form submissions
- File uploads
- UI component patterns
- Mobile-specific implementations

**Purpose:** Help AI understand how the frontend interacts with the backend and how to implement new frontend features.

---

### 4. [ARCHITECTURE.md](./ARCHITECTURE.md) (Recommended)
System architecture overview including:
- Project structure
- Technology stack
- Design patterns
- Component relationships
- Data flow
- Security considerations

**Purpose:** Help AI understand the overall system architecture and design decisions.

---

## Quick Reference

### Project Structure
```
EduMind-AI/
├── app.py                  # Main Flask application
├── models.py               # SQLAlchemy database models
├── app_helpers.py          # Helper functions and utilities
├── prompts.py              # AI prompts for chatbot
├── requirements.txt        # Python dependencies
├── routes/                 # Flask route blueprints
│   ├── __init__.py
│   ├── auth.py            # Authentication
│   ├── grades.py          # Grade management
│   ├── student.py         # Student portal
│   ├── ai_engine.py       # AI/Chatbot
│   ├── core.py            # Core routes
│   ├── admin_mgmt.py      # Admin management
│   ├── violations_mgmt.py # Violation management
│   ├── students_mgmt.py   # Student management
│   ├── subjects_mgmt.py   # Subject management
│   ├── rules_bonus.py     # Rules and bonuses
│   ├── messaging.py       # Messaging system
│   ├── lesson_book.py     # Lesson book
│   ├── timetable.py       # Timetable
│   ├── class_fund.py      # Class fund
│   ├── attendance.py      # Attendance
│   └── class_subjects.py  # Class-subject assignments
├── templates/              # HTML templates
├── prompts/                # AI prompt JSON files
├── logo/                   # Logo files
├── musics/                 # Audio files
├── uploads/                # Uploaded files
└── docs/                   # Documentation (this folder)
```

### Technology Stack
- **Backend:** Flask (Python)
- **Database:** SQLite with SQLAlchemy ORM
- **AI/LLM:** Ollama (local models)
- **Frontend:** HTML, CSS, JavaScript, Bootstrap
- **Authentication:** Flask-Login
- **OCR:** Gemini Vision API (via Ollama vision models)
- **Charts:** Chart.js

### Key Design Patterns
- **Blueprint Pattern:** Routes organized into blueprints
- **Role-Based Access Control:** Multiple user roles with granular permissions
- **Repository Pattern:** Database operations through SQLAlchemy ORM
- **Helper Pattern:** Shared utilities in app_helpers.py
- **Template Inheritance:** Base template with common elements

### User Roles
1. **admin** - Full system access
2. **homeroom_teacher** - Access to assigned class
3. **subject_teacher** - Access to assigned subject and classes
4. **both** - Combined homeroom + subject teacher
5. **discipline_officer** - Violation management
6. **parent_student** - Student/parent portal access

### Permission System
- Granular permissions defined in `Permission` table
- Assigned to teachers via `TeacherPermission` table
- Decorators: `@permission_required()`, `@role_or_permission_required()`

### AI Integration
- **Chatbot:** Context-aware with conversation memory
- **OCR:** Grade entry from images
- **Report Generation:** AI-generated reports and comments
- **Timetable:** AI-generated timetable from images
- **Models:** Configurable via Ollama (OLLAMA_MODEL in .env)

### Mobile Support
- Responsive design with Bootstrap
- Mobile bottom navigation bar
- Touch-friendly UI
- Swipe gestures for sidebar
- QR code scanning for attendance

---

## For AI Assistants

When working with EduMind-AI codebase:

1. **Always check the database schema** in DATABASE_SCHEMA.md before creating/modifying models
2. **Review existing routes** in API_ROUTES.md to understand patterns before adding new endpoints
3. **Follow frontend patterns** in FRONTEND_API_ROUTES.md for consistent API integration
4. **Use helper functions** from app_helpers.py (documented in API_ROUTES.md)
5. **Apply appropriate decorators** for authentication and authorization
6. **Log changes** using `log_change()` helper for audit trail
7. **Send notifications** using `create_notification()` for important events
8. **Test role-based access** to ensure proper permissions

### Common Tasks

**Adding a new route:**
1. Choose appropriate route file (or create new blueprint)
2. Apply decorators (@login_required, @permission_required, etc.)
3. Follow existing patterns for request/response handling
4. Update API_ROUTES.md documentation
5. Add corresponding frontend API calls if needed

**Adding a new model:**
1. Add model to models.py
2. Create migration function in app.py
3. Add relationships to existing models if needed
4. Update DATABASE_SCHEMA.md documentation
5. Create CRUD routes in appropriate route file

**Adding AI feature:**
1. Create prompt in prompts/ directory
2. Use `call_ollama()` or `_call_gemini()` helpers
3. Add API route in ai_engine.py or appropriate file
4. Implement frontend interface
5. Add error handling for AI failures

**Modifying permissions:**
1. Add permission code to Permission table
2. Update permission decorators on routes
3. Document in API_ROUTES.md
4. Test with different user roles

---

## Maintenance Notes

### Database Migrations
- Schema changes require migration functions in app.py
- Always test migrations on development database first
- Use `ensure_*` pattern for backward compatibility

### AI Model Configuration
- Configure Ollama host and model in .env file
- Test model availability before deployment
- Handle AI failures gracefully with fallback responses

### Security
- Never commit .env file with secrets
- Use password hashing for all user passwords
- Validate all user inputs
- Apply CSRF protection for form submissions
- Sanitize outputs to prevent XSS

### Performance
- Use database indexes on frequently queried fields
- Implement pagination for large datasets
- Cache frequently accessed data
- Optimize database queries with SQLAlchemy

---

## Updating Documentation

When making changes to the codebase:

1. **Update relevant documentation file(s)**
2. **Keep documentation in sync with code**
3. **Add examples for new features**
4. **Update architecture overview if structure changes**
5. **Review documentation for accuracy**

---

## Additional Resources

### Configuration Files
- `.env` - Environment variables (not in git)
- `.env.example` - Example environment variables
- `requirements.txt` - Python dependencies

### Key Files to Understand
- `app.py` - Application initialization and database setup
- `models.py` - All database models
- `app_helpers.py` - Shared helper functions
- `routes/__init__.py` - Blueprint registration
- `prompts.py` - AI prompt definitions

### Template Structure
- `base.html` - Base template with navigation
- `login.html` - Login page
- `dashboard.html` - Main dashboard
- `student_dashboard.html` - Student portal dashboard
- `chatbot.html` - AI chatbot interface

---

## Contact & Support

For questions about the codebase or documentation:
- Review existing code patterns
- Check documentation files
- Refer to Flask and SQLAlchemy documentation
- Consult Ollama documentation for AI features

---

## Version History

- **v1.0** - Initial documentation (April 2026)
  - Database schema documentation
  - API routes documentation
  - Frontend API documentation
  - README and architecture overview
