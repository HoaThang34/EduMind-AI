from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

from flask import g, has_request_context
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy import event
import sqlalchemy




class ClassRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.datetime.utcnow)


def get_default_school_name():
    config = SystemConfig.query.filter_by(key='school_name').first()
    return config.value if config else "THPT Chuyên Nguyễn Tất Thành"


class Permission(db.Model):
    """Định nghĩa các quyền hệ thống"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Mã quyền
    name = db.Column(db.String(100), nullable=False)  # Tên hiển thị
    description = db.Column(db.String(255))  # Mô tả
    category = db.Column(db.String(50))  # Phân loại: grades, discipline, students, attendance, etc.
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class TeacherPermission(db.Model):
    """Gán quyền cụ thể cho từng giáo viên - cho phép admin phân quyền linh hoạt"""
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), nullable=False)
    granted_by = db.Column(db.Integer, db.ForeignKey('teacher.id'))  # Admin nào cấp quyền
    granted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Quan hệ
    teacher = db.relationship('Teacher', foreign_keys=[teacher_id], backref='teacher_permissions')
    permission = db.relationship('Permission')
    grantor = db.relationship('Teacher', foreign_keys=[granted_by])
    
    __table_args__ = (db.UniqueConstraint('teacher_id', 'permission_id', name='uq_teacher_permission'),)


class Teacher(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    school_name = db.Column(db.String(150), default=get_default_school_name)
    main_class = db.Column(db.String(20))
    dob = db.Column(db.String(20))
    
    def set_password(self, pwd):
        self.password = generate_password_hash(pwd)
        
    def check_password(self, pwd):
        # Fallback for plain text password to avoid breaking existing users
        if self.password == pwd:
            return True
        try:
            return check_password_hash(self.password, pwd)
        except ValueError:
            # If the password in DB is not hashed, check_password_hash might throw ValueError or return False
            return False
    
    def has_permission(self, permission_code):
        """Kiểm tra giáo viên có quyền cụ thể không"""
        # Admin luôn có mọi quyền
        if self.role == 'admin':
            return True
        # Kiểm tra quyền được gán cụ thể
        return db.session.query(TeacherPermission).join(Permission).filter(
            TeacherPermission.teacher_id == self.id,
            Permission.code == permission_code
        ).first() is not None
    
    def get_all_permissions(self):
        """Lấy danh sách tất cả quyền của giáo viên"""
        if self.role == 'admin':
            return [p.code for p in Permission.query.all()]
        permissions = db.session.query(Permission.code).join(TeacherPermission).filter(
            TeacherPermission.teacher_id == self.id
        ).all()
        return [p[0] for p in permissions]

    def get_role_display(self):
        """Trả về tên hiển thị của vai trò"""
        role_map = {
            'admin': 'Quản trị viên',
            'homeroom_teacher': 'Giáo viên chủ nhiệm',
            'subject_teacher': 'Giáo viên bộ môn',
            'both': 'GVCN + GVBM',
            'discipline_officer': 'Giáo viên nề nếp',
            'parent_student': 'Phụ huynh/Học sinh'
        }
        return role_map.get(self.role, 'Giáo viên')

    # Hệ thống phân quyền mới
    # role: admin, homeroom_teacher, subject_teacher, both (GVCN + GVBM), discipline_officer, parent_student
    role = db.Column(db.String(20), default="homeroom_teacher")
    assigned_class = db.Column(db.String(50))  # Lớp được phân công (cho GVCN)
    assigned_subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'))  # Môn được phân công (cho GVBM)
    created_by = db.Column(db.Integer, db.ForeignKey('teacher.id'))  # Admin tạo tài khoản này
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    assigned_subject = db.relationship('Subject', backref='teachers', foreign_keys=[assigned_subject_id])


class ConductSetting(db.Model):
    """Cấu hình điểm sàn hạnh kiểm (BGH thiết lập)"""
    id = db.Column(db.Integer, primary_key=True)
    good_threshold = db.Column(db.Integer, default=80)    # Tốt >= 80
    fair_threshold = db.Column(db.Integer, default=65)    # Khá >= 65
    average_threshold = db.Column(db.Integer, default=50) # Trung bình >= 50
    # Ngưỡng báo động (mức điểm để kích hoạt cảnh báo)
    warning_yellow_threshold = db.Column(db.Integer, default=70) # Vàng
    warning_red_threshold = db.Column(db.Integer, default=55)    # Đỏ
    # Cấu hình học lực (BGH thiết lập)
    academic_yellow_threshold = db.Column(db.Float, default=6.5) # Vàng: GPA < 6.5
    academic_red_threshold = db.Column(db.Float, default=5.0)    # Đỏ: GPA < 5.0


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    student_class = db.Column(db.String(20), nullable=False)
    current_score = db.Column(db.Integer, default=100)
    parent_name = db.Column(db.String(150), nullable=True)
    parent_phone = db.Column(db.String(20), nullable=True)
    portrait_filename = db.Column(db.String(255), nullable=True)
    date_of_birth = db.Column(db.String(30), nullable=True)  # VD: 15/08/2008
    position = db.Column(db.String(50), nullable=True)  # Chức vụ: Lớp trưởng, Bí thư, ...
    conduct = db.Column(db.String(20), default="Tốt")
    warning_level = db.Column(db.String(20), default="Xanh") # Xanh, Vàng, Đỏ
    academic_rank = db.Column(db.String(20), default="Khá")
    academic_warning_level = db.Column(db.String(20), default="Xanh") # Xanh, Vàng, Đỏ
    id_card = db.Column(db.String(20), nullable=True)  # Số CCCD/CMND
    ethnicity = db.Column(db.String(50), nullable=True)  # Dân tộc
    password = db.Column(db.String(100), nullable=True)  # Mật khẩu đăng nhập

    def set_password(self, pwd):
        self.password = generate_password_hash(pwd)

    def check_password(self, pwd):
        # Fallback cho password plain text (để tương thích ngược)
        if self.password == pwd:
            return True
        try:
            return check_password_hash(self.password, pwd)
        except ValueError:
            return False


class ViolationType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    points_deducted = db.Column(db.Integer, nullable=False)


class Violation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    violation_type_name = db.Column(db.String(200), nullable=False)
    points_deducted = db.Column(db.Integer, nullable=False)
    date_committed = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    week_number = db.Column(db.Integer, default=1)
    lesson_book_entry_id = db.Column(db.Integer, db.ForeignKey('lesson_book_entry.id'), nullable=True)
    student = db.relationship('Student', backref=db.backref('violations', lazy=True))
    linked_lesson = db.relationship('LessonBookEntry', backref=db.backref('violations', lazy=True))


class WeeklyArchive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, nullable=False)
    student_id = db.Column(db.Integer, nullable=True)
    student_name = db.Column(db.String(100))
    student_code = db.Column(db.String(50))
    student_class = db.Column(db.String(20))
    final_score = db.Column(db.Integer)
    total_deductions = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class TimetableSlot(db.Model):
    """Một ô thời khóa biểu: lớp + thứ + tiết (theo năm học và số tuần ISO 1–53)."""
    __tablename__ = "timetable_slot"
    __table_args__ = (
        db.UniqueConstraint(
            "class_name", "day_of_week", "period_number", "school_year", "week_number",
            name="uq_timetable_cell",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    day_of_week = db.Column(db.Integer, nullable=False)  # 1=Thứ Hai … 7=Chủ nhật
    period_number = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=True)
    subject_name_override = db.Column(db.String(120))
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=True)
    room = db.Column(db.String(50))
    school_year = db.Column(db.String(20), nullable=False, index=True)
    week_number = db.Column(db.Integer, nullable=False, default=1)  # tuần ISO, cùng logic calculate_week_from_date
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    subject = db.relationship("Subject", backref=db.backref("timetable_slots", lazy=True))
    teacher = db.relationship("Teacher", backref=db.backref("timetable_slots", lazy=True))


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(200))
    num_tx_columns = db.Column(db.Integer, default=3)
    num_gk_columns = db.Column(db.Integer, default=1)
    num_hk_columns = db.Column(db.Integer, default=1)
    is_pass_fail = db.Column(db.Boolean, default=False)  # True: môn đạt/không đạt (Thể dục, GDĐP...)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class ClassSubject(db.Model):
    """Phân công môn học cho từng lớp - mỗi lớp có thể có các môn học khác nhau"""
    __tablename__ = "class_subject"
    __table_args__ = (
        db.UniqueConstraint("class_name", "subject_id", "school_year", name="uq_class_subject"),
    )
    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False, index=True)
    school_year = db.Column(db.String(20), nullable=False, default="2025-2026")
    is_compulsory = db.Column(db.Boolean, default=True)  # True: bắt buộc, False: tự chọn
    periods_per_week = db.Column(db.Integer, default=3)  # Số tiết/tuần
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("teacher.id"))

    subject = db.relationship("Subject", backref="class_assignments")
    creator = db.relationship("Teacher", foreign_keys=[created_by])


class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    grade_type = db.Column(db.String(10), nullable=False)
    column_index = db.Column(db.Integer, default=1)
    score = db.Column(db.Float, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    school_year = db.Column(db.String(20))
    date_recorded = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    student = db.relationship('Student', backref=db.backref('grades', lazy=True, cascade='all, delete-orphan'))
    subject = db.relationship('Subject', backref=db.backref('grades', lazy=True, cascade='all, delete-orphan'))


class ChatConversation(db.Model):
    """Model lưu trữ lịch sử hội thoại chatbot với context awareness"""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' hoặc 'assistant'
    message = db.Column(db.Text, nullable=False)
    context_data = db.Column(db.Text, nullable=True)  # JSON metadata (student_id, etc.)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)
    
    teacher = db.relationship('Teacher', backref=db.backref('chat_history', lazy=True))
    student = db.relationship('Student', backref=db.backref('chat_history', lazy=True))


class BonusType(db.Model):
    """Loại điểm cộng (VD: Tham gia cuộc thi HSG, Tiến bộ học tập, Hoạt động ngoại khóa)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    points_added = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(500))


