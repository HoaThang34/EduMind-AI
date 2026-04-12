"""Shared helpers and extensions (refactored from app.py)."""
import os
import json

from dotenv import load_dotenv
import hmac
import datetime
import base64
import re
import unicodedata
import uuid
from io import BytesIO
import markdown
import pandas as pd
import ollama
from functools import wraps
from flask import flash, redirect, url_for, session
from flask_login import current_user
from sqlalchemy import func, desc, or_, and_

from models import (
    db, Student, Violation, ViolationType, Teacher, SystemConfig, ClassRoom,
    WeeklyArchive, Subject, Grade, ChatConversation, BonusType, BonusRecord,
    Notification, GroupChatMessage, PrivateMessage, ChangeLog, StudentNotification,
    TimetableSlot, ConductSetting, AttendanceRecord, Permission, TeacherPermission,
)

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

UPLOAD_FOLDER = os.path.join(basedir, "uploads")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_ollama_host():
    """OLLAMA_HOST trong .env (mặc định localhost Ollama)."""
    h = (os.environ.get("OLLAMA_HOST") or "").strip()
    return h or "http://localhost:11434"


def get_ollama_model():
    """OLLAMA_MODEL trong .env — phải trùng `ollama list`."""
    m = (os.environ.get("OLLAMA_MODEL") or "").strip()
    if not m:
        raise ValueError("OLLAMA_MODEL không được cấu hình trong file .env")
    return m


def get_ollama_fallback_model():
    """OLLAMA_FALLBACK_MODEL trong .env; nếu trống thì dùng cùng model chính."""
    m = (os.environ.get("OLLAMA_FALLBACK_MODEL") or "").strip()
    return m if m else get_ollama_model()


def get_ollama_client():
    return ollama.Client(host=get_ollama_host())


def _ollama_client():
    return get_ollama_client()


def _parse_llm_json_response(text):
    """
    Parse JSON array hoặc object chứa mảng từ phản hồi LLM (có thể kèm markdown / chữ thừa).
    Trả về (list | None, error_str | None).
    """
    if not text or not str(text).strip():
        return None, "Phản hồi rỗng"

    raw = str(text).strip()
    if "```json" in raw:
        a = raw.find("```json") + 7
        b = raw.find("```", a)
        if b > a:
            raw = raw[a:b].strip()
    elif "```" in raw:
        a = raw.find("```") + 3
        b = raw.find("```", a)
        if b > a:
            raw = raw[a:b].strip()

    def try_load(s):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None

    data = try_load(raw)
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("items", "slots", "timetable", "data", "rows"):
            v = data.get(key)
            if isinstance(v, list):
                return v, None
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v, None

    start = raw.find("[")
    if start >= 0:
        depth = 0
        for i in range(start, len(raw)):
            c = raw[i]
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    chunk = raw[start : i + 1]
                    data = try_load(chunk)
                    if isinstance(data, list):
                        return data, None
                    break

    return None, f"Lỗi parse JSON. Đoạn đầu phản hồi: {raw[:280]!r}"

# === HELPER FUNCTIONS CHO PHÂN QUYỀN ===

