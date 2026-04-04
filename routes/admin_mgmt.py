"""Routes: admin_mgmt."""
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
    GroupChatMessage, PrivateMessage, ChangeLog, ConductSetting,
)
from app_helpers import (
    admin_required, get_accessible_students, can_access_student, normalize_student_code,
    parse_excel_file, import_violations_to_db, calculate_week_from_date, _call_gemini,
    save_weekly_archive, get_current_iso_week, create_notification, log_change,
    UPLOAD_FOLDER, calculate_student_gpa, is_reset_needed, update_student_conduct,
    update_student_academic_status,
)


def register(app):
    @app.route("/admin/settings", methods=["GET", "POST"])
    @admin_required
    def manage_settings():
        if request.method == "POST":
            config_keys = ["school_name", "current_week", "school_year", "current_semester"]
            for key in config_keys:
                val = request.form.get(key)
                if val is not None:
                    config = SystemConfig.query.filter_by(key=key).first()
                    if not config:
                        config = SystemConfig(key=key, value=val)
                        db.session.add(config)
                    else:
                        config.value = val
            
            # --- Cập nhật ConductSetting (BGH) ---
            conduct_settings = ConductSetting.query.first()
            if not conduct_settings:
                conduct_settings = ConductSetting()
                db.session.add(conduct_settings)
            
            try:
                conduct_settings.good_threshold = int(request.form.get("good_threshold", 80))
                conduct_settings.fair_threshold = int(request.form.get("fair_threshold", 65))
                conduct_settings.average_threshold = int(request.form.get("average_threshold", 50))
                conduct_settings.warning_yellow_threshold = int(request.form.get("warning_yellow_threshold", 70))
                conduct_settings.warning_red_threshold = int(request.form.get("warning_red_threshold", 55))
                # Học lực (academic)
                conduct_settings.academic_yellow_threshold = float(request.form.get("academic_yellow_threshold", 6.5))
                conduct_settings.academic_red_threshold = float(request.form.get("academic_red_threshold", 5.0))
            except (ValueError, TypeError):
                pass
            
            db.session.commit()
            
            # Cập nhật lại toàn bộ học sinh khi đổi cấu hình
            for s in Student.query.all():
                update_student_conduct(s.id)
                update_student_academic_status(s.id)
            flash("Cập nhật cài đặt hệ thống thành công!", "success")
            return redirect(url_for("manage_settings"))
    
        # Lấy tất cả config hiện có
        configs = {c.key: c.value for c in SystemConfig.query.all()}
    
        # Đảm bảo các key mặc định có giá trị hiển thị nếu chưa lưu trong DB
        if "school_name" not in configs: configs["school_name"] = "THPT Chuyên Nguyễn Tất Thành"
        if "current_week" not in configs: configs["current_week"] = "1"
        if "school_year" not in configs: configs["school_year"] = "2025-2026"
        if "current_semester" not in configs: configs["current_semester"] = "1"
    
        # Lấy conduct settings
        conduct_settings = ConductSetting.query.first()
        if not conduct_settings:
            conduct_settings = ConductSetting()
            db.session.add(conduct_settings)
            db.session.commit()
            
        return render_template("manage_settings.html", configs=configs, conduct_settings=conduct_settings)


    @app.route("/admin/reset_week", methods=["POST"])
    @login_required
    def reset_week():
        try:
            # 1. Lấy tuần hiển thị hiện tại
            week_cfg = SystemConfig.query.filter_by(key="current_week").first()
            current_week_num = int(week_cfg.value) if week_cfg else 1
        
            # 2. Lưu trữ dữ liệu tuần cũ
            save_weekly_archive(current_week_num)
        
            # 3. Reset điểm toàn bộ học sinh về 100
            db.session.query(Student).update({Student.current_score: 100})
        
            # 4. Tăng số tuần hiển thị lên 1
            if week_cfg:
                week_cfg.value = str(current_week_num + 1)
            
            # 5. Cập nhật "Dấu vết" tuần ISO để tắt cảnh báo
            current_iso = get_current_iso_week()
            last_reset_cfg = SystemConfig.query.filter_by(key="last_reset_week_id").first()
            if not last_reset_cfg:
                db.session.add(SystemConfig(key="last_reset_week_id", value=current_iso))
            else:
                last_reset_cfg.value = current_iso
            
            db.session.commit()
            
            # 6. Cập nhật hạnh kiểm & học lực cho toàn bộ học sinh sau khi reset điểm
            for s in Student.query.all():
                update_student_conduct(s.id)
                update_student_academic_status(s.id)
                
            flash(f"Đã kết thúc Tuần {current_week_num}. Hệ thống chuyển sang Tuần {current_week_num + 1}.", "success")
        
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi: {str(e)}", "error")
        
        return redirect(url_for("dashboard"))
    @app.route("/admin/update_week", methods=["POST"])
    def update_week():
        c = SystemConfig.query.filter_by(key="current_week").first()
        if c: c.value = str(request.form["new_week"]); db.session.commit()
        return redirect(url_for("dashboard"))
    @app.route("/admin/fix_scores")
    @login_required
    def fix_scores():
        """Hàm này giúp tính lại điểm cho toàn bộ học sinh dựa trên lỗi vi phạm"""
        try:
            # 1. Lấy danh sách tất cả học sinh
            students = Student.query.all()
            count = 0
        
            for s in students:
                # 2. Tìm tất cả lỗi vi phạm của học sinh này trong DB
                violations = Violation.query.filter_by(student_id=s.id).all()
            
                # 3. Cộng tổng điểm phạt
                total_deducted = sum(v.points_deducted for v in violations)
            
                # 4. Reset điểm về 100 rồi trừ đi tổng lỗi
                s.current_score = 100 - total_deducted
            
                count += 1
            
            # 5. Lưu tất cả thay đổi vào Database
            db.session.commit()
        
            flash(f"Đã sửa điểm thành công cho {count} học sinh!", "success")
            return redirect(url_for('index'))
        
        except Exception as e:
            db.session.rollback()
            return f"Có lỗi xảy ra: {str(e)}"   
    @app.route("/admin/teachers")
    @admin_required
    def manage_teachers():
        """Danh sách giáo viên - Chỉ Admin"""
        teachers = Teacher.query.filter(Teacher.id != current_user.id).order_by(Teacher.created_at.desc()).all()
        subjects = Subject.query.order_by(Subject.name).all()
        classes = ClassRoom.query.order_by(ClassRoom.name).all()
        return render_template("manage_teachers.html", teachers=teachers, subjects=subjects, classes=classes)


    @app.route("/admin/teachers/add", methods=["GET", "POST"])
    @admin_required
    def add_teacher():
        """Thêm giáo viên mới - Chỉ Admin"""
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            full_name = request.form.get("full_name", "").strip()
            role = request.form.get("role", "homeroom_teacher")
            assigned_class = request.form.get("assigned_class", "").strip() or None
            assigned_subject_id = request.form.get("assigned_subject_id") or None
        
            # Validation
            if not username or not password or not full_name:
                flash("Vui lòng điền đầy đủ thông tin!", "error")
                return redirect(url_for("add_teacher"))
        
            # Check username exists
            if Teacher.query.filter_by(username=username).first():
                flash(f"Username '{username}' đã tồn tại!", "error")
                return redirect(url_for("add_teacher"))
        
            # Create new teacher
            new_teacher = Teacher(
                username=username,
                full_name=full_name,
                role=role,
                assigned_class=assigned_class if role == "homeroom_teacher" else None,
                assigned_subject_id=int(assigned_subject_id) if role == "subject_teacher" and assigned_subject_id else None,
                created_by=current_user.id
            )
            new_teacher.set_password(password)

        
            try:
                db.session.add(new_teacher)
                db.session.commit()
                flash(f"Đã tạo tài khoản '{full_name}' thành công!", "success")
                return redirect(url_for("manage_teachers"))
            except Exception as e:
                db.session.rollback()
                flash(f"Lỗi tạo tài khoản: {str(e)}", "error")
                return redirect(url_for("add_teacher"))
    
        # GET: Render form
        subjects = Subject.query.order_by(Subject.name).all()
        classes = ClassRoom.query.order_by(ClassRoom.name).all()
        return render_template("add_teacher.html", subjects=subjects, classes=classes)


    @app.route("/admin/teachers/<int:teacher_id>/edit", methods=["GET", "POST"])
    @admin_required
    def edit_teacher(teacher_id):
        """Sửa thông tin giáo viên - Chỉ Admin"""
        teacher = Teacher.query.get_or_404(teacher_id)
    
        # Không cho sửa chính mình
        if teacher.id == current_user.id:
            flash("Không thể sửa tài khoản của chính mình!", "error")
            return redirect(url_for("manage_teachers"))
    
        if request.method == "POST":
            teacher.full_name = request.form.get("full_name", "").strip() or teacher.full_name
            teacher.role = request.form.get("role", teacher.role)
        
            new_password = request.form.get("password", "").strip()
            if new_password:
                teacher.set_password(new_password)
        
            if teacher.role == "homeroom_teacher":
                teacher.assigned_class = request.form.get("assigned_class", "").strip() or None
                teacher.assigned_subject_id = None
            elif teacher.role == "subject_teacher":
                teacher.assigned_subject_id = request.form.get("assigned_subject_id") or None
                if teacher.assigned_subject_id:
                    teacher.assigned_subject_id = int(teacher.assigned_subject_id)
                teacher.assigned_class = None
            else:  # admin
                teacher.assigned_class = None
                teacher.assigned_subject_id = None
        
            try:
                db.session.commit()
                flash(f"Đã cập nhật thông tin '{teacher.full_name}'!", "success")
                return redirect(url_for("manage_teachers"))
            except Exception as e:
                db.session.rollback()
                flash(f"Lỗi cập nhật: {str(e)}", "error")
    
        # GET: Render form
        subjects = Subject.query.order_by(Subject.name).all()
        classes = ClassRoom.query.order_by(ClassRoom.name).all()
        return render_template("edit_teacher.html", teacher=teacher, subjects=subjects, classes=classes)


    @app.route("/admin/teachers/<int:teacher_id>/delete", methods=["POST"])
    @admin_required
    def delete_teacher(teacher_id):
        """Xóa giáo viên - Chỉ Admin"""
        teacher = Teacher.query.get_or_404(teacher_id)
    
        # Không cho xóa chính mình
        if teacher.id == current_user.id:
            flash("Không thể xóa tài khoản của chính mình!", "error")
            return redirect(url_for("manage_teachers"))
    
        # Không cho xóa admin khác
        if teacher.role == "admin":
            flash("Không thể xóa tài khoản Admin!", "error")
            return redirect(url_for("manage_teachers"))
    
        try:
            name = teacher.full_name
        
            # Xóa tất cả tin nhắn group chat của giáo viên này
            GroupChatMessage.query.filter_by(sender_id=teacher_id).delete()
        
            # Xóa tất cả tin nhắn riêng của giáo viên này (cả gửi và nhận)
            PrivateMessage.query.filter(
                or_(
                    PrivateMessage.sender_id == teacher_id,
                    PrivateMessage.receiver_id == teacher_id
                )
            ).delete()
        
            # Xóa tất cả thông báo liên quan
            Notification.query.filter(
                or_(
                    Notification.created_by == teacher_id,
                    Notification.recipient_id == teacher_id
                )
            ).delete()
        
            # Cuối cùng xóa tài khoản giáo viên
            db.session.delete(teacher)
            db.session.commit()
            flash(f"Đã xóa tài khoản '{name}'!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi xóa tài khoản: {str(e)}", "error")
    
        return redirect(url_for("manage_teachers"))


    # === NOTIFICATION ROUTES ===

    @app.route("/admin/send_notification", methods=["GET", "POST"])
    @admin_required
    def send_notification():
        """Admin gửi thông báo chung"""
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            message = request.form.get("message", "").strip()
            target_role = request.form.get("target_role", "all")
        
            if not title or not message:
                flash("Vui lòng điền đầy đủ thông tin!", "error")
                return redirect(url_for("send_notification"))
        
            try:
                create_notification(title, message, 'announcement', target_role)
                flash("Đã gửi thông báo thành công!", "success")
            except Exception as e:
                flash(f"Lỗi gửi thông báo: {str(e)}", "error")
        
            return redirect(url_for("send_notification"))
    
        return render_template("send_notification.html")