class BonusRecord(db.Model):
    """Lịch sử điểm cộng của học sinh"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    bonus_type_name = db.Column(db.String(200), nullable=False)
    points_added = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(500))  # Lý do cụ thể (VD: "Giải nhì HSG Toán cấp Tỉnh")
    date_awarded = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    week_number = db.Column(db.Integer, default=1)
    student = db.relationship('Student', backref=db.backref('bonuses', lazy=True))


class Notification(db.Model):
    """Hệ thống thông báo"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('teacher.id'))  # Admin who created
    notification_type = db.Column(db.String(50))  # 'violation', 'grade', 'bonus', 'announcement'
    target_role = db.Column(db.String(50))  # 'all', 'homeroom_teacher', 'subject_teacher', or specific class
    is_read = db.Column(db.Boolean, default=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))  # Who receives this
    
    creator = db.relationship('Teacher', foreign_keys=[created_by], backref='sent_notifications')
    recipient = db.relationship('Teacher', foreign_keys=[recipient_id], backref='notifications')


class GroupChatMessage(db.Model):
    """Tin nhắn trong phòng chat chung"""
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    sender = db.relationship('Teacher', backref='group_messages')


class PrivateMessage(db.Model):
    """Tin nhắn riêng tư giữa 2 giáo viên"""
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
    sender = db.relationship('Teacher', foreign_keys=[sender_id], backref='sent_private_messages')
    receiver = db.relationship('Teacher', foreign_keys=[receiver_id], backref='received_private_messages')


