"""Routes: class_subjects - Quản lý phân công môn học cho từng lớp"""
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Subject, ClassSubject, ClassRoom, Teacher
from app_helpers import admin_required

def register(app):
    @app.route("/manage_class_subjects", methods=["GET", "POST"])
    @login_required
    def manage_class_subjects():
        """Quản lý phân công môn học cho từng lớp"""
        classes = ClassRoom.query.order_by(ClassRoom.name).all()
        subjects = Subject.query.order_by(Subject.name).all()
        school_year = request.args.get("school_year", "2025-2026")
        selected_class = request.args.get("class_name", "")
        
        if request.method == "POST":
            class_name = request.form.get("class_name", "").strip()
            school_year = request.form.get("school_year", "2025-2026").strip()
            
            if not class_name:
                flash("Vui lòng chọn lớp!", "error")
                return redirect(url_for("manage_class_subjects"))
            
            # Xóa tất cả phân công cũ của lớp này trong năm học
            ClassSubject.query.filter_by(
                class_name=class_name,
                school_year=school_year
            ).delete()
            
            # Thêm lại các phân công mới từ checkbox
            for subject in subjects:
                checkbox_name = f"subject_{subject.id}"
                periods_name = f"periods_{subject.id}"
                
                if request.form.get(checkbox_name):
                    periods_per_week = request.form.get(periods_name, type=int, default=3)
                    class_subject = ClassSubject(
                        class_name=class_name,
                        subject_id=subject.id,
                        school_year=school_year,
                        is_compulsory=True,
                        periods_per_week=periods_per_week,
                        created_by=current_user.id if current_user.is_authenticated else None
                    )
                    db.session.add(class_subject)
            
            db.session.commit()
            flash(f"Đã lưu phân công môn học cho lớp {class_name}", "success")
            return redirect(url_for("manage_class_subjects", class_name=class_name, school_year=school_year))
        
        # Lấy danh sách phân công của lớp được chọn
        class_subjects = {}
        if selected_class:
            class_subjects = {cs.subject_id: cs for cs in 
                            ClassSubject.query.filter_by(
                                class_name=selected_class,
                                school_year=school_year
                            ).all()}
        
        return render_template("manage_class_subjects.html",
                             classes=classes,
                             subjects=subjects,
                             class_subjects=class_subjects,
                             school_year=school_year,
                             selected_class=selected_class)

    @app.route("/delete_class_subject/<int:cs_id>", methods=["POST"])
    @login_required
    def delete_class_subject(cs_id):
        """Xóa phân công môn học cho lớp"""
        class_subject = db.session.get(ClassSubject, cs_id)
        if class_subject:
            db.session.delete(class_subject)
            db.session.commit()
            flash("Đã xóa phân công môn học!", "success")
        else:
            flash("Không tìm thấy phân công môn học!", "error")
        return redirect(url_for("manage_class_subjects"))

    @app.route("/api/class_subjects/<class_name>", methods=["GET"])
    @login_required
    def api_class_subjects(class_name):
        """API lấy danh sách môn học của một lớp"""
        school_year = request.args.get("school_year", "2025-2026")
        class_subjects = ClassSubject.query.filter_by(
            class_name=class_name,
            school_year=school_year
        ).all()
        
        subjects_list = []
        for cs in class_subjects:
            subjects_list.append({
                "id": cs.subject.id,
                "name": cs.subject.name,
                "code": cs.subject.code,
                "is_compulsory": cs.is_compulsory,
                "periods_per_week": cs.periods_per_week
            })
        
        return jsonify(subjects_list)

    @app.route("/copy_class_subjects", methods=["POST"])
    @login_required
    def copy_class_subjects():
        """Sao chép phân công môn học từ lớp này sang lớp khác"""
        source_class = request.form.get("source_class", "").strip()
        target_class = request.form.get("target_class", "").strip()
        school_year = request.form.get("school_year", "2025-2026").strip()
        
        if not source_class or not target_class:
            flash("Vui lòng chọn lớp nguồn và lớp đích!", "error")
            return redirect(url_for("manage_class_subjects"))
        
        if source_class == target_class:
            flash("Lớp nguồn và lớp đích phải khác nhau!", "error")
            return redirect(url_for("manage_class_subjects"))
        
        # Xóa phân công cũ của lớp đích
        ClassSubject.query.filter_by(
            class_name=target_class,
            school_year=school_year
        ).delete()
        
        # Sao chép phân công từ lớp nguồn
        source_assignments = ClassSubject.query.filter_by(
            class_name=source_class,
            school_year=school_year
        ).all()
        
        for assignment in source_assignments:
            new_assignment = ClassSubject(
                class_name=target_class,
                subject_id=assignment.subject_id,
                school_year=school_year,
                is_compulsory=assignment.is_compulsory,
                periods_per_week=assignment.periods_per_week,
                created_by=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(new_assignment)
        
        db.session.commit()
        flash(f"Đã sao chép phân công từ lớp {source_class} sang lớp {target_class}", "success")
        return redirect(url_for("manage_class_subjects"))
