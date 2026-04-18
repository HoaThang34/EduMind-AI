"""Sổ đầu bài điện tử — giao diện lưới theo tuần + form truyền thống."""
import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, desc, and_

from models import db, LessonBookWeek, LessonBookSlot, LessonBookEntry, Subject, ClassRoom, SystemConfig
from app_helpers import calculate_week_from_date


def _configs():
    return {c.key: c.value for c in SystemConfig.query.all()}


# ── Shared visibility helper (used by violations_mgmt) ────────────────────────

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


def _week_key(year, week):
    return f"{year}-W{week:02d}"


def _week_dates(year, week):
    """Trả về (mon_date, sun_date) của tuần ISO."""
    jan4 = datetime.date(year, 1, 4)
    week_monday = jan4 + datetime.timedelta(days=week - jan4.isocalendar()[1], weeks=0)
    while week_monday.isocalendar()[1] != week:
        week_monday -= datetime.timedelta(days=1)
    return week_monday, week_monday + datetime.timedelta(days=6)


def _grid_iso_year():
    """Năm ISO dùng cho lưới sổ đầu bài (khớp với lesson_book_grid)."""
    today = datetime.date.today()
    mon = today - datetime.timedelta(days=today.weekday())
    return mon.isocalendar()[0]


def lesson_date_for_grid_cell(week_number, day_of_week):
    """Ngày dạy tương ứng cột Thứ 2..CN (day_of_week 1..7) trong tuần đang xem."""
    wk_mon, _ = _week_dates(_grid_iso_year(), week_number)
    return wk_mon + datetime.timedelta(days=day_of_week - 1)


def build_day_meta_for_grid(wk_mon):
    """Metadata ngày cho 7 cột (Thứ 2 → CN), dùng chung header + ô lưới + API."""
    labels = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
    out = []
    for i in range(7):
        d = wk_mon + datetime.timedelta(days=i)
        out.append({
            "label": labels[i],
            "date": d.strftime("%d/%m"),
            "iso": d.isoformat(),
            "display_full": d.strftime("%d/%m/%Y"),
            "day_of_week": i + 1,
        })
    return out


