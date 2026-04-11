from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import Student, Violation, db, Grade, SystemConfig, Subject, ClassRoom
from sqlalchemy import or_
import json
import base64
import os
import uuid
from datetime import datetime

ai_engine_bp = Blueprint('ai_engine', __name__)

@ai_engine_bp.route("/chatbot")
@login_required
def chatbot():
    from app_helpers import call_ollama, get_or_create_chat_session, get_conversation_history, save_message, CHATBOT_SYSTEM_PROMPT, _call_gemini, log_change, create_notification, can_access_subject, can_access_student
    return render_template("chatbot.html")



@ai_engine_bp.route("/api/chatbot", methods=["POST"])
@login_required
def api_chatbot():
    from app_helpers import call_ollama, get_or_create_chat_session, get_conversation_history, save_message, CHATBOT_SYSTEM_PROMPT, _call_gemini, log_change, create_notification, can_access_subject, can_access_student
    """Context-aware chatbot với conversation memory"""
    msg = (request.json.get("message") or "").strip()
    if not msg:
        return jsonify({"response": "Vui lòng nhập câu hỏi."})
    
    # 1. Get/Create chat session
    session_id = get_or_create_chat_session()
    teacher_id = current_user.id
    
    # 2. Load conversation history
    history = get_conversation_history(session_id, limit=10)
    
    # 3. Save user message to database
    save_message(session_id, teacher_id, "user", msg)
    
    # 4. Tìm kiếm học sinh từ CSDL
    # Detect class name from message (e.g., "11 Tin", "12A", etc.)
    class_filter = None
    import re
    class_pattern = re.search(r'lớp\s*(\d+\s*[A-Za-z]+\d*|\d+)', msg, re.IGNORECASE)
    if class_pattern:
        class_filter = class_pattern.group(1).strip()
    
    # Build query
    query = Student.query.filter(
        or_(
            Student.name.ilike(f"%{msg}%"), 
            Student.student_code.ilike(f"%{msg}%")
        )
    )
    
    # Add class filter if detected
    if class_filter:
        query = query.filter(Student.student_class.ilike(f"%{class_filter}%"))
    
    s_list = query.limit(10).all()
    
    # Nếu tìm thấy học sinh
    if s_list:
        # Nếu có nhiều kết quả - hiển thị danh sách để chọn
        if len(s_list) > 1:
            response = f"**Tìm thấy {len(s_list)} học sinh:**\n\n"
            buttons = []
            
            for s in s_list:
                response += f"• {s.name} ({s.student_code}) - Lớp {s.student_class}\n"
                buttons.append({
                    "label": f"{s.name} - {s.student_class}",
                    "payload": f"{s.name}"
                })
            
            response += "\n*Nhấn vào tên để xem chi tiết*"
            
            # Save bot response
            save_message(session_id, teacher_id, "assistant", response)
            
            return jsonify({"response": response.strip(), "buttons": buttons})
        
        # Nếu chỉ có 1 kết quả - sử dụng AI để phân tích
        student = s_list[0]
        
        # Thu thập dữ liệu từ CSDL
        week_cfg = SystemConfig.query.filter_by(key="current_week").first()
        current_week = int(week_cfg.value) if week_cfg else 1
        # Lấy configs
        configs = {c.key: c.value for c in SystemConfig.query.all()}
        semester = int(configs.get("current_semester", "1"))
        school_year = configs.get("school_year", "2025-2026")
        
        # Lấy điểm học tập
        grades = Grade.query.filter_by(
            student_id=student.id,
            semester=semester,
            school_year=school_year
        ).all()
        
        grades_data = {}
        if grades:
            grades_by_subject = {}
            for grade in grades:
                if grade.subject_id not in grades_by_subject:
                    grades_by_subject[grade.subject_id] = {
                        'subject_name': grade.subject.name,
                        'TX': [],
                        'GK': [],
                        'HK': []
                    }
                grades_by_subject[grade.subject_id][grade.grade_type].append(grade.score)
            
            for subject_id, data in grades_by_subject.items():
                subject_name = data['subject_name']
                avg_score = None
                
                if data['TX'] and data['GK'] and data['HK']:
                    avg_tx = sum(data['TX']) / len(data['TX'])
                    avg_gk = sum(data['GK']) / len(data['GK'])
                    avg_hk = sum(data['HK']) / len(data['HK'])
                    avg_score = round((avg_tx + avg_gk * 2 + avg_hk * 3) / 6, 2)
                    
                    grades_data[subject_name] = {
                        'TX': round(avg_tx, 1),
                        'GK': round(avg_gk, 1),
                        'HK': round(avg_hk, 1),
                        'TB': avg_score
                    }
        
        # Lấy vi phạm
        violations = Violation.query.filter_by(student_id=student.id).order_by(Violation.date_committed.desc()).all()
        violations_data = []
        if violations:
            for v in violations[:5]:
                violations_data.append({
                    'type': v.violation_type_name,
                    'points': v.points_deducted,
                    'date': v.date_committed.strftime('%d/%m/%Y')
                })
        
        # Tạo response có cấu trúc
        response = f"**📊 Thông tin học sinh: {student.name}**\n\n"
        response += f"• **Mã số:** {student.student_code}\n"
        response += f"• **Lớp:** {student.student_class}\n"
        response += f"• **Điểm hành vi:** {student.current_score}/100\n\n"
        
        if grades_data:
            response += "**📚 Điểm học tập (HK1):**\n"
            for subject, scores in grades_data.items():
                response += f"• {subject}: TX={scores['TX']}, GK={scores['GK']}, HK={scores['HK']}, TB={scores['TB']}\n"
        else:
            response += "**📚 Điểm học tập:** Chưa có dữ liệu\n"
        
        if violations_data:
            response += f"\n**⚠️ Vi phạm:** {len(violations)} lần\n"
            response += "Chi tiết gần nhất:\n"
            for v in violations_data:
                response += f"• {v['date']}: {v['type']} (-{v['points']} điểm)\n"
        else:
            response += "\n**⚠️ Vi phạm:** Không có\n"
        
        save_message(session_id, teacher_id, "assistant", response)
        
        buttons = [
            {"label": "📊 Xem học bạ", "payload": f"/student/{student.id}/transcript"},
            {"label": "📈 Chi tiết điểm", "payload": f"/student/{student.id}"},
            {"label": "📜 Lịch sử vi phạm", "payload": f"/student/{student.id}/violations_timeline"}
        ]
        
        return jsonify({"response": response.strip(), "buttons": buttons})
    
    # Nếu không tìm thấy học sinh
    if class_filter:
        response_text = f"Hiện tại, hệ thống **không tìm thấy** học sinh nào có tên là **{msg}** trong **lớp {class_filter}** 🔍\n\n"
    else:
        response_text = f"Hiện tại, hệ thống **không tìm thấy** học sinh nào có tên là **{msg}** 🔍\n\n"
    
    response_text += "Cô/thầy vui lòng:\n"
    response_text += "• Kiểm tra lại **chính tả** hoặc đầu của họ tên (VD: Hòa hay Hóa).\n"
    response_text += "• Hoặc thử nhập **Mã số học sinh** để tra cứu chính xác hơn!\n\n"
    response_text += "Em luôn sẵn sàng hỗ trợ cô/thầy tiếp tục a. 😊"
    
    # Save AI response
    save_message(session_id, teacher_id, "assistant", response_text)
    
    return jsonify({"response": response_text})



