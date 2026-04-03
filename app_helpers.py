"""Shared helpers and extensions (refactored from app.py)."""
import os
import json
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
    Notification, GroupChatMessage, PrivateMessage, ChangeLog,
)

basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, "uploads")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

OLLAMA_MODEL = "gemini-3-flash-preview"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

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

def get_role_display(role):
    """Chuyển đổi role code thành tên hiển thị tiếng Việt"""
    role_map = {
        'admin': 'Quản trị viên',
        'homeroom_teacher': 'Giáo viên chủ nhiệm',
        'subject_teacher': 'Giáo viên bộ môn'
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


def call_ollama(prompt, model=None):
    """
    Gọi Ollama API để chat với AI model local.
    Model mặc định: gemini-3-flash-preview (chạy bằng: ollama run gemini-3-flash-preview)
    Args:
        prompt: Câu hỏi/prompt gửi cho AI
        model: Tên model Ollama (None = dùng OLLAMA_MODEL)
    Returns:
        (response_text, error)
    """
    model = model or OLLAMA_MODEL
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response['message']['content'], None
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
            
        except Exception as e:
            errors.append(f"Dòng {idx+1}: {str(e)}")
            db.session.rollback()
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        errors.append(f"Lỗi lưu database: {str(e)}")
    
    return errors, success_count

def _call_gemini(prompt, image_path=None, is_json=False):
    """
    Gọi Ollama local model để xử lý text hoặc vision tasks
    
    Args:
        prompt (str): Text prompt
        image_path (str, optional): Đường dẫn đến file ảnh
        is_json (bool): Yêu cầu response dạng JSON
    
    Returns:
        tuple: (response_text/dict, error_message)
    """
    try:
        # Prepare messages
        messages = []
        
        if image_path:
            # Vision task - sử dụng ollama.chat với images
            try:
                with open(image_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode("utf-8")
                
                messages.append({
                    'role': 'user',
                    'content': prompt,
                    'images': [image_data]
                })
            except Exception as e:
                return None, f"Lỗi đọc file ảnh: {str(e)}"
        else:
            # Text-only task
            messages.append({
                'role': 'user',
                'content': prompt
            })
        
        # Prepare options
        options = {}
        if is_json:
            # Thêm instruction vào prompt để yêu cầu JSON format
            messages[0]['content'] = f"{prompt}\n\nIMPORTANT: Response MUST be valid JSON only, no additional text."
        
        # Call Ollama
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            options=options
        )
        
        # Extract response text
        if response and 'message' in response and 'content' in response['message']:
            text = response['message']['content'].strip()
            
            # Parse JSON if requested
            if is_json:
                try:
                    # Try to extract JSON from markdown code blocks if present
                    if '```json' in text:
                        json_start = text.find('```json') + 7
                        json_end = text.find('```', json_start)
                        text = text[json_start:json_end].strip()
                    elif '```' in text:
                        json_start = text.find('```') + 3
                        json_end = text.find('```', json_start)
                        text = text[json_start:json_end].strip()
                    
                    return json.loads(text), None
                except json.JSONDecodeError as e:
                    return None, f"Lỗi parse JSON: {str(e)}\nResponse: {text[:200]}"
            
            return text, None
        else:
            return None, "Không nhận được response từ Ollama"
            
    except Exception as e:
        return None, f"Lỗi kết nối Ollama: {str(e)}"


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
