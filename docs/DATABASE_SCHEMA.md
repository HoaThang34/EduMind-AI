# Database Schema Documentation - EduMind-AI

## Tổng Quan

EduMind-AI sử dụng SQLAlchemy ORM với SQLite database. Tất cả 31 models được định nghĩa trong `models.py`.

## Danh Sách Models

| # | Model | Mô tả |
|---|-------|--------|
| 1 | ClassRoom | Lớp học |
| 2 | SystemConfig | Cấu hình hệ thống |
| 3 | Permission | Định nghĩa quyền |
| 4 | TeacherPermission | Gán quyền cho giáo viên |
| 5 | Teacher | Tài khoản giáo viên |
| 6 | ConductSetting | Cấu hình ngưỡng hạnh kiểm |
| 7 | Student | Hồ sơ học sinh |
| 8 | ViolationType | Loại vi phạm |
| 9 | Violation | Bản ghi vi phạm |
| 10 | WeeklyArchive | Lưu trữ tuần |
| 11 | TimetableSlot | Ô thời khóa biểu |
| 12 | Subject | Môn học |
| 13 | ClassSubject | Phân công môn cho lớp |
| 14 | Grade | Điểm số |
| 15 | ChatConversation | Lịch sử chatbot |
| 16 | BonusType | Loại điểm cộng |
| 17 | BonusRecord | Bản ghi điểm cộng |
| 18 | Notification | Thông báo giáo viên |
| 19 | GroupChatMessage | Tin nhắn nhóm |
| 20 | PrivateMessage | Tin nhắn riêng |
| 21 | ChangeLog | Lịch sử thay đổi |
| 22 | LessonBookEntry | Sổ đầu bài (entry) |
| 23 | LessonBookWeek | Meta tuần sổ đầu bài |
| 24 | LessonBookSlot | Ô slot trong grid tuần |
| 25 | StudentNotification | Thông báo học sinh |
| 26 | ClassFundCollection | Thu tiền quỹ lớp |
| 27 | ClassFundExpense | Chi tiêu quỹ lớp |
| 28 | AttendanceRecord | Bản ghi điểm danh |
| 29 | AttendanceMonitoringSession | Phiên theo dõi điểm danh |
| 30 | SessionViolationRecord | Vi phạm trong phiên |
| 31 | TeacherClassAssignment | Phân công giáo viên dạy lớp |

---

## Chi Tiết Từng Model

### 1. ClassRoom

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `name` | String(50), Unique, Not Null | Tên lớp (VD: "12 Tin") |

---

### 2. SystemConfig

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `key` | String(50), Unique, Not Null | Key cấu hình |
| `value` | String(255), Not Null | Giá trị |
| `last_updated` | DateTime | Thời gian cập nhật cuối |

**Common Keys:**
- `school_name` - Tên trường
- `school_year` - Năm học hiện tại
- `current_week` - Số tuần hiện tại
- `current_semester` - Học kỳ hiện tại
- `last_reset_week_id` - Tuần cuối reset điểm

---

### 3. Permission

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `code` | String(50), Unique, Not Null | Mã quyền |
| `name` | String(100), Not Null | Tên hiển thị |
| `description` | String(255) | Mô tả |
| `category` | String(50) | Phân loại |
| `created_at` | DateTime | Thời gian tạo |

---

### 4. TeacherPermission

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `teacher_id` | Integer, FK → Teacher, Not Null, Indexed | Giáo viên |
| `permission_id` | Integer, FK → Permission, Not Null | Quyền |
| `granted_by` | Integer, FK → Teacher | Admin cấp quyền |
| `granted_at` | DateTime | Thời gian cấp |

**Constraint:** Unique trên (teacher_id, permission_id)

---

### 5. Teacher

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `username` | String(50), Unique, Not Null | Tên đăng nhập |
| `password` | String(100), Not Null | Password (hashed) |
| `full_name` | String(100), Not Null | Họ tên đầy đủ |
| `school_name` | String(150), Default: "THPT Chuyên Nguyễn Tất Thành" | Tên trường |
| `main_class` | String(20) | Lớp chủ nhiệm chính |
| `dob` | String(20) | Ngày sinh |
| `role` | String(20), Default: "homeroom_teacher" | Vai trò |
| `assigned_class` | String(50) | Lớp được phân công (GVCN) |
| `assigned_subject_id` | Integer, FK → Subject | Môn được phân công (GVBM) |
| `created_by` | Integer, FK → Teacher | Admin tạo tài khoản |
| `created_at` | DateTime | Thời gian tạo |