@ai_engine_bp.route("/api/chatbot/clear", methods=["POST"])
@login_required
def clear_chat_session():
    from app_helpers import call_ollama, get_or_create_chat_session, get_conversation_history, save_message, CHATBOT_SYSTEM_PROMPT, _call_gemini, log_change, create_notification, can_access_subject, can_access_student
    """Tạo session mới và xóa session cũ khỏi Flask session"""
    session.pop('chat_session_id', None)
    return jsonify({"status": "success", "message": "Chat đã được làm mới"})




@ai_engine_bp.route("/assistant_chatbot")
@login_required
def assistant_chatbot():
    from app_helpers import call_ollama, get_or_create_chat_session, get_conversation_history, save_message, CHATBOT_SYSTEM_PROMPT, _call_gemini, log_change, create_notification, can_access_subject, can_access_student
    """Chatbot đa năng: nội quy, ứng xử, trợ giúp GV"""
    return render_template("assistant_chatbot.html")



@ai_engine_bp.route("/api/generate_report/<int:student_id>", methods=["POST"])
@login_required
def generate_report(student_id):
    from app_helpers import (
        call_ollama,
        get_or_create_chat_session,
        get_conversation_history,
        save_message,
        CHATBOT_SYSTEM_PROMPT,
        _call_gemini,
        log_change,
        create_notification,
        can_access_subject,
        can_access_student,
        get_ollama_model,
        get_ollama_client,
    )
    try:
        data = request.get_json() or {}
        week = data.get('week') # Nhận tham số tuần từ Frontend
        
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"error": "Học sinh không tồn tại"}), 404

        # Lấy dữ liệu vi phạm của tuần được chọn
        query = Violation.query.filter_by(student_id=student_id)
        if week:
            query = query.filter_by(week_number=week)
            time_context = f"TUẦN {week}"
        else:
            time_context = "TỪ TRƯỚC ĐẾN NAY"
            
        violations = query.all()
        
        # Tổng hợp dữ liệu gửi cho AI
        total_deducted = sum(v.points_deducted for v in violations)
        final_score = 100 - total_deducted
        
        violation_list = [f"- {v.violation_type_name} (ngày {v.date_committed.strftime('%d/%m')})" for v in violations]
        violation_text = "\n".join(violation_list) if violation_list else "Không có vi phạm nào."

        # Prompt dành cho Ollama
        prompt = f"""
        Đóng vai Trợ lý Giáo viên Chủ nhiệm. Hãy viết một nhận xét ngắn (khoảng 3-4 câu) gửi cho phụ huynh về tình hình nề nếp của học sinh:
        - Tên: {student.name}
        - Thời gian: {time_context}
        - Điểm nề nếp: {final_score}/100
        - Các lỗi vi phạm:
        {violation_text}

        Yêu cầu:
        1. Giọng văn lịch sự, xây dựng, quan tâm.
        2. Nếu điểm cao (>=90): Khen ngợi và động viên phát huy.
        3. Nếu điểm thấp (<70): Nhắc nhở khéo léo và đề nghị gia đình phối hợp.
        4. Trả lời bằng Tiếng Việt. Không cần chào hỏi rườm rà, vào thẳng nội dung nhận xét.
        """

        # Model: OLLAMA_TEXT_MODEL trong .env nếu có, không thì OLLAMA_MODEL (.env)
        override = (os.environ.get("OLLAMA_TEXT_MODEL") or "").strip()
        model_name = override or get_ollama_model()

        response = get_ollama_client().chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        
        ai_reply = response['message']['content']
        return jsonify({"report": ai_reply})

    except Exception as e:
        print(f"AI Error: {str(e)}")
        return jsonify({"error": "Lỗi khi gọi trợ lý ảo. Vui lòng thử lại sau."}), 500



