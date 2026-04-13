"""Routes: rules_bonus."""
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
    parse_excel_file, import_violations_to_db, calculate_week_from_date, _call_gemini,
    save_weekly_archive, get_current_iso_week, create_notification, log_change,
    UPLOAD_FOLDER, calculate_student_gpa, is_reset_needed, update_student_conduct,
)


def register(app):
    @app.route("/manage_rules", methods=["GET", "POST"])
    @login_required
    def manage_rules():
        """Quản lý các loại lỗi vi phạm"""
        if request.method == "POST":
            name = request.form.get("rule_name", "").strip()
            try:
                points = int(request.form.get("points", 0))
            except ValueError:
                points = 0
            
            if name and points > 0:
                existing = ViolationType.query.filter_by(name=name).first()
                if not existing:
                    new_rule = ViolationType(name=name, points_deducted=points)
                    db.session.add(new_rule)
                    db.session.commit()
                    flash(f"Đã thêm lỗi vi phạm: {name}", "success")
                else:
                    flash("Tên lỗi vi phạm này đã tồn tại!", "error")
            else:
                flash("Vui lòng nhập tên và điểm trừ hợp lệ!", "error")
            return redirect(url_for("manage_rules"))
    
        rules = ViolationType.query.order_by(ViolationType.points_deducted.desc()).all()
        return render_template("manage_rules.html", rules=rules)

    @app.route("/edit_rule/<int:rule_id>", methods=["GET", "POST"])
    @login_required
    def edit_rule(rule_id):
        """Sửa lỗi vi phạm"""
        rule = db.session.get(ViolationType, rule_id)
        if not rule:
            flash("Không tìm thấy lỗi vi phạm!", "error")
            return redirect(url_for("manage_rules"))
    
        if request.method == "POST":
            name = request.form.get("rule_name", "").strip()
            try:
                points = int(request.form.get("points", 0))
            except ValueError:
                points = 0
            
            if name and points > 0:
                rule.name = name
                rule.points_deducted = points
                db.session.commit()
                flash("Cập nhật thành công!", "success")
                return redirect(url_for("manage_rules"))
            else:
                flash("Dữ liệu không hợp lệ!", "error")
            
        return render_template("edit_rule.html", rule=rule)

    @app.route("/delete_rule/<int:rule_id>", methods=["POST"])
    @login_required
    def delete_rule(rule_id):
        """Xóa lỗi vi phạm"""
        rule = db.session.get(ViolationType, rule_id)
        if rule:
            db.session.delete(rule)
            db.session.commit()
            flash(f"Đã xóa lỗi: {rule.name}", "success")
        else:
            flash("Không tìm thấy lỗi cần xóa!", "error")
        return redirect(url_for("manage_rules"))

    # === BONUS POINTS ROUTES ===

    @app.route("/manage_bonus_types", methods=["GET", "POST"])
    @login_required
    def manage_bonus_types():
        """Quản lý loại điểm cộng"""
        if request.method == "POST":
            name = request.form.get("bonus_name", "").strip()
            points = int(request.form.get("points", 0))
            description = request.form.get("description", "").strip()
        
            if name and points > 0:
                if not BonusType.query.filter_by(name=name).first():
                    db.session.add(BonusType(name=name, points_added=points, description=description or None))
                    db.session.commit()
                    flash("Đã thêm loại điểm cộng mới!", "success")
                else:
                    flash("Loại điểm cộng này đã tồn tại!", "error")
            else:
                flash("Vui lòng nhập đầy đủ thông tin!", "error")
            return redirect(url_for("manage_bonus_types"))
    
        bonus_types = BonusType.query.order_by(BonusType.points_added.desc()).all()
        return render_template("manage_bonus_types.html", bonus_types=bonus_types)


    @app.route("/edit_bonus_type/<int:bonus_id>", methods=["GET", "POST"])
    @login_required
    def edit_bonus_type(bonus_id):
        """Sửa loại điểm cộng"""
        bonus = db.session.get(BonusType, bonus_id)
        if not bonus:
            flash("Không tìm thấy loại điểm cộng!", "error")
            return redirect(url_for("manage_bonus_types"))
    
        if request.method == "POST":
            bonus.name = request.form.get("bonus_name", "").strip()
            bonus.points_added = int(request.form.get("points", 0))
            bonus.description = request.form.get("description", "").strip() or None
            db.session.commit()
            flash("Đã cập nhật loại điểm cộng!", "success")
            return redirect(url_for("manage_bonus_types"))
    
        return render_template("edit_bonus_type.html", bonus=bonus)


    @app.route("/delete_bonus_type/<int:bonus_id>", methods=["POST"])
    @login_required
    def delete_bonus_type(bonus_id):
        """Xóa loại điểm cộng"""
        bonus = db.session.get(BonusType, bonus_id)
        if bonus:
            db.session.delete(bonus)
            db.session.commit()
            flash("Đã xóa loại điểm cộng!", "success")
        return redirect(url_for("manage_bonus_types"))


    @app.route("/add_bonus", methods=["GET", "POST"])
    @login_required
    def add_bonus():
        """Thêm điểm cộng cho học sinh"""
        if request.method == "POST":
            selected_student_ids = request.form.getlist("student_ids[]")
            selected_bonus_ids = request.form.getlist("bonus_ids[]")
            reason = request.form.get("reason", "").strip()
        
            if not selected_student_ids:
                flash("Vui lòng chọn ít nhất một học sinh!", "error")
                return redirect(url_for("discipline_management"))
        
            if not selected_bonus_ids:
                flash("Vui lòng chọn ít nhất một loại điểm cộng!", "error")
                return redirect(url_for("discipline_management"))
        
            # Lấy tuần hiện tại
            w_cfg = SystemConfig.query.filter_by(key="current_week").first()
            current_week = int(w_cfg.value) if w_cfg else 1
        
            count = 0
            for bonus_id in selected_bonus_ids:
                bonus_type = db.session.get(BonusType, int(bonus_id))
                if not bonus_type:
                    continue
            
                for s_id in selected_student_ids:
                    student = db.session.get(Student, int(s_id))
                    if student:
                        # Cộng điểm
                        old_score = student.current_score or 100
                        student.current_score = old_score + bonus_type.points_added
                    
                        # Lưu lịch sử
                        db.session.add(BonusRecord(
                            student_id=student.id,
                            bonus_type_name=bonus_type.name,
                            points_added=bonus_type.points_added,
                            reason=reason or None,
                            week_number=current_week
                        ))
                        log_change('bonus', f'Điểm cộng: {bonus_type.name} (+{bonus_type.points_added} điểm){" - " + reason if reason else ""}', student_id=student.id, student_name=student.name, student_class=student.student_class, old_value=old_score, new_value=student.current_score)
                        count += 1
                        # Cập nhật hạnh kiểm
                        update_student_conduct(student.id)
        
            if count > 0:
                db.session.commit()
                flash(f"Đã ghi nhận điểm cộng cho {len(selected_student_ids)} học sinh x {len(selected_bonus_ids)} loại!", "success")
            else:
                flash("Có lỗi xảy ra, không ghi nhận được điểm cộng!", "error")

            return redirect(url_for("discipline_management"))
    
        # GET: Render form (filtered by role)
        students = get_accessible_students().order_by(Student.student_class, Student.name).all()
        bonus_types = BonusType.query.order_by(BonusType.points_added.desc()).all()
        return render_template("add_bonus.html", students=students, bonus_types=bonus_types)
