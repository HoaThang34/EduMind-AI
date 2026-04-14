# EduMind-AI Documentation

Hệ thống quản lý trường học toàn diện kết hợp AI, xây dựng trên nền tảng Flask với khả năng quản lý học sinh, điểm số, điểm danh, thời khóa biểu, sổ đầu bài và chatbot AI.

## Cấu trúc Tài liệu

| File | Mô tả |
|------|-------|
| [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) | Schema database đầy đủ (31 models, quan hệ, migration) |
| [API_ROUTES.md](./API_ROUTES.md) | Danh sách API endpoints backend đầy đủ |
| [FRONTEND_API_ROUTES.md](./FRONTEND_API_ROUTES.md) | Tích hợp frontend - API gọi từ JavaScript |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Kiến trúc hệ thống chi tiết |
| [AI_QUICK_REFERENCE.md](./AI_QUICK_REFERENCE.md) | Hướng dẫn nhanh cho AI assistant |

## Cấu Trúc Dự Án

```
EduMind-AI/
├── app.py                  # Flask app chính, DB init, migrations
├── models.py               # 31 SQLAlchemy models
├── app_helpers.py          # Helper functions, decorators, AI integration
├── prompts.py              # AI prompts định nghĩa
├── requirements.txt        # Python dependencies
├── rebuild_db.py          # Script rebuild database
├── .env.example           # Environment variables mẫu
├── .env                    # Environment variables (không commit)
│
├── routes/                 # Flask Blueprints
│   ├── __init__.py        # Đăng ký tất cả blueprints
│   ├── auth.py            # Đăng nhập/đăng xuất (auth_bp)
│   ├── grades.py          # Quản lý điểm (grades_bp)
│   ├── student.py         # Cổng học sinh (student_bp)
│   ├── ai_engine.py      # Chatbot AI, OCR, reports (ai_engine_bp)
│   ├── core.py           # Dashboard, profile, history
│   ├── admin_mgmt.py     # Quản lý admin
│   ├── violations_mgmt.py # Quản lý vi phạm
│   ├── students_mgmt.py   # CRUD học sinh
│   ├── subjects_mgmt.py   # CRUD môn học
│   ├── rules_bonus.py     # Loại vi phạm, loại điểm cộng
│   ├── messaging.py       # Nhắn tin, thông báo
│   ├── lesson_book.py    # Sổ đầu bài điện tử
│   ├── timetable.py      # Thời khóa biểu
│   ├── class_fund.py     # Quỹ lớp
│   ├── attendance.py     # Điểm danh (face/QR)
│   ├── class_subjects.py # Phân công môn học
│   └── face_engine.py    # Nhận diện khuôn mặt (ArcFace ONNX)
│
├── templates/             # HTML templates (Jinja2)
│   ├── base.html         # Layout nền
│   ├── dashboard.html    # Dashboard chính
│   ├── chatbot.html      # Giao diện chatbot AI
│   ├── manage_grades.html # Quản lý điểm
│   ├── attendance/       # Templates điểm danh
│   ├── messaging/        # Templates nhắn tin
│   └── *.html            # Các trang chức năng
│
├── prompts/              # AI prompt JSON files
├── logo/                 # Logo trường
├── musics/               # File âm thanh
├── uploads/              # Uploaded files, face models
│   └── face_models/.onnx # ArcFace ONNX model
└── database.db            # SQLite database
```

## Các Tính Năng Chính

### 1. Quản Lý Học Sinh
- CRUD học sinh đầy đủ
- Thông tin phụ huynh, CCCD, dân tộc
- Ảnh chân dung, QR code học sinh
- Tự động cập nhật hạnh kiểm, cảnh báo

### 2. Quản Lý Điểm
- Điểm TX/GK/HK theo từng môn
- Nhiều cột điểm cùng loại
- OCR nhận diện điểm từ hình ảnh
- Tính GPA tự động
- Báo cáo phụ huynh

### 3. Hệ Thống Kỷ Luật
- Vi phạm + điểm trừ
- Điểm cộng (bonus)
- Tự động cập nhật hạnh kiểm (Tốt/Khá/Trung bình/Yếu)
- Mức cảnh báo (Xanh/Vàng/Đỏ)
- Nhập vi phạm hàng loạt từ Excel

### 4. AI Tích Hợp (Ollama)
- Chatbot có nhớ ngữ cảnh
- OCR nhận diện điểm từ ảnh
- Tạo báo cáo học sinh tự động
- Tạo báo cáo phụ huynh
- Sinh thời khóa biểu từ ảnh
- Phân tích thống kê lớp

### 5. Điểm Danh
- Nhận diện khuôn mặt (ArcFace ONNX)
- QR code check-in
- Phiên theo dõi điểm danh theo giờ
- Tự động ghi nhận vi phạm trễ/vắng

### 6. Thời Khóa Biểu
- Theo tuần ISO (1-53)
- Nhiều năm học
- Hỗ trợ AI sinh TKB từ ảnh
- Grid view trực quan