**Role Values:**
- `admin` - Quản trị viên
- `homeroom_teacher` - Giáo viên chủ nhiệm
- `subject_teacher` - Giáo viên bộ môn
- `both` - GVCN + GVBM
- `discipline_officer` - Giáo viên nền nếp
- `parent_student` - Phụ huynh/Học sinh

**Methods:**
- `set_password(pwd)` - Hash và set password
- `check_password(pwd)` - Verify password
- `has_permission(permission_code)` - Kiểm tra quyền
- `get_all_permissions()` - Lấy danh sách quyền
- `get_role_display()` - Tên hiển thị vai trò

**Relationships:**
- `assigned_subject` → Subject
- `teacher_permissions` → TeacherPermission
- `class_assignments` → TeacherClassAssignment

---

### 6. ConductSetting

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `good_threshold` | Integer, Default: 80 | Ngưỡng Tốt (>=80) |
| `fair_threshold` | Integer, Default: 65 | Ngưỡng Khá (>=65) |
| `average_threshold` | Integer, Default: 50 | Ngưỡng Trung bình (>=50) |
| `warning_yellow_threshold` | Integer, Default: 70 | Ngưỡng cảnh báo Vàng |
| `warning_red_threshold` | Integer, Default: 55 | Ngưỡng cảnh báo Đỏ |
| `academic_yellow_threshold` | Float, Default: 6.5 | Ngưỡng học lực Vàng |
| `academic_red_threshold` | Float, Default: 5.0 | Ngưỡng học lực Đỏ |

---

### 7. Student

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `student_code` | String(50), Unique, Not Null | Mã học sinh |
| `name` | String(100), Not Null | Họ tên |
| `student_class` | String(20), Not Null | Lớp |
| `current_score` | Integer, Default: 100 | Điểm nề nếp hiện tại |
| `parent_name` | String(150) | Tên phụ huynh |
| `parent_phone` | String(20) | SĐT phụ huynh |
| `portrait_filename` | String(255) | File ảnh chân dung |
| `date_of_birth` | String(30) | Ngày sinh (DD/MM/YYYY) |
| `position` | String(50) | Chức vụ (Lớp trưởng, Bí thư...) |
| `conduct` | String(20), Default: "Tốt" | Hạnh kiểm |
| `warning_level` | String(20), Default: "Xanh" | Mức cảnh báo |
| `academic_rank` | String(20), Default: "Khá" | Học lực |
| `academic_warning_level` | String(20), Default: "Xanh" | Cảnh báo học tập |
| `id_card` | String(20) | Số CCCD/CMND |
| `ethnicity` | String(50) | Dân tộc |
| `password` | String(100) | Password đăng nhập |

**Conduct Values:** Tốt, Khá, Trung bình, Yếu
**Warning Levels:** Xanh, Vàng, Đỏ
**Academic Ranks:** Giỏi, Khá, Trung bình, Yếu

**Methods:**
- `set_password(pwd)` - Hash và set password
- `check_password(pwd)` - Verify password

---

### 8. ViolationType

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `name` | String(200), Unique, Not Null | Tên loại vi phạm |
| `points_deducted` | Integer, Not Null | Điểm trừ |

---

### 9. Violation

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `student_id` | Integer, FK → Student, Not Null | Học sinh |
| `violation_type_name` | String(200), Not Null | Tên loại vi phạm |
| `points_deducted` | Integer, Not Null | Điểm trừ |
| `date_committed` | DateTime, Default: utcnow | Ngày vi phạm |
| `week_number` | Integer, Default: 1 | Số tuần |
| `lesson_book_entry_id` | Integer, FK → LessonBookEntry, Nullable | Liên kết sổ đầu bài |

**Relationships:**
- `student` → Student
- `linked_lesson` → LessonBookEntry

---

### 10. WeeklyArchive

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `week_number` | Integer, Not Null | Số tuần |
| `student_id` | Integer, Nullable | ID học sinh |
| `student_name` | String(100) | Tên học sinh |
| `student_code` | String(50) | Mã học sinh |
| `student_class` | String(20) | Lớp |
| `final_score` | Integer | Điểm cuối tuần |
| `total_deductions` | Integer | Tổng điểm trừ |
| `created_at` | DateTime | Thời gian tạo |

---