class ChangeLog(db.Model):
    """Lịch sử thay đổi CSDL - ghi nhận mọi thay đổi về điểm, vi phạm, điểm cộng"""
    id = db.Column(db.Integer, primary_key=True)
    changed_by_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    change_type = db.Column(db.String(50), nullable=False)  # 'violation', 'bonus', 'grade', 'grade_update', 'grade_delete', 'violation_delete', 'score_reset', 'bulk_violation'
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=True)
    student_name = db.Column(db.String(100))
    student_class = db.Column(db.String(20))
    description = db.Column(db.Text, nullable=False)
    old_value = db.Column(db.String(200))
    new_value = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    changed_by = db.relationship('Teacher', backref=db.backref('change_logs', lazy=True))
    student = db.relationship('Student', backref=db.backref('change_logs', lazy=True))


class LessonBookEntry(db.Model):
    """Sổ đầu bài điện tử — ghi nhận tiết dạy theo lớp/môn."""
    __tablename__ = "lesson_book_entry"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False, index=True)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    timetable_slot_id = db.Column(db.Integer, db.ForeignKey("timetable_slot.id"), nullable=True, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=True, index=True)
    lesson_date = db.Column(db.Date, nullable=False, index=True)
    period_number = db.Column(db.Integer, nullable=False, default=1)
    topic = db.Column(db.Text, nullable=False)
    objectives = db.Column(db.Text)
    teaching_method = db.Column(db.Text)
    evaluation = db.Column(db.Text)
    homework = db.Column(db.Text)
    notes = db.Column(db.Text)
    attendance_present = db.Column(db.Integer)
    attendance_absent = db.Column(db.Integer)
    school_year = db.Column(db.String(20))
    semester = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    teacher = db.relationship("Teacher", backref=db.backref("lesson_book_entries", lazy=True))
    subject = db.relationship("Subject", backref=db.backref("lesson_book_entries", lazy=True))
    timetable_slot = db.relationship("TimetableSlot", backref=db.backref("lesson_book_entries", lazy=True))