### 7. Sổ Đầu Bài
- Grid tuần theo tiết/ngày
- Mỗi slot ghi: môn, bài, mục tiêu, phương pháp, đánh giá, bài tập
- Ghi chú tuần cho giáo viên

### 8. Thông Báo & Nhắn Tin
- Thông báo hệ thống
- Nhắn tin nhóm
- Nhắn tin riêng
- Thông báo cho học sinh

## Vai Trò Người Dùng

| Role | Mã | Quyền truy cập |
|------|-----|---------------|
| Quản trị viên | admin | Toàn quyền hệ thống |
| Giáo viên chủ nhiệm | homeroom_teacher | Lớp được phân công |
| Giáo viên bộ môn | subject_teacher | Các lớp được phân công |
| GVCN + GVBM | both | Cả hai |
| Giáo viên nền nếp | discipline_officer | Tất cả học sinh |
| Phụ huynh/Học sinh | parent_student | Cổng học sinh |

## Công Nghệ Sử Dụng

| Layer | Công nghệ |
|-------|-----------|
| Backend | Flask 3.1, SQLAlchemy 2.0 |
| Database | SQLite |
| AI | Ollama (local LLM) |
| Face Recognition | ArcFace ONNX + OpenCV DNN |
| Frontend | HTML5, CSS3, Bootstrap 5, JavaScript ES6+ |
| Charts | Chart.js |
| Password | Werkzeug (hash + salt) |
| Auth | Flask-Login |

## Cài Đặt

```bash
# 1. Clone/Copy dự án
cd EduMind-AI

# 2. Tạo virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Copy và chỉnh .env
copy .env.example .env
# Chỉnh OLLAMA_MODEL, OLLAMA_HOST trong .env

# 5. Chạy Ollama (AI server)
ollama serve
ollama pull llama3.2  # hoặc model bạn chọn

# 6. Khởi chạy
python app.py
```

## Account Mặc Định

| Username | Password | Role |
|----------|----------|------|
| admin | admin | admin |

## Các Lệnh Quan Trọng

```bash
# Khởi tạo database
python rebuild_db.py

# Kiểm tra Ollama models
ollama list

# Pull model mới
ollama pull llama3.2
```

## AI Model Configuration (.env)

```env
SECRET_KEY=your-secret-key
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_FALLBACK_MODEL=llama3.2
```

## Hướng Dẫn Cho AI Assistant

Khi làm việc với codebase EduMind-AI:

1. **Check database schema** trong `docs/DATABASE_SCHEMA.md` trước khi tạo/sửa model
2. **Xem API routes** trong `docs/API_ROUTES.md` để hiểu pattern trước khi thêm endpoint mới
3. **Follow frontend patterns** trong `docs/FRONTEND_API_ROUTES.md` cho API integration nhất quán
4. **Dùng helper functions** từ `app_helpers.py` - đã được document đầy đủ
5. **Áp dụng decorators** phù hợp cho authentication và authorization
6. **Log changes** bằng `log_change()` cho audit trail
7. **Gửi notifications** bằng `create_notification()` cho các sự kiện quan trọng
8. **Test role-based access** để đảm bảo quyền hạn đúng

### Common Tasks

**Thêm route mới:**
1. Chọn file route phù hợp (hoặc tạo blueprint mới)
2. Áp decorators (@login_required, @permission_required, etc.)
3. Follow pattern có sẵn cho request/response
4. Update API_ROUTES.md

**Thêm model mới:**
1. Thêm model vào models.py
2. Tạo migration function trong app.py
3. Thêm relationships nếu cần
4. Update DATABASE_SCHEMA.md
5. Tạo CRUD routes

**Thêm tính năng AI:**
1. Tạo prompt trong prompts/ directory
2. Dùng `call_ollama()` hoặc `_call_gemini()` helpers
3. Thêm API route trong ai_engine.py
4. Implement frontend interface
5. Xử lý lỗi AI graceful

## Bảo Trì

### Database Migrations
- Schema changes cần migration functions trong app.py
- Luôn test migrations trên dev database trước
- Dùng pattern `ensure_*` cho backward compatibility

### AI Model Configuration
- Configure Ollama host và model trong .env
- Test model availability trước deployment
- Handle AI failures graceful với fallback responses

### Security
- Không commit .env file
- Dùng password hashing cho tất cả passwords
- Validate tất cả user inputs
- Sanitize outputs để prevent XSS

## Version History

- **v2.0** (April 2026) - Nâng cấp lớn
  - Face recognition engine (ArcFace ONNX)
  - Session-based attendance monitoring
  - Lesson book grid view
  - AI-powered report generation
  - Class fund management
  - Teacher class assignments
  - Mở rộng database schema (31 models)
  - Cập nhật tài liệu đầy đủ

- **v1.0** (Early 2026) - Phiên bản ban đầu
  - Basic student/grade/violation management
  - Simple chatbot