### 11. TimetableSlot

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `class_name` | String(50), Not Null, Indexed | Tên lớp |
| `day_of_week` | Integer, Not Null | Thứ (1=Thứ Hai...7=Chủ nhật) |
| `period_number` | Integer, Not Null | Số tiết |
| `subject_id` | Integer, FK → Subject, Nullable | Môn học |
| `subject_name_override` | String(120) | Ghi đè tên môn |
| `teacher_id` | Integer, FK → Teacher, Nullable | Giáo viên |
| `room` | String(50) | Phòng học |
| `school_year` | String(20), Not Null, Indexed | Năm học |
| `week_number` | Integer, Not Null, Default: 1 | Tuần ISO |
| `created_at` | DateTime | Thời gian tạo |
| `updated_at` | DateTime | Thời gian cập nhật |

**Constraint:** Unique trên (class_name, day_of_week, period_number, school_year, week_number)

---

### 12. Subject

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `name` | String(100), Unique, Not Null | Tên môn học |
| `code` | String(20), Unique, Not Null | Mã môn |
| `description` | String(200) | Mô tả |
| `num_tx_columns` | Integer, Default: 3 | Số cột TX (điểm thường xuyên) |
| `num_gk_columns` | Integer, Default: 1 | Số cột GK (giữa kỳ) |
| `num_hk_columns` | Integer, Default: 1 | Số cột HK (cuối kỳ) |
| `is_pass_fail` | Boolean, Default: False | Môn đạt/không đạt (Thể dục...) |
| `created_at` | DateTime | Thời gian tạo |

---

### 13. ClassSubject

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `class_name` | String(50), Not Null, Indexed | Tên lớp |
| `subject_id` | Integer, FK → Subject, Not Null, Indexed | Môn học |
| `school_year` | String(20), Not Null, Default: "2025-2026" | Năm học |
| `is_compulsory` | Boolean, Default: True | Bắt buộc |
| `periods_per_week` | Integer, Default: 3 | Số tiết/tuần |
| `created_at` | DateTime | Thời gian tạo |
| `created_by` | Integer, FK → Teacher | Người tạo |

**Constraint:** Unique trên (class_name, subject_id, school_year)

---

### 14. Grade

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `student_id` | Integer, FK → Student, Not Null | Học sinh |
| `subject_id` | Integer, FK → Subject, Not Null | Môn học |
| `grade_type` | String(10), Not Null | Loại điểm: TX, GK, HK |
| `column_index` | Integer, Default: 1 | Cột điểm (nhiều điểm cùng loại) |
| `score` | Float, Not Null | Điểm (0-10) |
| `semester` | Integer, Not Null | Học kỳ (1 hoặc 2) |
| `school_year` | String(20) | Năm học |
| `date_recorded` | DateTime, Default: utcnow | Ngày nhập |

**Relationships:**
- `student` → Student (cascade delete)
- `subject` → Subject (cascade delete)

---

### 15. ChatConversation

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `session_id` | String(100), Not Null, Indexed | Session ID |
| `teacher_id` | Integer, FK → Teacher, Nullable | ID giáo viên |
| `student_id` | Integer, FK → Student, Nullable | ID học sinh |
| `role` | String(20), Not Null | 'user' hoặc 'assistant' |
| `message` | Text, Not Null | Nội dung tin nhắn |
| `context_data` | Text, Nullable | JSON metadata |
| `created_at` | DateTime, Indexed | Thời gian tạo |

---

### 16. BonusType

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `name` | String(200), Unique, Not Null | Tên loại điểm cộng |
| `points_added` | Integer, Not Null | Điểm cộng |
| `description` | String(500) | Mô tả |

---

### 17. BonusRecord

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `student_id` | Integer, FK → Student, Not Null | Học sinh |
| `bonus_type_name` | String(200), Not Null | Tên loại điểm cộng |
| `points_added` | Integer, Not Null | Điểm cộng |
| `reason` | String(500) | Lý do cụ thể |
| `date_awarded` | DateTime, Default: utcnow | Ngày thưởng |
| `week_number` | Integer, Default: 1 | Số tuần |

---

### 18. Notification

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `title` | String(200), Not Null | Tiêu đề |
| `message` | Text, Not Null | Nội dung |
| `created_at` | DateTime | Thời gian tạo |
| `created_by` | Integer, FK → Teacher | Người tạo |
| `notification_type` | String(50) | Loại: violation, grade, bonus, announcement |
| `target_role` | String(50) | 'all', 'homeroom_teacher', 'subject_teacher', hoặc class name |
| `is_read` | Boolean, Default: False | Đã đọc |
| `recipient_id` | Integer, FK → Teacher | Người nhận |

---

