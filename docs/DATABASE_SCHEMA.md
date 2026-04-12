# Database Schema Documentation - EduMind-AI

## Overview
EduMind-AI uses SQLAlchemy ORM with SQLite database. All models are defined in `models.py`.

## Core Models

### 1. ClassRoom
**Description:** Represents a class in the school

**Fields:**
- `id` (Integer, Primary Key)
- `name` (String(50), Unique, Not Null) - Class name (e.g., "12 Tin")

---

### 2. SystemConfig
**Description:** System-wide configuration settings

**Fields:**
- `id` (Integer, Primary Key)
- `key` (String(50), Unique, Not Null) - Configuration key
- `value` (String(255), Not Null) - Configuration value
- `last_updated` (DateTime) - Last update timestamp

**Common Keys:**
- `school_name` - School name
- `school_year` - Current school year (e.g., "2025-2026")
- `current_week` - Current week number (ISO week)
- `current_semester` - Current semester (1 or 2)
- `last_reset_week_id` - Last week when scores were reset

---

### 3. Permission
**Description:** Defines system permissions for granular access control

**Fields:**
- `id` (Integer, Primary Key)
- `code` (String(50), Unique, Not Null) - Permission code
- `name` (String(100), Not Null) - Display name
- `description` (String(255)) - Description
- `category` (String(50)) - Category (grades, discipline, students, attendance, etc.)
- `created_at` (DateTime) - Creation timestamp

---

### 4. TeacherPermission
**Description:** Assigns specific permissions to teachers

**Fields:**
- `id` (Integer, Primary Key)
- `teacher_id` (Integer, Foreign Key → Teacher, Not Null, Indexed)
- `permission_id` (Integer, Foreign Key → Permission, Not Null)
- `granted_by` (Integer, Foreign Key → Teacher) - Admin who granted permission
- `granted_at` (DateTime) - When permission was granted

**Constraints:**
- Unique constraint on (teacher_id, permission_id)

**Relationships:**
- `teacher` → Teacher (foreign key: teacher_id)
- `permission` → Permission
- `grantor` → Teacher (foreign key: granted_by)

---

### 5. Teacher
**Description:** Teacher accounts with role-based access control

**Fields:**
- `id` (Integer, Primary Key)
- `username` (String(50), Unique, Not Null)
- `password` (String(100), Not Null) - Hashed password
- `full_name` (String(100), Not Null)
- `school_name` (String(150), Default: get_default_school_name())
- `main_class` (String(20)) - Main class assigned
- `dob` (String(20)) - Date of birth
- `role` (String(20), Default: "homeroom_teacher") - Role: admin, homeroom_teacher, subject_teacher, both, discipline_officer, parent_student
- `assigned_class` (String(50)) - Class assigned (for homeroom teachers)
- `assigned_subject_id` (Integer, Foreign Key → Subject) - Subject assigned (for subject teachers)
- `created_by` (Integer, Foreign Key → Teacher) - Admin who created this account
- `created_at` (DateTime) - Creation timestamp

**Methods:**
- `set_password(pwd)` - Hash and set password
- `check_password(pwd)` - Verify password (supports both hashed and legacy plain text)
- `has_permission(permission_code)` - Check if teacher has specific permission
- `get_all_permissions()` - Get list of all permission codes
- `get_role_display()` - Get Vietnamese display name for role

**Relationships:**
- `assigned_subject` → Subject (foreign key: assigned_subject_id)
- `teacher_permissions` → TeacherPermission (backref)
- `class_assignments` → TeacherClassAssignment

---

### 6. ConductSetting
**Description:** Configuration for conduct score thresholds

**Fields:**
- `id` (Integer, Primary Key)
- `good_threshold` (Integer, Default: 80) - Good conduct >= 80
- `fair_threshold` (Integer, Default: 65) - Fair conduct >= 65
- `average_threshold` (Integer, Default: 50) - Average conduct >= 50
- `warning_yellow_threshold` (Integer, Default: 70) - Yellow warning level
- `warning_red_threshold` (Integer, Default: 55) - Red warning level
- `academic_yellow_threshold` (Float, Default: 6.5) - Academic warning yellow
- `academic_red_threshold` (Float, Default: 5.0) - Academic warning red

