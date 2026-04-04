"""Thời khóa biểu — xem, quản trị (admin), nhập Excel / AI (Ollama)."""
import os
import re
import tempfile
import unicodedata
from io import BytesIO

import pandas as pd
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, TimetableSlot, Subject, ClassRoom, SystemConfig, Teacher
from app_helpers import (
    admin_required,
    broadcast_timetable_update,
    resolve_subject_for_timetable,
    _call_gemini,
)

DAY_LABELS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
MAX_PERIODS = 10


def _configs():
    return {c.key: c.value for c in SystemConfig.query.all()}


def parse_day_cell(v):
    """Trả về 1–7 (Thứ Hai=1 … CN=7) hoặc None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        x = int(v)
        if 1 <= x <= 7:
            return x
    s = str(v).strip().lower()
    if not s:
        return None
    if "cn" in s or "chủ" in s or "chu nhat" in s or "sun" in s:
        return 7
    m = re.search(r"(?:thứ|thu)\s*(\d)", s, re.I)
    if m:
        n = int(m.group(1))
        if 2 <= n <= 7:
            return n - 1
    m2 = re.search(r"^(\d)$", s)
    if m2:
        n = int(m2.group(1))
        if 1 <= n <= 7:
            return n
    return None


def parse_period_cell(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        p = int(float(v))
        return p if 1 <= p <= MAX_PERIODS else None
    except (ValueError, TypeError):
        return None


def upsert_slot(
    class_name,
    day_of_week,
    period_number,
    school_year,
    semester,
    subject_id=None,
    subject_name_override=None,
    room=None,
    teacher_id=None,
):
    slot = TimetableSlot.query.filter_by(
        class_name=class_name,
        day_of_week=day_of_week,
        period_number=period_number,
        school_year=school_year,
        semester=semester,
    ).first()
    if not slot:
        slot = TimetableSlot(
            class_name=class_name,
            day_of_week=day_of_week,
            period_number=period_number,
            school_year=school_year,
            semester=semester,
        )
        db.session.add(slot)
    slot.subject_id = subject_id
    slot.subject_name_override = subject_name_override if not subject_id else None
    slot.room = (room or "").strip() or None
    slot.teacher_id = teacher_id
    return slot


def _df_column_map(df):
    cols = {str(c).strip().lower(): c for c in df.columns}

    def pick(*keys):
        for k in keys:
            for cname, orig in cols.items():
                if k in cname.replace(" ", ""):
                    return orig
        return None

    return {
        "class_name": pick("lớp", "lop", "class"),
        "day": pick("thứ", "thu", "day"),
        "period": pick("tiết", "tiet", "period"),
        "subject": pick("môn", "mon", "subject"),
        "room": pick("phòng", "phong", "room"),
    }


def import_slots_from_dataframe(df, school_year, semester, notify=True):
    """Trả về (số ô đã ghi, danh sách lỗi)."""
    cmap = _df_column_map(df)
    errors = []
    if not cmap["class_name"] or not cmap["day"] or not cmap["period"] or not cmap["subject"]:
        return 0, ["Cần các cột: Lớp, Thứ, Tiết, Môn (hoặc class, day, period, subject)."]

    count = 0
    for idx, row in df.iterrows():
        try:
            cn = str(row[cmap["class_name"]]).strip()
            if not cn or cn.lower() == "nan":
                continue
            day = parse_day_cell(row[cmap["day"]])
            per = parse_period_cell(row[cmap["period"]])
            subj_raw = row[cmap["subject"]]
            if subj_raw is None or (isinstance(subj_raw, float) and pd.isna(subj_raw)):
                continue
            subj_raw = str(subj_raw).strip()
            if not subj_raw:
                continue
            if day is None or per is None:
                errors.append(f"Dòng {idx + 2}: Thứ hoặc tiết không hợp lệ.")
                continue
            room = None
            if cmap["room"]:
                r = row[cmap["room"]]
                if r is not None and not (isinstance(r, float) and pd.isna(r)):
                    room = str(r).strip()
            sid, override = resolve_subject_for_timetable(subj_raw)
            upsert_slot(cn, day, per, school_year, semester, subject_id=sid, subject_name_override=override, room=room)
            count += 1
        except Exception as e:
            errors.append(f"Dòng {idx + 2}: {e}")
    db.session.commit()
    if notify and count > 0:
        broadcast_timetable_update(
            "Thời khóa biểu đã cập nhật",
            f"Đã nhập/cập nhật {count} ô TKB (năm học {school_year}, HK{semester}).",
            created_by_id=current_user.id if current_user.is_authenticated else None,
        )
    return count, errors


def register(app):
    @app.route("/timetable")
    @login_required
    def timetable_view():
        cfg = _configs()
        default_year = cfg.get("school_year", "2025-2026")
        default_sem = int(cfg.get("current_semester", "1"))
        school_year = request.args.get("school_year", default_year).strip()
        semester = int(request.args.get("semester", default_sem))
        class_name = request.args.get("class_name", "").strip()

        if current_user.role == "homeroom_teacher" and current_user.assigned_class and not class_name:
            class_name = current_user.assigned_class

        classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
        slots = TimetableSlot.query.filter_by(school_year=school_year, semester=semester)
        if class_name:
            slots = slots.filter_by(class_name=class_name)
        slots = slots.all()

        grid = {}
        for s in slots:
            grid[(s.day_of_week, s.period_number)] = s

        return render_template(
            "timetable.html",
            grid=grid,
            classes=classes,
            class_name=class_name,
            school_year=school_year,
            semester=semester,
            day_labels=DAY_LABELS,
            max_periods=MAX_PERIODS,
            is_admin=current_user.role == "admin",
        )

    @app.route("/timetable/manage", methods=["GET", "POST"])
    @login_required
    @admin_required
    def timetable_manage():
        cfg = _configs()
        default_year = cfg.get("school_year", "2025-2026")
        default_sem = int(cfg.get("current_semester", "1"))
        school_year = request.args.get("school_year", default_year).strip() or default_year
        semester = int(request.args.get("semester", default_sem))
        class_name = request.args.get("class_name", "").strip()
        classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
        subjects = Subject.query.order_by(Subject.name).all()
        teachers = Teacher.query.order_by(Teacher.full_name).all()

        if request.method == "POST" and request.form.get("action") == "save_grid":
            class_name = request.form.get("class_name", "").strip()
            school_year = request.form.get("school_year", default_year).strip()
            semester = int(request.form.get("semester", default_sem))
            if not class_name:
                flash("Chọn lớp.", "error")
                return redirect(url_for("timetable_manage", school_year=school_year, semester=semester))

            n_saved = 0
            for d in range(1, 8):
                for p in range(1, MAX_PERIODS + 1):
                    subj = request.form.get(f"subj_{d}_{p}", "").strip()
                    room = request.form.get(f"room_{d}_{p}", "").strip()
                    tid = request.form.get(f"tid_{d}_{p}", "").strip()
                    teacher_id = int(tid) if tid.isdigit() else None
                    if not subj:
                        slot = TimetableSlot.query.filter_by(
                            class_name=class_name,
                            day_of_week=d,
                            period_number=p,
                            school_year=school_year,
                            semester=semester,
                        ).first()
                        if slot:
                            db.session.delete(slot)
                        continue
                    sid, override = resolve_subject_for_timetable(subj)
                    upsert_slot(
                        class_name,
                        d,
                        p,
                        school_year,
                        semester,
                        subject_id=sid,
                        subject_name_override=override,
                        room=room or None,
                        teacher_id=teacher_id,
                    )
                    n_saved += 1
            db.session.commit()
            broadcast_timetable_update(
                "Thời khóa biểu đã cập nhật",
                f"Lớp {class_name}: đã lưu lưới TKB ({school_year}, HK{semester}).",
                created_by_id=current_user.id,
            )
            flash(f"Đã lưu thời khóa biểu ({n_saved} ô có môn).", "success")
            return redirect(
                url_for(
                    "timetable_manage",
                    class_name=class_name,
                    school_year=school_year,
                    semester=semester,
                )
            )

        grid = {}
        if class_name:
            for s in TimetableSlot.query.filter_by(
                class_name=class_name, school_year=school_year, semester=semester
            ).all():
                grid[(s.day_of_week, s.period_number)] = s

        return render_template(
            "timetable_manage.html",
            classes=classes,
            class_name=class_name,
            school_year=school_year,
            semester=semester,
            day_labels=DAY_LABELS,
            max_periods=MAX_PERIODS,
            grid=grid,
            subjects=subjects,
            teachers=teachers,
            default_year=default_year,
            default_sem=default_sem,
        )

    @app.route("/timetable/import/xlsx", methods=["POST"])
    @login_required
    @admin_required
    def timetable_import_xlsx():
        f = request.files.get("file")
        if not f or not f.filename:
            flash("Chọn file Excel.", "error")
            return redirect(url_for("timetable_manage"))

        cfg = _configs()
        school_year = request.form.get("school_year", cfg.get("school_year", "2025-2026")).strip()
        semester = int(request.form.get("semester", cfg.get("current_semester", "1")))

        try:
            df = pd.read_excel(f)
        except Exception as e:
            flash(f"Không đọc được file: {e}", "error")
            return redirect(url_for("timetable_manage"))

        count, errors = import_slots_from_dataframe(df, school_year, semester, notify=True)
        if errors and count == 0:
            flash("; ".join(errors[:5]), "error")
        else:
            flash(f"Đã nhập {count} ô TKB." + (f" Cảnh báo: {'; '.join(errors[:3])}" if errors else ""), "success" if count else "warning")
        return redirect(url_for("timetable_manage"))

    @app.route("/timetable/import/ai", methods=["POST"])
    @login_required
    @admin_required
    def timetable_import_ai():
        cfg = _configs()
        school_year = request.form.get("school_year", cfg.get("school_year", "2025-2026")).strip()
        semester = int(request.form.get("semester", cfg.get("current_semester", "1")))
        raw_text = (request.form.get("raw_text") or "").strip()

        up = request.files.get("file")
        temp_path = None
        image_mode = False

        if up and up.filename:
            ext = up.filename.rsplit(".", 1)[-1].lower()
            data = up.read()
            if ext in {"xlsx", "xls"}:
                try:
                    df = pd.read_excel(BytesIO(data))
                    count, errors = import_slots_from_dataframe(df, school_year, semester, notify=True)
                    if count:
                        flash(f"Đã nhập {count} ô từ Excel (AI không cần).", "success")
                    else:
                        flash("Không đọc được dòng hợp lệ từ Excel: " + "; ".join(errors[:3]), "error")
                    return redirect(url_for("timetable_manage"))
                except Exception as e:
                    flash(f"Lỗi đọc Excel: {e}", "error")
                    return redirect(url_for("timetable_manage"))

            if ext in {"txt", "csv", "md"}:
                try:
                    raw_text = data.decode("utf-8", errors="replace")
                except Exception:
                    raw_text = data.decode("latin-1", errors="replace")

            elif ext in {"png", "jpg", "jpeg", "webp", "gif"}:
                fd, temp_path = tempfile.mkstemp(suffix="." + ext)
                os.close(fd)
                with open(temp_path, "wb") as out:
                    out.write(data)
                image_mode = True
            else:
                flash("Định dạng file chưa hỗ trợ. Dùng xlsx, txt, csv hoặc ảnh png/jpg.", "error")
                return redirect(url_for("timetable_manage"))

        if not raw_text and not temp_path:
            flash("Nhập nội dung hoặc đính kèm file.", "error")
            return redirect(url_for("timetable_manage"))

        prompt = (
            "Chuyển dữ liệu thời khóa biểu sau thành một mảng JSON duy nhất. "
            "Mỗi phần tử: {\"class_name\": string, \"day_of_week\": integer 1-7 (Thứ Hai=1, Thứ Ba=2, ..., Chủ nhật=7), "
            "\"period_number\": integer (tiết 1-10), \"subject_name\": string, \"room\": string hoặc null}. "
            "Chỉ trả về JSON array hợp lệ, không markdown.\n\nNội dung:\n"
        )
        if raw_text:
            prompt += raw_text[:14000]
        else:
            prompt += "(Ảnh đính kèm — đọc bảng thời khóa biểu.)"

        try:
            if image_mode and temp_path:
                data, err = _call_gemini(prompt, image_path=temp_path, is_json=True)
            else:
                data, err = _call_gemini(prompt, is_json=True)
        finally:
            if temp_path and os.path.isfile(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        if err or not isinstance(data, list):
            flash(f"Ollama/AI: {err or 'Không parse được JSON'}", "error")
            return redirect(url_for("timetable_manage"))

        count = 0
        for item in data:
            try:
                cn = str(item.get("class_name", "")).strip()
                day = int(item.get("day_of_week"))
                per = int(item.get("period_number"))
                subj = str(item.get("subject_name", "")).strip()
                room = item.get("room")
                if not cn or not subj:
                    continue
                if day < 1 or day > 7 or per < 1 or per > MAX_PERIODS:
                    continue
                sid, override = resolve_subject_for_timetable(subj)
                r = str(room).strip() if room else None
                upsert_slot(cn, day, per, school_year, semester, subject_id=sid, subject_name_override=override, room=r)
                count += 1
            except (TypeError, ValueError):
                continue

        db.session.commit()
        if count > 0:
            broadcast_timetable_update(
                "Thời khóa biểu đã cập nhật (AI)",
                f"Đã chuẩn hóa và nhập {count} ô TKB ({school_year}, HK{semester}).",
                created_by_id=current_user.id,
            )
            flash(f"AI đã format và nhập {count} ô TKB.", "success")
        else:
            flash("Không có ô hợp lệ sau khi AI xử lý.", "warning")
        return redirect(url_for("timetable_manage"))

    @app.route("/api/timetable/match_slots", methods=["GET"])
    @login_required
    def api_timetable_match_slots():
        class_name = request.args.get("class_name", "").strip()
        lesson_date = request.args.get("lesson_date", "").strip()
        period = request.args.get("period", type=int)
        cfg = _configs()
        school_year = request.args.get("school_year", cfg.get("school_year", "2025-2026")).strip()
        semester = int(request.args.get("semester", cfg.get("current_semester", "1")))

        if not class_name or not lesson_date or not period:
            return jsonify({"slots": []})

        try:
            import datetime as dt

            d = dt.datetime.strptime(lesson_date, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"slots": []})

        dow = d.weekday() + 1
        q = TimetableSlot.query.filter_by(
            class_name=class_name,
            day_of_week=dow,
            period_number=period,
            school_year=school_year,
            semester=semester,
        ).all()
        out = []
        for s in q:
            label = f"Thứ {dow} — Tiết {s.period_number}"
            sub = s.subject.name if s.subject else (s.subject_name_override or "")
            out.append(
                {
                    "id": s.id,
                    "label": f"{label} — {sub}" + (f" — {s.room}" if s.room else ""),
                }
            )
        return jsonify({"slots": out})