@ai_engine_bp.route("/api/generate_parent_report/<int:student_id>", methods=["POST"])
@login_required
def generate_parent_report(student_id):
    from app_helpers import call_ollama, get_or_create_chat_session, get_conversation_history, save_message, CHATBOT_SYSTEM_PROMPT, _call_gemini, log_change, create_notification, can_access_subject, can_access_student
    """Gọi AI tạo nhận xét tổng hợp cho phụ huynh"""
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({"error": "Không tìm thấy học sinh"}), 404
    
    semester = int(request.json.get('semester', 1))
    school_year = request.json.get('school_year', '2023-2024')
    
    subjects = Subject.query.all()
    grades_info = []
    for subject in subjects:
        grades = Grade.query.filter_by(
            student_id=student_id,
            subject_id=subject.id,
            semester=semester,
            school_year=school_year
        ).all()
        
        tx_scores = [g.score for g in grades if g.grade_type == 'TX']
        gk_scores = [g.score for g in grades if g.grade_type == 'GK']
        hk_scores = [g.score for g in grades if g.grade_type == 'HK']
        
        if tx_scores and gk_scores and hk_scores:
            avg_tx = sum(tx_scores) / len(tx_scores)
            avg_gk = sum(gk_scores) / len(gk_scores)
            avg_hk = sum(hk_scores) / len(hk_scores)
            avg_score = round((avg_tx + avg_gk * 2 + avg_hk * 3) / 6, 2)
            grades_info.append(f"{subject.name}: {avg_score}")
    
    valid_avg = [float(g.split(': ')[1]) for g in grades_info if g]
    gpa = round(sum(valid_avg) / len(valid_avg), 2) if valid_avg else 0
    
    violations = Violation.query.filter_by(student_id=student_id)\
        .order_by(Violation.date_committed.desc())\
        .limit(10).all()
    
    violation_summary = f"{len(violations)} vi phạm gần đây" if violations else "Không có vi phạm"
    
    prompt = f"""Bạn là giáo viên chủ nhiệm. Hãy viết nhận xét NGẮN GỌN (3-4 câu) gửi phụ huynh về học sinh {student.name} (Lớp {student.student_class}):

THÔNG TIN HỌC TẬP:
- GPA học kỳ {semester}: {gpa}/10
- Điểm các môn: {', '.join(grades_info) if grades_info else 'Chưa có điểm'}

THÔNG TIN RÈN LUYỆN:
- Điểm rèn luyện hiện tại: {student.current_score}/100
- {violation_summary}

Hãy viết nhận xét xúc tích, chân thành, khích lệ học sinh và đưa ra lời khuyên cụ thể. Không cần xưng hô, viết trực tiếp nội dung."""
    
    response, error = _call_gemini(prompt)
    
    if error:
        return jsonify({"error": error}), 500
    
    return jsonify({"report": response})




