"""Sổ đầu bài điện tử — ghi nhận nội dung tiết dạy."""
import datetime
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_, desc

from models import db, LessonBookEntry, Subject, ClassRoom, SystemConfig


def _system_configs():
    return {c.key: c.value for c in SystemConfig.query.all()}


def lesson_book_visible_query():
    """Bản ghi do mình tạo, hoặc (GVCN) lớp chủ nhiệm, hoặc (GVBM) đúng môn phân công; admin xem tất cả."""
    q = LessonBookEntry.query
    if not current_user.is_authenticated:
        return q.filter(LessonBookEntry.id == -1)
    if current_user.role == "admin":
        return q
    conds = [LessonBookEntry.teacher_id == current_user.id]
    if current_user.role == "homeroom_teacher" and current_user.assigned_class:
        conds.append(LessonBookEntry.class_name == current_user.assigned_class)
    if current_user.role == "subject_teacher" and current_user.assigned_subject_id:
        conds.append(LessonBookEntry.subject_id == current_user.assigned_subject_id)
    return q.filter(or_(*conds))


def can_edit_lesson_entry(entry):
    if not current_user.is_authenticated:
        return False
    if current_user.role == "admin":
        return True
    return entry.teacher_id == current_user.id


def can_set_class_for_lesson(class_name):
    if current_user.role == "admin":
        return True
    if current_user.role == "homeroom_teacher":
        return bool(current_user.assigned_class) and class_name == current_user.assigned_class
    if current_user.role == "subject_teacher":
        return True
    return False


def can_set_subject_for_lesson(subject_id):
    if subject_id is None:
        return True
    if current_user.role == "admin":
        return True
    if current_user.role == "homeroom_teacher":
        return True
    if current_user.role == "subject_teacher":
        return current_user.assigned_subject_id == subject_id
    return False