class LessonBookWeek(db.Model):
    """
    Mỗi tuần/lớp/gv có một bản ghi meta (tuần nào, năm học, ghi chú tuần).
    Dùng để gộp các tiết trong tuần và lưu thông tin tuần.
    """
    __tablename__ = "lesson_book_week"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False, index=True)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    week_number = db.Column(db.Integer, nullable=False, index=True)  # ISO week (1-53)
    school_year = db.Column(db.String(20), nullable=False)
    semester = db.Column(db.Integer, default=1)
    teacher_notes = db.Column(db.Text)  # Ghi chú chung tuần
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("teacher_id", "class_name", "week_number", name="uq_lbw_teacher_class_week"),
    )

    teacher = db.relationship("Teacher", backref=db.backref("lesson_book_weeks", lazy=True))


class LessonBookSlot(db.Model):
    """
    Mỗi ô cell trong sổ đầu bài — tương ứng 1 tiết (period) trong 1 ngày (day_of_week) của 1 tuần.
    Dùng để ghi nhanh nội dung trực tiếp trên lưới, không cần form riêng.
    """
    __tablename__ = "lesson_book_slot"
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey("lesson_book_week.id"), nullable=False, index=True)
    day_of_week = db.Column(db.Integer, nullable=False)   # 1=Thứ 2, 7=Chủ nhật
    period_number = db.Column(db.Integer, nullable=False, default=1)
    lesson_date = db.Column(db.Date, nullable=True, index=True)  # Ngày dạy (tự điền theo cột tuần)
    subject_name = db.Column(db.String(100))               # Tên môn (ghi nhanh, không bắt buộc)
    topic = db.Column(db.Text)                             # Nội dung bài dạy
    objectives = db.Column(db.Text)
    teaching_method = db.Column(db.Text)
    evaluation = db.Column(db.Text)
    homework = db.Column(db.Text)
    notes = db.Column(db.Text)
    attendance_present = db.Column(db.Integer)
    attendance_absent = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("week_id", "day_of_week", "period_number", name="uq_lbs_week_day_period"),
    )

    week = db.relationship("LessonBookWeek", backref=db.backref("slots", lazy=True, cascade="all, delete-orphan"))


