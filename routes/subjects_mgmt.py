"""Routes: subjects_mgmt."""
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
    UPLOAD_FOLDER, calculate_student_gpa, is_reset_needed,
)


def register(app):
    @app.route("/manage_subjects", methods=["GET", "POST"])
    @login_required
    def manage_subjects():
        """Quản lý danh sách môn học"""
        if request.method == "POST":
            name = request.form.get("subject_name", "").strip()
            code = request.form.get("subject_code", "").strip().upper()
            description = request.form.get("description", "").strip()
            num_tx = int(request.form.get("num_tx_columns", 3))
            num_gk = int(request.form.get("num_gk_columns", 1))
            num_hk = int(request.form.get("num_hk_columns", 1))
            is_pass_fail = request.form.get("is_pass_fail") == "on"
        
            if not name or not code:
                flash("Vui lòng nhập tên và mã môn học!", "error")
                return redirect(url_for("manage_subjects"))
        
            if Subject.query.filter_by(code=code).first():
                flash("Mã môn học đã tồn tại!", "error")
                return redirect(url_for("manage_subjects"))
        
            subject = Subject(
                name=name,
                code=code,
                description=description,
                num_tx_columns=num_tx,
                num_gk_columns=num_gk,
                num_hk_columns=num_hk,
                is_pass_fail=is_pass_fail
            )
            db.session.add(subject)
            db.session.commit()
            flash(f"Đã thêm môn {name}", "success")
            return redirect(url_for("manage_subjects"))
    
        subjects = Subject.query.order_by(Subject.name).all()
        return render_template("manage_subjects.html", subjects=subjects)

    @app.route("/edit_subject/<int:subject_id>", methods=["GET", "POST"])
    @login_required
    def edit_subject(subject_id):
        """Sửa thông tin môn học"""
        subject = db.session.get(Subject, subject_id)
        if not subject:
            flash("Không tìm thấy môn học!", "error")
            return redirect(url_for("manage_subjects"))
    
        if request.method == "POST":
            subject.name = request.form.get("subject_name", "").strip()
            subject.code = request.form.get("subject_code", "").strip().upper()
            subject.description = request.form.get("description", "").strip()
            subject.num_tx_columns = int(request.form.get("num_tx_columns", 3))
            subject.num_gk_columns = int(request.form.get("num_gk_columns", 1))
            subject.num_hk_columns = int(request.form.get("num_hk_columns", 1))
            subject.is_pass_fail = request.form.get("is_pass_fail") == "on"

            db.session.commit()
            flash("Đã cập nhật môn học!", "success")
            return redirect(url_for("manage_subjects"))
    
        return render_template("edit_subject.html", subject=subject)

    @app.route("/delete_subject/<int:subject_id>", methods=["POST"])
    @login_required
    def delete_subject(subject_id):
        """Xóa môn học"""
        subject = db.session.get(Subject, subject_id)
        if subject:
            db.session.delete(subject)
            db.session.commit()
            flash("Đã xóa môn học!", "success")
        return redirect(url_for("manage_subjects"))