def register(app):
    @app.route("/lesson_book", methods=["GET"])
    @login_required
    def lesson_book():
        q = lesson_book_visible_query()
        class_filter = request.args.get("class_name", "").strip()
        subject_filter = request.args.get("subject_id", type=int)
        date_from = request.args.get("date_from", "").strip()
        date_to = request.args.get("date_to", "").strip()

        if class_filter:
            q = q.filter(LessonBookEntry.class_name == class_filter)
        if subject_filter:
            q = q.filter(LessonBookEntry.subject_id == subject_filter)
        if date_from:
            try:
                d0 = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
                q = q.filter(LessonBookEntry.lesson_date >= d0)
            except ValueError:
                pass
        if date_to:
            try:
                d1 = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
                q = q.filter(LessonBookEntry.lesson_date <= d1)
            except ValueError:
                pass

        entries = q.order_by(desc(LessonBookEntry.lesson_date), desc(LessonBookEntry.period_number)).all()
        classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
        subjects = Subject.query.order_by(Subject.name).all()
        return render_template(
            "lesson_book.html",
            entries=entries,
            classes=classes,
            subjects=subjects,
            class_filter=class_filter,
            subject_filter=subject_filter,
            date_from=date_from,
            date_to=date_to,
        )

    @app.route("/lesson_book/add", methods=["GET", "POST"])
    @login_required
    def lesson_book_add():
        configs = _system_configs()
        default_year = configs.get("school_year", "2025-2026")
        default_semester = int(configs.get("current_semester", "1"))
        classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
        subjects = Subject.query.order_by(Subject.name).all()

        if request.method == "POST":
            class_name = request.form.get("class_name", "").strip()
            subject_id_raw = request.form.get("subject_id", "").strip()
            subject_id = int(subject_id_raw) if subject_id_raw else None
            if current_user.role == "subject_teacher" and current_user.assigned_subject_id and not subject_id:
                subject_id = current_user.assigned_subject_id
            topic = request.form.get("topic", "").strip()
            objectives = request.form.get("objectives", "").strip() or None
            teaching_method = request.form.get("teaching_method", "").strip() or None
            evaluation = request.form.get("evaluation", "").strip() or None
            homework = request.form.get("homework", "").strip() or None
            notes = request.form.get("notes", "").strip() or None
            school_year = request.form.get("school_year", default_year).strip() or default_year
            try:
                semester = int(request.form.get("semester", default_semester))
            except ValueError:
                semester = default_semester
            try:
                period_number = int(request.form.get("period_number", 1))
            except ValueError:
                period_number = 1
            period_number = max(1, min(period_number, 15))
            try:
                lesson_date = datetime.datetime.strptime(
                    request.form.get("lesson_date", ""), "%Y-%m-%d"
                ).date()
            except ValueError:
                flash("Ngày dạy không hợp lệ.", "error")
                return redirect(url_for("lesson_book_add"))

            ap = request.form.get("attendance_present", "").strip()
            aa = request.form.get("attendance_absent", "").strip()
            attendance_present = int(ap) if ap.isdigit() else None
            attendance_absent = int(aa) if aa.isdigit() else None

            if not class_name or not topic:
                flash("Vui lòng nhập lớp và nội dung bài dạy.", "error")
                return redirect(url_for("lesson_book_add"))
            if not can_set_class_for_lesson(class_name):
                flash("Bạn không có quyền ghi sổ cho lớp này.", "error")
                return redirect(url_for("lesson_book_add"))
            if not can_set_subject_for_lesson(subject_id):
                flash("Bạn không có quyền chọn môn này.", "error")
                return redirect(url_for("lesson_book_add"))

            entry = LessonBookEntry(
                teacher_id=current_user.id,
                class_name=class_name,
                subject_id=subject_id,
                lesson_date=lesson_date,
                period_number=period_number,
                topic=topic,
                objectives=objectives,
                teaching_method=teaching_method,
                evaluation=evaluation,
                homework=homework,
                notes=notes,
                attendance_present=attendance_present,
                attendance_absent=attendance_absent,
                school_year=school_year,
                semester=semester,
            )
            db.session.add(entry)
            db.session.commit()
            flash("Đã lưu vào sổ đầu bài.", "success")
            return redirect(url_for("lesson_book"))

        default_class = ""
        if current_user.role == "homeroom_teacher" and current_user.assigned_class:
            default_class = current_user.assigned_class
        default_subject_id = None
        if current_user.role == "subject_teacher" and current_user.assigned_subject_id:
            default_subject_id = current_user.assigned_subject_id

        today_str = datetime.date.today().strftime("%Y-%m-%d")
        return render_template(
            "lesson_book_form.html",
            form_title="Thêm tiết dạy",
            action_url=url_for("lesson_book_add"),
            classes=classes,
            subjects=subjects,
            entry=None,
            default_class=default_class,
            default_subject_id=default_subject_id,
            default_year=default_year,
            default_semester=default_semester,
            today_str=today_str,
        )

    @app.route("/lesson_book/<int:entry_id>/edit", methods=["GET", "POST"])
    @login_required
    def lesson_book_edit(entry_id):
        entry = db.session.get(LessonBookEntry, entry_id)
        if not entry:
            flash("Không tìm thấy bản ghi.", "error")
            return redirect(url_for("lesson_book"))
        if not lesson_book_visible_query().filter(LessonBookEntry.id == entry_id).first():
            flash("Bạn không có quyền xem bản ghi này.", "error")
            return redirect(url_for("lesson_book"))
        if not can_edit_lesson_entry(entry):
            flash("Bạn chỉ có thể sửa tiết dạy do chính mình ghi.", "error")
            return redirect(url_for("lesson_book"))

        configs = _system_configs()
        default_year = configs.get("school_year", "2025-2026")
        classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
        subjects = Subject.query.order_by(Subject.name).all()

        if request.method == "POST":
            class_name = request.form.get("class_name", "").strip()
            subject_id_raw = request.form.get("subject_id", "").strip()
            subject_id = int(subject_id_raw) if subject_id_raw else None
            if current_user.role == "subject_teacher" and current_user.assigned_subject_id and not subject_id:
                subject_id = current_user.assigned_subject_id
            topic = request.form.get("topic", "").strip()
            objectives = request.form.get("objectives", "").strip() or None
            teaching_method = request.form.get("teaching_method", "").strip() or None
            evaluation = request.form.get("evaluation", "").strip() or None
            homework = request.form.get("homework", "").strip() or None
            notes = request.form.get("notes", "").strip() or None
            school_year = request.form.get("school_year", default_year).strip() or default_year
            try:
                semester = int(request.form.get("semester", entry.semester or 1))
            except ValueError:
                semester = entry.semester or 1
            try:
                period_number = int(request.form.get("period_number", 1))
            except ValueError:
                period_number = entry.period_number or 1
            period_number = max(1, min(period_number, 15))
            try:
                lesson_date = datetime.datetime.strptime(
                    request.form.get("lesson_date", ""), "%Y-%m-%d"
                ).date()
            except ValueError:
                flash("Ngày dạy không hợp lệ.", "error")
                return redirect(url_for("lesson_book_edit", entry_id=entry_id))

            ap = request.form.get("attendance_present", "").strip()
            aa = request.form.get("attendance_absent", "").strip()
            attendance_present = int(ap) if ap.isdigit() else None
            attendance_absent = int(aa) if aa.isdigit() else None

            if not class_name or not topic:
                flash("Vui lòng nhập lớp và nội dung bài dạy.", "error")
                return redirect(url_for("lesson_book_edit", entry_id=entry_id))
            if not can_set_class_for_lesson(class_name):
                flash("Bạn không có quyền gán lớp này.", "error")
                return redirect(url_for("lesson_book_edit", entry_id=entry_id))
            if not can_set_subject_for_lesson(subject_id):
                flash("Bạn không có quyền chọn môn này.", "error")
                return redirect(url_for("lesson_book_edit", entry_id=entry_id))

            entry.class_name = class_name
            entry.subject_id = subject_id
            entry.lesson_date = lesson_date
            entry.period_number = period_number
            entry.topic = topic
            entry.objectives = objectives
            entry.teaching_method = teaching_method
            entry.evaluation = evaluation
            entry.homework = homework
            entry.notes = notes
            entry.attendance_present = attendance_present
            entry.attendance_absent = attendance_absent
            entry.school_year = school_year
            entry.semester = semester
            entry.updated_at = datetime.datetime.utcnow()
            db.session.commit()
            flash("Đã cập nhật sổ đầu bài.", "success")
            return redirect(url_for("lesson_book"))

        today_str = entry.lesson_date.strftime("%Y-%m-%d")
        return render_template(
            "lesson_book_form.html",
            form_title="Sửa tiết dạy",
            action_url=url_for("lesson_book_edit", entry_id=entry.id),
            classes=classes,
            subjects=subjects,
            entry=entry,
            default_class="",
            default_subject_id=None,
            default_year=default_year,
            default_semester=entry.semester or int(configs.get("current_semester", "1")),
            today_str=today_str,
        )

    @app.route("/lesson_book/<int:entry_id>/delete", methods=["POST"])
    @login_required
    def lesson_book_delete(entry_id):
        entry = db.session.get(LessonBookEntry, entry_id)
        if not entry:
            flash("Không tìm thấy bản ghi.", "error")
            return redirect(url_for("lesson_book"))
        if not can_edit_lesson_entry(entry):
            flash("Bạn không có quyền xóa bản ghi này.", "error")
            return redirect(url_for("lesson_book"))
        db.session.delete(entry)
        db.session.commit()
        flash("Đã xóa bản ghi.", "success")
        return redirect(url_for("lesson_book"))