---

### 7. Student
**Description:** Student records

**Fields:**
- `id` (Integer, Primary Key)
- `student_code` (String(50), Unique, Not Null) - Student code
- `name` (String(100), Not Null) - Full name
- `student_class` (String(20), Not Null) - Class name
- `current_score` (Integer, Default: 100) - Current conduct score (100-based)
- `parent_name` (String(150)) - Parent/guardian name
- `parent_phone` (String(20)) - Parent phone number
- `portrait_filename` (String(255)) - Portrait photo filename
- `date_of_birth` (String(30)) - Date of birth (format: DD/MM/YYYY)
- `position` (String(50)) - Class position (Class monitor, Secretary, etc.)
- `conduct` (String(20), Default: "Tốt") - Conduct rating
- `warning_level` (String(20), Default: "Xanh") - Warning level (Xanh, Vàng, Đỏ)
- `academic_rank` (String(20), Default: "Khá") - Academic ranking
- `academic_warning_level` (String(20), Default: "Xanh") - Academic warning level
- `id_card` (String(20)) - ID card number
- `ethnicity` (String(50)) - Ethnicity
- `password` (String(100)) - Password for student portal login

**Methods:**
- `set_password(pwd)` - Hash and set password
- `check_password(pwd)` - Verify password

**Relationships:**
- `grades` → Grade (backref, cascade delete)
- `violations` → Violation (backref)
- `bonuses` → BonusRecord (backref)
- `chat_history` → ChatConversation (backref)
- `student_notifications` → StudentNotification (backref)

---

### 8. ViolationType
**Description:** Types of violations with point deductions

**Fields:**
- `id` (Integer, Primary Key)
- `name` (String(200), Unique, Not Null) - Violation name
- `points_deducted` (Integer, Not Null) - Points to deduct

---

### 9. Violation
**Description:** Student violation records

**Fields:**
- `id` (Integer, Primary Key)
- `student_id` (Integer, Foreign Key → Student, Not Null)
- `violation_type_name` (String(200), Not Null) - Type of violation
- `points_deducted` (Integer, Not Null) - Points deducted
- `date_committed` (DateTime, Default: datetime.utcnow) - When violation occurred
- `week_number` (Integer, Default: 1) - Week number (ISO week)
- `lesson_book_entry_id` (Integer, Foreign Key → LessonBookEntry, Nullable) - Linked lesson

**Relationships:**
- `student` → Student (backref)
- `linked_lesson` → LessonBookEntry (backref)

---

### 10. WeeklyArchive
**Description:** Weekly archived student data

**Fields:**
- `id` (Integer, Primary Key)
- `week_number` (Integer, Not Null) - Week number
- `student_id` (Integer, Nullable) - Student ID
- `student_name` (String(100)) - Student name
- `student_code` (String(50)) - Student code
- `student_class` (String(20)) - Class name
- `final_score` (Integer) - Final score for the week
- `total_deductions` (Integer) - Total points deducted
- `created_at` (DateTime) - Creation timestamp

---

### 11. TimetableSlot
**Description:** Timetable slot for a class, day, period

**Table:** `timetable_slot`

**Fields:**
- `id` (Integer, Primary Key)
- `class_name` (String(50), Not Null, Indexed) - Class name
- `day_of_week` (Integer, Not Null) - Day (1=Monday, 7=Sunday)
- `period_number` (Integer, Not Null) - Period number
- `subject_id` (Integer, Foreign Key → Subject, Nullable) - Subject
- `subject_name_override` (String(120)) - Override subject name
- `teacher_id` (Integer, Foreign Key → Teacher, Nullable) - Teacher
- `room` (String(50)) - Room number
- `school_year` (String(20), Not Null, Indexed) - School year
- `week_number` (Integer, Not Null, Default: 1) - ISO week number
- `created_at` (DateTime) - Creation timestamp
- `updated_at` (DateTime, onupdate) - Last update timestamp