### 19. GroupChatMessage

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `sender_id` | Integer, FK → Teacher, Not Null | Người gửi |
| `message` | Text, Not Null | Nội dung tin nhắn |
| `created_at` | DateTime | Thời gian gửi |

---

### 20. PrivateMessage

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `sender_id` | Integer, FK → Teacher, Not Null | Người gửi |
| `receiver_id` | Integer, FK → Teacher, Not Null | Người nhận |
| `message` | Text, Not Null | Nội dung tin nhắn |
| `created_at` | DateTime | Thời gian gửi |
| `is_read` | Boolean, Default: False | Đã đọc |

---

### 21. ChangeLog

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `changed_by_id` | Integer, FK → Teacher, Nullable | Người thay đổi |
| `change_type` | String(50), Not Null | Loại thay đổi |
| `student_id` | Integer, FK → Student, Nullable | Học sinh bị ảnh hưởng |
| `student_name` | String(100) | Tên học sinh |
| `student_class` | String(20) | Lớp học sinh |
| `description` | Text, Not Null | Mô tả thay đổi |
| `old_value` | String(200) | Giá trị cũ |
| `new_value` | String(200) | Giá trị mới |
| `created_at` | DateTime | Thời gian thay đổi |

**Change Types:** violation, bonus, grade, grade_update, grade_delete, violation_delete, score_reset, bulk_violation

---

### 22. LessonBookEntry

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `teacher_id` | Integer, FK → Teacher, Not Null, Indexed | Giáo viên |
| `class_name` | String(50), Not Null, Indexed | Tên lớp |
| `timetable_slot_id` | Integer, FK → TimetableSlot, Nullable, Indexed | Liên kết TKB |
| `subject_id` | Integer, FK → Subject, Nullable, Indexed | Môn học |
| `lesson_date` | Date, Not Null, Indexed | Ngày dạy |
| `period_number` | Integer, Not Null, Default: 1 | Tiết thứ |
| `topic` | Text, Not Null | Bài dạy |
| `objectives` | Text | Mục tiêu |
| `teaching_method` | Text | Phương pháp dạy học |
| `evaluation` | Text | Đánh giá |
| `homework` | Text | Bài tập |
| `notes` | Text | Ghi chú |
| `attendance_present` | Integer | Số có mặt |
| `attendance_absent` | Integer | Số vắng |
| `school_year` | String(20) | Năm học |
| `semester` | Integer, Default: 1 | Học kỳ |
| `created_at` | DateTime | Thời gian tạo |
| `updated_at` | DateTime | Thời gian cập nhật |

---

### 23. LessonBookWeek

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `teacher_id` | Integer, FK → Teacher, Not Null, Indexed | Giáo viên |
| `class_name` | String(50), Not Null, Indexed | Tên lớp |
| `week_number` | Integer, Not Null, Indexed | Số tuần ISO (1-53) |
| `school_year` | String(20), Not Null | Năm học |
| `semester` | Integer, Default: 1 | Học kỳ |
| `teacher_notes` | Text | Ghi chú tuần |
| `created_at` | DateTime | Thời gian tạo |
| `updated_at` | DateTime | Thời gian cập nhật |

**Constraint:** Unique trên (teacher_id, class_name, week_number)

---

### 24. LessonBookSlot

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `week_id` | Integer, FK → LessonBookWeek, Not Null, Indexed | Tuần reference |
| `day_of_week` | Integer, Not Null | Thứ (1=Thứ 2...7=Chủ nhật) |
| `period_number` | Integer, Not Null, Default: 1 | Tiết thứ |
| `lesson_date` | Date, Nullable, Indexed | Ngày dạy |
| `subject_name` | String(100) | Tên môn (ghi nhanh) |
| `topic` | Text | Bài dạy |
| `objectives` | Text | Mục tiêu |
| `teaching_method` | Text | Phương pháp dạy học |
| `evaluation` | Text | Đánh giá |
| `homework` | Text | Bài tập |
| `notes` | Text | Ghi chú |
| `attendance_present` | Integer | Số có mặt |
| `attendance_absent` | Integer | Số vắng |
| `created_at` | DateTime | Thời gian tạo |
| `updated_at` | DateTime | Thời gian cập nhật |

**Constraint:** Unique trên (week_id, day_of_week, period_number)

---

### 25. StudentNotification

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `student_id` | Integer, FK → Student, Not Null, Indexed | Học sinh |
| `title` | String(200), Not Null | Tiêu đề |
| `message` | Text, Not Null | Nội dung |
| `notification_type` | String(50) | Loại thông báo |
| `is_read` | Boolean, Default: False | Đã đọc |
| `created_at` | DateTime | Thời gian tạo |
| `sender_id` | Integer, FK → Teacher, Nullable | Người gửi |

