from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import (
    Student, Violation, BonusRecord, Grade, Subject, SystemConfig, db,
    TimetableSlot, StudentNotification,
)
import base64
import json
import datetime
from functools import wraps
from urllib.parse import quote
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


student_bp = Blueprint('student', __name__)

# Token xác minh thẻ học sinh (QR) — không lộ dữ liệu nếu không có chữ ký hợp lệ
def _student_card_serializer():
    from flask import current_app
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt="student-id-card-v1",
    )


def make_student_card_token(student_id):
    return _student_card_serializer().dumps({"sid": student_id})


def load_student_card_token(token, max_age=90 * 86400):
    try:
        data = _student_card_serializer().loads(token, max_age=max_age)
        return data.get("sid"), None
    except SignatureExpired:
        return None, "expired"
    except (BadSignature, TypeError, ValueError):
        return None, "invalid"


# QR điểm danh — chứa trực tiếp student_id, không hết hạn
def make_attendance_qr_data(student_id):
    return f"EDUATT:{student_id}"

# We might need to copy `student_required`, `get_student_ai_advice`, `_student_chat_call_ollama` and `ALLOWED_CHAT_EXTENSIONS` here.
# Let's extract them:
def student_required(f):
    """Decorator yêu cầu quyền học sinh để truy cập"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app_helpers import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa, call_ollama
        if 'student_id' not in session:
            return redirect(url_for('student.student_login'))
        return f(*args, **kwargs)
    return decorated_function



def get_student_ai_advice(student):
    from app_helpers import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa, call_ollama, get_ollama_model
    """
    Phân tích dữ liệu học sinh và đưa ra lời khuyên từ AI
    """
    try:
        # 1. Lấy dữ liệu
        import prompts
        
        # Lấy vi phạm tuần hiện tại
        week_cfg = SystemConfig.query.filter_by(key="current_week").first()
        current_week = int(week_cfg.value) if week_cfg else 1
        
        violations = Violation.query.filter_by(
            student_id=student.id, 
            week_number=current_week
        ).all()
        violation_text = ", ".join([v.violation_type_name for v in violations]) if violations else "Không có"
        
        # Lấy điểm cộng
        bonuses = BonusRecord.query.filter_by(
            student_id=student.id,
            week_number=current_week
        ).all()
        bonus_text = ", ".join([b.bonus_type_name for b in bonuses]) if bonuses else "Không có"
        
        # Lấy configs
        configs = {c.key: c.value for c in SystemConfig.query.all()}
        semester = int(configs.get("current_semester", "1"))
        school_year = configs.get("school_year", "2025-2026")
        gpa = calculate_student_gpa(student.id, semester, school_year)
        gpa_text = str(gpa) if gpa else "Chưa có"
        
        # 2. Tạo prompt
        prompt = prompts.STUDENT_ANALYSIS_PROMPT.format(
            name=student.name,
            student_class=student.student_class,
            score=student.current_score,
            violations=violation_text,
            bonuses=bonus_text,
            gpa=gpa_text
        )
        
        # 3. Gọi AI
        advice, err = call_ollama(prompt)
        if err:
            print(f"AI Advice Ollama Error: {err}")
            return f"Lỗi kết nối AI: {err}\n\nVui lòng kiểm tra:\n• Ollama đã được cài đặt và chạy chưa?\n• Model đã được pull chưa? (`ollama pull {get_ollama_model()}`)"
        return advice
        
    except Exception as e:
        print(f"AI Advice Error: {e}")
        import traceback
        traceback.print_exc()
        return f"Lỗi hệ thống: {str(e)}\n\nVui lòng liên hệ quản trị viên."



ALLOWED_CHAT_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}


def _student_chat_call_ollama(system_prompt, history, user_message, image_base64=None):
    from app_helpers import (
        normalize_student_code,
        get_or_create_chat_session,
        get_conversation_history,
        save_message,
        calculate_student_gpa,
        get_ollama_client,
        get_ollama_model,
    )
    """
    Gọi Ollama cho student chat. Nếu có image_base64 thì dùng message có images.
    history: list of dict {role, content}
    """
    model = get_ollama_model()
    # Build messages cho Ollama (có hỗ trợ images trong user message)
    messages = []
    # System context: gộp system + history vào prompt của user đầu (hoặc message riêng tùy model)
    context = f"{system_prompt}\n\nLịch sử trò chuyện:\n"
    for h in history:
        context += f"{h['role'].title()}: {h['content']}\n"
    context += f"\nUser: {user_message}\nAssistant:"
    if image_base64:
        messages.append({"role": "user", "content": context, "images": [image_base64]})
    else:
        messages.append({"role": "user", "content": context})
    try:
        response = get_ollama_client().chat(model=model, messages=messages)
        return (response.get("message") or {}).get("content", "").strip(), None
    except Exception as e:
        return None, str(e)




@student_bp.route("/student/login", methods=["GET", "POST"])
def student_login():
    from app_helpers import (
        normalize_student_code,
        parent_phone_login_match,
        get_or_create_chat_session,
        get_conversation_history,
        save_message,
        calculate_student_gpa,
    )
    if request.method == "POST":
        code = request.form.get("student_code", "").strip()
        pwd = request.form.get("student_password", "").strip()
        norm_code = normalize_student_code(code)

        student = Student.query.filter_by(student_code=norm_code).first()
        if not student:
            flash("Mã học sinh không tồn tại! Vui lòng kiểm tra lại.", "error")
        elif not pwd:
            flash("Vui lòng nhập mật khẩu.", "error")
        else:
            # Ưu tiên kiểm tra mật khẩu đã đặt
            if student.password and student.check_password(pwd):
                session["student_id"] = student.id
                session["student_name"] = student.name
                return redirect(url_for("student.student_dashboard"))
            # Fallback: kiểm tra số điện thoại phụ huynh (cho tương thích ngược)
            elif parent_phone_login_match(student.parent_phone, pwd):
                session["student_id"] = student.id
                session["student_name"] = student.name
                return redirect(url_for("student.student_dashboard"))
            else:
                flash("Sai mật khẩu.", "error")

    return render_template("student_login.html")



@student_bp.route("/student/logout")
def student_logout():
    from app_helpers import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa
    session.pop('student_id', None)
    session.pop('student_name', None)
    return redirect(url_for('student.student_login'))


@student_bp.route("/student/api/generate_ai_advice", methods=["POST"])
@student_required
def generate_ai_advice():
    """API endpoint để tạo nhận xét AI thủ công khi học sinh bấm nút"""
    from app_helpers import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa
    student_id = session['student_id']
    student = Student.query.get(student_id)
    if not student:
        return jsonify({"error": "Không tìm thấy học sinh"}), 404

    try:
        advice = get_student_ai_advice(student)
        return jsonify({"advice": advice})
    except Exception as e:
        print(f"AI Advice API Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Lỗi hệ thống: {str(e)}"}), 500



@student_bp.route("/student/dashboard")
@student_required
def student_dashboard():
    from app_helpers import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa
    student_id = session['student_id']
    student = Student.query.get(student_id)
    if not student:
        return redirect(url_for('student.student_logout'))
        
    # Lấy dữ liệu hiển thị
    week_cfg = SystemConfig.query.filter_by(key="current_week").first()
    current_week = int(week_cfg.value) if week_cfg else 1
    
    # 1. Vi phạm tuần này
    current_violations = Violation.query.filter_by(
        student_id=student_id, 
        week_number=current_week
    ).all()
    
    # 2. Điểm cộng tuần này
    current_bonuses = BonusRecord.query.filter_by(
        student_id=student_id,
        week_number=current_week
    ).all()
    
    # 3. Điểm số các môn (GPA)
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    semester = int(configs.get("current_semester", "1"))
    school_year = configs.get("school_year", "2025-2026")
    
    grades = Grade.query.filter_by(
        student_id=student_id,
        semester=semester,
        school_year=school_year
    ).all()
    
    # Group grades
    transcript = {}
    subjects = Subject.query.all()
    for sub in subjects:
        transcript[sub.name] = {'TX': [], 'GK': [], 'HK': [], 'TB': None}
        
    for g in grades:
        if g.subject.name in transcript:
            transcript[g.subject.name][g.grade_type].append(g.score)
            
    # Tính TB môn
    for sub_name, data in transcript.items():
        if data['TX'] and data['GK'] and data['HK']:
            avg = (sum(data['TX'])/len(data['TX']) + sum(data['GK'])/len(data['GK'])*2 + sum(data['HK'])/len(data['HK'])*3) / 6
            data['TB'] = round(avg, 2)
            
    # 4. Không tự động lấy lời khuyên AI - sẽ có nút để tạo nhận xét thủ công
    ai_advice = None

    unread_notifications = StudentNotification.query.filter_by(
        student_id=student_id, is_read=False
    ).count()

    return render_template("student_dashboard.html",
                           student=student,
                           violations=current_violations,
                           bonuses=current_bonuses,
                           transcript=transcript,
                           ai_advice=ai_advice,
                           current_week=current_week,
                           unread_notifications=unread_notifications)


STUDENT_DAY_LABELS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
STUDENT_MAX_PERIODS = 10
STUDENT_MAX_ISO_WEEK = 53


@student_bp.route("/student/thoi-khoa-bieu")
@student_required
def student_timetable():
    from app_helpers import timetable_class_variants_for_filter

    student_id = session["student_id"]
    student = db.session.get(Student, student_id)
    if not student:
        return redirect(url_for("student.student_logout"))
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    school_year = configs.get("school_year", "2025-2026")
    try:
        school_current_week = int(configs.get("current_week", "1"))
    except (TypeError, ValueError):
        school_current_week = 1
    school_current_week = max(1, min(STUDENT_MAX_ISO_WEEK, school_current_week))
    raw_w = request.args.get("week_number", type=int)
    if raw_w is not None and 1 <= raw_w <= STUDENT_MAX_ISO_WEEK:
        week_number = raw_w
    else:
        week_number = school_current_week

    prev_week = max(1, week_number - 1)
    next_week = min(STUDENT_MAX_ISO_WEEK, week_number + 1)

    variants = timetable_class_variants_for_filter(student.student_class)
    slots = TimetableSlot.query.filter(
        TimetableSlot.class_name.in_(variants),
        TimetableSlot.school_year == school_year,
        TimetableSlot.week_number == week_number,
    ).all()
    grid = {}
    for s in slots:
        grid[(s.day_of_week, s.period_number)] = s
    return render_template(
        "student_timetable.html",
        student=student,
        grid=grid,
        school_year=school_year,
        week_number=week_number,
        school_current_week=school_current_week,
        prev_week=prev_week,
        next_week=next_week,
        max_iso_week=STUDENT_MAX_ISO_WEEK,
        day_labels=STUDENT_DAY_LABELS,
        max_periods=STUDENT_MAX_PERIODS,
    )


@student_bp.route("/student/thong-bao")
@student_required
def student_notifications_list():
    student_id = session["student_id"]
    student = db.session.get(Student, student_id)
    if not student:
        return redirect(url_for("student.student_logout"))
    notifications = (
        StudentNotification.query.filter_by(student_id=student_id)
        .order_by(StudentNotification.created_at.desc())
        .limit(100)
        .all()
    )
    return render_template(
        "student_notifications.html",
        student=student,
        notifications=notifications,
    )


@student_bp.route("/student/thong-bao/<int:nid>/doc", methods=["POST"])
@student_required
def student_notification_read(nid):
    student_id = session["student_id"]
    n = StudentNotification.query.filter_by(id=nid, student_id=student_id).first()
    if n:
        n.is_read = True
        db.session.commit()
    return redirect(url_for("student.student_notifications_list"))


@student_bp.route("/student/the-hoc-sinh")
@student_required
def student_id_card():
    """Thẻ học sinh dạng toàn màn hình; có QR xác minh & QR điểm danh."""
    student_id = session["student_id"]
    student = db.session.get(Student, student_id)
    if not student:
        return redirect(url_for("student.student_logout"))

    configs = {c.key: c.value for c in SystemConfig.query.all()}
    school_name = configs.get("school_name", "Trường học")

    # Mã QR xác minh thẻ (dùng salt riêng — hiệu lực 90 ngày)
    verify_token = make_student_card_token(student.id)
    verify_url = url_for("student.verify_student_card", token=verify_token, _external=True)
    verify_qr_src = (
        "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data="
        + quote(verify_url, safe="")
    )

    # Mã QR điểm danh — chứa trực tiếp student_id, không hết hạn
    qr_data = make_attendance_qr_data(student.id)
    attendance_qr_src = (
        "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data="
        + quote(qr_data, safe="")
    )
    attendance_qr_url = url_for(
        "student.student_qr_attendance_page", student_id=student.id, _external=True
    )

    return render_template(
        "student_id_card.html",
        student=student,
        school_name=school_name,
        verify_url=verify_url,
        qr_src=verify_qr_src,
        attendance_qr_src=attendance_qr_src,
        attendance_qr_url=attendance_qr_url,
    )


@student_bp.route("/student/the-hoc-sinh/xac-minh/<token>")
def verify_student_card(token):
    """Trang công khai: quét QR trên thẻ để xác minh (giáo viên / bảo vệ)."""
    sid, token_err = load_student_card_token(token)
    if not sid:
        return render_template(
            "student_id_card_verify.html",
            valid=False,
            reason=token_err or "invalid",
            student=None,
            school_name=None,
        )

    student = db.session.get(Student, sid)
    if not student:
        return render_template(
            "student_id_card_verify.html",
            valid=False,
            reason="missing",
            student=None,
            school_name=None,
        )

    configs = {c.key: c.value for c in SystemConfig.query.all()}
    school_name = configs.get("school_name", "Trường học")
    return render_template(
        "student_id_card_verify.html",
        valid=True,
        reason=None,
        student=student,
        school_name=school_name,
    )


@student_bp.route("/student/qr-diem-danh/<int:student_id>")
def student_qr_attendance_page(student_id):
    """
    Trang điểm danh QR — dành cho học sinh mở trên điện thoại.
    QR chứa trực tiếp student_id — không hết hạn, không cần token.
    """
    student = db.session.get(Student, student_id)
    if not student:
        return render_template(
            "student_qr_attendance.html",
            valid=False,
            reason="missing",
            student=None,
            school_name=None,
        )

    configs = {c.key: c.value for c in SystemConfig.query.all()}
    school_name = configs.get("school_name", "Trường học")

    qr_data = make_attendance_qr_data(student.id)

    return render_template(
        "student_qr_attendance.html",
        valid=True,
        reason=None,
        student=student,
        school_name=school_name,
        qr_data=qr_data,
    )


@student_bp.route("/student/diem-danh-qr")
@student_required
def student_qr_attendance_dashboard():
    """
    Trang tạo mã QR điểm danh nhanh — dành cho học sinh bấm nút trên dashboard.
    QR chứa trực tiếp student_id — không hết hạn.
    """
    student_id = session["student_id"]
    student = db.session.get(Student, student_id)
    if not student:
        return redirect(url_for("student.student_logout"))

    qr_data = make_attendance_qr_data(student.id)
    return render_template(
        "student_qr_attendance.html",
        valid=True,
        reason=None,
        student=student,
        school_name=None,
        qr_data=qr_data,
    )


@student_bp.route("/api/student/chat", methods=["POST"])
@student_required
def student_chat():
    """
    API Chatbot cho học sinh.
    Chấp nhận: application/json { "message", "mode" } hoặc multipart/form-data với message, mode, file (tùy chọn).
    """
    from app_helpers import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa
    msg = ""
    mode = "rule"
    file_obj = None
    image_base64 = None
    attached_filename = None

    if request.content_type and "multipart/form-data" in request.content_type:
        msg = (request.form.get("message") or "").strip()
        mode = request.form.get("mode") or "rule"
        file_obj = request.files.get("file")
        if file_obj and file_obj.filename:
            ext = (file_obj.filename or "").rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED_CHAT_EXTENSIONS:
                return jsonify({"error": "Định dạng file không hỗ trợ. Chỉ chấp nhận: " + ", ".join(ALLOWED_CHAT_EXTENSIONS)}), 400
            attached_filename = file_obj.filename
            data = file_obj.read()
            if ext in {"png", "jpg", "jpeg", "gif", "webp"}:
                image_base64 = base64.b64encode(data).decode("utf-8")
            # PDF có thể mở rộng sau (OCR hoặc text extraction)
    else:
        data = request.get_json() or {}
        msg = data.get("message", "").strip()
        mode = data.get("mode", "rule")

    if not msg and not attached_filename:
        return jsonify({"error": "Empty message"}), 400
    if not msg:
        msg = f"[Đã gửi file: {attached_filename}]"

    student_id = session["student_id"]
    session_id = get_or_create_chat_session()

    save_message(session_id, None, "user", msg, context_data={"student_id": student_id, "mode": mode, "attachment": attached_filename})

    import prompts
    system_prompt = prompts.STUDENT_LEARNING_PROMPT if mode == "study" else prompts.STUDENT_RULE_PROMPT
    history = get_conversation_history(session_id, limit=6)
    reply, err = _student_chat_call_ollama(system_prompt, history, msg, image_base64=image_base64)
    if err:
        reply = "Xin lỗi, hiện tại mình đang bị 'lag' xíu. Bạn hỏi lại sau nhé! 😿"
    save_message(session_id, None, "assistant", reply, context_data={"student_id": student_id, "mode": mode})
    return jsonify({"reply": reply})