**Constraints:**
- Unique constraint on (class_name, day_of_week, period_number, school_year, week_number)

**Relationships:**
- `subject` → Subject (backref)
- `teacher` → Teacher (backref)

---

### 12. Subject
**Description:** School subjects

**Fields:**
- `id` (Integer, Primary Key)
- `name` (String(100), Unique, Not Null) - Subject name
- `code` (String(20), Unique, Not Null) - Subject code
- `description` (String(200)) - Description
- `num_tx_columns` (Integer, Default: 3) - Number of TX (regular test) columns
- `num_gk_columns` (Integer, Default: 1) - Number of GK (midterm) columns
- `num_hk_columns` (Integer, Default: 1) - Number of HK (final) columns
- `is_pass_fail` (Boolean, Default: False) - Pass/fail grading (for PE, civic education, etc.)
- `created_at` (DateTime) - Creation timestamp

**Relationships:**
- `grades` → Grade (backref, cascade delete)
- `timetable_slots` → TimetableSlot (backref)
- `class_assignments` → ClassSubject
- `teacher_assignments` → TeacherClassAssignment

---

### 13. ClassSubject
**Description:** Subject assignments for each class

**Table:** `class_subject`

**Fields:**
- `id` (Integer, Primary Key)
- `class_name` (String(50), Not Null, Indexed) - Class name
- `subject_id` (Integer, Foreign Key → Subject, Not Null, Indexed) - Subject
- `school_year` (String(20), Not Null, Default: "2025-2026") - School year
- `is_compulsory` (Boolean, Default: True) - Is compulsory subject
- `periods_per_week` (Integer, Default: 3) - Periods per week
- `created_at` (DateTime) - Creation timestamp
- `created_by` (Integer, Foreign Key → Teacher) - Creator

**Constraints:**
- Unique constraint on (class_name, subject_id, school_year)

**Relationships:**
- `subject` → Subject (backref)
- `creator` → Teacher (foreign key: created_by)

---

### 14. Grade
**Description:** Student grades

**Fields:**
- `id` (Integer, Primary Key)
- `student_id` (Integer, Foreign Key → Student, Not Null)
- `subject_id` (Integer, Foreign Key → Subject, Not Null)
- `grade_type` (String(10), Not Null) - Type: TX (regular), GK (midterm), HK (final)
- `column_index` (Integer, Default: 1) - Column index for multiple grades of same type
- `score` (Float, Not Null) - Score (0-10)
- `semester` (Integer, Not Null) - Semester (1 or 2)
- `school_year` (String(20)) - School year
- `date_recorded` (DateTime, Default: datetime.utcnow) - When recorded

**Relationships:**
- `student` → Student (backref, cascade delete)
- `subject` → Subject (backref, cascade delete)

---

### 15. ChatConversation
**Description:** Chatbot conversation history with context

**Fields:**
- `id` (Integer, Primary Key)
- `session_id` (String(100), Not Null, Indexed) - Session identifier
- `teacher_id` (Integer, Foreign Key → Teacher, Nullable) - Teacher ID
- `student_id` (Integer, Foreign Key → Student, Nullable) - Student ID
- `role` (String(20), Not Null) - Role: 'user' or 'assistant'
- `message` (Text, Not Null) - Message content
- `context_data` (Text, Nullable) - JSON metadata
- `created_at` (DateTime, Indexed) - Creation timestamp

**Relationships:**
- `teacher` → Teacher (backref)
- `student` → Student (backref)

---

### 16. BonusType
**Description:** Types of bonus points

**Fields:**
- `id` (Integer, Primary Key)
- `name` (String(200), Unique, Not Null) - Bonus type name
- `points_added` (Integer, Not Null) - Points to add
- `description` (String(500)) - Description

---

### 17. BonusRecord
**Description:** Student bonus point records