---

### 26. ClassFundCollection

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `class_name` | String(50), Not Null, Indexed | Tên lớp |
| `school_year` | String(20), Not Null, Indexed | Năm học |
| `amount_vnd` | Integer, Not Null | Số tiền (VND) |
| `purpose` | String(200), Not Null | Mục đích thu |
| `student_id` | Integer, FK → Student, Nullable, Indexed | Học sinh cụ thể |
| `payer_name` | String(150) | Tên người nộp |
| `collection_date` | Date, Not Null | Ngày thu |
| `notes` | Text | Ghi chú |
| `created_by_id` | Integer, FK → Teacher, Nullable | Người tạo |
| `created_at` | DateTime | Thời gian tạo |

---

### 27. ClassFundExpense

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `class_name` | String(50), Not Null, Indexed | Tên lớp |
| `school_year` | String(20), Not Null, Indexed | Năm học |
| `amount_vnd` | Integer, Not Null | Số tiền (VND) |
| `title` | String(200), Not Null | Nội dung chi |
| `expense_date` | Date, Not Null | Ngày chi |
| `notes` | Text | Ghi chú |
| `created_by_id` | Integer, FK → Teacher, Nullable | Người tạo |
| `created_at` | DateTime | Thời gian tạo |

---

### 28. AttendanceRecord

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `student_id` | Integer, FK → Student, Not Null, Indexed | Học sinh |
| `class_name` | String(50), Not Null, Indexed | Tên lớp |
| `check_in_time` | DateTime, Not Null, Default: utcnow | Giờ check-in |
| `captured_photo` | String(255), Nullable | Đường dẫn ảnh chụp |
| `confidence` | Float, Default: 0.0 | Độ tin cậy nhận diện (0-1) |
| `status` | String(20), Default: "Có mặt" | Trạng thái |
| `notes` | Text, Nullable | Ghi chú |
| `recorded_by_id` | Integer, FK → Teacher, Nullable | Người ghi |
| `attendance_date` | Date, Not Null, Indexed | Ngày điểm danh |
| `attendance_mode` | String(20), Default: "face" | Mode: 'face' hoặc 'qr' |
| `qr_scan_method` | String(30), Nullable | 'camera' hoặc 'direct' |
| `monitoring_session_id` | Integer, FK → AttendanceMonitoringSession, Nullable | Phiên theo dõi |

**Status Values:** Có mặt, Trễ, Vắng

---

### 29. AttendanceMonitoringSession

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `teacher_id` | Integer, FK → Teacher, Not Null, Indexed | Giáo viên |
| `class_name` | String(50), Not Null, Indexed | Tên lớp |
| `start_time` | DateTime, Not Null | Giờ bắt đầu |
| `end_time` | DateTime, Nullable | Giờ kết thúc |
| `session_date` | Date, Not Null, Indexed | Ngày phiên |
| `status` | String(20), Default: "open" | Trạng thái |
| `notes` | Text, Nullable | Ghi chú |
| `created_at` | DateTime | Thời gian tạo |

**Status Values:** 'open', 'confirmed', 'cancelled'

---

### 30. SessionViolationRecord

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `session_id` | Integer, FK → AttendanceMonitoringSession, Not Null, Indexed | Phiên |
| `student_id` | Integer, FK → Student, Not Null, Indexed | Học sinh |
| `violation_type_name` | String(200), Not Null | Tên loại vi phạm |
| `points_deducted` | Integer, Not Null | Điểm trừ |
| `status` | String(20), Default: "pending" | Trạng thái |
| `recorded_at` | DateTime, Default: utcnow | Thời điểm ghi |
| `notes` | Text, Nullable | Ghi chú |
| `official_violation_id` | Integer, FK → Violation, Nullable | Violation chính thức |

**Status Values:** 'pending', 'confirmed'

---

### 31. TeacherClassAssignment

| Trường | Kiểu | Mô tả |
|---------|------|--------|
| `id` | Integer, PK | Primary key |
| `teacher_id` | Integer, FK → Teacher, Not Null, Indexed | Giáo viên |
| `class_name` | String(50), Not Null, Indexed | Lớp được phân công |
| `subject_id` | Integer, FK → Subject, Nullable | Môn dạy ở lớp này |
| `school_year` | String(20), Not Null, Default: "2025-2026" | Năm học |
| `created_at` | DateTime | Thời gian tạo |
| `created_by` | Integer, FK → Teacher | Người tạo |