@ai_engine_bp.route("/api/generate_chart_comments/<int:student_id>", methods=["POST"])
@login_required
def generate_chart_comments(student_id):
    from app_helpers import _call_gemini, can_access_student
    """Gọi AI tạo nhận xét trực quan về biểu đồ học tập và nề nếp cho phụ huynh"""
    
    if not can_access_student(student_id):
        return jsonify({"error": "Không có quyền truy cập"}), 403
    
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({"error": "Không tìm thấy học sinh"}), 404
    
    data = request.get_json() or {}
    
    # Lấy dữ liệu phân tích từ request
    gpa = data.get('gpa', 0)
    avg_score = data.get('avg_score', 0)
    highest_score = data.get('highest_score', 0)
    lowest_score = data.get('lowest_score', 0)
    strong_subjects = data.get('strong_subjects', [])
    weak_subjects = data.get('weak_subjects', [])
    total_subjects = data.get('total_subjects', 0)
    conduct_score = data.get('conduct_score', 100)
    total_violations = data.get('total_violations', 0)
    semester = data.get('semester', 1)
    
    # Phân loại học lực
    if gpa >= 8.5:
        academic_rank = "Giỏi"
    elif gpa >= 7.0:
        academic_rank = "Khá"
    elif gpa >= 5.0:
        academic_rank = "Trung Bình"
    else:
        academic_rank = "Yếu"
    
    # Phân loại nề nếp
    if conduct_score >= 80:
        conduct_rank = "Tốt"
    elif conduct_score >= 65:
        conduct_rank = "Khá"
    elif conduct_score >= 50:
        conduct_rank = "Trung Bình"
    else:
        conduct_rank = "Yếu"
    
    # Tạo phân tích phân bố điểm
    score_distribution = []
    if highest_score and lowest_score and total_subjects > 0:
        if float(highest_score) >= 8:
            score_distribution.append("có môn đạt điểm cao (Giỏi)")
        if float(lowest_score) < 5:
            score_distribution.append("có môn cần cải thiện (Yếu)")
        if 5 <= float(lowest_score) < 6.5:
            score_distribution.append("có môn đạt mức trung bình khá")
    
    distribution_text = ", ".join(score_distribution) if score_distribution else "phân bố điểm đều giữa các môn"
    
    # Tạo prompt cho AI
    prompt = f"""Bạn là giáo viên chủ nhiệm. Hãy viết nhận xét TRỰC QUAN (4-5 câu) dựa trên phân tích biểu đồ học tập và nề nếp của học sinh {student.name} (Lớp {student.student_class}) để gửi cho phụ huynh:

**PHÂN TÍCH BIỂU ĐỒ HỌC TẬP:**
- GPA học kỳ {semester}: {gpa}/10 (Xếp loại: {academic_rank})
- Điểm trung bình các môn: {avg_score}/10
- Điểm cao nhất: {highest_score}/10
- Điểm thấp nhất: {lowest_score}/10
- Số môn học có điểm: {total_subjects}
- Phân bố điểm: {distribution_text}
- Các môn mạnh (>=8đ): {', '.join(strong_subjects) if strong_subjects else 'Không có'}
- Các môn cần cải thiện (<5đ): {', '.join(weak_subjects) if weak_subjects else 'Không có'}

**PHÂN TÍCH BIỂU ĐỒ NỀ NẾP:**
- Điểm rèn luyện: {conduct_score}/100 (Xếp loại: {conduct_rank})
- Tổng số vi phạm: {total_violations}
- Mức độ rèn luyện: {conduct_rank}

**YÊU CẦU:**
1. Viết nhận xét dựa trên PHÂN TÍCH TRỰC QUAN từ biểu đồ
2. Đánh giá ưu điểm và điểm cần cải thiện qua biểu đồ phân bố điểm
3. Nhận xét về sự cân bằng giữa học tập và rèn luyện
4. Đưa ra lời khuyên cụ thể cho gia đình dựa trên xu hướng biểu đồ
5. Giọng văn thân thiện, chuyên nghiệp, dễ hiểu cho phụ huynh
6. Không cần xưng hô, viết trực tiếp nội dung nhận xét

Nhận xét:"""
    
    response, error = _call_gemini(prompt)
    
    if error:
        return jsonify({"error": error}), 500
    
    return jsonify({"comments": response})



