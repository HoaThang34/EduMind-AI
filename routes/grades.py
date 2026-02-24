from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Student, Grade, Subject, SystemConfig, Violation, db
from sqlalchemy import or_, desc
import datetime

grades_bp = Blueprint('grades', __name__)

@grades_bp.route("/manage_grades")
@login_required
def manage_grades():
    from app import admin_required, can_access_student, get_accessible_students, log_change, can_access_subject, create_notification, calculate_student_gpa
    """Danh sách học sinh để chọn nhập điểm"""
    search = request.args.get('search', '').strip()
    selected_class = request.args.get('class_select', '').strip()
    
    q = get_accessible_students()  # Filter by role
    if selected_class:
        q = q.filter_by(student_class=selected_class)
    if search:
        q = q.filter(or_(
            Student.name.ilike(f"%{search}%"),
            Student.student_code.ilike(f"%{search}%")
        ))
    
    students = q.order_by(Student.student_code.asc()).all()
    return render_template("manage_grades.html", students=students, search_query=search, selected_class=selected_class)



@grades_bp.route("/student_grades/<int:student_id>", methods=["GET", "POST"])
@login_required
def student_grades(student_id):
    from app import admin_required, can_access_student, get_accessible_students, log_change, can_access_subject, create_notification, calculate_student_gpa
    """Xem và nhập điểm cho học sinh"""
    # Kiểm tra quyền truy cập học sinh
    if not can_access_student(student_id):
        flash("Bạn không có quyền xem học sinh này!", "error")
        return redirect(url_for('dashboard'))
    
    student = db.session.get(Student, student_id)
    if not student:
        flash("Không tìm thấy học sinh!", "error")
        return redirect(url_for("grades.manage_grades"))
    
    if request.method == "POST":
        # Lấy cấu hình mặc định
        configs = {c.key: c.value for c in SystemConfig.query.all()}
        default_year = configs.get("school_year", "2025-2026")
        default_semester = int(configs.get("current_semester", "1"))

        subject_id = request.form.get("subject_id")
        grade_type = request.form.get("grade_type")
        column_index = int(request.form.get("column_index", 1))
        score = request.form.get("score")
        semester = int(request.form.get("semester", default_semester))
        school_year = request.form.get("school_year", default_year)
        
        if not all([subject_id, grade_type, score]):
            flash("Vui lòng điền đầy đủ thông tin!", "error")
            return redirect(url_for("grades.student_grades", student_id=student_id))
        
        # Kiểm tra quyền sửa môn học
        if not can_access_subject(int(subject_id)):
            flash("Bạn không có quyền sửa điểm môn này!", "error")
            return redirect(url_for("grades.student_grades", student_id=student_id))
        
        try:
            score_float = float(score)
            if score_float < 0 or score_float > 10:
                flash("Điểm phải từ 0 đến 10!", "error")
                return redirect(url_for("grades.student_grades", student_id=student_id))
        except ValueError:
            flash("Điểm không hợp lệ!", "error")
            return redirect(url_for("grades.student_grades", student_id=student_id))
        
        existing = Grade.query.filter_by(
            student_id=student_id,
            subject_id=subject_id,
            grade_type=grade_type,
            column_index=column_index,
            semester=semester,
            school_year=school_year
        ).first()
        
        subject_obj = db.session.get(Subject, int(subject_id))
        subject_name = subject_obj.name if subject_obj else 'N/A'
        
        if existing:
            old_score_val = existing.score
            existing.score = score_float
            log_change('grade_update', f'Cập nhật điểm {grade_type} môn {subject_name}: {old_score_val} → {score_float}', student_id=student_id, student_name=student.name, student_class=student.student_class, old_value=old_score_val, new_value=score_float)
            flash("Đã cập nhật điểm!", "success")
        else:
            grade = Grade(
                student_id=student_id,
                subject_id=subject_id,
                grade_type=grade_type,
                column_index=column_index,
                score=score_float,
                semester=semester,
                school_year=school_year
            )
            db.session.add(grade)
            log_change('grade', f'Thêm điểm {grade_type} môn {subject_name}: {score_float}', student_id=student_id, student_name=student.name, student_class=student.student_class, new_value=score_float)
            flash("Đã thêm điểm!", "success")
        
        db.session.commit()
        
        # Thông báo cho GVCN lớp
        try:
            if student.student_class:
                subject = db.session.get(Subject, int(subject_id))
                create_notification(
                    title=f"📊 Điểm mới - {student.name}",
                    message=f"{current_user.full_name} đã nhập điểm {subject.name if subject else 'môn học'} cho {student.name} (Lớp {student.student_class})",
                    notification_type='grade',
                    target_role=student.student_class
                )
        except:
            pass  # Không để lỗi notification làm gián đoạn
        
        return redirect(url_for("grades.student_grades", student_id=student_id))
    
    # Lấy cấu hình mặc định cho GET request
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    default_year = configs.get("school_year", "2025-2026")
    default_semester = int(configs.get("current_semester", "1"))

    subjects = Subject.query.order_by(Subject.name).all()
    semester = int(request.args.get('semester', default_semester))
    school_year = request.args.get('school_year', default_year)
    
    grades = Grade.query.filter_by(
        student_id=student_id,
        semester=semester,
        school_year=school_year
    ).all()
    
    grades_by_subject = {}
    for subject in subjects:
        subject_grades = {
            'TX': {},
            'GK': {},
            'HK': {}
        }
        for grade in grades:
            if grade.subject_id == subject.id:
                subject_grades[grade.grade_type][grade.column_index] = grade
        grades_by_subject[subject.id] = subject_grades
    
    # Truyền assigned_subject_id để disable input field trong template
    assigned_subject_id = current_user.assigned_subject_id if current_user.role == 'subject_teacher' else None
    
    return render_template(
        "student_grades.html",
        student=student,
        subjects=subjects,
        grades_by_subject=grades_by_subject,
        semester=semester,
        school_year=school_year,
        assigned_subject_id=assigned_subject_id
    )



