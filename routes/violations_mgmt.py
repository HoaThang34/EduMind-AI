"""Routes: violations_mgmt."""
import json
import os
import uuid
import datetime
from io import BytesIO
import pandas as pd
from flask import render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_login import login_user, login_required, current_user
from sqlalchemy import func, desc, or_, and_

from routes.lesson_book import lesson_book_visible_query
from werkzeug.security import generate_password_hash

from models import (
    db, Student, Violation, ViolationType, Teacher, SystemConfig, ClassRoom,
    WeeklyArchive, Subject, Grade, BonusType, BonusRecord, Notification,
    GroupChatMessage, PrivateMessage, ChangeLog, LessonBookEntry,
)
from app_helpers import (
    admin_required, permission_required, role_or_permission_required, get_accessible_students, can_access_student, normalize_student_code,
    parse_excel_file, import_violations_to_db, calculate_week_from_date, _call_gemini,
    save_weekly_archive, get_current_iso_week, create_notification, log_change,
    UPLOAD_FOLDER, calculate_student_gpa, is_reset_needed, update_student_conduct,
)


def register(app):
    @app.route("/add_violation", methods=["GET", "POST"])
    @login_required
    @role_or_permission_required('discipline_officer', 'manage_discipline')
    def add_violation():
        if request.method == "POST":
            # Get list of rule IDs (can be multiple)
            selected_rule_ids = request.form.getlist("rule_ids[]")
        
            # 1. Lấy danh sách ID học sinh từ Form (Dạng Select nhiều)
            selected_student_ids = request.form.getlist("student_ids[]")
        
            # 2. Lấy danh sách từ OCR (Dạng JSON nếu có)
            ocr_json = request.form.get("students_list")

            lb_raw = request.form.get("lesson_book_entry_id", "").strip()
            lesson_book_entry_id = int(lb_raw) if lb_raw.isdigit() else None
            linked_lesson = db.session.get(LessonBookEntry, lesson_book_entry_id) if lesson_book_entry_id else None
        
            if not selected_rule_ids:
                flash("Vui lòng chọn ít nhất một lỗi vi phạm!", "error")
                return redirect(url_for("discipline_management"))

            w_cfg = SystemConfig.query.filter_by(key="current_week").first()
            current_week = int(w_cfg.value) if w_cfg else 1
            count = 0

            if linked_lesson and selected_student_ids:
                st_classes = set()
                for s_id in selected_student_ids:
                    st = db.session.get(Student, int(s_id))
                    if st:
                        st_classes.add(st.student_class)
                if len(st_classes) != 1 or list(st_classes)[0] != linked_lesson.class_name:
                    lesson_book_entry_id = None
                    linked_lesson = None
            elif linked_lesson and ocr_json:
                lesson_book_entry_id = None
                linked_lesson = None

            # Process each violation type
            for rule_id in selected_rule_ids:
                try:
                    rule = db.session.get(ViolationType, int(rule_id))
                except:
                    continue
            
                if not rule:
                    continue

                # A. Xử lý danh sách từ Dropdown chọn tay
                if selected_student_ids:
                    for s_id in selected_student_ids:
                        student = db.session.get(Student, int(s_id))
                        if student:
                            old_score = student.current_score or 100
                            student.current_score = old_score - rule.points_deducted
                            db.session.add(Violation(
                                student_id=student.id,
                                violation_type_name=rule.name,
                                points_deducted=rule.points_deducted,
                                week_number=current_week,
                                lesson_book_entry_id=lesson_book_entry_id,
                            ))
                            log_change('violation', f'Vi phạm: {rule.name} (-{rule.points_deducted} điểm)', student_id=student.id, student_name=student.name, student_class=student.student_class, old_value=old_score, new_value=student.current_score)
                            count += 1
                            # Cập nhật hạnh kiểm
                            update_student_conduct(student.id)
            
                # B. Xử lý danh sách từ OCR (Áp dụng normalize)
                elif ocr_json:
                    try:
                        student_codes = json.loads(ocr_json)
                        for code in student_codes:
                            if not code: continue
                        
                            # Tìm kiếm với normalized code
                            code_normalized = normalize_student_code(str(code).strip())
                            s = None
                        
                            # Thử exact match trước
                            s = Student.query.filter_by(student_code=str(code).strip().upper()).first()
                        
                            # Thử normalized match nếu không tìm thấy
                            if not s:
                                all_students = Student.query.all()
                                for student in all_students:
                                    if normalize_student_code(student.student_code) == code_normalized:
                                        s = student
                                        break
                        
                            if s:
                                old_score = s.current_score or 100
                                s.current_score = old_score - rule.points_deducted
                                db.session.add(Violation(
                                    student_id=s.id,
                                    violation_type_name=rule.name,
                                    points_deducted=rule.points_deducted,
                                    week_number=current_week,
                                    lesson_book_entry_id=None,
                                ))
                                log_change('violation', f'Vi phạm (OCR): {rule.name} (-{rule.points_deducted} điểm)', student_id=s.id, student_name=s.name, student_class=s.student_class, old_value=old_score, new_value=s.current_score)
                                count += 1
                                # Cập nhật hạnh kiểm
                                update_student_conduct(s.id)
                    except Exception as e:
                        print(f"OCR Error: {e}")

            if count > 0:
                db.session.commit()

                # Tạo thông báo cho GVCN các lớp bị ảnh hưởng
                affected_classes = set()
                if selected_student_ids:
                    for s_id in selected_student_ids:
                        student = db.session.get(Student, int(s_id))
                        if student and student.student_class:
                            affected_classes.add(student.student_class)

                for class_name in affected_classes:
                    try:
                        create_notification(
                            title=f"⚠️ Vi phạm mới - Lớp {class_name}",
                            message=f"{current_user.full_name} đã ghi nhận {count} vi phạm cho học sinh lớp {class_name}",
                            notification_type='violation',
                            target_role=class_name
                        )
                    except:
                        pass  # Không để lỗi notification làm gián đoạn chức năng chính

                flash(f"Đã ghi nhận {count} vi phạm (cho {len(selected_student_ids) if selected_student_ids else 'nhiều'} học sinh x {len(selected_rule_ids)} lỗi).", "success")
            else:
                flash("Chưa chọn học sinh nào hoặc xảy ra lỗi.", "error")

            return redirect(url_for("discipline_management"))

        # GET: Truyền thêm danh sách học sinh để hiển thị trong Dropdown (filtered by role)
        students = get_accessible_students().order_by(Student.student_class, Student.name).all()
        lesson_entries = (
            lesson_book_visible_query()
            .order_by(desc(LessonBookEntry.lesson_date), desc(LessonBookEntry.id))
            .limit(120)
            .all()
        )
        return render_template(
            "add_violation.html",
            rules=ViolationType.query.all(),
            students=students,
            lesson_entries=lesson_entries,
        )



    @app.route("/bulk_import_violations")
    @login_required
    @role_or_permission_required('discipline_officer', 'manage_discipline')
    def bulk_import_violations():
        """Display bulk import page"""
        students = Student.query.order_by(Student.student_class, Student.name).all()
        violation_types = ViolationType.query.all()
        return render_template("bulk_import_violations.html", 
                              students=students, 
                              violation_types=violation_types)

    @app.route("/process_bulk_violations", methods=["POST"])
    @login_required
    @role_or_permission_required('discipline_officer', 'manage_discipline')
    def process_bulk_violations():
        """
        Process bulk violation import from either:
        - Manual form entry (JSON array from frontend)
        - Excel file upload
        """
        try:
            # Check source type
            excel_file = request.files.get('excel_file')
            manual_data = request.form.get('manual_violations_json')
        
            violations_to_import = []
        
            if excel_file and excel_file.filename:
                # Process Excel file
                violations_to_import = parse_excel_file(excel_file)
            elif manual_data:
                # Process manual JSON data
                violations_to_import = json.loads(manual_data)
            
                # Convert date strings to datetime objects
                for v in violations_to_import:
                    if isinstance(v['date_committed'], str):
                        v['date_committed'] = datetime.datetime.strptime(v['date_committed'], '%Y-%m-%dT%H:%M')
                    if 'week_number' not in v or v['week_number'] is None:
                        v['week_number'] = calculate_week_from_date(v['date_committed'])
            else:
                return jsonify({"status": "error", "message": "Không có dữ liệu để import"}), 400
        
            # Validate & Import
            errors, success_count = import_violations_to_db(violations_to_import)
        
            if errors:
                return jsonify({
                    "status": "partial" if success_count > 0 else "error",
                    "errors": errors,
                    "success": success_count,
                    "message": f"Đã import {success_count} vi phạm. Có {len(errors)} lỗi."
                })
        
            return jsonify({
                "status": "success",
                "count": success_count,
                "message": f"✅ Đã import thành công {success_count} vi phạm!"
            })
        
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/download_violation_template")
    @login_required
    @permission_required('view_discipline')
    def download_violation_template():
        """Generate and download Excel template"""
        # Create sample template
        df = pd.DataFrame({
            'Mã học sinh': ['12TIN-001', '12TIN-002', '11A1-005'],
            'Loại vi phạm': ['Đi trễ', 'Không mặc đồng phục', 'Thiếu học liệu'],
            'Điểm trừ': [5, 10, 3],
            'Ngày vi phạm': ['2024-01-15 08:30', '2024-01-16 07:45', '2024-01-20 14:00'],
            'Tuần': [3, 3, 4]
        })
    
        # Save to BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Violations')
    
        output.seek(0)
    
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='template_import_violations.xlsx'
        )


    @app.route("/upload_ocr", methods=["POST"])
    @login_required
    @role_or_permission_required('discipline_officer', 'manage_discipline')
    def upload_ocr():
        """⚡ Đọc CHỈ MÃ HỌC SINH từ thẻ và tìm trực tiếp trong CSDL."""
        uploaded_files = request.files.getlist("files[]")
        if not uploaded_files: 
            return jsonify({"error": "Chưa chọn file."})

        results = []
    
        # ⚡ PROMPT NÂNG CẤP - Đọc mã học sinh với nhiều biến thể
        prompt = """
        Hãy đọc MÃ HỌC SINH từ thẻ trong ảnh này.
    
        Mã học sinh có thể có các dạng:
        - 12TIN-001, 11A1-005, 10B-023
        - 34 TOAN - 001035 hoặc 34 TOÁN - 001035 (có thể có hoặc không có dấu tiếng Việt)
        - Có thể có hoặc không có khoảng trắng
        - HS123, SV2024001
    
        Trả về JSON với format:
        {
            "student_code": "mã số học sinh"
        }
    
        Lưu ý QUAN TRỌNG:
        - CHỈ trích xuất mã số học sinh, KHÔNG cần tên hoặc lớp
        - Đọc CHÍNH XÁC những gì thấy trên thẻ, GIỮ NGUYÊN format (có dấu thì giữ dấu, có space thì giữ space)
        - Nếu không đọc được mã số, trả về chuỗi rỗng ""
        """

        for f in uploaded_files:
            if f.filename == '': 
                continue
            
            p = os.path.join(UPLOAD_FOLDER, f.filename)
            f.save(p)
        
            # Gọi AI Vision để đọc mã
            data, error = _call_gemini(prompt, image_path=p, is_json=True)
        
            # Xóa file tạm
            if os.path.exists(p): 
                os.remove(p)

            if data:
                # Lấy mã học sinh từ response (GIỮ NGUYÊN format gốc)
                ocr_code_raw = str(data.get("student_code", "")).strip()
            
                if ocr_code_raw:
                    # ⚡ TÌM KIẾM 2 LẦN: Exact match → Normalized match
                    student = None
                    match_method = ""
                
                    # Lần 1: Thử exact match (uppercase)
                    student = Student.query.filter_by(student_code=ocr_code_raw.upper()).first()
                    if student:
                        match_method = "Exact match (uppercase)"
                
                    # Lần 2: Nếu không tìm thấy, thử normalized match
                    if not student:
                        ocr_code_normalized = normalize_student_code(ocr_code_raw)
                        all_students = Student.query.all()
                    
                        for s in all_students:
                            if normalize_student_code(s.student_code) == ocr_code_normalized:
                                student = s
                                match_method = f"Normalized match (chuẩn hóa: '{ocr_code_normalized}')"
                                break
                
                    if student:
                        # ✅ Tìm thấy học sinh
                        item = {
                            "file_name": f.filename,
                            "ocr_data": {
                                "code": ocr_code_raw,
                                "normalized": normalize_student_code(ocr_code_raw)
                            },
                            "found": True,
                            "confidence": 100 if "Exact" in match_method else 95,
                            "match_reasons": [match_method],
                            "db_info": {
                                "name": student.name,
                                "code": student.student_code,
                                "class": student.student_class
                            },
                            "alternatives": []
                        }
                    else:
                        # ❌ Không tìm thấy trong CSDL
                        item = {
                            "file_name": f.filename,
                            "ocr_data": {
                                "code": ocr_code_raw,
                                "normalized": normalize_student_code(ocr_code_raw)
                            },
                            "found": False,
                            "db_info": None,
                            "error": f"Không tìm thấy học sinh có mã '{ocr_code_raw}' (hoặc '{normalize_student_code(ocr_code_raw)}') trong hệ thống"
                        }
                else:
                    # AI không đọc được mã
                    item = {
                        "file_name": f.filename,
                        "ocr_data": {
                            "code": ""
                        },
                        "found": False,
                        "db_info": None,
                        "error": "AI không nhận diện được mã học sinh trên thẻ"
                    }
            
                results.append(item)
            else:
                # Lỗi gọi AI
                results.append({
                    "file_name": f.filename, 
                    "error": error or "Không đọc được thông tin từ thẻ"
                })

        return jsonify({"results": results})

    @app.route("/batch_violation", methods=["POST"])
    def batch_violation(): return redirect(url_for('add_violation'))
    @app.route("/student/<int:student_id>/violations_timeline")
    @login_required
    @permission_required('view_discipline')
    def violations_timeline(student_id):
        """Timeline lịch sử vi phạm của học sinh"""
        student = db.session.get(Student, student_id)
        if not student:
            flash("Không tìm thấy học sinh!", "error")
            return redirect(url_for("manage_students"))
    
        violations = Violation.query.filter_by(student_id=student_id)\
            .order_by(Violation.date_committed.desc()).all()
    
        violations_by_week = db.session.query(
            Violation.week_number,
            func.count(Violation.id).label('count'),
            func.sum(Violation.points_deducted).label('total_deducted')
        ).filter(Violation.student_id == student_id)\
        .group_by(Violation.week_number)\
        .order_by(Violation.week_number).all()
    
        violations_by_type = db.session.query(
            Violation.violation_type_name,
            func.count(Violation.id).label('count')
        ).filter(Violation.student_id == student_id)\
        .group_by(Violation.violation_type_name)\
        .order_by(desc('count')).all()
    
        week_labels = [w[0] for w in violations_by_week]
        week_counts = [w[1] for w in violations_by_week]
        type_labels = [t[0] for t in violations_by_type]
        type_counts = [t[1] for t in violations_by_type]
    
        return render_template(
            "violations_timeline.html",
            student=student,
            violations=violations,
            violations_by_week=violations_by_week,
            violations_by_type=violations_by_type,
            week_labels=week_labels,
        week_counts=week_counts,
            type_labels=type_labels,
            type_counts=type_counts
        )
    @app.route("/delete_violation/<int:violation_id>", methods=["POST"])
    @login_required
    @role_or_permission_required('discipline_officer', 'manage_discipline')
    def delete_violation(violation_id):
        try:
            # 1. Tìm bản ghi vi phạm
            violation = Violation.query.get_or_404(violation_id)
            student = Student.query.get(violation.student_id)
        
            # 2. KHÔI PHỤC ĐIỂM SỐ
            # Cộng trả lại điểm đã trừ
            if student:
                old_score = student.current_score
                student.current_score += violation.points_deducted
                # Đảm bảo điểm không vượt quá 100 (nếu quy chế là max 100)
                if student.current_score > 100:
                    student.current_score = 100
                log_change('violation_delete', f'Xóa vi phạm: {violation.violation_type_name} (hoàn +{violation.points_deducted} điểm)', student_id=student.id, student_name=student.name, student_class=student.student_class, old_value=old_score, new_value=student.current_score)
        
            # 3. Xóa vi phạm
            db.session.delete(violation)
            db.session.commit()
        
            # 4. CẬP NHẬT HẠNH KIỂM
            if student:
                update_student_conduct(student.id)
                
            flash(f"Đã xóa vi phạm và khôi phục {violation.points_deducted} điểm cho học sinh.", "success")
        
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi khi xóa: {str(e)}", "error")
        
        # Quay lại trang Timeline của học sinh đó
        return redirect(url_for('violations_timeline', student_id=student.id if student else 0))

    @app.route("/discipline_management", methods=["GET"])
    @login_required
    def discipline_management():
        """Trang quản lý kỷ luật và điểm cộng thống nhất"""
        from routes.lesson_book import lesson_book_visible_query
        
        # Lấy tham số lọc
        selected_week = request.args.get('week', type=int)
        selected_class = request.args.get('class_select', '')
        
        # Dữ liệu cho tab Quản lý quy định
        rules = ViolationType.query.order_by(ViolationType.points_deducted.desc()).all()
        bonus_types = BonusType.query.order_by(BonusType.points_added.desc()).all()
        
        # Dữ liệu cho tab Ghi nhận
        students = get_accessible_students().order_by(Student.student_class, Student.name).all()
        lesson_entries = (
            lesson_book_visible_query()
            .order_by(desc(LessonBookEntry.lesson_date), desc(LessonBookEntry.id))
            .limit(120)
            .all()
        )
        
        # Dữ liệu cho tab Lịch sử
        weeks = db.session.query(Violation.week_number).distinct().order_by(Violation.week_number.desc()).all()
        weeks = [w[0] for w in weeks if w[0]]
        all_classes = db.session.query(Student.student_class).distinct().order_by(Student.student_class).all()
        all_classes = [c[0] for c in all_classes if c[0]]
        
        # Mặc định chọn tuần hiện tại nếu chưa chọn
        if not selected_week and weeks:
            selected_week = weeks[0]
        
        # Lấy dữ liệu vi phạm theo tuần và lớp
        violations = None
        if selected_week:
            query = Violation.query.filter_by(week_number=selected_week)
            if selected_class:
                query = query.join(Student).filter(Student.student_class == selected_class)
            violations = query.order_by(Violation.date_committed.desc()).paginate(
                page=request.args.get('page', 1, type=int),
                per_page=20,
                error_out=False
            )
        
        return render_template(
            "discipline_management.html",
            rules=rules,
            bonus_types=bonus_types,
            students=students,
            lesson_entries=lesson_entries,
            weeks=weeks,
            all_classes=all_classes,
            selected_week=selected_week,
            selected_class=selected_class,
            violations=violations
        )