**Fields:**
- `id` (Integer, Primary Key)
- `student_id` (Integer, Foreign Key → Student, Not Null)
- `bonus_type_name` (String(200), Not Null) - Bonus type
- `points_added` (Integer, Not Null) - Points added
- `reason` (String(500)) - Specific reason
- `date_awarded` (DateTime, Default: datetime.utcnow) - When awarded
- `week_number` (Integer, Default: 1) - Week number

**Relationships:**
- `student` → Student (backref)

---

### 18. Notification
**Description:** System notifications for teachers

**Fields:**
- `id` (Integer, Primary Key)
- `title` (String(200), Not Null) - Notification title
- `message` (Text, Not Null) - Notification message
- `created_at` (DateTime) - Creation timestamp
- `created_by` (Integer, Foreign Key → Teacher) - Creator
- `notification_type` (String(50)) - Type: violation, grade, bonus, announcement
- `target_role` (String(50)) - Target: all, homeroom_teacher, subject_teacher, or class name
- `is_read` (Boolean, Default: False) - Read status
- `recipient_id` (Integer, Foreign Key → Teacher) - Recipient

**Relationships:**
- `creator` → Teacher (foreign key: created_by, backref: sent_notifications)
- `recipient` → Teacher (foreign key: recipient_id, backref: notifications)

---

### 19. GroupChatMessage
**Description:** Messages in group chat

**Fields:**
- `id` (Integer, Primary Key)
- `sender_id` (Integer, Foreign Key → Teacher, Not Null) - Sender
- `message` (Text, Not Null) - Message content
- `created_at` (DateTime) - Creation timestamp

**Relationships:**
- `sender` → Teacher (backref)

---

### 20. PrivateMessage
**Description:** Private messages between teachers

**Fields:**
- `id` (Integer, Primary Key)
- `sender_id` (Integer, Foreign Key → Teacher, Not Null) - Sender
- `receiver_id` (Integer, Foreign Key → Teacher, Not Null) - Receiver
- `message` (Text, Not Null) - Message content
- `created_at` (DateTime) - Creation timestamp
- `is_read` (Boolean, Default: False) - Read status

**Relationships:**
- `sender` → Teacher (backref: sent_private_messages)
- `receiver` → Teacher (backref: received_private_messages)

---

### 21. ChangeLog
**Description:** Audit log for database changes

**Fields:**
- `id` (Integer, Primary Key)
- `changed_by_id` (Integer, Foreign Key → Teacher, Nullable) - Who made change
- `change_type` (String(50), Not Null) - Type: violation, bonus, grade, grade_update, grade_delete, violation_delete, score_reset, bulk_violation
- `student_id` (Integer, Foreign Key → Student, Nullable) - Student affected
- `student_name` (String(100)) - Student name
- `student_class` (String(20)) - Student class
- `description` (Text, Not Null) - Change description
- `old_value` (String(200)) - Old value
- `new_value` (String(200)) - New value
- `created_at` (DateTime) - Creation timestamp

**Relationships:**
- `changed_by` → Teacher (backref)
- `student` → Student (backref)

---

### 22. LessonBookEntry
**Description:** Electronic lesson book entries

**Table:** `lesson_book_entry`

**Fields:**
- `id` (Integer, Primary Key)
- `teacher_id` (Integer, Foreign Key → Teacher, Not Null, Indexed) - Teacher
- `class_name` (String(50), Not Null, Indexed) - Class name
- `timetable_slot_id` (Integer, Foreign Key → TimetableSlot, Nullable, Indexed) - Linked timetable slot
- `subject_id` (Integer, Foreign Key → Subject, Nullable, Indexed) - Subject
- `lesson_date` (Date, Not Null, Indexed) - Lesson date
- `period_number` (Integer, Not Null, Default: 1) - Period number
- `topic` (Text, Not Null) - Lesson topic
- `objectives` (Text) - Learning objectives
- `teaching_method` (Text) - Teaching method
- `evaluation` (Text) - Evaluation
- `homework` (Text) - Homework
- `notes` (Text) - Notes
- `attendance_present` (Integer) - Present count
- `attendance_absent` (Integer) - Absent count
- `school_year` (String(20)) - School year
- `semester` (Integer, Default: 1) - Semester
- `created_at` (DateTime) - Creation timestamp
- `updated_at` (DateTime, onupdate) - Last update timestamp