def admin_required(f):
    """Decorator yêu cầu quyền admin để truy cập route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Vui lòng đăng nhập!", "error")
            return redirect(url_for('auth.login'))
        if current_user.role != 'admin':
            flash("Bạn không có quyền truy cập chức năng này!", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def permission_required(permission_code):
    """Decorator kiểm tra quyền cụ thể - cho phép admin hoặc user có permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Vui lòng đăng nhập!", "error")
                return redirect(url_for('auth.login'))
            if not current_user.has_permission(permission_code):
                flash("Bạn không có quyền truy cập chức năng này!", "error")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_or_permission_required(role, permission_code):
    """Decorator cho phép role cụ thể HOẶC có permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Vui lòng đăng nhập!", "error")
                return redirect(url_for('auth.login'))
            has_access = (current_user.role == role or 
                         current_user.role == 'admin' or 
                         current_user.has_permission(permission_code))
            if not has_access:
                flash("Bạn không có quyền truy cập chức năng này!", "error")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_role_display(role):
    """Chuyển đổi role code thành tên hiển thị tiếng Việt"""
    role_map = {
        'admin': 'Quản trị viên',
        'homeroom_teacher': 'Giáo viên chủ nhiệm',
        'subject_teacher': 'Giáo viên bộ môn',
        'discipline_officer': 'Giáo viên nề nếp',
        'parent_student': 'Phụ huynh/Học sinh'
    }
    return role_map.get(role, 'Giáo viên')

def get_accessible_students():
    """
    Trả về query Student dựa trên role của current_user
    - Admin: Tất cả học sinh
    - GVCN: Chỉ học sinh lớp assigned_class
    - GVBM: Tất cả học sinh (để chấm điểm)
    """
    if not current_user.is_authenticated:
        return Student.query.filter(Student.id == -1)  # Empty query
    
    if current_user.role == 'admin':
        return Student.query
    elif current_user.role == 'homeroom_teacher' and current_user.assigned_class:
        return Student.query.filter_by(student_class=current_user.assigned_class)
    elif current_user.role == 'subject_teacher':
        return Student.query  # GVBM có thể xem tất cả HS để chấm điểm
    return Student.query.filter(Student.id == -1)  # Empty query

def can_access_student(student_id):
    """Kiểm tra quyền truy cập học sinh cụ thể"""
    if not current_user.is_authenticated:
        return False
    if current_user.role == 'admin':
        return True
    student = Student.query.get(student_id)
    if not student:
        return False
    if current_user.role == 'homeroom_teacher':
        return student.student_class == current_user.assigned_class
    if current_user.role == 'subject_teacher':
        return True  # GVBM có thể truy cập tất cả HS để chấm điểm
    return False


def call_ollama(prompt, model=None, timeout=120):
    """
    Gọi Ollama API để chat với AI model local.
    Model mặc định: OLLAMA_MODEL trong file .env; host: OLLAMA_HOST.
    Args:
        prompt: Câu hỏi/prompt gửi cho AI
        model: Tên model Ollama (None = đọc từ .env qua get_ollama_model())
        timeout: Thời gian chờ tối đa (giây), mặc định 120 giây
    Returns:
        (response_text, error)
    """
    model = model or get_ollama_model()
    client = get_ollama_client()
    try:
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response["message"]["content"], None
    except Exception as e:
        return None, f"Lỗi kết nối Ollama: {str(e)}"

def can_access_subject(subject_id):
    """Kiểm tra quyền truy cập môn học"""
    if not current_user.is_authenticated:
        return False
    if current_user.role == 'admin':
        return True
    if current_user.role == 'subject_teacher':
        return current_user.assigned_subject_id == subject_id
    if current_user.role == 'homeroom_teacher':
        return True  # GVCN có thể xem tất cả môn
    return False

def create_notification(title, message, notification_type, target_role='all', specific_recipient_id=None):
    """
    Tạo thông báo mới
    - target_role: 'all', 'homeroom_teacher', 'subject_teacher', hoặc class name (VD: '12 Tin')
    - specific_recipient_id: Gửi cho 1 giáo viên cụ thể
    """
    if specific_recipient_id:
        # Gửi cho 1 người cụ thể
        notif = Notification(
            title=title,
            message=message,
            notification_type=notification_type,
            created_by=current_user.id if current_user.is_authenticated else None,
            recipient_id=specific_recipient_id,
            target_role=target_role
        )
        db.session.add(notif)
    else:
        # Broadcast: tạo notification cho mỗi giáo viên phù hợp
        if target_role == 'all':
            recipients = Teacher.query.all()
        elif target_role == 'homeroom_teacher':
            recipients = Teacher.query.filter_by(role='homeroom_teacher').all()
        elif target_role == 'subject_teacher':
            recipients = Teacher.query.filter_by(role='subject_teacher').all()
        else:
            # Target là class name -> chỉ gửi cho GVCN lớp đó
            recipients = Teacher.query.filter_by(role='homeroom_teacher', assigned_class=target_role).all()
        
        for recipient in recipients:
            if recipient.id != (current_user.id if current_user.is_authenticated else None):
                notif = Notification(
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    created_by=current_user.id if current_user.is_authenticated else None,
                    recipient_id=recipient.id,
                    target_role=target_role
                )
                db.session.add(notif)
    
    db.session.commit()


def broadcast_timetable_update(title, message, created_by_id=None):
    """Gửi thông báo cập nhật thời khóa biểu tới toàn bộ giáo viên và học sinh."""
    try:
        for t in Teacher.query.all():
            db.session.add(
                Notification(
                    title=title,
                    message=message,
                    notification_type="timetable",
                    created_by=created_by_id,
                    recipient_id=t.id,
                    target_role="all",
                )
            )
        for s in Student.query.all():
            db.session.add(
                StudentNotification(
                    student_id=s.id,
                    title=title,
                    message=message,
                    notification_type="timetable",
                    is_read=False,
                )
            )
        db.session.commit()
    except Exception as e:
        print(f"broadcast_timetable_update: {e}")
        db.session.rollback()


def _timetable_class_compact_key(s):
    """Khóa so khớp tên lớp: bỏ khoảng trắng, chữ thường (11 TIN ≡ 11TIN)."""
    return "".join(str(s).lower().split())


def resolve_class_name_for_timetable(raw):
    """
    Chuẩn hóa tên lớp về bản ghi trong ClassRoom (tránh lệch '11 TIN' / '11TIN').
    Không khớp danh sách lớp thì trả về chuỗi đã strip để giữ nguyên nhập liệu tự do.
    """
    if raw is None:
        return ""
    t = str(raw).strip()
    if not t or t.lower() == "nan":
        return t
    classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
    if t in classes:
        return t
    nt = _timetable_class_compact_key(t)
    for name in classes:
        if _timetable_class_compact_key(name) == nt:
            return name
    return t


def timetable_class_variants_for_filter(selected_class_name):
    """
    Mọi giá trị class_name thực tế trong DB (và ClassRoom) cùng nhóm với lớp đang chọn,
    để truy vấn TKB không bỏ sót do sai khác khoảng trắng / hoa thường.
    """
    if not (selected_class_name or "").strip():
        return []
    k = _timetable_class_compact_key(selected_class_name)
    variants = set()
    for c in ClassRoom.query.all():
        if _timetable_class_compact_key(c.name) == k:
            variants.add(c.name)
    for (stored,) in db.session.query(TimetableSlot.class_name).distinct().all():
        if _timetable_class_compact_key(stored) == k:
            variants.add(stored)
    return list(variants) if variants else [selected_class_name.strip()]


def resolve_subject_for_timetable(text):
    """
    Khớp môn trong CSDL theo tên hoặc mã.
    Trả về (subject_id hoặc None, subject_name_override hoặc None).
    """
    if text is None:
        return None, None
    t = str(text).strip()
    if not t:
        return None, None
    s = Subject.query.filter(
        or_(Subject.name.ilike(t), Subject.code.ilike(t))
    ).first()
    if s:
        return s.id, None
    return None, t[:120]


def log_change(change_type, description, student_id=None, student_name=None, student_class=None, old_value=None, new_value=None):
    """
    Ghi nhận thay đổi CSDL vào bảng ChangeLog.
    Gọi hàm này TRƯỚC db.session.commit() để đảm bảo cùng transaction.
    """
    try:
        changed_by_id = current_user.id if current_user.is_authenticated else None
        log_entry = ChangeLog(
            changed_by_id=changed_by_id,
            change_type=change_type,
            student_id=student_id,
            student_name=student_name,
            student_class=student_class,
            description=description,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None
        )
        db.session.add(log_entry)
    except Exception as e:
        print(f"ChangeLog Error: {e}")

def normalize_student_code(code):
    """
    Chuẩn hóa mã học sinh để tăng khả năng matching khi OCR đọc sai format
    
    Xử lý:
    - Bỏ dấu tiếng Việt (TOÁN → TOAN, Đạt → DAT)
    - Uppercase toàn bộ
    - Chuẩn hóa khoảng trắng (nhiều space → 1 space, trim đầu cuối)
    - Giữ nguyên dấu gạch ngang (-)
    
    Examples:
        "34 TOÁN - 001035" → "34 TOAN - 001035"
        "12  tin-001" → "12 TIN-001"
        "11a1  -  005" → "11A1 - 005"
        "Nguyễn Văn A" → "NGUYEN VAN A"
    
    Args:
        code (str): Mã học sinh cần chuẩn hóa
    
    Returns:
        str: Mã đã chuẩn hóa
    """
    if not code:
        return ""
    
    # 1. Bỏ dấu tiếng Việt bằng unicodedata
    code = unicodedata.normalize('NFD', str(code))
    code = ''.join(char for char in code if unicodedata.category(char) != 'Mn')
    
    # 2. Uppercase
    code = code.upper()
    
    # 3. Chuẩn hóa khoảng trắng: nhiều space → 1 space
    code = re.sub(r'\s+', ' ', code)
    
    # 4. Trim đầu cuối
    code = code.strip()
    
    return code


def normalize_parent_phone_for_login(s):
    """
    Chuẩn hóa số điện thoại (VN) để so khớp mật khẩu đăng nhập cổng học sinh.
    Chỉ giữ chữ số; tiền tố +84 / 84 → 0; 9 số (không 0 đầu) → thêm 0.
    """
    if not s:
        return ""
    d = "".join(c for c in str(s).strip() if c.isdigit())
    if not d:
        return ""
    if d.startswith("84") and len(d) >= 10:
        d = "0" + d[2:]
    if len(d) == 9 and not d.startswith("0"):
        d = "0" + d
    return d


def parent_phone_login_match(stored_phone, entered_password):
    """True nếu mật khẩu nhập khớp SĐT đã lưu (sau chuẩn hóa). So sánh constant-time."""
    a = normalize_parent_phone_for_login(stored_phone)
    b = normalize_parent_phone_for_login(entered_password)
    if not a or not b or len(a) != len(b):
        return False
    return hmac.compare_digest(a, b)


def get_current_iso_week():
    today = datetime.datetime.now()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week}"

def format_date_vn(date_obj):
    return date_obj.strftime('%d/%m')

def save_weekly_archive(week_num):
    try:
        WeeklyArchive.query.filter_by(week_number=week_num).delete()
        students = Student.query.all()
        for s in students:
            deductions = db.session.query(func.sum(Violation.points_deducted))\
                .filter(Violation.student_id == s.id, Violation.week_number == week_num)\
                .scalar() or 0
            archive = WeeklyArchive(
                week_number=week_num, student_id=s.id, student_name=s.name,
                student_code=s.student_code, student_class=s.student_class,
                final_score=s.current_score, total_deductions=deductions
            )
            db.session.add(archive)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Archive Error: {e}")
        db.session.rollback()
        return False

def is_reset_needed():
    """Kiểm tra xem đã sang tuần thực tế mới chưa để hiện cảnh báo"""
    try:
        current_iso_week = get_current_iso_week()
        last_reset_cfg = SystemConfig.query.filter_by(key="last_reset_week_id").first()
        
        # Nếu chưa từng reset lần nào -> Cần báo
        if not last_reset_cfg:
            return True
            
        # Nếu tuần thực tế khác tuần đã lưu -> Cần báo
        if current_iso_week != last_reset_cfg.value:
            return True
    except:
        pass
    return False

# === CHATBOT MEMORY HELPER FUNCTIONS ===

def get_or_create_chat_session():
    """
    Lấy session_id hiện tại từ Flask session hoặc tạo mới
    
    Returns:
        str: Session ID duy nhất cho cuộc hội thoại hiện tại
    """
    if 'chat_session_id' not in session:
        session['chat_session_id'] = str(uuid.uuid4())
    return session['chat_session_id']

def get_conversation_history(session_id, limit=10):
    """
    Lấy lịch sử hội thoại từ database
    
    Args:
        session_id (str): ID của chat session
        limit (int): Số lượng messages gần nhất (default 10)
    
    Returns:
        list[dict]: Danh sách messages theo format {"role": str, "content": str}
    """
    messages = ChatConversation.query.filter_by(
        session_id=session_id
    ).order_by(
        ChatConversation.created_at.asc()
    ).limit(limit).all()
    
    return [{"role": msg.role, "content": msg.message} for msg in messages]

def save_message(session_id, teacher_id, role, message, context_data=None):
    """
    Lưu message vào database
    
    Args:
        session_id (str): ID của session
        teacher_id (int): ID của teacher
        role (str): 'user' hoặc 'assistant'
        message (str): Nội dung message
        context_data (dict, optional): Metadata bổ sung (student_id, etc.)
    """
    chat_msg = ChatConversation(
        session_id=session_id,
        teacher_id=teacher_id,
        role=role,
        message=message,
        context_data=json.dumps(context_data) if context_data else None
    )
    db.session.add(chat_msg)
    db.session.commit()

# Context-aware AI System Prompt
CHATBOT_SYSTEM_PROMPT = """Vai trò: Bạn là một Trợ lý AI có Nhận thức Ngữ cảnh Cao (Context-Aware AI Assistant) cho giáo viên chủ nhiệm.