@ai_engine_bp.route("/api/assistant_chatbot", methods=["POST"])
@login_required
def api_assistant_chatbot():
    from app_helpers import call_ollama, get_ollama_model
    """API cho chatbot đa năng với intent detection"""
    msg = request.json.get("message", "").strip()
    
    if not msg:
        return jsonify({"response": "Vui lòng nhập câu hỏi."})
    
    # Import prompts từ file riêng
    try:
        from prompts import (
            SCHOOL_RULES_PROMPT, 
            BEHAVIOR_GUIDE_PROMPT, 
            TEACHER_ASSISTANT_PROMPT,
            DEFAULT_ASSISTANT_PROMPT
        )
    except ImportError:
        return jsonify({"response": "Lỗi: Không tìm thấy file prompts.py"})
    
    # Intent detection - phát hiện chủ đề câu hỏi
    msg_lower = msg.lower()
    
    # Kiểm tra từ khóa nội quy
    school_rules_keywords = ["nội quy", "vi phạm", "quy định", "điểm rèn luyện", "bị trừ", "mức phạt", "xử lý kỷ luật"]
    if any(kw in msg_lower for kw in school_rules_keywords):
        system_prompt = SCHOOL_RULES_PROMPT
        category = "nội quy"
    
    # Kiểm tra từ khóa ứng xử
    elif any(kw in msg_lower for kw in ["ứng xử", "cách xử lý", "tình huống", "kỹ năng", "giao tiếp", "cãi nhau", "đánh nhau", "bắt nạt"]):
        system_prompt = BEHAVIOR_GUIDE_PROMPT
        category = "ứng xử"
    
    # Kiểm tra từ khóa trợ giúp giáo viên
    elif any(kw in msg_lower for kw in ["nhận xét", "viết nhận xét", "đánh giá học sinh", "soạn", "phương pháp", "quản lý lớp", "giáo dục", "động viên"]):
        system_prompt = TEACHER_ASSISTANT_PROMPT
        category = "trợ giúp GV"
    
    # Mặc định
    else:
        system_prompt = DEFAULT_ASSISTANT_PROMPT
        category = "general"
    
    # Tạo full prompt
    full_prompt = f"""{system_prompt}

===== CÂU HỎI =====
{msg}

===== YÊU CẦU =====
Trả lời ngắn gọn, rõ ràng bằng tiếng Việt. Sử dụng markdown và emoji phù hợp."""
    
    # Gọi Ollama
    answer, err = call_ollama(full_prompt)
    
    if err:
        response_text = (
            f"⚠️ {err}\n\nVui lòng kiểm tra:\n• Ollama đã được cài đặt và chạy chưa?\n"
            f"• Model đã được pull chưa? (`ollama pull {get_ollama_model()}` — tên phải khớp OLLAMA_MODEL trong .env và `ollama list`)"
        )
    else:
        response_text = answer or "Xin lỗi, tôi không thể trả lời câu hỏi này."
    
    return jsonify({
        "response": response_text,
        "category": category
    })
@ai_engine_bp.route("/ocr-grades")
@login_required
def ocr_grades():
    """Giao diện nhập điểm bằng OCR Vision"""
    subjects = Subject.query.order_by(Subject.name).all()
    class_list = ClassRoom.query.order_by(ClassRoom.name).all()
    # Lấy thông tin tuần/năm học hiện tại từ config
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    current_week = int(configs.get("current_week", "1"))
    semester = int(configs.get("current_semester", "1"))

    return render_template("ocr_grades.html",
                         subjects=subjects,
                         class_list=class_list,
                         semester=semester)