**Constraint:** Unique trên (teacher_id, class_name)

---

## Indexes

### Indexed Fields

| Bảng | Fields |
|------|--------|
| Student | student_code, student_class |
| TeacherPermission | teacher_id |
| TeacherClassAssignment | teacher_id, class_name |
| ClassSubject | class_name, subject_id |
| Violation | student_id, week_number |
| Grade | student_id, subject_id |
| TimetableSlot | class_name, school_year |
| LessonBookEntry | teacher_id, class_name, subject_id, lesson_date |
| LessonBookWeek | teacher_id, class_name, week_number |
| LessonBookSlot | week_id |
| AttendanceRecord | student_id, class_name, attendance_date |
| AttendanceMonitoringSession | teacher_id, class_name, session_date |
| SessionViolationRecord | session_id, student_id |
| ChatConversation | session_id, created_at |
| Notification | recipient_id |
| StudentNotification | student_id |
| ClassFundCollection | class_name, school_year, student_id |
| ClassFundExpense | class_name, school_year |

---

## Quan Hệ Giữa Các Bảng

### One-to-Many
- ClassRoom → Students (via student_class)
- Subject → Grades
- Subject → TimetableSlots
- Teacher → TeacherPermissions
- Teacher → LessonBookEntries
- Student → Grades (cascade delete)
- Student → Violations
- Student → BonusRecords
- Student → ChatConversations
- Student → StudentNotifications
- Student → AttendanceRecords
- LessonBookWeek → LessonBookSlots (cascade delete)
- AttendanceMonitoringSession → SessionViolationRecords
- AttendanceMonitoringSession → AttendanceRecords

### Many-to-One
- Grade → Student
- Grade → Subject
- Violation → Student
- BonusRecord → Student
- ChatConversation → Teacher
- ChatConversation → Student
- LessonBookEntry → Teacher
- LessonBookEntry → Subject
- LessonBookSlot → LessonBookWeek
- TeacherPermission → Teacher
- TeacherPermission → Permission
- TeacherClassAssignment → Teacher
- TeacherClassAssignment → Subject

### Many-to-Many
- Teacher ↔ Permission (via TeacherPermission)
- Teacher ↔ Class (via TeacherClassAssignment)

---

## Database Migrations

Hệ thống bao gồm 16 migration functions trong `app.py`:

| # | Function | Mô tả |
|---|----------|--------|
| 1 | ensure_student_parent_columns | Thêm parent_name, parent_phone |
| 2 | ensure_student_portrait_column | Thêm portrait_filename |
| 3 | ensure_student_date_of_birth_column | Thêm date_of_birth |
| 4 | ensure_student_position_column | Thêm position |
| 5 | ensure_lesson_book_timetable_column | Thêm timetable_slot_id |
| 6 | ensure_violation_lesson_book_column | Thêm lesson_book_entry_id |
| 7 | ensure_timetable_slot_week_number_column | Đổi semester → week_number |
| 8 | ensure_student_notification_sender_column | Thêm sender_id |
| 9 | ensure_student_conduct_columns | Thêm conduct, warning_level, academic_rank, academic_warning_level |
| 10 | ensure_attendance_qr_columns | Thêm attendance_mode, qr_scan_method |
| 11 | ensure_attendance_monitoring_session_column | Thêm monitoring_session_id |
| 12 | ensure_lesson_book_week_and_slot_tables | Tạo bảng lesson_book_week và lesson_book_slot |
| 13 | ensure_lesson_book_slot_lesson_date_column | Thêm lesson_date |
| 14 | ensure_subject_is_pass_fail_column | Thêm is_pass_fail |
| 15 | ensure_teacher_class_assignment_table | Tạo bảng teacher_class_assignment |
| 16 | ensure_class_subject_table | Tạo bảng class_subject |

---

## Dữ Liệu Mặc Định

### Default Admin User
- Username: `admin`
- Password: `admin` (hashed on first run)

### Default SystemConfig
- `current_week`: "1"
- `school_name`: "THPT Chuyên Nguyễn Tất Thành"

### Default ViolationType
- "Đi muộn": 2 điểm

### Default ConductSetting
- good_threshold: 80
- fair_threshold: 65
- average_threshold: 50
- warning_yellow_threshold: 70
- warning_red_threshold: 55
- academic_yellow_threshold: 6.5
- academic_red_threshold: 5.0