**Relationships:**
- `teacher` → Teacher (backref)
- `subject` → Subject (backref)
- `timetable_slot` → TimetableSlot (backref)
- `violations` → Violation (backref)

---

### 23. LessonBookWeek
**Description:** Weekly lesson book metadata

**Table:** `lesson_book_week`

**Fields:**
- `id` (Integer, Primary Key)
- `teacher_id` (Integer, Foreign Key → Teacher, Not Null, Indexed) - Teacher
- `class_name` (String(50), Not Null, Indexed) - Class name
- `week_number` (Integer, Not Null, Indexed) - ISO week (1-53)
- `school_year` (String(20), Not Null) - School year
- `semester` (Integer, Default: 1) - Semester
- `teacher_notes` (Text) - Teacher's weekly notes
- `created_at` (DateTime) - Creation timestamp
- `updated_at` (DateTime, onupdate) - Last update timestamp

**Constraints:**
- Unique constraint on (teacher_id, class_name, week_number)

**Relationships:**
- `teacher` → Teacher (backref)
- `slots` → LessonBookSlot (backref, cascade delete)

---

### 24. LessonBookSlot
**Description:** Individual lesson book slot (cell in weekly grid)

**Table:** `lesson_book_slot`

**Fields:**
- `id` (Integer, Primary Key)
- `week_id` (Integer, Foreign Key → LessonBookWeek, Not Null, Indexed) - Week reference
- `day_of_week` (Integer, Not Null) - Day (1=Monday, 7=Sunday)
- `period_number` (Integer, Not Null, Default: 1) - Period number
- `lesson_date` (Date, Nullable, Indexed) - Lesson date
- `subject_name` (String(100)) - Subject name (quick entry)
- `topic` (Text) - Lesson topic
- `objectives` (Text) - Learning objectives
- `teaching_method` (Text) - Teaching method
- `evaluation` (Text) - Evaluation
- `homework` (Text) - Homework
- `notes` (Text) - Notes
- `attendance_present` (Integer) - Present count
- `attendance_absent` (Integer) - Absent count
- `created_at` (DateTime) - Creation timestamp
- `updated_at` (DateTime, onupdate) - Last update timestamp

**Constraints:**
- Unique constraint on (week_id, day_of_week, period_number)

**Relationships:**
- `week` → LessonBookWeek (backref, cascade delete)

---

### 25. StudentNotification
**Description:** Notifications for students (separate from teacher notifications)

**Fields:**
- `id` (Integer, Primary Key)
- `student_id` (Integer, Foreign Key → Student, Not Null, Indexed) - Student
- `title` (String(200), Not Null) - Title
- `message` (Text, Not Null) - Message
- `notification_type` (String(50)) - Type
- `is_read` (Boolean, Default: False) - Read status
- `created_at` (DateTime) - Creation timestamp
- `sender_id` (Integer, Foreign Key → Teacher, Nullable) - Sender (teacher)

**Relationships:**
- `student` → Student (backref)
- `sender` → Teacher (backref)

---

### 26. ClassFundCollection
**Description:** Class fund collection records

**Table:** `class_fund_collection`

**Fields:**
- `id` (Integer, Primary Key)
- `class_name` (String(50), Not Null, Indexed) - Class name
- `school_year` (String(20), Not Null, Indexed) - School year
- `amount_vnd` (Integer, Not Null) - Amount in VND
- `purpose` (String(200), Not Null) - Purpose of collection
- `student_id` (Integer, Foreign Key → Student, Nullable, Indexed) - Student (if specific)
- `payer_name` (String(150)) - Payer name
- `collection_date` (Date, Not Null) - Collection date
- `notes` (Text) - Notes
- `created_by_id` (Integer, Foreign Key → Teacher, Nullable) - Creator
- `created_at` (DateTime) - Creation timestamp