@ai_engine_bp.route("/api/ocr-grades", methods=["POST"])
@login_required
def api_ocr_grades():
    """Xử lý ảnh OCR sử dụng Gemini Vision"""
    from app_helpers import _call_gemini
    from prompts import VISION_GRADE_OCR_PROMPT

    if 'image' not in request.files:
        return jsonify({"error": "Không tìm thấy file ảnh"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "Tên file rỗng"}), 400

    # Save temporary file
    from app_helpers import UPLOAD_FOLDER
    filename = f"ocr_{uuid.uuid4().hex}_{file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        # Gọi AI Vision (không dùng is_json=True để tránh xung đột với prompt)
        results, error = _call_gemini(VISION_GRADE_OCR_PROMPT, image_path=filepath, is_json=False)

        # Xóa file tạm sau khi xử lý để tránh đầy disk
        try:
            os.remove(filepath)
        except Exception as cleanup_err:
            print(f"Warning: Could not delete temp file {filepath}: {cleanup_err}")

        if error:
            return jsonify({"error": f"Lỗi AI: {error}"}), 500

        # Parse JSON từ response của AI
        import json
        try:
            # AI có thể trả về JSON trong markdown code block hoặc trực tiếp
            text = results.strip()

            # Debug: Log raw response
            print(f"[OCR DEBUG] Raw AI response length: {len(text)}")
            print(f"[OCR DEBUG] First 500 chars: {text[:500]}")

            # Xóa markdown code block nếu có
            if text.startswith('```json'):
                text = text[7:]
            elif text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

            parsed = json.loads(text)
            print(f"[OCR DEBUG] Parsed JSON type: {type(parsed)}")

            # Nếu AI trả về object với key "results", dùng nó
            if isinstance(parsed, dict) and 'results' in parsed:
                print(f"[OCR DEBUG] Returning dict with results, count: {len(parsed.get('results', []))}")
                return jsonify(parsed)
            # Nếu AI trả về array trực tiếp, wrap vào object
            elif isinstance(parsed, list):
                print(f"[OCR DEBUG] Wrapping array with {len(parsed)} items")
                return jsonify({"results": parsed, "metadata": {"total_detected": len(parsed)}})
            else:
                print(f"[OCR DEBUG] Invalid structure: {type(parsed)}")
                return jsonify({"error": "Cấu trúc JSON không hợp lệ"}), 500

        except json.JSONDecodeError as e:
            print(f"[OCR DEBUG] JSON decode error: {str(e)}")
            print(f"[OCR DEBUG] Text that failed: {text[:1000]}")
            return jsonify({"error": f"Lỗi parse JSON: {str(e)}"}), 500

    except Exception as e:
        # Cleanup file on error too
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass
        return jsonify({"error": f"Lỗi xử lý: {str(e)}"}), 500


