"""Thời khóa biểu — xem, quản trị (admin), nhập Excel / AI (Ollama)."""
import json
import os
import re
import tempfile
import unicodedata
import uuid
from io import BytesIO

import pandas as pd
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import login_required, current_user
from models import db, TimetableSlot, Subject, ClassRoom, SystemConfig, Teacher
from app_helpers import (
    UPLOAD_FOLDER,
    admin_required,
    broadcast_timetable_update,
    resolve_class_name_for_timetable,
    resolve_subject_for_timetable,
    timetable_class_variants_for_filter,
    _call_gemini,
)

DAY_LABELS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
MAX_PERIODS = 10
AI_PREVIEW_SUBDIR = "timetable_ai_preview"
SESSION_AI_PREVIEW = "timetable_ai_preview_id"
AI_PROMPT_TEXT_MAX = 28000


def _ai_preview_dir():
    d = os.path.join(UPLOAD_FOLDER, AI_PREVIEW_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def _ai_preview_json_path(token):
    if not token or not re.fullmatch(r"[a-f0-9]{32}", token):
        return None
    return os.path.join(_ai_preview_dir(), f"{token}.json")


def _clear_ai_preview_session():
    old = session.pop(SESSION_AI_PREVIEW, None)
    if old:
        p = _ai_preview_json_path(old)
        if p and os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _row_from_ai_item(item, idx):
    """Chuẩn hóa một phần tử JSON từ AI để hiển thị / nhập."""
    try:
        cn = str(item.get("class_name", "")).strip()
        day = int(item.get("day_of_week"))
        per = int(item.get("period_number"))
        subj = str(item.get("subject_name", "")).strip()
        room = item.get("room")
        r = str(room).strip() if room not in (None, "") else ""
        issues = []
        if not cn:
            issues.append("Thiếu lớp")
        if not subj:
            issues.append("Thiếu môn")
        if day < 1 or day > 7:
            issues.append("Thứ không hợp lệ (1–7)")
        if per < 1 or per > MAX_PERIODS:
            issues.append(f"Tiết không hợp lệ (1–{MAX_PERIODS})")
        ok = not issues
        return {
            "i": idx,
            "class_name": cn,
            "day_of_week": day,
            "period_number": per,
            "subject_name": subj,
            "room": r or None,
            "ok": ok,
            "issues": "; ".join(issues),
        }
    except (TypeError, ValueError):
        return {
            "i": idx,
            "class_name": str(item.get("class_name", "") or ""),
            "day_of_week": item.get("day_of_week"),
            "period_number": item.get("period_number"),
            "subject_name": str(item.get("subject_name", "") or ""),
            "room": item.get("room"),
            "ok": False,
            "issues": "Không đọc được thứ/tiết (kiểu dữ liệu sai)",
        }


def _load_ai_preview_payload():
    token = session.get(SESSION_AI_PREVIEW)
    if not token:
        return None
    path = _ai_preview_json_path(token)
    if not path or not os.path.isfile(path):
        session.pop(SESSION_AI_PREVIEW, None)
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        session.pop(SESSION_AI_PREVIEW, None)
        return None


def _save_ai_preview_payload(payload):
    _clear_ai_preview_session()
    token = uuid.uuid4().hex
    path = os.path.join(_ai_preview_dir(), f"{token}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    session[SESSION_AI_PREVIEW] = token
    return token


def _configs():
    return {c.key: c.value for c in SystemConfig.query.all()}


def _timetable_manage_redirect_kwargs():
    """Sau POST nhập TKB: giữ lớp / năm / học kỳ từ hidden return_* (khớp bộ lọc trang quản trị)."""
    kw = {}
    cn = (request.form.get("return_class_name") or "").strip()
    if cn:
        kw["class_name"] = cn
    sy = (request.form.get("return_school_year") or "").strip()
    if sy:
        kw["school_year"] = sy
    rs = request.form.get("return_semester")
    if rs is not None and str(rs).strip().isdigit():
        kw["semester"] = int(rs)
    return kw


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
            cn = resolve_class_name_for_timetable(cn)
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
            variants = timetable_class_variants_for_filter(class_name)
            slots = slots.filter(TimetableSlot.class_name.in_(variants))
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

            variants = timetable_class_variants_for_filter(class_name)
            canonical = resolve_class_name_for_timetable(class_name)

            n_saved = 0
            for d in range(1, 8):
                for p in range(1, MAX_PERIODS + 1):
                    subj = request.form.get(f"subj_{d}_{p}", "").strip()
                    room = request.form.get(f"room_{d}_{p}", "").strip()
                    tid = request.form.get(f"tid_{d}_{p}", "").strip()
                    teacher_id = int(tid) if tid.isdigit() else None
                    cell_q = TimetableSlot.query.filter(
                        TimetableSlot.class_name.in_(variants),
                        TimetableSlot.day_of_week == d,
                        TimetableSlot.period_number == p,
                        TimetableSlot.school_year == school_year,
                        TimetableSlot.semester == semester,
                    )
                    if not subj:
                        for slot in cell_q.all():
                            db.session.delete(slot)
                        continue
                    for slot in cell_q.all():
                        db.session.delete(slot)
                    db.session.flush()
                    sid, override = resolve_subject_for_timetable(subj)
                    upsert_slot(
                        canonical,
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
                f"Lớp {canonical}: đã lưu lưới TKB ({school_year}, HK{semester}).",
                created_by_id=current_user.id,
            )
            flash(f"Đã lưu thời khóa biểu ({n_saved} ô có môn).", "success")
            return redirect(
                url_for(
                    "timetable_manage",
                    class_name=canonical,
                    school_year=school_year,
                    semester=semester,
                )
            )

        grid = {}
        if class_name:
            variants = timetable_class_variants_for_filter(class_name)
            for s in TimetableSlot.query.filter(
                TimetableSlot.class_name.in_(variants),
                TimetableSlot.school_year == school_year,
                TimetableSlot.semester == semester,
            ).all():
                grid[(s.day_of_week, s.period_number)] = s

        ai_preview = _load_ai_preview_payload()
        ai_preview_token = session.get(SESSION_AI_PREVIEW) if ai_preview else None

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
            ai_preview=ai_preview,
            ai_preview_token=ai_preview_token,
        )

    @app.route("/timetable/import/xlsx", methods=["POST"])
    @login_required
    @admin_required
    def timetable_import_xlsx():
        f = request.files.get("file")
        if not f or not f.filename:
            flash("Chọn file Excel.", "error")
            return redirect(url_for("timetable_manage", **_timetable_manage_redirect_kwargs()))

        cfg = _configs()
        school_year = request.form.get("school_year", cfg.get("school_year", "2025-2026")).strip()
        semester = int(request.form.get("semester", cfg.get("current_semester", "1")))

        try:
            df = pd.read_excel(f)
        except Exception as e:
            flash(f"Không đọc được file: {e}", "error")
            return redirect(url_for("timetable_manage", **_timetable_manage_redirect_kwargs()))

        count, errors = import_slots_from_dataframe(df, school_year, semester, notify=True)
        if errors and count == 0:
            flash("; ".join(errors[:5]), "error")
        else:
            flash(f"Đã nhập {count} ô TKB." + (f" Cảnh báo: {'; '.join(errors[:3])}" if errors else ""), "success" if count else "warning")
        return redirect(url_for("timetable_manage", **_timetable_manage_redirect_kwargs()))

    @app.route("/timetable/import/xlsx/template", methods=["GET"])
    @login_required
    @admin_required
    def timetable_xlsx_template():
        """File mẫu Excel: cột khớp import_slots_from_dataframe (_df_column_map)."""
        df = pd.DataFrame(
            [
                {
                    "Lớp": "11 TIN",
                    "Thứ": 2,
                    "Tiết": 1,
                    "Môn": "Toán",
                    "Phòng": "A101",
                },
                {
                    "Lớp": "11 TIN",
                    "Thứ": "Thứ 3",
                    "Tiết": 2,
                    "Môn": "Văn",
                    "Phòng": "",
                },
            ]
        )
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="TKB")
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name="mau_thoi_khoa_bieu.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def _redirect_manage_from_form():
        return redirect(url_for("timetable_manage", **_timetable_manage_redirect_kwargs()))

    def _gather_ai_uploads():
        out = []
        for key in ("files", "file"):
            for f in request.files.getlist(key):
                if f and getattr(f, "filename", None) and f.filename.strip():
                    out.append(f)
        return out

    @app.route("/timetable/import/ai/preview", methods=["POST"])
    @login_required
    @admin_required
    def timetable_import_ai_preview():
        cfg = _configs()
        school_year = request.form.get("school_year", cfg.get("school_year", "2025-2026")).strip()
        semester = int(request.form.get("semester", cfg.get("current_semester", "1")))
        raw_text = (request.form.get("raw_text") or "").strip()

        text_parts = []
        if raw_text:
            text_parts.append(raw_text)
        image_paths = []
        source_files = []
        data, err = None, None

        try:
            for up in _gather_ai_uploads():
                ext = up.filename.rsplit(".", 1)[-1].lower()
                data = up.read()
                source_files.append(up.filename)

                if ext in {"xlsx", "xls"}:
                    try:
                        df = pd.read_excel(BytesIO(data))
                        chunk = df.to_csv(index=False)
                        text_parts.append(f"--- File: {up.filename} (bảng Excel → CSV) ---\n{chunk[:12000]}")
                    except Exception as e:
                        flash(f"Lỗi đọc Excel «{up.filename}»: {e}", "error")
                        return _redirect_manage_from_form()
                elif ext in {"txt", "csv", "md"}:
                    try:
                        t = data.decode("utf-8", errors="replace")
                    except Exception:
                        t = data.decode("latin-1", errors="replace")
                    text_parts.append(f"--- File: {up.filename} ---\n{t[:12000]}")
                elif ext in {"png", "jpg", "jpeg", "webp", "gif"}:
                    fd, tmp = tempfile.mkstemp(suffix="." + ext)
                    os.close(fd)
                    with open(tmp, "wb") as out:
                        out.write(data)
                    image_paths.append(tmp)
                else:
                    flash(f"Định dạng không hỗ trợ: {up.filename}", "error")
                    return _redirect_manage_from_form()

            combined = "\n\n".join(text_parts).strip()
            if len(combined) > AI_PROMPT_TEXT_MAX:
                combined = combined[:AI_PROMPT_TEXT_MAX] + "\n\n[...đã cắt bớt do giới hạn độ dài...]"

            if not combined and not image_paths:
                flash("Nhập nội dung hoặc chọn ít nhất một file.", "error")
                return _redirect_manage_from_form()

            prompt = (
                "Chuyển dữ liệu thời khóa biểu sau thành một mảng JSON duy nhất. "
                "Mỗi phần tử: {\"class_name\": string, \"day_of_week\": integer 1-7 (Thứ Hai=1, Thứ Ba=2, ..., Chủ nhật=7), "
                "\"period_number\": integer (tiết 1-10), \"subject_name\": string, \"room\": string hoặc null}. "
                "Chỉ trả về JSON array hợp lệ, không markdown.\n\nNội dung:\n"
            )
            if combined:
                prompt += combined
            else:
                prompt += "(Chỉ có ảnh đính kèm — đọc tất cả ảnh và gộp thành một mảng JSON.)"

            if image_paths:
                data, err = _call_gemini(prompt, image_paths=image_paths, is_json=True)
            else:
                data, err = _call_gemini(prompt, is_json=True)
        finally:
            for p in image_paths:
                if p and os.path.isfile(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

        if err or not isinstance(data, list):
            flash(f"AI (Ollama): {err or 'Không nhận được mảng JSON hợp lệ'}", "error")
            return _redirect_manage_from_form()

        rows = [_row_from_ai_item(item, i + 1) for i, item in enumerate(data)]
        n_ok = sum(1 for r in rows if r["ok"])
        _save_ai_preview_payload(
            {
                "school_year": school_year,
                "semester": semester,
                "rows": rows,
                "source_files": source_files,
            }
        )
        flash(
            f"AI đã chuẩn hóa {len(rows)} dòng ({n_ok} hợp lệ). Xem bảng bên dưới và xác nhận khi sẵn sàng.",
            "success",
        )
        return _redirect_manage_from_form()

    @app.route("/timetable/import/ai/confirm", methods=["POST"])
    @login_required
    @admin_required
    def timetable_import_ai_confirm():
        token = (request.form.get("preview_token") or "").strip()
        if not token or token != session.get(SESSION_AI_PREVIEW):
            flash("Phiên xem trước không hợp lệ. Hãy chạy lại «Chuẩn hóa bằng AI».", "error")
            return _redirect_manage_from_form()

        path = _ai_preview_json_path(token)
        if not path or not os.path.isfile(path):
            session.pop(SESSION_AI_PREVIEW, None)
            flash("Không tìm thấy dữ liệu xem trước (có thể đã hết hạn).", "error")
            return _redirect_manage_from_form()

        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            session.pop(SESSION_AI_PREVIEW, None)
            flash("Không đọc được file xem trước.", "error")
            return _redirect_manage_from_form()

        school_year = str(payload.get("school_year", "")).strip()
        semester = int(payload.get("semester", 1))
        rows = payload.get("rows") or []
        if not school_year:
            flash("Thiếu năm học trong bản xem trước.", "error")
            return _redirect_manage_from_form()

        count = 0
        for row in rows:
            chk = _row_from_ai_item(
                {
                    "class_name": row.get("class_name"),
                    "day_of_week": row.get("day_of_week"),
                    "period_number": row.get("period_number"),
                    "subject_name": row.get("subject_name"),
                    "room": row.get("room"),
                },
                row.get("i", 0),
            )
            if not chk["ok"]:
                continue
            try:
                cn = resolve_class_name_for_timetable(chk["class_name"])
                day = int(chk["day_of_week"])
                per = int(chk["period_number"])
                subj = chk["subject_name"]
                room = chk.get("room")
                r = str(room).strip() if room else None
                sid, override = resolve_subject_for_timetable(subj)
                upsert_slot(cn, day, per, school_year, semester, subject_id=sid, subject_name_override=override, room=r)
                count += 1
            except (TypeError, ValueError, KeyError):
                continue

        db.session.commit()
        try:
            os.remove(path)
        except OSError:
            pass
        session.pop(SESSION_AI_PREVIEW, None)

        if count > 0:
            broadcast_timetable_update(
                "Thời khóa biểu đã cập nhật (AI)",
                f"Đã nhập {count} ô TKB ({school_year}, HK{semester}) sau khi xác nhận.",
                created_by_id=current_user.id,
            )
            flash(f"Đã nhập {count} ô vào CSDL.", "success")
        else:
            flash("Không có dòng hợp lệ để nhập (chỉ các dòng được đánh dấu hợp lệ mới được ghi).", "warning")
        return _redirect_manage_from_form()

    @app.route("/timetable/import/ai/cancel", methods=["POST"])
    @login_required
    @admin_required
    def timetable_import_ai_cancel():
        _clear_ai_preview_session()
        flash("Đã hủy xem trước AI.", "info")
        return _redirect_manage_from_form()

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
        variants = timetable_class_variants_for_filter(class_name)
        q = TimetableSlot.query.filter(
            TimetableSlot.class_name.in_(variants),
            TimetableSlot.day_of_week == dow,
            TimetableSlot.period_number == period,
            TimetableSlot.school_year == school_year,
            TimetableSlot.semester == semester,
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