@grades_bp.route("/delete_grade/<int:grade_id>", methods=["POST"])
@login_required
def delete_grade(grade_id):
    from app import admin_required, can_access_student, get_accessible_students, log_change, can_access_subject, create_notification, calculate_student_gpa
    """Xóa một điểm"""
    grade = db.session.get(Grade, grade_id)
    if grade:
        student_id = grade.student_id
        student = db.session.get(Student, student_id)
        subject = db.session.get(Subject, grade.subject_id)
        log_change('grade_delete', f'Xóa điểm {grade.grade_type} môn {subject.name if subject else "N/A"}: {grade.score}', student_id=student_id, student_name=student.name if student else None, student_class=student.student_class if student else None, old_value=grade.score)
        db.session.delete(grade)
        db.session.commit()
        flash("Đã xóa điểm!", "success")
        return redirect(url_for("grades.student_grades", student_id=student_id))
    return redirect(url_for("grades.manage_grades"))



@grades_bp.route("/api/update_grade/<int:grade_id>", methods=["POST"])
@login_required
def update_grade_api(grade_id):
    from app import admin_required, can_access_student, get_accessible_students, log_change, can_access_subject, create_notification, calculate_student_gpa
    """API endpoint để cập nhật điểm inline"""
    try:
        data = request.get_json()
        new_score = float(data.get("score", 0))
        
        if new_score < 0 or new_score > 10:
            return jsonify({"success": False, "error": "Điểm phải từ 0 đến 10"}), 400
        
        grade = db.session.get(Grade, grade_id)
        if not grade:
            return jsonify({"success": False, "error": "Không tìm thấy điểm"}), 404
        
        old_score_val = grade.score
        grade.score = new_score
        student = db.session.get(Student, grade.student_id)
        subject = db.session.get(Subject, grade.subject_id)
        log_change('grade_update', f'Cập nhật điểm inline {grade.grade_type} môn {subject.name if subject else "N/A"}: {old_score_val} → {new_score}', student_id=grade.student_id, student_name=student.name if student else None, student_class=student.student_class if student else None, old_value=old_score_val, new_value=new_score)
        db.session.commit()
        
        return jsonify({"success": True, "score": new_score})
    except ValueError:
        return jsonify({"success": False, "error": "Điểm không hợp lệ"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500



@grades_bp.route("/student/<int:student_id>/transcript")
@login_required
def student_transcript(student_id):
    from app import admin_required, can_access_student, get_accessible_students, log_change, can_access_subject, create_notification, calculate_student_gpa
    """Xem bảng điểm tổng hợp (học bạ) của học sinh"""
    # Kiểm tra quyền truy cập học sinh
    if not can_access_student(student_id):
        flash("Bạn không có quyền xem học bạ này!", "error")
        return redirect(url_for('dashboard'))
        
    student = db.session.get(Student, student_id)
    if not student:
        flash("Không tìm thấy học sinh!", "error")
        return redirect(url_for("grades.manage_grades"))
    
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    default_year = configs.get("school_year", "2025-2026")
    default_semester = int(configs.get("current_semester", "1"))

    semester = int(request.args.get('semester', default_semester))
    school_year = request.args.get('school_year', default_year)
    
    subjects = Subject.query.order_by(Subject.name).all()
    
    transcript_data = []
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
        
        avg_score = None
        if tx_scores and gk_scores and hk_scores:
            avg_tx = sum(tx_scores) / len(tx_scores)
            avg_gk = sum(gk_scores) / len(gk_scores)
            avg_hk = sum(hk_scores) / len(hk_scores)
            avg_score = round((avg_tx + avg_gk * 2 + avg_hk * 3) / 6, 2)
        
        transcript_data.append({
            'subject': subject,
            'tx_scores': tx_scores,
            'gk_scores': gk_scores,
            'hk_scores': hk_scores,
            'avg_score': avg_score
        })
    
    valid_averages = [item['avg_score'] for item in transcript_data if item['avg_score'] is not None]
    gpa = round(sum(valid_averages) / len(valid_averages), 2) if valid_averages else None
    
    return render_template(
        "student_transcript.html",
        student=student,
        transcript_data=transcript_data,
        semester=semester,
        school_year=school_year,
        gpa=gpa
    )




@grades_bp.route("/student/<int:student_id>/parent_report")
@login_required
def parent_report(student_id):
    from app import admin_required, can_access_student, get_accessible_students, log_change, can_access_subject, create_notification, calculate_student_gpa
    """Báo cáo tổng hợp cho phụ huynh"""
    # Kiểm tra quyền truy cập học sinh
    if not can_access_student(student_id):
        flash("Bạn không có quyền xem báo cáo này!", "error")
        return redirect(url_for('dashboard'))
        
    student = db.session.get(Student, student_id)
    if not student:
        flash("Không tìm thấy học sinh!", "error")
        return redirect(url_for("grades.manage_grades"))
    
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    default_year = configs.get("school_year", "2025-2026")
    default_semester = int(configs.get("current_semester", "1"))

    semester = int(request.args.get('semester', default_semester))
    school_year = request.args.get('school_year', default_year)
    
    subjects = Subject.query.order_by(Subject.name).all()
    transcript_data = []
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
        
        avg_score = None
        if tx_scores and gk_scores and hk_scores:
            avg_tx = sum(tx_scores) / len(tx_scores)
            avg_gk = sum(gk_scores) / len(gk_scores)
            avg_hk = sum(hk_scores) / len(hk_scores)
            avg_score = round((avg_tx + avg_gk * 2 + avg_hk * 3) / 6, 2)
        
        transcript_data.append({
            'subject': subject,
            'tx_scores': tx_scores,
            'gk_scores': gk_scores,
            'hk_scores': hk_scores,
            'avg_score': avg_score
        })
    
    valid_averages = [item['avg_score'] for item in transcript_data if item['avg_score'] is not None]
    gpa = round(sum(valid_averages) / len(valid_averages), 2) if valid_averages else None
    
    # Bổ sung dữ liệu vi phạm cho báo cáo phụ huynh
    total_violations = Violation.query.filter_by(student_id=student_id).count()
    recent_violations = Violation.query.filter_by(student_id=student_id)\
        .order_by(Violation.date_committed.desc()).limit(5).all()
    
    return render_template(
        "parent_report.html",
        student=student,
        transcript_data=transcript_data,
        semester=semester,
        school_year=school_year,
        gpa=gpa,
        total_violations=total_violations,
        recent_violations=recent_violations,
        now=datetime.datetime.now()
    )
