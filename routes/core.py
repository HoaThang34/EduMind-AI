"""Routes: core."""
import json
import os
import uuid
import datetime
from io import BytesIO
import pandas as pd
from flask import render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_login import login_user, login_required, current_user
from sqlalchemy import func, desc, or_, and_
from werkzeug.security import generate_password_hash

from models import (
    db, Student, Violation, ViolationType, Teacher, SystemConfig, ClassRoom,
    WeeklyArchive, Subject, Grade, BonusType, BonusRecord, Notification,
    GroupChatMessage, PrivateMessage, ChangeLog,
)
from app_helpers import (
    admin_required, get_accessible_students, can_access_student, normalize_student_code,
    parent_phone_login_match,
    parse_excel_file, import_violations_to_db, calculate_week_from_date, _call_gemini,
    save_weekly_archive, get_current_iso_week, create_notification, log_change,
    UPLOAD_FOLDER, calculate_student_gpa, is_reset_needed,
)


def register(app):
    @app.route('/admin')
    def redirect_admin_login():
        return redirect(url_for('auth.login'))

    @app.route("/", methods=["GET", "POST"])
    def welcome():
        if current_user.is_authenticated:
            return redirect(url_for('home'))
    
        if request.method == "POST":
            login_type = request.form.get("login_type", "staff")
        
            if login_type == "staff":
                username = request.form.get("username", "").strip()
                password = request.form.get("password", "").strip()
                # Tìm giáo viên (không lọc theo school_id nữa)
                user = Teacher.query.filter_by(username=username).first()
                if user and user.check_password(password):
                    login_user(user)
                    return redirect(url_for("dashboard"))
                flash("Sai tài khoản hoặc mật khẩu!", "error")
            
            elif login_type == "student":
                student_code = request.form.get("student_code", "").strip()
                pwd = request.form.get("student_password", "").strip()
                norm_code = normalize_student_code(student_code)
                student = Student.query.filter_by(student_code=norm_code).first()
                if not student:
                    flash("Mã số học sinh không tồn tại trong hệ thống!", "error")
                elif not (student.parent_phone or "").strip():
                    flash(
                        "Học sinh chưa có số điện thoại phụ huynh trong hệ thống. "
                        "Vui lòng liên hệ nhà trường để cập nhật trước khi đăng nhập.",
                        "error",
                    )
                elif not pwd:
                    flash("Vui lòng nhập mật khẩu (số điện thoại phụ huynh).", "error")
                elif not parent_phone_login_match(student.parent_phone, pwd):
                    flash("Sai mật khẩu. Mật khẩu là số điện thoại phụ huynh đã đăng ký.", "error")
                else:
                    session["student_id"] = student.id
                    session["student_name"] = student.name
                    return redirect(url_for("student.student_dashboard"))
            
        return render_template('welcome.html')


    @app.route("/home")
    @login_required
    def home():
        cfg = {}
        try:
            for row in SystemConfig.query.filter(
                SystemConfig.key.in_(["school_name", "school_year"])
            ).all():
                cfg[row.key] = (row.value or "").strip()
        except Exception:
            pass
        school_name = cfg.get("school_name") or "THPT Chuyên Nguyễn Tất Thành"
        school_year = cfg.get("school_year") or "2025-2026"
        return render_template(
            "home.html",
            school_name=school_name,
            school_year=school_year,
        )


    @app.route('/docs')
    def docs(): return render_template('docs.html')


    @app.route('/terms')
    def terms(): return render_template('terms.html')


    @app.route('/privacy')
    def privacy(): return render_template('privacy.html')


    @app.route('/scoreboard')
    @login_required
    def index():
        search = request.args.get('search', '').strip()
        selected_class = request.args.get('class_select', '').strip()
        selected_warning = request.args.get('warning_level', '').strip()
        selected_academic_warning = request.args.get('academic_warning', '').strip()
        
        q = get_accessible_students()  # Filter by role
        if selected_class: q = q.filter_by(student_class=selected_class)
        if selected_warning: q = q.filter_by(warning_level=selected_warning)
        if selected_academic_warning: q = q.filter_by(academic_warning_level=selected_academic_warning)
        if search: q = q.filter(or_(Student.name.ilike(f"%{search}%"), Student.student_code.ilike(f"%{search}%")))
        students = q.order_by(Student.student_code.asc()).all()
    
        # Calculate GPA for each student
        configs = {c.key: c.value for c in SystemConfig.query.all()}
        semester = int(configs.get("current_semester", "1"))
        school_year = configs.get("school_year", "2025-2026")
    
        student_gpas = {}
        for student in students:
            gpa = calculate_student_gpa(student.id, semester, school_year)
            student_gpas[student.id] = gpa
    
        return render_template('index.html', students=students, student_gpas=student_gpas, search_query=search, selected_class=selected_class, selected_warning=selected_warning, selected_academic_warning=selected_academic_warning)
    @app.route("/dashboard")
    @login_required
    def dashboard():
        show_reset_warning = is_reset_needed()
    
        # 1. Lấy số thứ tự tuần hiện tại
        w_cfg = SystemConfig.query.filter_by(key="current_week").first()
        current_week = int(w_cfg.value) if w_cfg else 1
    
        s_class = request.args.get("class_select")
    
        # 2. Thống kê điểm số (Filter by role)
        # Nếu GVCN và không chọn lớp cụ thể, tự động filter assigned_class
        if not s_class and current_user.role == 'homeroom_teacher' and current_user.assigned_class:
            s_class = current_user.assigned_class
    
        q = get_accessible_students()  # Already filtered by role
        if s_class: 
            q = q.filter_by(student_class=s_class)
        c_tot = q.filter(Student.current_score >= 90).count()
        c_kha = q.filter(Student.current_score >= 70, Student.current_score < 90).count()
        c_tb = q.filter(Student.current_score < 70).count()
    
        # 3. Thống kê lỗi (CHỈ LẤY CỦA TUẦN HIỆN TẠI)
        vios_q = db.session.query(Violation.violation_type_name, func.count(Violation.violation_type_name).label("c"))
    
        # Lọc theo tuần hiện tại
        vios_q = vios_q.filter(Violation.week_number == current_week)
    
        if s_class: 
            vios_q = vios_q.join(Student).filter(Student.student_class == s_class)
        
        top = vios_q.group_by(Violation.violation_type_name).order_by(desc("c")).limit(5).all()
    
        return render_template("dashboard.html", 
                               show_reset_warning=show_reset_warning,
                               selected_class=s_class, 
                               pie_labels=json.dumps(["Tốt", "Khá", "Cần cố gắng"]), 
                               pie_data=json.dumps([c_tot, c_kha, c_tb]), 
                               bar_labels=json.dumps([n for n, _ in top]), 
                               bar_data=json.dumps([c for _, c in top]))


    # === STUDENT PORTAL ROUTES ===

    @app.route("/api/analyze_class_stats", methods=["POST"])
    @login_required
    def analyze_class_stats():
        """
        API Phân tích tình hình nề nếp.
        - Có khả năng TỰ ĐỘNG chọn tuần hiện tại nếu không nhận được tham số.
        """
        try:
            data = request.get_json() or {} # Thêm or {} để tránh lỗi nếu data None
            s_class = data.get("class_name", "")
        
            # 1. Lấy tuần hiện tại của hệ thống (QUAN TRỌNG)
            sys_week_cfg = SystemConfig.query.filter_by(key="current_week").first()
            sys_week = int(sys_week_cfg.value) if sys_week_cfg else 1

            # 2. Xử lý tham số tuần từ Frontend
            weeks_input = data.get("weeks", [])
        
            # Hỗ trợ format cũ (single week)
            if not weeks_input and data.get("week"):
                weeks_input = [int(data.get("week"))]
            
            # --- SỬA LỖI TẠI ĐÂY: Logic Default ---
            # Nếu Frontend không gửi tuần nào (trường hợp Dashboard) -> Lấy tuần hiện tại
            if not weeks_input:
                weeks_input = [sys_week]
            # -------------------------------------

            # Sắp xếp tuần tăng dần
            weeks_input = sorted(list(set([int(w) for w in weeks_input]))) # set() để loại bỏ trùng lặp

            stats_summary = [] 

            # 3. Quét qua từng tuần để lấy số liệu
            for w in weeks_input:
                # Logic: Tuần nhỏ hơn tuần hệ thống là Lịch sử (Archive), ngược lại là Hiện tại (Student)
                is_history = (w < sys_week)
            
                # --- Lấy thống kê Điểm số & Sĩ số ---
                if is_history:
                    # Lấy từ kho lưu trữ
                    q = WeeklyArchive.query.filter_by(week_number=w)
                    if s_class: q = q.filter_by(student_class=s_class)
                    archives = q.all()
                
                    total_students = len(archives)
                    if total_students > 0:
                        avg_score = sum(a.final_score for a in archives) / total_students
                        c_tot = sum(1 for a in archives if a.final_score >= 90)
                        c_tb = sum(1 for a in archives if a.final_score < 70)
                    else:
                        avg_score, c_tot, c_tb = 0, 0, 0
                else:
                    # Lấy từ dữ liệu thực tế đang chạy
                    q = Student.query
                    if s_class: q = q.filter_by(student_class=s_class)
                    students = q.all()
                
                    total_students = len(students)
                    if total_students > 0:
                        avg_score = sum(s.current_score for s in students) / total_students
                        c_tot = sum(1 for s in students if s.current_score >= 90)
                        c_tb = sum(1 for s in students if s.current_score < 70)
                    else:
                        avg_score, c_tot, c_tb = 0, 0, 0

                # --- Lấy Top vi phạm ---
                vios_q = db.session.query(Violation.violation_type_name, func.count(Violation.violation_type_name).label("c"))
                vios_q = vios_q.filter(Violation.week_number == w)
                if s_class:
                    vios_q = vios_q.join(Student).filter(Student.student_class == s_class)
            
                top_violations = vios_q.group_by(Violation.violation_type_name).order_by(desc("c")).limit(3).all()
            
                violations_text = ", ".join([f"{name} ({count})" for name, count in top_violations])
                if not violations_text: violations_text = "Không có vi phạm đáng kể"

                stats_summary.append(
                    f"- TUẦN {w}: Điểm TB {avg_score:.1f}/100. (Tốt: {c_tot}, Yếu/TB: {c_tb}). Vi phạm chính: {violations_text}."
                )

            # 4. Tạo Prompt gửi AI
            context_name = f"Lớp {s_class}" if s_class else "Toàn Trường"
            data_context = "\n".join(stats_summary)
        
            # Nếu chỉ phân tích 1 tuần -> Dùng prompt nhận xét tình hình
            if len(weeks_input) == 1:
                prompt = f"""
                Đóng vai Trợ lý Giáo dục. Phân tích nề nếp {context_name} trong {weeks_input[0]}:
                {data_context}
            
                Yêu cầu: Nhận xét ngắn gọn (3-4 câu) về tình hình, chỉ ra điểm tốt/xấu và đưa ra 1 lời khuyên. Giọng văn sư phạm, xây dựng.
                """
            else:
                # Nếu phân tích nhiều tuần -> Dùng prompt so sánh sự tiến bộ
                prompt = f"""
                Đóng vai Trợ lý Giáo dục. Hãy phân tích SỰ TIẾN BỘ nề nếp của {context_name} qua các tuần:
                {data_context}

                Yêu cầu:
                1. Nhận xét xu hướng (Tốt lên/Đi xuống?).
                2. Chỉ ra sự thay đổi về các lỗi vi phạm (Lỗi nào giảm, lỗi nào tăng?).
                3. Kết luận ngắn gọn: Khen ngợi hoặc nhắc nhở.
                4. Viết đoạn văn khoảng 4-5 câu.
                """
        
            # Gọi AI
            analysis_text, error = _call_gemini(prompt)
        
            if error: 
                return jsonify({"error": error}), 500
            
            return jsonify({"analysis": analysis_text})

        except Exception as e:
            print(f"Analyze Error: {e}")
            return jsonify({"error": str(e)}), 500
    @app.route("/profile")
    @login_required
    def profile(): return render_template("profile.html", user=current_user)

    @app.route("/edit_profile", methods=["GET", "POST"])
    @login_required
    @admin_required
    def edit_profile():
        if request.method == "POST":
            return redirect(url_for("profile"))
        return render_template("edit_profile.html", user=current_user)
    @app.route("/history")
    @login_required
    def history():
        # 1. Lấy danh sách tuần có dữ liệu
        weeks = [w[0] for w in db.session.query(Violation.week_number).distinct().order_by(Violation.week_number.desc()).all()]
    
        selected_week = request.args.get('week', type=int)
        selected_class = request.args.get('class_select', '').strip()

        # Mặc định chọn tuần mới nhất
        if not selected_week and weeks: selected_week = weeks[0]
        
        violations = []     
        class_rankings = [] 
        pie_data = [0, 0, 0] 
        bar_labels = []      
        bar_data = []        

        if selected_week:
            # A. LẤY CHI TIẾT VI PHẠM (để hiện bảng danh sách lỗi)
            query = db.session.query(Violation).join(Student).filter(Violation.week_number == selected_week)
            if selected_class:
                query = query.filter(Student.student_class == selected_class)
            violations = query.order_by(Violation.date_committed.desc()).all()

            # B. TÍNH TOÁN BIỂU ĐỒ TRÒN & CỘT
            # Thay vì lấy từ Archive, ta tính toán trực tiếp ("Real-time")
        
            # Lấy danh sách học sinh cần tính
            q_students = Student.query
            if selected_class: q_students = q_students.filter_by(student_class=selected_class)
            students = q_students.all()

            count_tot, count_kha, count_tb = 0, 0, 0

            # Tính điểm cho từng học sinh trong tuần đã chọn
            for s in students:
                # Tổng điểm trừ của học sinh này trong tuần đó
                s_deduct = db.session.query(func.sum(Violation.points_deducted))\
                    .filter(Violation.student_id == s.id, Violation.week_number == selected_week)\
                    .scalar() or 0
            
                s_score = 100 - s_deduct
            
                if s_score >= 90: count_tot += 1
                elif s_score >= 70: count_kha += 1
                else: count_tb += 1

            pie_data = [count_tot, count_kha, count_tb]

            # Top vi phạm
            vios_chart_q = db.session.query(Violation.violation_type_name, func.count(Violation.id).label("c"))\
                .filter(Violation.week_number == selected_week)
            if selected_class:
                vios_chart_q = vios_chart_q.join(Student).filter(Student.student_class == selected_class)
            top = vios_chart_q.group_by(Violation.violation_type_name).order_by(desc("c")).limit(5).all()
            bar_labels = [t[0] for t in top]
            bar_data = [t[1] for t in top]

            # C. TÍNH BẢNG XẾP HẠNG (QUAN TRỌNG: ĐÃ SỬA LẠI LOGIC)
            # Chỉ tính khi không lọc lớp cụ thể
            if not selected_class:
                all_classes_obj = ClassRoom.query.all()
                for cls in all_classes_obj:
                    # 1. Lấy tất cả học sinh của lớp
                    students_in_class = Student.query.filter_by(student_class=cls.name).all()
                    student_count = len(students_in_class)

                    if student_count > 0:
                        # 2. Tính tổng điểm trừ của cả lớp trong tuần này
                        total_deduct_class = db.session.query(func.sum(Violation.points_deducted))\
                            .join(Student)\
                            .filter(Student.student_class == cls.name, Violation.week_number == selected_week)\
                            .scalar() or 0
                    
                        # 3. Tính điểm trung bình chuẩn: (Tổng điểm tất cả HS) / Số lượng HS
                        # Tổng điểm tất cả HS = (100 * Số HS) - Tổng điểm trừ
                        HE_SO_PHAT = 15.0
                    
                        avg_deduct = total_deduct_class / student_count
                        avg_score = 100 - (avg_deduct * HE_SO_PHAT)
                    
                        if avg_score < 0: avg_score = 0
                    else:
                        total_deduct_class = 0
                        avg_score = 100 

                    class_rankings.append({
                        "name": cls.name,
                        "weekly_deduct": total_deduct_class,
                        "avg_score": round(avg_score, 2)
                    })
            
                # Sắp xếp từ cao xuống thấp
                class_rankings.sort(key=lambda x: x['avg_score'], reverse=True)

        all_classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]

        return render_template("history.html", 
                               weeks=weeks, 
                               selected_week=selected_week, 
                               selected_class=selected_class,
                               violations=violations, 
                               class_rankings=class_rankings,
                               all_classes=all_classes,
                               pie_data=json.dumps(pie_data),
                               bar_labels=json.dumps(bar_labels),
                               bar_data=json.dumps(bar_data))

    # --- THÊM ROUTE MỚI ĐỂ XUẤT EXCEL ---

    @app.route("/export_history")
    @login_required
    def export_history():
        selected_week = request.args.get('week', type=int)
        selected_class = request.args.get('class_select', '').strip()
    
        if not selected_week:
            flash("Vui lòng chọn tuần để xuất báo cáo", "error")
            return redirect(url_for('history'))

        # Truy vấn giống hệt bên trên
        query = db.session.query(Violation).join(Student).filter(Violation.week_number == selected_week)
        if selected_class:
            query = query.filter(Student.student_class == selected_class)
    
        violations = query.order_by(Violation.date_committed.desc()).all()
    
        # Tạo dữ liệu cho Excel
        data = []
        for v in violations:
            data.append({
                "Ngày": v.date_committed.strftime('%d/%m/%Y'),
                "Mã HS": v.student.student_code,
                "Họ Tên": v.student.name,
                "Lớp": v.student.student_class,
                "Lỗi Vi Phạm": v.violation_type_name,
                "Điểm Trừ": v.points_deducted,
                "Tuần": v.week_number
            })
    
        # Xuất file
        if data:
            df = pd.read_json(json.dumps(data))
        else:
            df = pd.DataFrame([{"Thông báo": "Không có dữ liệu vi phạm"}])

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f"Tuan_{selected_week}")
            # Tự động điều chỉnh độ rộng cột (cơ bản)
            worksheet = writer.sheets[f"Tuan_{selected_week}"]
            for idx, col in enumerate(df.columns):
                worksheet.column_dimensions[chr(65 + idx)].width = 20

        output.seek(0)
        filename = f"BaoCao_ViPham_Tuan{selected_week}"
        if selected_class:
            filename += f"_{selected_class}"
        filename += ".xlsx"
    
        return send_file(output, download_name=filename, as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    @app.route("/weekly_report")
    @login_required
    def weekly_report():
        # 1. Lấy tuần hiện tại của hệ thống
        w_cfg = SystemConfig.query.filter_by(key="current_week").first()
        sys_week = int(w_cfg.value) if w_cfg else 1
    
        # 2. Lấy tuần được chọn từ URL (nếu không có thì mặc định là tuần hệ thống)
        selected_week = request.args.get('week', sys_week, type=int)
    
        # 3. Lấy danh sách vi phạm chi tiết để hiện bảng
        vios = db.session.query(Violation, Student).join(Student).filter(Violation.week_number == selected_week).all()
    
        total_errors = len(vios)
        total_points = sum(v.Violation.points_deducted for v in vios)
    
        # 4. Tính toán Bảng xếp hạng (ĐÃ SỬA LOGIC)
        all_classes = ClassRoom.query.all()
        class_data = []
    
        for cls in all_classes:
            # Lấy danh sách học sinh thực tế của lớp
            students_in_class = Student.query.filter_by(student_class=cls.name).all()
            student_count = len(students_in_class)
        
            # Bỏ qua nếu lớp không có học sinh (tránh chia cho 0)
            if student_count == 0:
                continue
        
            # Tính tổng điểm trừ của cả lớp trong tuần đó
            weekly_deduct = db.session.query(func.sum(Violation.points_deducted))\
                .join(Student)\
                .filter(Student.student_class == cls.name, Violation.week_number == selected_week)\
                .scalar() or 0
        
            # --- CÔNG THỨC CHUẨN: (Tổng điểm có sẵn - Tổng trừ) / Số lượng HS ---
            HE_SO_PHAT = 15.0 
        
            # Công thức: 100 - (Điểm trừ trung bình * Hệ số)
            avg_deduct = weekly_deduct / student_count
            avg_score = 100 - (avg_deduct * HE_SO_PHAT)
        
            # Đảm bảo không bị âm điểm
            if avg_score < 0: avg_score = 0
        
            class_data.append({
                'name': cls.name,
                'avg_score': round(avg_score, 2),
                'weekly_deduct': weekly_deduct
            })
    
        # Sắp xếp từ cao xuống thấp
        class_rankings = sorted(class_data, key=lambda x: x['avg_score'], reverse=True)
    
        return render_template("weekly_report.html", 
                               violations=vios, 
                               selected_week=selected_week, 
                               system_week=sys_week, 
                               total_points=total_points, 
                               total_errors=total_errors, 
                               class_rankings=class_rankings)

    @app.route("/export_report")
    @login_required
    def export_report():
        week = request.args.get('week', type=int)
        if not week: return "Vui lòng chọn tuần", 400
        violations = db.session.query(Violation, Student).join(Student).filter(Violation.week_number == week).all()
        data = [{"Tên": r.Student.name, "Lớp": r.Student.student_class, "Lỗi": r.Violation.violation_type_name} for r in violations]
        df = pd.read_json(json.dumps(data)) if data else pd.DataFrame([{"Thông báo": "Trống"}])
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False)
        output.seek(0)
        return send_file(output, download_name=f"Report_{week}.xlsx", as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- Thay thế hàm student_detail cũ ---
    @app.route("/student/<int:student_id>")
    @login_required
    def student_detail(student_id):
        # Kiểm tra quyền truy cập học sinh
        if not can_access_student(student_id):
            flash("Bạn không có quyền xem học sinh này!", "error")
            return redirect(url_for('dashboard'))
    
        student = db.session.get(Student, student_id)
        if not student:
            flash("Học sinh không tồn tại.", "error")
            return redirect(url_for('manage_students'))

        # 1. Lấy danh sách các tuần có dữ liệu (từ cả violations và bonuses)
        violation_weeks = [w[0] for w in db.session.query(Violation.week_number).distinct().all()]
        bonus_weeks = [w[0] for w in db.session.query(BonusRecord.week_number).distinct().all()]
        weeks = sorted(set(violation_weeks + bonus_weeks), reverse=True)
    
        # 2. Xác định tuần được chọn (Mặc định là tuần hiện tại của hệ thống)
        w_cfg = SystemConfig.query.filter_by(key="current_week").first()
        sys_current_week = int(w_cfg.value) if w_cfg else 1
    
        selected_week = request.args.get('week', type=int)
        if not selected_week:
            selected_week = sys_current_week

        # 3. Lấy vi phạm CHỈ CỦA TUẦN ĐÓ
        violations = Violation.query.filter_by(student_id=student_id, week_number=selected_week)\
            .order_by(Violation.date_committed.asc()).all()

        # 4. Lấy điểm cộng CHỈ CỦA TUẦN ĐÓ
        bonuses = BonusRecord.query.filter_by(student_id=student_id, week_number=selected_week)\
            .order_by(BonusRecord.date_awarded.asc()).all()

        # 5. Tính toán dữ liệu biểu đồ (Reset về 100 mỗi đầu tuần)
        chart_labels = ["Đầu tuần"]
        chart_scores = [100]
    
        # Kết hợp violations và bonuses theo thời gian
        events = []
        for v in violations:
            events.append({'type': 'violation', 'date': v.date_committed, 'points': -v.points_deducted, 'name': v.violation_type_name})
        for b in bonuses:
            events.append({'type': 'bonus', 'date': b.date_awarded, 'points': b.points_added, 'name': b.bonus_type_name})
    
        # Sắp xếp theo thời gian
        events.sort(key=lambda x: x['date'])
    
        current_score = 100
        for event in events:
            current_score += event['points']  # -points cho violation, +points cho bonus
            date_str = event['date'].strftime('%d/%m')
            chart_labels.append(date_str)
            chart_scores.append(current_score)
    
        # Tính tổng
        total_deducted = sum(v.points_deducted for v in violations)
        total_added = sum(b.points_added for b in bonuses)
    
        # Điểm hiển thị trên thẻ (Score Card)
        display_score = 100 - total_deducted + total_added

        # Cảnh báo nếu điểm thấp
        warning = None
        if display_score < 70:
            warning = f"Học sinh này đang có điểm nề nếp thấp ({display_score} điểm) trong tuần {selected_week}. Cần nhắc nhở!"

        return render_template("student_detail.html", 
                               student=student,
                               weeks=weeks,
                               selected_week=selected_week,
                               violations=violations,
                               bonuses=bonuses,
                               chart_labels=json.dumps(chart_labels),
                               chart_scores=json.dumps(chart_scores),
                               display_score=display_score,
                               total_added=total_added,
                               warning=warning)

    @app.route("/violation_history")
    @login_required
    def violation_history():
        """Xem lịch sử vi phạm theo tuần và lớp - Tối ưu mobile."""
        page = request.args.get('page', 1, type=int)
        per_page = 20

        selected_week = request.args.get('week', type=int)
        selected_class = request.args.get('class_select', '').strip()

        # Lấy danh sách tuần có dữ liệu
        weeks = [w[0] for w in db.session.query(Violation.week_number).distinct().order_by(Violation.week_number.desc()).all()]

        # Lấy danh sách lớp
        all_classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]

        # Mặc định chọn tuần mới nhất
        if not selected_week and weeks:
            selected_week = weeks[0]

        # Query vi phạm
        query = db.session.query(Violation).join(Student)

        if selected_week:
            query = query.filter(Violation.week_number == selected_week)
        if selected_class:
            query = query.filter(Student.student_class == selected_class)

        violations = query.order_by(Violation.date_committed.desc()).paginate(page=page, per_page=per_page, error_out=False)

        # Thống kê tổng quan theo tuần
        weekly_stats = []
        for w in weeks[:8]:  # Chỉ lấy 8 tuần gần nhất
            total_v = Violation.query.filter_by(week_number=w).count()
            total_pts = db.session.query(func.sum(Violation.points_deducted)).filter(Violation.week_number == w).scalar() or 0
            weekly_stats.append({'week': w, 'total': total_v, 'points': total_pts})

        # Thống kê theo lớp cho tuần đã chọn
        class_stats = []
        if selected_week:
            for cls in ClassRoom.query.order_by(ClassRoom.name).all():
                stu_count = Student.query.filter_by(student_class=cls.name).count()
                if stu_count == 0:
                    continue
                cls_vios = Violation.query.filter_by(week_number=selected_week).join(Student).filter(Student.student_class == cls.name).all()
                cls_total = len(cls_vios)
                cls_pts = sum(v.points_deducted for v in cls_vios)
                class_stats.append({
                    'name': cls.name,
                    'total': cls_total,
                    'points': cls_pts,
                    'students': stu_count
                })

        # Sắp xếp theo tổng vi phạm giảm dần
        class_stats.sort(key=lambda x: x['total'], reverse=True)

        # Biểu đồ theo tuần
        chart_labels = json.dumps([f"T{w['week']}" for w in weekly_stats])
        chart_data = json.dumps([w['total'] for w in weekly_stats])

        return render_template(
            "violation_history.html",
            violations=violations,
            weeks=weeks,
            selected_week=selected_week,
            selected_class=selected_class,
            all_classes=all_classes,
            weekly_stats=weekly_stats,
            class_stats=class_stats,
            chart_labels=chart_labels,
            chart_data=chart_data
        )

    @app.route("/changelog")
    @login_required
    def changelog():
        """Xem lịch sử thay đổi CSDL - Tất cả người dùng đều có thể xem"""
        page = request.args.get('page', 1, type=int)
        per_page = 30
        search = request.args.get('search', '').strip()
        change_type_filter = request.args.get('type', '').strip()
    
        q = ChangeLog.query
    
        if search:
            q = q.filter(
                or_(
                    ChangeLog.description.ilike(f'%{search}%'),
                    ChangeLog.student_name.ilike(f'%{search}%'),
                    ChangeLog.student_class.ilike(f'%{search}%')
                )
            )
    
        if change_type_filter:
            q = q.filter(ChangeLog.change_type == change_type_filter)
    
        # Sắp xếp mới nhất trước
        logs = q.order_by(ChangeLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
        # Lấy danh sách change_type duy nhất để filter
        all_types = db.session.query(ChangeLog.change_type).distinct().all()
        type_labels = {
            'violation': 'Vi phạm',
            'bonus': 'Điểm cộng',
            'grade': 'Thêm điểm',
            'grade_update': 'Cập nhật điểm',
            'grade_delete': 'Xóa điểm',
            'violation_delete': 'Xóa vi phạm',
            'score_reset': 'Reset điểm',
            'bulk_violation': 'Nhập VP hàng loạt'
        }
    
        return render_template("changelog.html", 
            logs=logs, 
            search=search, 
            change_type_filter=change_type_filter,
            all_types=[t[0] for t in all_types],
            type_labels=type_labels
        )

    @app.route("/api/check_duplicate_student", methods=["POST"])
    def check_duplicate_student(): return jsonify([])