Mục tiêu: Duy trì sự liền mạch của cuộc hội thoại bằng cách ghi nhớ và sử dụng tích cực thông tin từ lịch sử trò chuyện.

Quy tắc Hoạt động:
1. Ghi nhớ Chủ động: Rà soát toàn bộ thông tin người dùng đã cung cấp trước đó (tên học sinh, yêu cầu, bối cảnh).
2. Tham chiếu Chéo: Lồng ghép chi tiết từ quá khứ để chứng minh bạn đang nhớ (VD: "Như bạn đã hỏi về em [tên] lúc nãy...").
3. Tránh Lặp lại: Không hỏi lại thông tin đã được cung cấp.
4. Cập nhật Trạng thái: Nếu người dùng thay đổi ý định, cập nhật ngay và xác nhận.

Định dạng Đầu ra: Phản hồi tự nhiên, ngắn gọn, thấu hiểu và luôn kết nối logic với các dữ kiện trước đó. Sử dụng emoji và markdown để dễ đọc.
"""

# === BULK VIOLATION IMPORT HELPER FUNCTIONS ===

def calculate_week_from_date(date_obj):
    """
    Calculate week_number from date
    Simple implementation: week of year
    
    Args:
        date_obj: datetime object
    
    Returns:
        int: week number
    """
    _, week_num, _ = date_obj.isocalendar()
    return week_num

def parse_excel_file(file):
    """
    Parse Excel file using pandas
    
    Expected columns:
    - Mã học sinh (student_code)
    - Loại vi phạm (violation_type_name)
    - Điểm trừ (points_deducted)
    - Ngày vi phạm (date_committed) - format: YYYY-MM-DD HH:MM or DD/MM/YYYY HH:MM
    - Tuần (week_number) - optional, auto-calculate if empty
    
    Returns:
        List[dict]: Violations data
    """
    try:
        df = pd.read_excel(file)
        
        # Validate required columns
        required_cols = ['Mã học sinh', 'Loại vi phạm', 'Điểm trừ', 'Ngày vi phạm']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Thiếu cột bắt buộc: {col}")
        
        violations = []
        for idx, row in df.iterrows():
            # Parse datetime
            date_str = str(row['Ngày vi phạm'])
            try:
                # Try YYYY-MM-DD HH:MM format
                date_committed = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            except:
                try:
                    # Try DD/MM/YYYY HH:MM format
                    date_committed = datetime.datetime.strptime(date_str, '%d/%m/%Y %H:%M')
                except:
                    try:
                        # Try date only YYYY-MM-DD
                        date_committed = datetime.datetime.strptime(date_str.split()[0], '%Y-%m-%d')
                    except:
                        raise ValueError(f"Dòng {idx+2}: Định dạng ngày không hợp lệ: {date_str}")
            
            # Calculate week_number if not provided
            week_number = row.get('Tuần', None)
            if pd.isna(week_number):
                week_number = calculate_week_from_date(date_committed)
            
            violations.append({
                'student_code': str(row['Mã học sinh']).strip(),
                'violation_type_name': str(row['Loại vi phạm']).strip(),
                'points_deducted': int(row['Điểm trừ']),
                'date_committed': date_committed,
                'week_number': int(week_number)
            })
        
        return violations
    except Exception as e:
        raise ValueError(f"Lỗi đọc file Excel: {str(e)}")

def import_violations_to_db(violations_data):
    """
    Import violations to database
    
    Args:
        violations_data: List[dict] with keys:
            - student_code
            - violation_type_name
            - points_deducted
            - date_committed
            - week_number
    
    Returns:
        Tuple[List[str], int]: (errors, success_count)
    """
    errors = []
    success_count = 0
    
    for idx, v_data in enumerate(violations_data):
        try:
            # 1. Tìm học sinh
            student = Student.query.filter_by(student_code=v_data['student_code']).first()
            if not student:
                errors.append(f"Dòng {idx+1}: Không tìm thấy học sinh '{v_data['student_code']}'")
                continue
            
            # 2. Lưu vào lịch sử vi phạm
            violation = Violation(
                student_id=student.id,
                violation_type_name=v_data['violation_type_name'],
                points_deducted=v_data['points_deducted'],
                date_committed=v_data['date_committed'],
                week_number=v_data['week_number']
            )
            
            db.session.add(violation)
            
            # 3. CẬP NHẬT TRỪ ĐIỂM NGAY LẬP TỨC (Đây là đoạn quan trọng mới thêm)
            current = student.current_score if student.current_score is not None else 100
            student.current_score = current - v_data['points_deducted']
            
            log_change('bulk_violation', f'Nhập vi phạm hàng loạt: {v_data["violation_type_name"]} (-{v_data["points_deducted"]} điểm)', student_id=student.id, student_name=student.name, student_class=student.student_class, old_value=current, new_value=student.current_score)
            
            success_count += 1
            
            # 4. CẬP NHẬT HẠNH KIỂM & CẢNH BÁO
            update_student_conduct(student.id)
            
        except Exception as e:
            errors.append(f"Dòng {idx+1}: {str(e)}")
            db.session.rollback()
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        errors.append(f"Lỗi lưu database: {str(e)}")
    
    return errors, success_count

def _call_gemini(prompt, image_path=None, image_paths=None, is_json=False):
    """
    Gọi Ollama (host OLLAMA_HOST, model OLLAMA_MODEL) — tên hàm lịch sử; không gọi Google Gemini API.

    Args:
        prompt (str): Text prompt
        image_path (str, optional): Một file ảnh (tương thích ngược)
        image_paths (list, optional): Nhiều ảnh (cần model vision, vd llava, qwen2.5-vl)
        is_json (bool): Nếu True, parse thành list/object từ phản hồi

    Returns:
        tuple: (response_text/dict/list, error_message)
    """
    client = get_ollama_client()
    messages = []

    paths = []
    if image_paths:
        paths = [p for p in image_paths if p]
    elif image_path:
        paths = [image_path]

    if paths:
        image_blobs = []
        for p in paths:
            try:
                with open(p, "rb") as image_file:
                    image_blobs.append(base64.b64encode(image_file.read()).decode("utf-8"))
            except Exception as e:
                return None, f"Lỗi đọc file ảnh: {str(e)}"
        vision_prompt = prompt
        if len(paths) > 1:
            vision_prompt = (
                f"{prompt}\n\n(Có {len(paths)} ảnh đính kèm — gộp toàn bộ thành một mảng JSON duy nhất.)"
            )
        messages.append(
            {
                "role": "user",
                "content": vision_prompt,
                "images": image_blobs,
            }
        )
    else:
        messages.append({"role": "user", "content": prompt})

    if is_json:
        messages[0]["content"] = (
            f"{messages[0]['content']}\n\n"
            "IMPORTANT: Response MUST be a single valid JSON array only, no markdown, no explanation."
        )

    models_to_try = []
    for m in (get_ollama_model(), get_ollama_fallback_model()):
        if m and m not in models_to_try:
            models_to_try.append(m)

    last_err = None
    for model_name in models_to_try:
        try:
            response = client.chat(model=model_name, messages=messages)
        except Exception as e:
            last_err = f"Model «{model_name}»: {str(e)}"
            continue

        if not response or "message" not in response or "content" not in response["message"]:
            last_err = f"Model «{model_name}»: không có nội dung phản hồi"
            continue

        text = response["message"]["content"].strip()
        if not is_json:
            return text, None

        data, parse_err = _parse_llm_json_response(text)
        if data is not None:
            return data, None
        last_err = parse_err or f"Model «{model_name}»: parse JSON thất bại"

    hint = (
        " Kiểm tra Ollama đang chạy, chạy `ollama list`, và đặt OLLAMA_MODEL trùng tên model đã pull "
        "trong file .env. Biến OLLAMA_FALLBACK_MODEL có thể đặt model dự phòng."
    )
    return None, (last_err or "Lỗi Ollama không xác định") + hint


def calculate_student_gpa(student_id, semester, school_year):
    """
    Calculate GPA for a student
    Formula: (TX + GK*2 + HK*3) / 6 for each subject, then average all subjects

    Returns:
        float: GPA value (0.0 - 10.0) or None if no grades
    """
    grades = Grade.query.filter_by(
        student_id=student_id,
        semester=semester,
        school_year=school_year
    ).all()

    if not grades:
        return None

    grades_by_subject = {}
    for grade in grades:
        if grade.subject_id not in grades_by_subject:
            grades_by_subject[grade.subject_id] = {'TX': [], 'GK': [], 'HK': []}
        grades_by_subject[grade.subject_id][grade.grade_type].append(grade.score)

    subject_averages = []
    for subject_id, data in grades_by_subject.items():
        if data['TX'] and data['GK'] and data['HK']:
            avg_tx = sum(data['TX']) / len(data['TX'])
            avg_gk = sum(data['GK']) / len(data['GK'])
            avg_hk = sum(data['HK']) / len(data['HK'])
            subject_avg = round((avg_tx + avg_gk * 2 + avg_hk * 3) / 6, 2)
            subject_averages.append(subject_avg)

    if not subject_averages:
        return None

    return round(sum(subject_averages) / len(subject_averages), 2)


    return round(sum(subject_averages) / len(subject_averages), 2)


def update_student_conduct(student_id):
    """
    Tự động cập nhật hạnh kiểm và mức cảnh báo cho học sinh dựa trên điểm số hiện tại.
    Gửi thông báo nếu có sự thay đổi hoặc mức cảnh báo cao.
    """
    try:
        student = db.session.get(Student, student_id)
        if not student:
            return
            
        settings = ConductSetting.query.first()
        if not settings:
            settings = ConductSetting()
            db.session.add(settings)
            db.session.commit()
            
        old_conduct = student.conduct
        old_warning = student.warning_level
        score = student.current_score if student.current_score is not None else 100
        
        # 1. Xác định hạnh kiểm
        if score >= settings.good_threshold:
            new_conduct = "Tốt"
        elif score >= settings.fair_threshold:
            new_conduct = "Khá"
        elif score >= settings.average_threshold:
            new_conduct = "Trung bình"
        else:
            new_conduct = "Yếu"
            
        # 2. Xác định mức cảnh báo (Ánh xạ từ hạnh kiểm theo yêu cầu)
        if new_conduct == "Tốt":
            new_warning = "Xanh"
        elif new_conduct == "Khá":
            new_warning = "Vàng"
        else: # Trung bình hoặc Yếu
            new_warning = "Đỏ"
            
        # 3. Cập nhật nếu có thay đổi
        if new_conduct != old_conduct or new_warning != old_warning:
            student.conduct = new_conduct
            student.warning_level = new_warning
            db.session.commit()
            
            # 4. Gửi thông báo nếu mức cảnh báo là Vàng hoặc Đỏ
            if new_warning in ["Vàng", "Đỏ"]:
                title = f"CẢNH BÁO HẠNH KIỂM: Học sinh {student.name}"
                level_text = "BÁO ĐỘNG" if new_warning == "Đỏ" else "CẢNH BÁO"
                msg = (f"Học sinh {student.name} ({student.student_class}) có mức hạnh kiểm {new_conduct} "
                       f"với số điểm {score}. Mức cảnh báo: {new_warning}. "
                       f"Vui lòng kiểm tra và có biện pháp nhắc nhở.")
                
                # Thông báo cho BGH (Admins)
                admins = Teacher.query.filter_by(role='admin').all()
                for admin in admins:
                    create_notification(title, msg, 'violation', specific_recipient_id=admin.id)
                    
                # Thông báo cho GVCN
                gvcn = Teacher.query.filter_by(role='homeroom_teacher', assigned_class=student.student_class).first()
                if gvcn:
                    create_notification(title, msg, 'violation', specific_recipient_id=gvcn.id)
                    
                # Thông báo cho Học sinh
                student_msg = (f"Chào {student.name}, hệ thống ghi nhận hạnh kiểm của em đang ở mức {new_conduct} "
                               f"({score} điểm). Mức cảnh báo: {new_warning}. "
                               f"Em hãy chú ý rèn luyện tốt hơn nhé!")
                db.session.add(StudentNotification(
                    student_id=student.id,
                    title="Thông báo Hạnh kiểm",
                    message=student_msg,
                    notification_type="violation"
                ))
                db.session.commit()
                
    except Exception as e:
        print(f"Update Conduct Error: {e}")
        db.session.rollback()


def update_student_academic_status(student_id):
    """
    Tự động cập nhật học lực và mức cảnh báo học tập cho học sinh dựa trên điểm số hiện tại.
    Gửi thông báo nếu có sự thay đổi hoặc mức cảnh báo cao.
    """
    try:
        student = db.session.get(Student, student_id)
        if not student:
            return
            
        settings = ConductSetting.query.first()
        if not settings:
            settings = ConductSetting()
            db.session.add(settings)
            db.session.commit()
            
        old_rank = student.academic_rank
        old_warning = student.academic_warning_level
        
        # Lấy kỳ học hiện tại
        configs = {c.key: c.value for c in SystemConfig.query.all()}
        semester = int(configs.get("current_semester", "1"))
        school_year = configs.get("school_year", "2025-2026")
        
        gpa = calculate_student_gpa(student.id, semester, school_year)
        if gpa is None:
            return # Chưa có điểm môn nào đầy đủ để tính GPA
        
        # 1. Xác định học lực (Academic Rank)
        if gpa >= 8.0:
            new_rank = "Giỏi"
        elif gpa >= 6.5:
            new_rank = "Khá"
        elif gpa >= 5.0:
            new_rank = "Trung bình"
        else:
            new_rank = "Yếu"
            
        # 2. Xác định mức cảnh báo (Dựa vào ngưỡng BGH cài đặt)
        if gpa < settings.academic_red_threshold:
            new_warning = "Đỏ"
        elif gpa < settings.academic_yellow_threshold:
            new_warning = "Vàng"
        else:
            new_warning = "Xanh"
            
        # 3. Cập nhật nếu có thay đổi
        if new_rank != old_rank or new_warning != old_warning:
            student.academic_rank = new_rank
            student.academic_warning_level = new_warning
            db.session.commit()
            
            # 4. Gửi thông báo nếu mức cảnh báo là Vàng hoặc Đỏ
            if new_warning in ["Vàng", "Đỏ"]:
                title = f"CẢNH BÁO HỌC TẬP: Học sinh {student.name}"
                msg = (f"Học sinh {student.name} ({student.student_class}) có học lực hiện tại là {new_rank} "
                       f"với điểm trung bình (GPA) là {gpa}. Mức cảnh báo học tập: {new_warning}. "
                       f"Vui lòng kiểm tra và có biện pháp hỗ trợ học tập cho học sinh.")
                
                # Thông báo cho BGH (Admins)
                admins = Teacher.query.filter_by(role='admin').all()
                for admin in admins:
                    create_notification(title, msg, 'grade', specific_recipient_id=admin.id)
                    
                # Thông báo cho GVCN
                gvcn = Teacher.query.filter_by(role='homeroom_teacher', assigned_class=student.student_class).first()
                if gvcn:
                    create_notification(title, msg, 'grade', specific_recipient_id=gvcn.id)
                    
                # Thông báo cho Học sinh
                student_msg = (f"Chào {student.name}, hệ thống ghi nhận học lực của em hiện đang là {new_rank} "
                               f"(GPA: {gpa}). Mức cảnh báo học tập: {new_warning}. "
                               f"Em hãy cố gắng học tập tốt hơn nhé!")
                db.session.add(StudentNotification(
                    student_id=student.id,
                    title="Thông báo Học lực",
                    message=student_msg,
                    notification_type="grade"
                ))
                db.session.commit()
                
    except Exception as e:
        print(f"Update Academic Error: {e}")
        db.session.rollback()


def register_template_extensions(app):
    @app.template_filter('markdown')
    def markdown_filter(text):
        return markdown.markdown(text, extensions=['fenced_code', 'tables'])

    @app.context_processor
    def inject_global_data():
        try:
            week_cfg = SystemConfig.query.filter_by(key="current_week").first()
            current_week = int(week_cfg.value) if week_cfg else 1
            classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
        except:
            current_week = 1
            classes = []
        
        # Inject role info cho templates
        role_display = ''
        is_admin = False
        if current_user.is_authenticated:
            role_display = get_role_display(getattr(current_user, 'role', 'homeroom_teacher'))
            is_admin = getattr(current_user, 'role', None) == 'admin'
        
        return dict(
            current_week_number=current_week, 
            all_classes=classes,
            role_display=role_display,
            is_admin=is_admin
        )