**Relationships:**
- `student` → Student (backref)
- `created_by` → Teacher (backref)

---

### 27. ClassFundExpense
**Description:** Class fund expense records

**Table:** `class_fund_expense`

**Fields:**
- `id` (Integer, Primary Key)
- `class_name` (String(50), Not Null, Indexed) - Class name
- `school_year` (String(20), Not Null, Indexed) - School year
- `amount_vnd` (Integer, Not Null) - Amount in VND
- `title` (String(200), Not Null) - Expense title
- `expense_date` (Date, Not Null) - Expense date
- `notes` (Text) - Notes
- `created_by_id` (Integer, Foreign Key → Teacher, Nullable) - Creator
- `created_at` (DateTime) - Creation timestamp

**Relationships:**
- `created_by` → Teacher (backref)

---

### 28. AttendanceRecord
**Description:** Attendance records via face recognition or QR code

**Table:** `attendance_record`

**Fields:**
- `id` (Integer, Primary Key)
- `student_id` (Integer, Foreign Key → Student, Not Null, Indexed) - Student
- `class_name` (String(50), Not Null, Indexed) - Class name
- `check_in_time` (DateTime, Not Null, Default: datetime.utcnow) - Check-in time
- `captured_photo` (String(255), Nullable) - Captured photo path
- `confidence` (Float, Default: 0.0) - Face recognition confidence (0-1)
- `status` (String(20), Default: "Có mặt") - Status: Có mặt, Trễ, Vắng
- `notes` (Text, Nullable) - Notes
- `recorded_by_id` (Integer, Foreign Key → Teacher, Nullable) - Recorder
- `attendance_date` (Date, Not Null, Indexed) - Attendance date
- `attendance_mode` (String(20), Default: "face") - Mode: face or qr
- `qr_scan_method` (String(30), Nullable) - QR scan method: camera or direct
- `monitoring_session_id` (Integer, Foreign Key → AttendanceMonitoringSession, Nullable) - Monitoring session

**Relationships:**
- `student` → Student (backref)
- `recorded_by` → Teacher (backref)
- `monitoring_session` → AttendanceMonitoringSession (backref)

---

### 29. AttendanceMonitoringSession
**Description:** Hourly attendance monitoring session

**Table:** `attendance_monitoring_session`

**Fields:**
- `id` (Integer, Primary Key)
- `teacher_id` (Integer, Foreign Key → Teacher, Not Null, Indexed) - Teacher
- `class_name` (String(50), Not Null, Indexed) - Class name
- `start_time` (DateTime, Not Null) - Session start time
- `end_time` (DateTime, Nullable) - Session end time (null = open)
- `session_date` (Date, Not Null, Indexed) - Session date
- `status` (String(20), Default: "open") - Status: open, confirmed, cancelled
- `notes` (Text, Nullable) - Notes
- `created_at` (DateTime) - Creation timestamp

**Relationships:**
- `teacher` → Teacher (backref)
- `violation_records` → SessionViolationRecord (backref)
- `attendance_records` → AttendanceRecord (backref)

---

### 30. SessionViolationRecord
**Description:** Violation records within monitoring session (pending confirmation)

**Table:** `session_violation_record`

**Fields:**
- `id` (Integer, Primary Key)
- `session_id` (Integer, Foreign Key → AttendanceMonitoringSession, Not Null, Indexed) - Session
- `student_id` (Integer, Foreign Key → Student, Not Null, Indexed) - Student
- `violation_type_name` (String(200), Not Null) - Violation type
- `points_deducted` (Integer, Not Null) - Points to deduct
- `status` (String(20), Default: "pending") - Status: pending or confirmed
- `recorded_at` (DateTime, Default: datetime.utcnow) - When recorded
- `notes` (Text, Nullable) - Teacher's notes
- `official_violation_id` (Integer, Foreign Key → Violation, Nullable) - Official violation after confirmation

