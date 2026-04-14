# API Routes Documentation - EduMind-AI

## Tổng Quan

EduMind-AI sử dụng Flask với Blueprint pattern cho route organization. Routes được chia thành nhiều files trong `routes/`.

## Route Files Structure

| File | Blueprint | Mô tả |
|------|-----------|--------|
| `routes/__init__.py` | - | Đăng ký tất cả blueprints |
| `routes/auth.py` | `auth_bp` | Đăng nhập/đăng xuất |
| `routes/grades.py` | `grades_bp` | Quản lý điểm |
| `routes/student.py` | `student_bp` | Cổng học sinh |
| `routes/ai_engine.py` | `ai_engine_bp` | AI/Chatbot/OCR |
| `routes/core.py` | (app) | Core routes đăng ký trực tiếp |
| `routes/admin_mgmt.py` | (app) | Quản lý admin |
| `routes/violations_mgmt.py` | (app) | Quản lý vi phạm |
| `routes/students_mgmt.py` | (app) | CRUD học sinh |
| `routes/subjects_mgmt.py` | (app) | CRUD môn học |
| `routes/rules_bonus.py` | (app) | Rules và bonus |
| `routes/messaging.py` | (app) | Nhắn tin, thông báo |
| `routes/lesson_book.py` | (app) | Sổ đầu bài |
| `routes/timetable.py` | (app) | Thời khóa biểu |
| `routes/class_fund.py` | (app) | Quỹ lớp |
| `routes/attendance.py` | (app) | Điểm danh (face/QR) |
| `routes/class_subjects.py` | (app) | Phân công môn học |

---

## Authentication Routes (`auth_bp`)

### `GET|POST /login`
**Description:** Đăng nhập giáo viên

**POST Request Body:**
- `username` (string) - Tên đăng nhập
- `password` (string) - Mật khẩu

**Response:** Redirects to home on success, flashes error on failure

---

### `GET /logout`
**Description:** Đăng xuất giáo viên (requires login)

**Response:** Redirects to login page

---

## Student Portal Routes (`student_bp`)

### `GET|POST /student/login`
**Description:** Đăng nhập học sinh

**POST Request Body:**
- `student_code` (string) - Mã học sinh
- `student_password` (string) - Password hoặc SĐT phụ huynh

**Response:** Redirects to student dashboard on success

---

### `GET /student/logout`
**Description:** Đăng xuất học sinh

**Response:** Redirects to student login

---

### `GET /student/dashboard`
**Description:** Dashboard học sinh (requires student login)

**Response:** Renders `student_dashboard.html` với violations, bonuses, grades, notifications

---

### `GET /student/thoi-khoa-bieu`
**Description:** Thời khóa biểu học sinh (requires student login)

**Query Parameters:**
- `week_number` (integer) - ISO week (default: current week)

**Response:** Renders `student_timetable.html`

---

### `GET /student/thong-bao`
**Description:** Danh sách thông báo học sinh (requires student login)

**Response:** Renders `student_notifications.html`

---

### `POST /student/thong-bao/<int:nid>/doc`
**Description:** Đánh dấu thông báo đã đọc (requires student login)

**Response:** Redirects to notifications list

---

### `GET /student/the-hoc-sinh`
**Description:** Thẻ học sinh với QR codes (requires student login)

**Response:** Renders `student_id_card.html` với verification QR (90-day expiry) và attendance QR

---

### `GET /student/the-hoc-sinh/xac-minh/<token>`
**Description:** Route công khai xác minh thẻ học sinh qua QR

**Response:** Renders `student_id_card_verify.html`

---

### `GET /student/qr-diem-danh/<int:student_id>`
**Description:** Trang QR điểm danh học sinh (công khai)

**Response:** Renders `student_qr_attendance.html`

---

### `POST /student/api/generate_ai_advice`
**Description:** API tạo lời khuyên AI cho học sinh (requires student login)

**Response (JSON):**
```json
{
  "advice": "AI-generated advice text"
}
```

---

## Grade Management Routes (`grades_bp`)

### `GET /manage_grades`
**Description:** Danh sách học sinh để nhập điểm (requires login, permission: view_grades)

**Query Parameters:**
- `search` (string) - Tìm kiếm theo tên/mã
- `class_select` (string) - Lọc theo lớp

**Response:** Renders `manage_grades.html`

---

### `GET|POST /student_grades/<int:student_id>`
**Description:** Xem và nhập điểm học sinh (requires login, role: subject_teacher hoặc permission: manage_grades)