@ai_engine_bp.route("/api/confirm-ocr-grades", methods=["POST"])
@login_required
def api_confirm_ocr_grades():
    """Lưu kết quả điểm đã soát lại vào database"""
    from app_helpers import call_ollama, get_or_create_chat_session, get_conversation_history, save_message, CHATBOT_SYSTEM_PROMPT, _call_gemini, log_change, create_notification, can_access_subject, can_access_student
    data = request.get_json()
    if not data:
        return jsonify({"error": "Không có dữ liệu"}), 400
    
    subject_id = data.get('subject_id')
    class_filter = data.get('class_filter', '')  # Lọc theo lớp (tùy chọn)
    # Lấy thông tin năm học và học kỳ mặc định từ cấu hình hệ thống
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    school_year = configs.get("school_year", "2025-2026")
    default_semester = int(configs.get("current_semester", "1"))

    semester = data.get('semester', default_semester)
    
    if not subject_id:
        return jsonify({"error": "Thiếu thông tin môn học"}), 400
    
    subject = db.session.get(Subject, int(subject_id))
    if not subject:
        return jsonify({"error": "Môn học không tồn tại"}), 400
    
    success_count = 0
    errors = []
    item_results = []
    
    grades_list = data.get('grades', [])
    for item in grades_list:
        row_id = item.get('rowId')  # Changed from rowIndex to rowId for better tracking
        student_code = item.get('student_code')
        student_name = item.get('student_name')
        date_of_birth = item.get('date_of_birth')
        roll_number = item.get('roll_number')
        score = item.get('score')
        grade_type = item.get('grade_type', 'TX')
        
        try:
            column_index = int(item.get('column_index', 1))
        except (ValueError, TypeError):
            column_index = 1
        
        if score is None or score == '':
            item_results.append({"rowId": row_id, "status": "ignored", "message": "Bỏ qua ô trống"})
            continue

        try:
            score_val = float(score)
            if score_val < 0 or score_val > 10:
                msg = f"Điểm {score_val} không hợp lệ"
                errors.append(f"Mã {student_code}: {msg}")
                item_results.append({"rowId": row_id, "status": "error", "message": msg})
                continue
        except ValueError:
            msg = f"Điểm {score} không phải là số"
            errors.append(f"Mã {student_code}: {msg}")
            item_results.append({"rowId": row_id, "status": "error", "message": msg})
            continue

        # Validate grade_type
        valid_grade_types = ['TX', 'GK', 'HK']
        if grade_type not in valid_grade_types:
            msg = f"Loại điểm {grade_type} không hợp lệ (chấp nhận: TX, GK, HK)"
            errors.append(f"Mã {student_code}: {msg}")
            item_results.append({"rowId": row_id, "status": "error", "message": msg})
            continue

        # Tìm học sinh - ưu tiên: ngày sinh + số thứ tự + lớp, sau đó là mã, cuối cùng là tên
        from app_helpers import normalize_student_code

        student = None

        # Chiến lược 1: Nếu có ngày sinh + số thứ tự + lớp, tìm theo combo này
        if date_of_birth and roll_number:
            # Chuẩn hóa ngày sinh (bỏ khoảng trắng, chuẩn format)
            dob_normalized = date_of_birth.strip().replace(' ', '')
            roll_normalized = str(roll_number).strip()

            # Tìm theo lớp nếu có chọn filter
            query = Student.query
            if class_filter:
                query = query.filter_by(student_class=class_filter)

            # Tìm học sinh khớp ngày sinh và số thứ tự
            candidates = query.all()
            for s in candidates:
                s_dob = (s.date_of_birth or '').strip().replace(' ', '')
                if s_dob == dob_normalized:
                    # Nếu có số thứ tự trong tên hoặc thông tin khác, so sánh
                    # (Giả sửu roll_number được lưu trong một trường, nếu không có thì bỏ qua)
                    student = s
                    break

        # Chiến lược 2: Tìm theo mã học sinh (nếu có)
        if not student and student_code:
            normalized_code = normalize_student_code(student_code)
            student = Student.query.filter_by(student_code=student_code).first()
            if not student:
                # Nếu không tìm thấy, thử tìm theo mã đã chuẩn hóa
                all_students = Student.query.all()
                for s in all_students:
                    if normalize_student_code(s.student_code) == normalized_code:
                        student = s
                        break

        # Chiến lược 3: Tìm theo tên + lớp (nếu có)
        if not student and student_name:
            query = Student.query.filter_by(name=student_name)
            if class_filter:
                query = query.filter_by(student_class=class_filter)
            student = query.first()

            # Nếu không tìm thấy với lớp, thử tìm tên khớp bất kỳ
            if not student and not class_filter:
                student = Student.query.filter_by(name=student_name).first()
            
        if not student:
            msg = f"Không tìm thấy học sinh trong CSDL"
            errors.append(f"Mã {student_code or item.get('student_name')}: {msg}")
            item_results.append({"rowId": row_id, "status": "error", "message": msg})
            continue

        # Validate lớp nếu có chọn filter
        class_warning = None
        if class_filter and student.student_class != class_filter:
            msg = f"Cảnh báo: Học sinh thuộc lớp {student.student_class}, không phải {class_filter}"
            errors.append(f"Mã {student_code}: {msg}")
            class_warning = f"Lớp khác ({student.student_class})"
            # Không block, chỉ cảnh báo - vẫn cho phép lưu điểm
            
        # Kiểm tra xem đã có điểm chưa
        existing = Grade.query.filter_by(
            student_id=student.id,
            subject_id=subject.id,
            grade_type=grade_type,
            column_index=column_index,
            semester=semester,
            school_year=school_year
        ).first()
        
        if existing:
            old_val = existing.score
            existing.score = score_val
            log_change('grade_update', f'OCR: Cập nhật điểm {grade_type} môn {subject.name}: {old_val} → {score_val}',
                      student_id=student.id, student_name=student.name, student_class=student.student_class,
                      old_value=old_val, new_value=score_val)
            if class_warning:
                item_results.append({"rowId": row_id, "status": "warning", "message": f"Đã cập nhật ({class_warning})"})
            else:
                item_results.append({"rowId": row_id, "status": "success", "message": "Đã cập nhật"})
        else:
            new_grade = Grade(
                student_id=student.id,
                subject_id=subject.id,
                grade_type=grade_type,
                column_index=column_index,
                score=score_val,
                semester=semester,
                school_year=school_year
            )
            db.session.add(new_grade)
            log_change('grade', f'OCR: Thêm điểm {grade_type} môn {subject.name}: {score_val}',
                      student_id=student.id, student_name=student.name, student_class=student.student_class,
                      new_value=score_val)
            if class_warning:
                item_results.append({"rowId": row_id, "status": "warning", "message": f"Đã lưu mới ({class_warning})"})
            else:
                item_results.append({"rowId": row_id, "status": "success", "message": "Đã lưu mới"})
        
        success_count += 1
        
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "message": f"Đã lưu thành công {success_count} đầu điểm.",
        "errors": errors,
        "item_results": item_results
    })