def register(app):

    # ── List / filter (legacy entries + week overviews) ────────────────────────

    @app.route("/lesson_book", methods=["GET"])
    @login_required
    def lesson_book():
        """Trang chính: danh sách sổ đầu bài theo tuần + lọc."""
        cfg = _configs()
        default_year = cfg.get("school_year", "2025-2026")
        default_sem = int(cfg.get("current_semester", "1"))

        class_filter = request.args.get("class_name", "").strip()
        subject_filter = request.args.get("subject_id", type=int)
        year_filter = request.args.get("school_year", default_year).strip()
        sem_filter = request.args.get("semester", default_sem, type=int)
        week_filter = request.args.get("week_number", type=int)

        # Week overviews (new grid style)
        wq = LessonBookWeek.query
        if current_user.role != "admin":
            wq = wq.filter(LessonBookWeek.teacher_id == current_user.id)
        if class_filter:
            wq = wq.filter(LessonBookWeek.class_name == class_filter)
        if year_filter:
            wq = wq.filter(LessonBookWeek.school_year == year_filter)
        if sem_filter:
            wq = wq.filter(LessonBookWeek.semester == sem_filter)
        if week_filter:
            wq = wq.filter(LessonBookWeek.week_number == week_filter)

        weeks = wq.order_by(
            desc(LessonBookWeek.school_year),
            desc(LessonBookWeek.semester),
            desc(LessonBookWeek.week_number),
        ).all()

        # Legacy entries (fallback / backwards compat)
        lq = LessonBookEntry.query
        if current_user.role != "admin":
            lq = lq.filter(LessonBookEntry.teacher_id == current_user.id)
        if class_filter:
            lq = lq.filter(LessonBookEntry.class_name == class_filter)
        if subject_filter:
            lq = lq.filter(LessonBookEntry.subject_id == subject_filter)
        entries = lq.order_by(desc(LessonBookEntry.lesson_date), desc(LessonBookEntry.period_number)).all()

        classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
        subjects = Subject.query.order_by(Subject.name).all()

        return render_template(
            "lesson_book.html",
            weeks=weeks,
            entries=entries,
            classes=classes,
            subjects=subjects,
            class_filter=class_filter,
            subject_filter=subject_filter,
            year_filter=year_filter,
            sem_filter=sem_filter,
            week_filter=week_filter,
        )

    # ── Grid view — tạo / mở sổ tuần cụ thể ─────────────────────────────────

    @app.route("/lesson_book/grid", methods=["GET"])
    @login_required
    def lesson_book_grid():
        """Mở giao diện lưới sổ đầu bài cho một tuần/lớp cụ thể."""
        cfg = _configs()
        default_year = cfg.get("school_year", "2025-2026")
        default_sem = int(cfg.get("current_semester", "1"))

        class_name = request.args.get("class_name", "").strip()
        school_year = request.args.get("school_year", default_year).strip()
        semester = request.args.get("semester", default_sem, type=int)
        week_number = request.args.get("week_number", type=int)

        # Lấy tuần hiện tại từ cấu hình nhà trường (SystemConfig.current_week)
        cfg_week_raw = cfg.get("current_week", "")
        current_school_week = int(cfg_week_raw) if cfg_week_raw and cfg_week_raw.isdigit() else None

        today = datetime.date.today()
        if not week_number:
            # Ưu tiên tuần từ cấu hình nhà trường; fallback sang ISO week thực tế
            week_number = current_school_week or calculate_week_from_date(today)
        if not school_year:
            school_year = default_year

        # Resolve ISO year cho _week_dates
        # Dùng thực tế: lấy thứ 2 của tuần mong muốn trong năm ISO tương ứng
        mon = today - datetime.timedelta(days=today.weekday())
        iso_year = mon.isocalendar()[0]

        # Build week label + metadata 7 ngày (header + ô lưới + lưu DB)
        wk_mon, wk_sun = _week_dates(iso_year, week_number)
        week_label = f"Từ {wk_mon.strftime('%d/%m')} – {wk_sun.strftime('%d/%m/%Y')}"
        day_meta = build_day_meta_for_grid(wk_mon)

        # Week records visible to this user
        wq = LessonBookWeek.query.filter(
            LessonBookWeek.teacher_id == current_user.id,
            LessonBookWeek.class_name == class_name,
            LessonBookWeek.week_number == week_number,
        )
        week_record = wq.first()

        # Nav: prev / next week (tính theo tuần học, không giới hạn 1-52)
        prev_week = week_number - 1 if week_number > 1 else None
        # Giới hạn tuần tối đa là 52 (đủ cho 1 năm học)
        next_week = week_number + 1 if week_number < 52 else None

        classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
        subjects = [s.name for s in Subject.query.order_by(Subject.name).all()]

        return render_template(
            "lesson_book_grid.html",
            class_name=class_name,
            school_year=school_year,
            semester=semester,
            week_number=week_number,
            week_label=week_label,
            week_mon=wk_mon.strftime("%Y-%m-%d"),
            week_sun=wk_sun.strftime("%Y-%m-%d"),
            week_record=week_record,
            subjects=subjects,
            classes=classes,
            prev_week=prev_week,
            next_week=next_week,
            day_meta=day_meta,
            current_school_week=current_school_week,
            today_iso=today.isoformat(),
        )

    # ── API: load slots for a week ────────────────────────────────────────────

    @app.route("/lesson_book/api/load_week", methods=["GET"])
    @login_required
    def api_lesson_book_load():
        """Trả về JSON tất cả slots + week meta cho tuần/lớp."""
        class_name = request.args.get("class_name", "").strip()
        week_number = request.args.get("week_number", type=int)
        school_year = request.args.get("school_year", "").strip()

        if not class_name or not week_number:
            return jsonify({"error": "Thiếu tham số."}), 400

        week = LessonBookWeek.query.filter(
            LessonBookWeek.teacher_id == current_user.id,
            LessonBookWeek.class_name == class_name,
            LessonBookWeek.week_number == week_number,
            LessonBookWeek.school_year == school_year,
        ).first()

        slots = []
        if week:
            for s in week.slots:
                ld = s.lesson_date
                if ld is None:
                    ld = lesson_date_for_grid_cell(week_number, s.day_of_week)
                slots.append({
                    "id": s.id,
                    "day_of_week": s.day_of_week,
                    "period_number": s.period_number,
                    "lesson_date": ld.isoformat() if ld else None,
                    "lesson_date_display": ld.strftime("%d/%m/%Y") if ld else "",
                    "subject_name": s.subject_name or "",
                    "topic": s.topic or "",
                    "objectives": s.objectives or "",
                    "teaching_method": s.teaching_method or "",
                    "evaluation": s.evaluation or "",
                    "homework": s.homework or "",
                    "notes": s.notes or "",
                    "attendance_present": s.attendance_present,
                    "attendance_absent": s.attendance_absent,
                })

        return jsonify({
            "week_id": week.id if week else None,
            "teacher_notes": week.teacher_notes or "" if week else "",
            "slots": slots,
            "day_meta": build_day_meta_for_grid(_week_dates(_grid_iso_year(), week_number)[0]),
        })

    # ── API: save a single cell (auto-save on blur) ────────────────────────────

    @app.route("/lesson_book/api/save_cell", methods=["POST"])
    @login_required
    def api_lesson_book_save():
        """Lưu một ô trong lưới sổ đầu bài. Tự tạo week/slot nếu chưa có."""
        data = request.get_json() or {}
        class_name = data.get("class_name", "").strip()
        week_number = data.get("week_number", type=int)
        school_year = data.get("school_year", "").strip()
        day_of_week = data.get("day_of_week", type=int)
        period_number = data.get("period_number", type=int)
        field = data.get("field", "")
        value = data.get("value", "")  # string; may be int for attendance

        if not all([class_name, week_number, day_of_week, period_number, field]):
            return jsonify({"error": "Thiếu tham số."}), 400

        # Resolve semester from school_year
        try:
            sy_start = int(school_year.split("-")[0])
        except:
            sy_start = datetime.date.today().year
        semester = 1 if datetime.date.today().month < 7 else 2

        # Upsert week record
        week = LessonBookWeek.query.filter(
            LessonBookWeek.teacher_id == current_user.id,
            LessonBookWeek.class_name == class_name,
            LessonBookWeek.week_number == week_number,
            LessonBookWeek.school_year == school_year,
        ).first()
        if not week:
            week = LessonBookWeek(
                teacher_id=current_user.id,
                class_name=class_name,
                week_number=week_number,
                school_year=school_year,
                semester=semester,
            )
            db.session.add(week)
            db.session.flush()  # get id

        # Upsert slot
        slot = LessonBookSlot.query.filter(
            LessonBookSlot.week_id == week.id,
            LessonBookSlot.day_of_week == day_of_week,
            LessonBookSlot.period_number == period_number,
        ).first()
        if not slot:
            slot = LessonBookSlot(
                week_id=week.id,
                day_of_week=day_of_week,
                period_number=period_number,
            )
            db.session.add(slot)
            db.session.flush()

        # Allowed fields (lesson_date handled separately)
        allowed_fields = {
            "subject_name", "topic", "objectives", "teaching_method",
            "evaluation", "homework", "notes",
            "attendance_present", "attendance_absent",
            "lesson_date",
        }
        if field not in allowed_fields:
            return jsonify({"error": "Trường không hợp lệ."}), 400

        # Cast attendance to int
        if field in ("attendance_present", "attendance_absent"):
            try:
                value = int(value) if value not in ("", None) else None
            except (ValueError, TypeError):
                value = None

        # Parse lesson_date from string dd/mm/yyyy if provided
        if field == "lesson_date":
            value = None
            raw = data.get("value", "").strip()
            if raw:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        value = datetime.datetime.strptime(raw, fmt).date()
                        break
                    except ValueError:
                        pass

        setattr(slot, field, value)
        slot.updated_at = datetime.datetime.utcnow()
        week.updated_at = datetime.datetime.utcnow()
        db.session.commit()

        return jsonify({"ok": True, "slot_id": slot.id, "week_id": week.id})

    # ── API: save week-level notes ─────────────────────────────────────────────

    @app.route("/lesson_book/api/save_week_notes", methods=["POST"])
    @login_required
    def api_lesson_book_save_week_notes():
        """Lưu ghi chú chung cả tuần."""
        data = request.get_json() or {}
        week_id = data.get("week_id", type=int)
        notes = data.get("notes", "")

        if not week_id:
            return jsonify({"error": "Thiếu week_id."}), 400

        week = db.session.get(LessonBookWeek, week_id)
        if not week or week.teacher_id != current_user.id:
            return jsonify({"error": "Không có quyền."}), 403

        week.teacher_notes = notes
        week.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        return jsonify({"ok": True})

    # ── Legacy form routes (backwards compat) ───────────────────────────────────

    @app.route("/lesson_book/add", methods=["GET", "POST"])
    @login_required
    def lesson_book_add():
        return _legacy_form("add")

    @app.route("/lesson_book/<int:entry_id>/edit", methods=["GET", "POST"])
    @login_required
    def lesson_book_edit(entry_id):
        return _legacy_form("edit", entry_id)

    @app.route("/lesson_book/<int:entry_id>/delete", methods=["POST"])
    @login_required
    def lesson_book_delete(entry_id):
        entry = db.session.get(LessonBookEntry, entry_id)
        if not entry:
            flash("Không tìm thấy bản ghi.", "error")
            return redirect(url_for("lesson_book"))
        if current_user.role != "admin" and entry.teacher_id != current_user.id:
            flash("Bạn chỉ có thể xóa tiết do chính mình ghi.", "error")
            return redirect(url_for("lesson_book"))
        db.session.delete(entry)
        db.session.commit()
        flash("Đã xóa bản ghi.", "success")
        return redirect(url_for("lesson_book"))