**POST Request Body:**
- `subject_id` (integer) - Môn học
- `grade_type` (string) - TX, GK, hoặc HK
- `column_index` (integer) - Cột điểm (default: 1)
- `score` (float) - Điểm (0-10)
- `semester` (integer) - Học kỳ
- `school_year` (string) - Năm học

**Response:** Renders `student_grades.html`

---

### `POST /delete_grade/<int:grade_id>`
**Description:** Xóa điểm (requires login)

**Response:** Redirects to student grades page

---

### `POST /api/update_grade/<int:grade_id>`
**Description:** API cập nhật điểm inline (requires login)

**Request Body (JSON):**
```json
{ "score": 8.5 }
```

**Response (JSON):**
```json
{ "success": true, "score": 8.5 }
```

---

### `GET /student/<int:student_id>/transcript`
**Description:** Bảng điểm học sinh (requires login, permission: view_grades)

**Query Parameters:**
- `semester` (integer) - Học kỳ
- `school_year` (string) - Năm học

**Response:** Renders `student_transcript.html`

---

### `GET /student/<int:student_id>/parent_report`
**Description:** Báo cáo phụ huynh (requires login, permission: view_grades)

**Response:** Renders `parent_report.html`

---

## AI Engine Routes (`ai_engine_bp`)

### `GET /chatbot`
**Description:** Giao diện chatbot (requires login)

**Response:** Renders `chatbot.html`

---

### `GET /assistant_chatbot`
**Description:** Chatbot đa năng (requires login)

**Response:** Renders `assistant_chatbot.html`

---

### `POST /api/chatbot`
**Description:** Chatbot context-aware API (requires login)

**Request Body (JSON):**
```json
{ "message": "Tìm học sinh Nguyễn Văn A" }
```

**Response (JSON):**
```json
{
  "response": "AI response",
  "buttons": [{ "label": "Button text", "payload": "payload" }]
}
```

---

### `POST /api/chatbot/clear`
**Description:** Xóa session chat (requires login)

**Response (JSON):**
```json
{ "status": "success", "message": "Chat đã được làm mới" }
```

---

### `POST /api/assistant_chatbot`
**Description:** API chatbot đa năng với intent detection (requires login)

**Request Body (JSON):**
```json
{ "message": "Quy định về đi muộn là gì?" }
```

**Response (JSON):**
```json
{
  "response": "AI response",
  "category": "nội quy|ứng xử|trợ giúp GV|general"
}
```

---

### `POST /api/generate_report/<int:student_id>`
**Description:** Tạo báo cáo AI cho học sinh (requires login)

**Request Body (JSON):**
```json
{ "week": 5 }
```

**Response (JSON):**
```json
{ "report": "AI-generated report text" }
```

---

### `POST /api/generate_parent_report/<int:student_id>`
**Description:** Tạo báo cáo phụ huynh bằng AI (requires login)

**Request Body (JSON):**
```json
{ "semester": 1, "school_year": "2025-2026" }
```

---

### `POST /api/generate_chart_comments/<int:student_id>`
**Description:** Tạo bình luận AI cho biểu đồ (requires login)

**Request Body (JSON):**
```json
{
  "gpa": 7.5, "avg_score": 7.2, "highest_score": 9.0,
  "lowest_score": 6.0, "strong_subjects": ["Toán"],
  "weak_subjects": ["Hóa"], "total_subjects": 8,
  "conduct_score": 85, "total_violations": 2, "semester": 1
}
```

---

### `POST /api/ocr-grades`
**Description:** Xử lý ảnh điểm bằng OCR (requires login)

**Request Body (multipart/form-data):**
- `image` (file) - File ảnh bảng điểm

**Response (JSON):**
```json
{
  "results": [
    {
      "rowId": "1", "student_code": "12345",
      "student_name": "Nguyễn Văn A", "score": "8.5", "grade_type": "TX"
    }
  ],
  "metadata": { "total_detected": 10 }
}
```

---

### `POST /api/confirm-ocr-grades`
**Description:** Lưu điểm OCR đã xác nhận vào database (requires login)

**Request Body (JSON):**
```json
{
  "subject_id": 1, "class_filter": "12 Tin",
  "semester": 1,
  "grades": [{ "rowId": "1", "student_code": "12345", "score": "8.5", "grade_type": "TX" }]
}
```

**Response (JSON):**
```json
{
  "success": true, "success_count": 10, "errors": [], "item_results": []
}
```

---

## Core Routes (registered on app)

### `GET|POST /`
**Description:** Trang welcome với form đăng nhập