@ai_engine_bp.route("/api/predict_trend/<int:student_id>", methods=["POST"])
@login_required
def predict_trend(student_id):
    try:
        from app_helpers import _call_gemini
        from prompts import STUDENT_TREND_PREDICTION_PROMPT
        
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"error": "Không tìm thấy học sinh"}), 404
            
        # Lấy dữ liệu điểm số
        grades = Grade.query.filter_by(student_id=student_id).order_by(Grade.date_recorded.desc()).limit(20).all()
        grades_text = "Không có dữ liệu điểm"
        if grades:
            grades_list = []
            for g in grades:
                date_str = g.date_recorded.strftime('%d/%m/%Y') if g.date_recorded else "N/A"
                subject_name = g.subject.name if g.subject else "N/A"
                score = g.score if g.score is not None else 0
                grades_list.append(f"- Môn {subject_name}: {score} ({g.grade_type}) - Ngày: {date_str}")
            grades_text = "\n".join(grades_list)
            
        # Tính GPA (ước tính đơn giản từ các điểm có sẵn)
        gpa = 0
        if grades:
            valid_scores = [g.score for g in grades if g.score is not None]
            if valid_scores:
                gpa = round(sum(valid_scores) / len(valid_scores), 2)
            
        # Lấy dữ liệu vi phạm
        violations = Violation.query.filter_by(student_id=student_id).order_by(Violation.date_committed.desc()).limit(15).all()
        violations_text = "Không có vi phạm"
        if violations:
            v_list = []
            for v in violations:
                date_str = v.date_committed.strftime('%d/%m/%Y') if v.date_committed else "N/A"
                v_list.append(f"- {v.violation_type_name} (-{v.points_deducted}đ) - Ngày: {date_str}")
            violations_text = "\n".join(v_list)
            
        # Lấy dữ liệu điểm cộng
        try:
            from models import BonusRecord
            bonuses = BonusRecord.query.filter_by(student_id=student_id).order_by(BonusRecord.date_awarded.desc()).limit(10).all()
            bonuses_text = "Không có thành tích"
            if bonuses:
                b_list = []
                for b in bonuses:
                    date_str = b.date_awarded.strftime('%d/%m/%Y') if b.date_awarded else "N/A"
                    b_list.append(f"- {b.bonus_type_name} (+{b.points_added}đ) - Ngày: {date_str}")
                bonuses_text = "\n".join(b_list)
        except Exception as inner_e:
            bonuses_text = "Chưa có dữ liệu"

        # Tạo prompt
        prompt = STUDENT_TREND_PREDICTION_PROMPT.format(
            name=student.name,
            student_class=student.student_class,
            current_score=student.current_score if student.current_score is not None else 100,
            gpa=gpa,
            grades_text=grades_text,
            violations_text=violations_text,
            bonuses_text=bonuses_text
        )
        
        # Gọi AI bằng chế độ bắt JSON
        result, error = _call_gemini(prompt, is_json=True)
        
        if error:
            return jsonify({"error": error}), 500
            
        return jsonify(result)

    except Exception as e:
        # Avoid printing full Exception to stdout on Windows to prevent UnicodeEncodeError crashes
        print(f"Bugs in Predict Trend: {type(e).__name__}")
        return jsonify({"error": f"Lỗi xử lý nội bộ: {str(e)}"}), 500

@ai_engine_bp.route("/voice-to-text")
@login_required
def voice_to_text():
    """Giao diện chuẩn hóa nhận xét từ giọng nói"""
    return render_template("voice_to_text.html")

@ai_engine_bp.route("/api/normalize-comment", methods=["POST"])
@login_required
def api_normalize_comment():
    """API chuẩn hóa nhận xét bằng AI"""
    from app_helpers import _call_gemini
    from prompts import VOICE_TO_PEDAGOGICAL_PROMPT
    
    data = request.get_json()
    raw_text = data.get("text", "").strip()
    
    if not raw_text:
        return jsonify({"error": "Vui lòng nhập hoặc nói nội dung nhận xét."}), 400
        
    prompt = f"{VOICE_TO_PEDAGOGICAL_PROMPT}\n\n**VĂN BẢN CẦN CHUẨN HÓA:**\n{raw_text}"
    
    # Gọi AI để chuẩn hóa
    normalized_text, error = _call_gemini(prompt)
    
    if error:
        return jsonify({"error": f"Lỗi AI: {error}"}), 500
        
    return jsonify({"normalized_text": normalized_text.strip()})