**Relationships:**
- `session` → AttendanceMonitoringSession (backref)
- `student` → Student (backref)
- `official_violation` → Violation

---

### 31. TeacherClassAssignment
**Description:** Teacher-to-class assignments

**Table:** `teacher_class_assignment`

**Fields:**
- `id` (Integer, Primary Key)
- `teacher_id` (Integer, Foreign Key → Teacher, Not Null, Indexed) - Teacher
- `class_name` (String(50), Not Null, Indexed) - Class name
- `subject_id` (Integer, Foreign Key → Subject, Nullable) - Subject teaching
- `school_year` (String(20), Not Null, Default: "2025-2026") - School year
- `created_at` (DateTime) - Creation timestamp
- `created_by` (Integer, Foreign Key → Teacher) - Creator

**Constraints:**
- Unique constraint on (teacher_id, class_name)

**Relationships:**
- `teacher` → Teacher (foreign key: teacher_id, backref)
- `subject` → Subject (backref)
- `creator` → Teacher (foreign key: created_by)

---

## Indexes

### Common Indexed Fields
- `student_code` (Student)
- `student_class` (Student, TimetableSlot, AttendanceRecord, ClassFundCollection, ClassFundExpense)
- `teacher_id` (TeacherPermission, LessonBookEntry, LessonBookWeek, AttendanceMonitoringSession)
- `subject_id` (ClassSubject, Grade, LessonBookEntry)
- `week_number` (Violation, TimetableSlot, LessonBookWeek)
- `created_at` (ChatConversation)
- `session_id` (ChatConversation)

---

## Relationships Summary

### One-to-Many
- ClassRoom → Students (via student_class)
- Subject → Grades
- Subject → TimetableSlots
- Teacher → TeacherPermissions
- Teacher → Violations (via changed_by_id)
- Teacher → ChangeLogs
- Student → Grades
- Student → Violations
- Student → BonusRecords
- Student → ChatConversations
- Student → StudentNotifications
- Student → AttendanceRecords
- LessonBookWeek → LessonBookSlots
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

## Database Migration Notes

The application includes automatic migration functions in `app.py` to handle schema updates:
- `ensure_student_parent_columns()` - Add parent_name, parent_phone
- `ensure_student_portrait_column()` - Add portrait_filename
- `ensure_student_date_of_birth_column()` - Add date_of_birth
- `ensure_student_position_column()` - Add position
- `ensure_lesson_book_timetable_column()` - Add timetable_slot_id
- `ensure_violation_lesson_book_column()` - Add lesson_book_entry_id
- `ensure_timetable_slot_week_number_column()` - Change semester to week_number
- `ensure_student_notification_sender_column()` - Add sender_id
- `ensure_student_conduct_columns()` - Add conduct, warning_level, academic_rank, academic_warning_level
- `ensure_attendance_qr_columns()` - Add attendance_mode, qr_scan_method
- `ensure_attendance_monitoring_session_column()` - Add monitoring_session_id
- `ensure_lesson_book_week_and_slot_tables()` - Create lesson_book_week and lesson_book_slot tables
- `ensure_lesson_book_slot_lesson_date_column()` - Add lesson_date
- `ensure_subject_is_pass_fail_column()` - Add is_pass_fail
- `ensure_teacher_class_assignment_table()` - Create teacher_class_assignment table
- `ensure_class_subject_table()` - Create class_subject table

---

## Default Data

### Default Admin User
- Username: `admin`
- Password: `admin` (hashed on first run)

### Default SystemConfig
- `current_week`: "1"

### Default ViolationType
- "Đi muộn": 2 points

### Default ConductSetting
- good_threshold: 80
- fair_threshold: 65
- average_threshold: 50
- warning_yellow_threshold: 70
- warning_red_threshold: 55
- academic_yellow_threshold: 6.5
- academic_red_threshold: 5.0