**POST Request Body:**
- `login_type` (string) - "staff" hoặc "student"
- `username` (string) - Staff username
- `password` (string) - Password
- `student_code` (string) - Student code
- `student_password` (string) - Student password

**Response:** Renders `welcome.html` hoặc redirects

---

### `GET /home`
**Description:** Trang chủ (requires login)

**Response:** Renders `home.html`

---

### `GET /dashboard`
**Description:** Dashboard chính (requires login)

**Query Parameters:**
- `class_select` (string) - Lọc theo lớp

**Response:** Renders `dashboard.html` với stats, charts

---

### `GET /scoreboard`
**Description:** Bảng xếp hạng học sinh (requires login)

**Query Parameters:**
- `search`, `class_select`, `warning_level`, `academic_warning`

**Response:** Renders `index.html`

---

### `GET /student/<int:student_id>`
**Description:** Trang chi tiết học sinh (requires login, access control)

**Query Parameters:**
- `week` (integer) - Số tuần (default: current week)

**Response:** Renders `student_detail.html`

---

### `GET /history`
**Description:** Lịch sử vi phạm theo tuần (requires login)

**Query Parameters:**
- `week`, `class_select`

**Response:** Renders `history.html`

---

### `GET /weekly_report`
**Description:** Báo cáo tuần vi phạm (requires login)

**Response:** Renders `weekly_report.html`

---

### `GET /violation_history`
**Description:** Lịch sử vi phạm phân trang (requires login)

**Query Parameters:**
- `page`, `per_page`, `week`, `class_select`

**Response:** Renders `violation_history.html`

---

### `POST /api/analyze_class_stats`
**Description:** API phân tích thống kê lớp bằng AI (requires login)

**Request Body (JSON):**
```json
{ "class_name": "12 Tin", "weeks": [1, 2, 3] }
```

**Response (JSON):**
```json
{ "analysis": "AI-generated analysis text" }
```

---

## Violations Management Routes

### `GET|POST /add_violation`
**Description:** Thêm vi phạm mới (requires login, role: discipline_officer hoặc permission: manage_discipline)

**Features:** Hỗ trợ chọn nhiều HS, nhiều loại vi phạm, OCR

---

### `GET /bulk_import_violations`
**Description:** Giao diện nhập vi phạm hàng loạt từ Excel (requires login)

**Response:** Renders `bulk_import_violations.html`

---

### `POST /api/import_violations`
**Description:** API nhập vi phạm từ Excel (requires login)

**Request Body (multipart/form-data):**
- `file` (file) - File Excel

**Response (JSON):**
```json
{ "success": true, "imported": 50, "errors": [] }
```

---

### `POST /api/add_violation_bulk`
**Description:** API thêm vi phạm hàng loạt (requires login)

**Request Body (JSON):**
```json
{
  "student_ids": [1, 2, 3],
  "violation_type_id": 1,
  "week_number": 5,
  "lesson_book_entry_id": null
}
```

---

### `POST /delete_violation/<int:violation_id>`
**Description:** Xóa vi phạm (requires login)

---

### `GET /discipline_management`
**Description:** Trang quản lý kỷ luật (requires login)

**Response:** Renders `discipline_management.html`

---

## Attendance Routes

### `GET /attendance`
**Description:** Trang quản lý điểm danh (requires login)

**Response:** Renders `attendance.html`

---

### `POST /api/attendance/face_checkin`
**Description:** Điểm danh bằng nhận diện khuôn mặt (requires login)

**Request Body (multipart/form-data):**
- `image` (file) - Ảnh chụp từ camera
- `class_name` (string) - Tên lớp
- `attendance_date` (string) - Ngày điểm danh

**Response (JSON):**
```json
{
  "success": true, "student_id": 123, "student_name": "Nguyễn Văn A",
  "confidence": 0.95, "status": "Có mặt"
}
```

---

### `POST /api/attendance/qr_checkin`
**Description:** Điểm danh bằng QR code (requires login)

**Request Body (JSON):**
```json
{
  "qr_data": "EDUATT:123", "class_name": "12 Tin",
  "attendance_date": "2025-04-12", "scan_method": "camera"
}
```

---

### `GET /attendance/enroll/<int:student_id>`
**Description:** Trang đăng ký khuôn mặt học sinh (requires login)

**Response:** Renders `enroll_face.html`

---

### `POST /api/attendance/enroll/<int:student_id>`
**Description:** API đăng ký khuôn mặt học sinh (requires login)