def _legacy_form(mode, entry_id=None):
    """Shared form handler for legacy add/edit."""
    cfg = _configs()
    default_year = cfg.get("school_year", "2025-2026")
    default_sem = int(cfg.get("current_semester", "1"))
    classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
    subjects = Subject.query.order_by(Subject.name).all()

    entry = None
    if mode == "edit":
        entry = db.session.get(LessonBookEntry, entry_id)
        if not entry:
            flash("Không tìm thấy bản ghi.", "error")
            return redirect(url_for("lesson_book"))

    if request.method == "POST":
        class_name = request.form.get("class_name", "").strip()
        subject_id_raw = request.form.get("subject_id", "").strip()
        subject_id = int(subject_id_raw) if subject_id_raw else None
        topic = request.form.get("topic", "").strip()
        objectives = request.form.get("objectives", "").strip() or None
        teaching_method = request.form.get("teaching_method", "").strip() or None
        evaluation = request.form.get("evaluation", "").strip() or None
        homework = request.form.get("homework", "").strip() or None
        notes = request.form.get("notes", "").strip() or None
        school_year = request.form.get("school_year", default_year).strip() or default_year
        try:
            semester = int(request.form.get("semester", default_sem))
        except ValueError:
            semester = default_sem
        try:
            period_number = max(1, min(int(request.form.get("period_number", 1)), 15))
        except ValueError:
            period_number = 1
        try:
            lesson_date = datetime.datetime.strptime(
                request.form.get("lesson_date", ""), "%Y-%m-%d"
            ).date()
        except ValueError:
            flash("Ngày dạy không hợp lệ.", "error")
            return redirect(url_for("lesson_book_add" if mode == "add" else "lesson_book_edit", entry_id=entry_id))

        ap = request.form.get("attendance_present", "").strip()
        aa = request.form.get("attendance_absent", "").strip()
        attendance_present = int(ap) if ap.isdigit() else None
        attendance_absent = int(aa) if aa.isdigit() else None

        if not class_name or not topic:
            flash("Vui lòng nhập lớp và nội dung bài dạy.", "error")
            return redirect(url_for("lesson_book_add" if mode == "add" else "lesson_book_edit", entry_id=entry_id))

        if mode == "add":
            record = LessonBookEntry(
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
            db.session.add(record)
            db.session.commit()
            flash("Đã lưu vào sổ đầu bài.", "success")
        else:
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

    default_class = ""
    if current_user.role == "homeroom_teacher" and current_user.assigned_class:
        default_class = current_user.assigned_class
    default_subject_id = None
    if current_user.role == "subject_teacher" and current_user.assigned_subject_id:
        default_subject_id = current_user.assigned_subject_id

    today_str = (entry.lesson_date if entry else datetime.date.today()).strftime("%Y-%m-%d")
    form_title = "Sửa tiết dạy" if mode == "edit" else "Thêm tiết dạy"
    action_url = url_for("lesson_book_edit", entry_id=entry_id) if mode == "edit" else url_for("lesson_book_add")

    return render_template(
        "lesson_book_form.html",
        form_title=form_title,
        action_url=action_url,
        classes=classes,
        subjects=subjects,
        entry=entry,
        default_class=default_class,
        default_subject_id=default_subject_id,
        default_year=default_year,
        default_semester=default_sem,
        today_str=today_str,
        cfg_school_year=default_year,
        cfg_semester=default_sem,
    )
