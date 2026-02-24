from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import Student, Violation, BonusRecord, Grade, Subject, SystemConfig, db
import base64
import json
import ollama
from functools import wraps


student_bp = Blueprint('student', __name__)

OLLAMA_MODEL = "gemini-3-flash-preview"

# We might need to copy `student_required`, `get_student_ai_advice`, `_student_chat_call_ollama` and `ALLOWED_CHAT_EXTENSIONS` here.
# Let's extract them:
def student_required(f):
    """Decorator yêu cầu quyền học sinh để truy cập"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa, call_ollama
        if 'student_id' not in session:
            return redirect(url_for('student.student_login'))
        return f(*args, **kwargs)
    return decorated_function



def get_student_ai_advice(student):
    from app import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa, call_ollama
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
        return advice if not err else "Hệ thống đang bận, em quay lại sau nhé!"
        
    except Exception as e:
        print(f"AI Advice Error: {e}")
        return "Chào em, chúc em một ngày học tập thật tốt! (Hệ thống tư vấn đang bảo trì)"



ALLOWED_CHAT_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}


def _student_chat_call_ollama(system_prompt, history, user_message, image_base64=None):
    from app import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa
    """
    Gọi Ollama cho student chat. Nếu có image_base64 thì dùng message có images.
    history: list of dict {role, content}
    """
    model = OLLAMA_MODEL
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
        response = ollama.chat(model=model, messages=messages)
        return (response.get("message") or {}).get("content", "").strip(), None
    except Exception as e:
        return None, str(e)




@student_bp.route("/student/login", methods=["GET", "POST"])
def student_login():
    from app import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa
    if request.method == "POST":
        code = request.form.get("student_code", "").strip()
        # Chuẩn hóa mã
        norm_code = normalize_student_code(code)
        
        student = Student.query.filter_by(student_code=norm_code).first()
        if student:
            session['student_id'] = student.id
            session['student_name'] = student.name
            return redirect(url_for('student.student_dashboard'))
        else:
            flash("Mã học sinh không tồn tại! Vui lòng kiểm tra lại.", "error")
            
    return render_template("student_login.html")



@student_bp.route("/student/logout")
def student_logout():
    from app import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa
    session.pop('student_id', None)
    session.pop('student_name', None)
    return redirect(url_for('student.student_login'))



@student_bp.route("/student/dashboard")
@student_required
def student_dashboard():
    from app import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa
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
            
    # 4. Lấy lời khuyên AI (Optional - có thể load async)
    ai_advice = get_student_ai_advice(student)
    
    return render_template("student_dashboard.html", 
                           student=student, 
                           violations=current_violations,
                           bonuses=current_bonuses,
                           transcript=transcript,
                           ai_advice=ai_advice,
                           current_week=current_week)





@student_bp.route("/api/student/chat", methods=["POST"])
@student_required
def student_chat_api():
    from app import normalize_student_code, get_or_create_chat_session, get_conversation_history, save_message, calculate_student_gpa
    """
    API Chatbot cho học sinh.
    Chấp nhận: application/json { "message", "mode" } hoặc multipart/form-data với message, mode, file (tùy chọn).
    """
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