**Request Body (multipart/form-data):**
- `images` (files) - Nhiều ảnh khuôn mặt

**Response (JSON):**
```json
{ "success": true, "enrolled": 5, "errors": [] }
```

---

### `POST /api/attendance/start_session`
**Description:** Bắt đầu phiên theo dõi điểm danh (requires login)

**Request Body (JSON):**
```json
{ "class_name": "12 Tin", "session_date": "2025-04-12" }
```

---

### `POST /api/attendance/confirm_session/<int:session_id>`
**Description:** Xác nhận phiên theo dõi và chuyển vi phạm (requires login)

---

### `GET /api/attendance/sessions`
**Description:** API lấy danh sách phiên điểm danh (requires login)

**Response (JSON):**
```json
{ "sessions": [{ "id": 1, "class_name": "12 Tin", "status": "open" }] }
```

---

### `GET /api/attendance/records`
**Description:** API lấy bản ghi điểm danh (requires login)

**Query Parameters:**
- `class_name`, `attendance_date`

---

## Timetable Routes

### `GET /timetable`
**Description:** Xem thời khóa biểu (requires login)

**Query Parameters:**
- `class_name`, `school_year`, `week_number`

**Response:** Renders `timetable.html`

---

### `GET /timetable_manage`
**Description:** Quản lý thời khóa biểu (requires login, admin)

**Query Parameters:**
- `class_name`, `school_year`, `week_number`

**Response:** Renders `timetable_manage.html`

---

### `POST /api/timetable/generate`
**Description:** Sinh thời khóa biểu bằng AI từ ảnh (requires login)

**Request Body (multipart/form-data):**
- `image` (file) - Ảnh thời khóa biểu
- `class_name` (string) - Tên lớp
- `school_year` (string) - Năm học
- `week_number` (integer) - Số tuần

---

### `POST /api/timetable/confirm`
**Description:** Lưu thời khóa biểu AI vào database (requires login)

**Request Body (JSON):**
```json
{
  "class_name": "12 Tin", "school_year": "2025-2026",
  "week_number": 15,
  "slots": [{ "day_of_week": 2, "period_number": 1, "subject_id": 1, "room": "A101" }]
}
```

---

### `POST /api/timetable/cell/save`
**Description:** Lưu một ô thời khóa biểu (requires login)

**Request Body (JSON):**
```json
{
  "class_name": "12 Tin", "school_year": "2025-2026",
  "week_number": 1, "day_of_week": 2, "period_number": 1,
  "subject_id": 1, "room": "A101"
}
```

---

### `GET /api/timetable/cell`
**Description:** API lấy thông tin một ô TKB (requires login)

**Query Parameters:**
- `class_name`, `day_of_week`, `period_number`, `school_year`, `week_number`

---

## Lesson Book Routes

### `GET /lesson_book`
**Description:** Trang chính sổ đầu bài (requires login)

**Response:** Renders `lesson_book.html`

---

### `GET /lesson_book/grid`
**Description:** Giao diện grid sổ đầu bài theo tuần (requires login)

**Query Parameters:**
- `class_name`, `school_year`, `semester`, `week_number`

**Response:** Renders `lesson_book_grid.html`

---

### `POST /api/lesson_book/week/save`
**Description:** Lưu thông tin tuần sổ đầu bài (requires login)

**Request Body (JSON):**
```json
{
  "class_name": "12 Tin", "school_year": "2025-2026",
  "week_number": 1, "semester": 1,
  "teacher_notes": "Ghi chú tuần"
}
```

---

### `POST /api/lesson_book/slot/save`
**Description:** Lưu một slot sổ đầu bài (requires login)

**Request Body (JSON):**
```json
{
  "week_id": 1, "day_of_week": 2, "period_number": 1,
  "subject_name": "Toán", "topic": "Đạo hàm",
  "objectives": "Hiểu khái niệm", "teaching_method": "Thuyết trình",
  "evaluation": "Trắc nghiệm", "homework": "Bài 1-10",
  "attendance_present": 40, "attendance_absent": 0
}
```

---

### `GET /api/lesson_book/slots/<int:week_id>`
**Description:** API lấy danh sách slots của một tuần (requires login)

---

### `GET /api/lesson_book/week`
**Description:** API lấy thông tin tuần (requires login)

**Query Parameters:**
- `class_name`, `week_number`, `school_year`

---

### `POST /api/lesson_book/entry`
**Description:** Tạo entry sổ đầu bài truyền thống (requires login)

---

## Messaging Routes