class StudentNotification(db.Model):
    """Thông báo cho học sinh (TKB, v.v.) — tách bảng notification giáo viên."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)

    student = db.relationship("Student", backref=db.backref("student_notifications", lazy=True))
    sender = db.relationship("Teacher", backref=db.backref("sent_student_notifications", lazy=True))


class ClassFundCollection(db.Model):
    """Thu tiền từ phụ huynh (quỹ lớp, các khoản theo lớp)."""
    __tablename__ = "class_fund_collection"
    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    school_year = db.Column(db.String(20), nullable=False, index=True)
    amount_vnd = db.Column(db.Integer, nullable=False)
    purpose = db.Column(db.String(200), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=True, index=True)
    payer_name = db.Column(db.String(150))
    collection_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    student = db.relationship("Student", backref=db.backref("class_fund_collections", lazy=True))
    created_by = db.relationship("Teacher", backref=db.backref("class_fund_collections_created", lazy=True))


class ClassFundExpense(db.Model):
    """Chi tiêu quỹ lớp."""
    __tablename__ = "class_fund_expense"
    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    school_year = db.Column(db.String(20), nullable=False, index=True)
    amount_vnd = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    created_by = db.relationship("Teacher", backref=db.backref("class_fund_expenses_created", lazy=True))


class AttendanceRecord(db.Model):
    """Lịch sử điểm danh bằng nhận diện khuôn mặt hoặc mã QR."""
    __tablename__ = "attendance_record"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    check_in_time = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    captured_photo = db.Column(db.String(255), nullable=True)  # Đường dẫn ảnh chụp từ camera
    confidence = db.Column(db.Float, default=0.0)  # Độ tin cậy nhận diện (0-1)
    status = db.Column(db.String(20), default="Có mặt")  # Có mặt, Trễ, Vắng
    notes = db.Column(db.Text, nullable=True)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=True)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    attendance_mode = db.Column(db.String(20), default="face")  # 'face' hoặc 'qr'
    qr_scan_method = db.Column(db.String(30), nullable=True)  # 'camera' (quét QR trên camera) hoặc 'direct' (quét từ app)
    monitoring_session_id = db.Column(db.Integer, db.ForeignKey("attendance_monitoring_session.id"), nullable=True)  # Phiên theo dõi

    student = db.relationship("Student", backref=db.backref("attendance_records", lazy=True))
    recorded_by = db.relationship("Teacher", backref=db.backref("attendance_records_created", lazy=True))
    monitoring_session = db.relationship("AttendanceMonitoringSession", backref=db.backref("attendance_records", lazy=True))


class AttendanceMonitoringSession(db.Model):
    """Phiên theo dõi điểm danh theo giờ — giáo viên mở phiên trong 1 khung giờ,
    đánh dấu HS vi phạm trong phiên, sau đó xác nhận để đưa lên hệ thống xử phạt."""
    __tablename__ = "attendance_monitoring_session"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False, index=True)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    start_time = db.Column(db.DateTime, nullable=False)       # Giờ bắt đầu theo dõi
    end_time = db.Column(db.DateTime, nullable=True)            # Giờ kết thúc theo dõi (None = đang mở)
    session_date = db.Column(db.Date, nullable=False, index=True)
    # Trạng thái: 'open' = đang mở, 'confirmed' = đã xác nhận xử phạt, 'cancelled' = đã hủy
    status = db.Column(db.String(20), default="open")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    teacher = db.relationship("Teacher", backref=db.backref("monitoring_sessions", lazy=True))


class SessionViolationRecord(db.Model):
    """Bản ghi vi phạm trong phiên theo dõi — được đánh dấu trong giờ theo dõi,
    sau đó chuyển thành Violation chính thức khi giáo viên xác nhận."""
    __tablename__ = "session_violation_record"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_monitoring_session.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    violation_type_name = db.Column(db.String(200), nullable=False)
    points_deducted = db.Column(db.Integer, nullable=False)
    # Trạng thái: 'pending' = chờ xác nhận, 'confirmed' = đã xác nhận (chuyển thành Violation)
    status = db.Column(db.String(20), default="pending")
    # Thời điểm vi phạm được ghi nhận trong phiên
    recorded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Ghi chú của giáo viên trong phiên
    notes = db.Column(db.Text, nullable=True)
    # Violation chính thức được tạo (sau khi confirm)
    official_violation_id = db.Column(db.Integer, db.ForeignKey("violation.id"), nullable=True)

    session = db.relationship("AttendanceMonitoringSession", backref=db.backref("violation_records", lazy=True))
    student = db.relationship("Student", backref=db.backref("session_violation_records", lazy=True))
    official_violation = db.relationship("Violation")


class TeacherClassAssignment(db.Model):
    """Phân công giáo viên dạy lớp - một giáo viên có thể dạy nhiều lớp"""
    __tablename__ = "teacher_class_assignment"
    __table_args__ = (
        db.UniqueConstraint("teacher_id", "class_name", name="uq_teacher_class"),
    )
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False, index=True)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=True)  # Môn dạy ở lớp này
    school_year = db.Column(db.String(20), nullable=False, default="2025-2026")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("teacher.id"))

    teacher = db.relationship("Teacher", foreign_keys=[teacher_id], backref="class_assignments")
    subject = db.relationship("Subject", backref="teacher_assignments")
    creator = db.relationship("Teacher", foreign_keys=[created_by])