### `GET /group_chat`
**Description:** Chat nhóm (requires login)

**Response:** Renders `group_chat.html`

---

### `GET /private_chats`
**Description:** Chat riêng (requires login)

**Response:** Renders `private_chats.html`

---

### `GET /notifications`
**Description:** Thông báo (requires login)

**Response:** Renders `notifications.html`

---

### `POST /api/messaging/group/send`
**Description:** Gửi tin nhắn nhóm (requires login)

**Request Body (JSON):**
```json
{ "message": "Hello everyone" }
```

---

### `POST /api/messaging/private/send`
**Description:** Gửi tin nhắn riêng (requires login)

**Request Body (JSON):**
```json
{ "receiver_id": 5, "message": "Hello" }
```

---

### `POST /api/messaging/mark_read/<int:message_id>`
**Description:** Đánh dấu tin nhắn đã đọc (requires login)

---

### `POST /api/notifications/send`
**Description:** Gửi thông báo (requires login)

**Request Body (JSON):**
```json
{
  "title": "Thông báo", "message": "Nội dung",
  "target_role": "all", "notification_type": "announcement"
}
```

---

### `POST /api/notifications/<int:notif_id>/read`
**Description:** Đánh dấu thông báo đã đọc (requires login)

---

### `GET /api/notifications/unread_count`
**Description:** API đếm thông báo chưa đọc (requires login)

**Response (JSON):**
```json
{ "count": 5 }
```

---

## Student Management Routes

### `GET /manage_students`
**Description:** Danh sách học sinh (requires login)

**Query Parameters:**
- `search`, `class_select`

**Response:** Renders `manage_students.html`

---

### `GET|POST /add_student`
**Description:** Thêm học sinh mới (requires login, admin)

**POST:** Xử lý form thêm học sinh

---

### `GET|POST /edit_student/<int:student_id>`
**Description:** Sửa thông tin học sinh (requires login)

---

### `GET /student_detail/<int:student_id>`
**Description:** Trang chi tiết học sinh (requires login)

---

### `POST /delete_student/<int:student_id>`
**Description:** Xóa học sinh (requires login, admin)

---

### `GET /import_students`
**Description:** Giao diện nhập học sinh từ Excel (requires login, admin)

**Response:** Renders `import_students.html`

---

### `POST /api/import_students`
**Description:** API nhập học sinh từ Excel (requires login, admin)

**Request Body (multipart/form-data):**
- `file` (file) - File Excel

---

### `POST /upload_student_photo/<int:student_id>`
**Description:** Upload ảnh học sinh (requires login)

**Request Body (multipart/form-data):**
- `photo` (file) - File ảnh

---

### `POST /api/student/notification/send`
**Description:** Gửi thông báo cho học sinh (requires login)

**Request Body (JSON):**
```json
{
  "target_type": "class", "target_value": "12 Tin",
  "title": "Thông báo", "message": "Nội dung"
}
```

---

## Class Fund Routes

### `GET /class_fund`
**Description:** Quản lý quỹ lớp (requires login)

**Response:** Renders `class_fund.html`

---

### `POST /api/class_fund/collection`
**Description:** Ghi nhận thu tiền (requires login)

**Request Body (JSON):**
```json
{
  "class_name": "12 Tin", "school_year": "2025-2026",
  "amount_vnd": 500000, "purpose": "Quỹ lớp tháng 4",
  "payer_name": "Nguyễn Văn B", "collection_date": "2025-04-12"
}
```

---

### `POST /api/class_fund/expense`
**Description:** Ghi nhận chi tiêu (requires login)

**Request Body (JSON):**
```json
{
  "class_name": "12 Tin", "school_year": "2025-2026",
  "amount_vnd": 300000, "title": "Mua nước uống",
  "expense_date": "2025-04-12"
}
```

---

## Admin Management Routes

### `GET /admin/settings`
**Description:** Quản lý cài đặt hệ thống (requires admin)

**Response:** Renders `manage_settings.html`

---

### `POST /admin/reset_week`
**Description:** Reset tuần - lưu archive và reset điểm (requires admin)

---

### `POST /admin/update_week`
**Description:** Cập nhật số tuần hiện tại (requires admin)

---

### `GET /admin/fix_scores`
**Description:** Sửa điểm cho tất cả học sinh (requires admin)

---

### `GET /admin/teachers`
**Description:** Danh sách giáo viên (requires admin)

**Response:** Renders `manage_teachers.html`

---

### `GET|POST /admin/teachers/add`
**Description:** Thêm giáo viên mới (requires admin)

---

### `POST /admin/teachers/delete/<int:teacher_id>`
**Description:** Xóa giáo viên (requires admin)

---

### `POST /admin/teachers/<int:teacher_id>/permissions`
**Description:** Cập nhật quyền giáo viên (requires admin)

---

### `GET /admin/classes`
**Description:** Quản lý lớp học (requires admin)

**Response:** Renders `manage_classes.html`

---

### `POST /admin/classes/add`
**Description:** Thêm lớp mới (requires admin)

---

## Subjects Management Routes

### `GET /subjects_mgmt`
**Description:** Quản lý môn học (requires admin)

**Response:** Renders `subjects_mgmt.html`

---

### `POST /add_subject`
**Description:** Thêm môn học mới (requires admin)

---

### `POST /delete_subject/<int:subject_id>`
**Description:** Xóa môn học (requires admin)

---

## Class Subjects Routes

### `GET /class_subjects`
**Description:** Phân công môn học cho lớp (requires login)

**Query Parameters:**
- `class_name`, `school_year`

**Response:** Renders `class_subjects.html`

---

### `POST /api/class_subjects/save`
**Description:** Lưu phân công môn học (requires login)

**Request Body (JSON):**
```json
{
  "class_name": "12 Tin", "school_year": "2025-2026",
  "subjects": [{ "subject_id": 1, "is_compulsory": true, "periods_per_week": 5 }]
}
```

---

## Rules & Bonus Routes

### `GET /rules`
**Description:** Quản lý loại vi phạm (requires login)

**Response:** Renders `rules.html`

---

### `POST /add_rule`
**Description:** Thêm loại vi phạm (requires admin)

---

### `POST /delete_rule/<int:rule_id>`
**Description:** Xóa loại vi phạm (requires admin)

---

### `GET /bonuses`
**Description:** Quản lý loại điểm cộng (requires login)

**Response:** Renders `bonuses.html`

---

### `POST /add_bonus`
**Description:** Thêm loại điểm cộng (requires admin)

---

### `POST /delete_bonus/<int:bonus_id>`
**Description:** Xóa loại điểm cộng (requires admin)

---

### `POST /add_bonus_record`
**Description:** Thêm điểm cộng cho học sinh (requires login)

**Request Body (form):**
- `bonus_type_id`, `student_id`, `reason`

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

---

## Access Control

### Role-Based Access
| Role | Access |
|------|--------|
| admin | Full access |
| homeroom_teacher | Assigned class students |
| subject_teacher | Assigned subject grades, assigned classes |
| both | Homeroom + subject teacher privileges |
| discipline_officer | All students for discipline management |
| parent_student | Student/parent portal access |

### Permission-Based Access
Granular permissions in `Permission` table:
- `view_grades` - View student grades
- `manage_grades` - Enter/edit grades
- `manage_students` - Manage student records
- `manage_discipline` - Manage violations
- `manage_subjects` - Manage subjects
- etc.

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

### Timetable AI Preview
- `session['timetable_ai_preview_id']` for AI preview state

---

## AI Integration

### Ollama Integration
- Uses local Ollama server (configurable via `OLLAMA_HOST` and `OLLAMA_MODEL` in .env)
- `call_ollama(prompt)` - Simple text chat
- `_call_gemini(prompt, image_path, is_json)` - Vision and JSON support (legacy name, uses Ollama)

### AI Features
1. **Context-Aware Chatbot** - Conversation memory, student search, action buttons
2. **OCR Grade Entry** - Image processing, JSON parsing, student matching
3. **Report Generation** - Conduct reports, parent reports, chart comments
4. **Timetable Generation** - Image-to-timetable conversion
5. **Class Statistics Analysis** - AI-powered class analysis

---

## Security

### Password Hashing
- Uses `werkzeug.security.generate_password_hash()`
- Supports legacy plain text for backward compatibility

### SQL Injection Prevention
- Uses SQLAlchemy ORM (parameterized queries)

### Session Security
- Flask-Login secure session management
- SECRET_KEY in app config

---

## File Uploads

### Upload Folder
- Configured in `UPLOAD_FOLDER` (default: `uploads/`)
- Subfolders: `student_portraits/`, `face_enrollment/`, `attendance_photos/`, `face_models/`, `timetable_ai_preview/`

### File Handling Pattern
```python
filename = f"prefix_{uuid.uuid4().hex}_{original_filename}"
filepath = os.path.join(UPLOAD_FOLDER, filename)
file.save(filepath)
```
