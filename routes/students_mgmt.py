"""Routes: students_mgmt."""
import json
import math
import os
import uuid
import datetime
from io import BytesIO
import pandas as pd
from flask import render_template, request, jsonify, redirect, url_for, flash, session, send_file, abort
from flask_login import login_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc, or_, and_
from werkzeug.security import generate_password_hash

from models import (
    db, Student, Violation, ViolationType, Teacher, SystemConfig, ClassRoom,
    WeeklyArchive, Subject, Grade, BonusType, BonusRecord, Notification,
    GroupChatMessage, PrivateMessage, ChangeLog,
)
from app_helpers import (
    admin_required, permission_required, role_or_permission_required, get_accessible_students, can_access_student, normalize_student_code,
    parse_excel_file, import_violations_to_db, calculate_week_from_date, _call_gemini,
    save_weekly_archive, get_current_iso_week, create_notification, log_change,
    UPLOAD_FOLDER, calculate_student_gpa, is_reset_needed,
)


def _empty_to_none(s):
    s = (s or "").strip()
    return s if s else None


def _excel_cell_str(v):
    if pd.isna(v):
        return None
    if isinstance(v, float) and not math.isnan(v) and v == int(v):
        return str(int(v))
    s = str(v).strip()
    return s if s else None


def _student_name_column(df_columns):
    """Cột họ tên học sinh — loại trừ cột phụ huynh."""
    for c in df_columns:
        cl = str(c).strip().lower()
        if "phụ huynh" in cl or "phu huynh" in cl or "phhs" in cl:
            continue
        if "tên" in cl or "name" in cl:
            return c
    return None


def _find_dob_column(df_columns):
    """Cột ngày sinh: tiêu đề có 'ngày sinh', 'birth', 'dob', 'năm sinh' (không lấy cột phụ huynh)."""
    for c in df_columns:
        cl = str(c).strip().lower()
        if "phụ huynh" in cl or "phu huynh" in cl or "phhs" in cl:
            continue
        if (
            "ngày sinh" in cl
            or "ngay sinh" in cl
            or "năm sinh" in cl
            or "nam sinh" in cl
            or "birth" in cl
            or cl == "dob"
        ):
            return c
    return None


def _find_position_column(df_columns):
    """Cột chức vụ: 'chức vụ', 'chuc vu', 'position'."""
    for c in df_columns:
        cl = str(c).strip().lower()
        if "chức vụ" in cl or "chuc vu" in cl or "position" in cl:
            return c
    return None


def _find_id_card_column(df_columns):
    """Cột CCCD/CMND: 'cccd', 'cmnd', 'số cccd', 'id card', 'căn cước'."""
    for c in df_columns:
        cl = str(c).strip().lower()
        if any(x in cl for x in ["cccd", "cmnd", "căn cước", "can cuoc", "id card", "số cccd"]):
            return c
    return None


def _find_ethnicity_column(df_columns):
    """Cột dân tộc: 'dân tộc', 'dan toc', 'ethnicity', 'dantoc'."""
    for c in df_columns:
        cl = str(c).strip().lower()
        if any(x in cl for x in ["dân tộc", "dan toc", "ethnicity", "dantoc"]):
            return c
    return None


def _format_dob_from_excel_cell(v):
    """Chuẩn hóa ô Excel (datetime hoặc chuỗi) thành chuỗi hiển thị."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if pd.isna(v):
        return None
    if isinstance(v, datetime.datetime):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, datetime.date):
        return v.strftime("%d/%m/%Y")
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def _find_parent_import_columns(df_columns):
    """Nhận diện cột Excel: Họ tên phụ huynh / SĐT phụ huynh (tùy chọn)."""
    orig = list(df_columns)
    name_col = None
    phone_col = None
    for o in orig:
        cl = str(o).strip().lower()
        is_ph = "phụ huynh" in cl or "phu huynh" in cl or "phhs" in cl
        is_phone = any(
            x in cl
            for x in ("sđt", "sdt", "phone", "điện thoại", "dien thoai", "tel", "mobile")
        )
        if is_ph and is_phone:
            phone_col = o
        elif is_ph and not is_phone:
            name_col = o
    if not phone_col:
        for o in orig:
            cl = str(o).strip().lower()
            if "sđt" in cl or "sdt" in cl:
                if "ph" in cl or "phhs" in cl or "phụ" in cl or "phu" in cl:
                    phone_col = o
                    break
    return name_col, phone_col


PORTRAIT_SUBDIR = "student_portraits"
ALLOWED_PORTRAIT_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_PORTRAIT_BYTES = 5 * 1024 * 1024


def _portrait_dir():
    d = os.path.join(UPLOAD_FOLDER, PORTRAIT_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def _delete_portrait_file(filename):
    if not filename:
        return
    safe = os.path.basename(filename)
    path = os.path.join(_portrait_dir(), safe)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _save_portrait_file(student_id, file_storage):
    """Lưu ảnh chân dung; trả về tên file trong thư mục portrait hoặc None."""
    if not file_storage or not file_storage.filename:
        return None
    orig = secure_filename(file_storage.filename)
    if not orig:
        return None
    ext = os.path.splitext(orig)[1].lower()
    if ext not in ALLOWED_PORTRAIT_EXT:
        return None
    name = f"student_{student_id}_{uuid.uuid4().hex[:12]}{ext}"
    path = os.path.join(_portrait_dir(), name)
    file_storage.save(path)
    if os.path.getsize(path) > MAX_PORTRAIT_BYTES:
        os.remove(path)
        return None
    return name


def register(app):
    @app.route("/student/<int:student_id>/portrait")
    def student_portrait_view(student_id):
        """Ảnh chân dung: học sinh (session) hoặc giáo viên có quyền."""
        s = db.session.get(Student, student_id)
        if not s or not s.portrait_filename:
            abort(404)
        allowed = False
        if session.get("student_id") == student_id:
            allowed = True
        elif current_user.is_authenticated and can_access_student(student_id):
            allowed = True
        if not allowed:
            if current_user.is_authenticated:
                abort(403)
            return redirect(url_for("auth.login"))
        path = os.path.join(_portrait_dir(), os.path.basename(s.portrait_filename))
        if not os.path.isfile(path):
            abort(404)
        ext = os.path.splitext(path)[1].lower()
        mimetype = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(ext, "application/octet-stream")
        return send_file(path, mimetype=mimetype)
    @app.route("/manage_students")
    @login_required
    @permission_required('view_students')
    def manage_students():
        # Lấy tham số lọc và phân trang
        page = request.args.get('page', 1, type=int)
        per_page = 20  # Số học sinh mỗi trang
        filter_class = request.args.get('filter_class', '', type=str)
        
        # Lấy danh sách học sinh (filtered by role)
        query = get_accessible_students()
        
        # Lọc theo lớp nếu được chọn
        if filter_class:
            query = query.filter(Student.student_class == filter_class)
        
        # Phân trang
        total = query.count()
        students = query.order_by(Student.student_code.asc()).offset((page - 1) * per_page).limit(per_page).all()
        
        # Tính tổng số trang
        total_pages = (total + per_page - 1) // per_page
        
        class_list = ClassRoom.query.order_by(ClassRoom.name).all()
        
        return render_template("manage_students.html", 
                             students=students, 
                             class_list=class_list,
                             page=page,
                             per_page=per_page,
                             total=total,
                             total_pages=total_pages,
                             filter_class=filter_class)

    @app.route("/add_student", methods=["POST"])
    @login_required
    @admin_required
    def add_student():
        st = Student(
            name=request.form["student_name"].upper(),
            student_code=request.form["student_code"],
            student_class=request.form["student_class"],
            parent_name=_empty_to_none(request.form.get("parent_name")),
            parent_phone=_empty_to_none(request.form.get("parent_phone")),
            date_of_birth=_empty_to_none(request.form.get("date_of_birth")),
            position=_empty_to_none(request.form.get("position")),
            id_card=_empty_to_none(request.form.get("id_card")),
            ethnicity=_empty_to_none(request.form.get("ethnicity")),
        )
        st.set_password("123456")  # Mật khẩu mặc định
        db.session.add(st)
        db.session.flush()
        pf = request.files.get("portrait")
        if pf and pf.filename:
            fn = _save_portrait_file(st.id, pf)
            if fn:
                st.portrait_filename = fn
            else:
                flash("Ảnh chân dung không hợp lệ (JPG, PNG, WebP, GIF, tối đa 5MB).", "warning")
        db.session.commit()
        flash("Thêm học sinh thành công. Mật khẩu mặc định: 123456", "success")
        return redirect(url_for("manage_students"))

    @app.route("/delete_student/<int:student_id>", methods=["POST"])
    @login_required
    @admin_required
    def delete_student(student_id):
        s = db.session.get(Student, student_id)
        if s:
            _delete_portrait_file(s.portrait_filename)
            Violation.query.filter_by(student_id=student_id).delete()
            db.session.delete(s)
            db.session.commit()
            flash("Đã xóa học sinh", "success")
        return redirect(url_for("manage_students"))

    @app.route("/edit_student/<int:student_id>", methods=["GET", "POST"])
    @login_required
    @admin_required
    def edit_student(student_id):
        s = db.session.get(Student, student_id)
        if not s:
            flash("Không tìm thấy học sinh", "error")
            return redirect(url_for("manage_students"))
        
        if request.method == "POST":
            s.name = request.form["student_name"].upper()
            s.student_code = request.form["student_code"]
            s.student_class = request.form["student_class"]
            s.parent_name = _empty_to_none(request.form.get("parent_name"))
            s.parent_phone = _empty_to_none(request.form.get("parent_phone"))
            s.date_of_birth = _empty_to_none(request.form.get("date_of_birth"))
            s.position = _empty_to_none(request.form.get("position"))
            s.id_card = _empty_to_none(request.form.get("id_card"))
            s.ethnicity = _empty_to_none(request.form.get("ethnicity"))
            if request.form.get("remove_portrait"):
                _delete_portrait_file(s.portrait_filename)
                s.portrait_filename = None
            pf = request.files.get("portrait")
            if pf and pf.filename:
                old = s.portrait_filename
                fn = _save_portrait_file(s.id, pf)
                if fn:
                    _delete_portrait_file(old)
                    s.portrait_filename = fn
                else:
                    flash("Ảnh chân dung không hợp lệ (JPG, PNG, WebP, GIF, tối đa 5MB).", "warning")
            db.session.commit()
            flash("Cập nhật thành công", "success")
            # Preserve filter parameter
            filter_class = request.args.get('filter_class', '')
            return redirect(url_for("manage_students", filter_class=filter_class))
        
        class_list = ClassRoom.query.order_by(ClassRoom.name).all()
        return render_template("edit_student.html", student=s, class_list=class_list)

    @app.route("/add_class", methods=["POST"])
    @login_required
    @admin_required
    def add_class():
        if not ClassRoom.query.filter_by(name=request.form["class_name"]).first():
            db.session.add(ClassRoom(name=request.form["class_name"]))
            db.session.commit()
        return redirect(url_for("manage_students"))
    #chỉnh sửa lớp học

    @app.route("/edit_class/<int:class_id>", methods=["POST"])
    @login_required
    @admin_required
    def edit_class(class_id):
        """Đổi tên lớp và cập nhật lại lớp cho toàn bộ học sinh"""
        try:
            new_name = request.form.get("new_name", "").strip()
            if not new_name:
                flash("Tên lớp không được để trống!", "error")
                return redirect(url_for("manage_students"))

            # Tìm lớp cần sửa
            cls = db.session.get(ClassRoom, class_id)
            if cls:
                old_name = cls.name
            
                # 1. Cập nhật tên trong bảng ClassRoom
                cls.name = new_name
            
                # 2. Cập nhật lại tên lớp cho TẤT CẢ học sinh đang ở lớp cũ
                # (Logic quan trọng để đồng bộ dữ liệu)
                students_in_class = Student.query.filter_by(student_class=old_name).all()
                for s in students_in_class:
                    s.student_class = new_name
                
                db.session.commit()
                flash(f"Đã đổi tên lớp '{old_name}' thành '{new_name}' và cập nhật {len(students_in_class)} học sinh.", "success")
            else:
                flash("Không tìm thấy lớp học!", "error")
            
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi: {str(e)}", "error")
        
        return redirect(url_for("manage_students"))

    @app.route("/delete_class/<int:class_id>", methods=["POST"])
    @login_required
    @admin_required
    def delete_class(class_id):
        """Xóa lớp học"""
        try:
            cls = db.session.get(ClassRoom, class_id)
            if cls:
                # Kiểm tra an toàn: Chỉ cho xóa nếu lớp RỖNG (không có học sinh)
                student_count = Student.query.filter_by(student_class=cls.name).count()
                if student_count > 0:
                    flash(f"Không thể xóa lớp '{cls.name}' vì đang có {student_count} học sinh. Hãy chuyển hoặc xóa học sinh trước.", "error")
                else:
                    db.session.delete(cls)
                    db.session.commit()
                    flash(f"Đã xóa lớp {cls.name}", "success")
        except Exception as e:
            flash(f"Lỗi: {str(e)}", "error")
        # Preserve filter parameter
        filter_class = request.args.get('filter_class', '')
        return redirect(url_for("manage_students", filter_class=filter_class))
    @app.route("/import_students", methods=["GET", "POST"])
    @login_required
    @admin_required
    def import_students():
        """Import students from Excel with columns: Mã học sinh, Họ và tên, Lớp"""
        if request.method == "POST":
            file = request.files.get("file")
        
            if not file:
                flash("Vui lòng chọn file Excel!", "error")
                return redirect(request.url)

            try:
                # Save temporary file
                if not os.path.exists("uploads"):
                    os.makedirs("uploads")
            
                filename = f"import_students_{uuid.uuid4().hex[:8]}.xlsx"
                filepath = os.path.join("uploads", filename)
                file.save(filepath)

                # Đọc file Excel
                df = pd.read_excel(filepath)
                # Chuẩn hóa tên cột về chữ thường để dễ tìm
                df.columns = [str(c).strip().lower() for c in df.columns]
            
                preview_data = []
            
                # Tìm các cột cần thiết
                code_col = next((c for c in df.columns if "mã" in str(c).lower() or "code" in str(c).lower()), None)
                name_col = _student_name_column(df.columns)
                class_col = next((c for c in df.columns if "lớp" in str(c).lower() or "class" in str(c).lower()), None)
            
                if not code_col or not name_col or not class_col:
                    if os.path.exists(filepath): os.remove(filepath)
                    flash("File Excel cần có 3 cột: 'Mã học sinh', 'Họ và tên', 'Lớp'", "error")
                    return redirect(request.url)

                parent_name_col, parent_phone_col = _find_parent_import_columns(df.columns)
                dob_col = _find_dob_column(df.columns)
                pos_col = _find_position_column(df.columns)
                id_card_col = _find_id_card_column(df.columns)
                ethnicity_col = _find_ethnicity_column(df.columns)

                # Lặp qua từng dòng trong Excel
                for index, row in df.iterrows():
                    student_code = str(row[code_col]).strip()
                    name = str(row[name_col]).strip().upper()
                    s_class = str(row[class_col]).strip()
                
                    # Bỏ qua dòng trống
                    if not name or name.lower() == 'nan': 
                        continue
                    if not student_code or student_code.lower() == 'nan':
                        continue
                
                    entry = {
                        "name": name,
                        "class": s_class,
                        "student_code": student_code,
                    }
                    if parent_name_col:
                        pn = _excel_cell_str(row.get(parent_name_col))
                        if pn:
                            entry["parent_name"] = pn
                    if parent_phone_col:
                        pp = _excel_cell_str(row.get(parent_phone_col))
                        if pp:
                            entry["parent_phone"] = pp
                    if dob_col:
                        dob = _format_dob_from_excel_cell(row.get(dob_col))
                        if dob:
                            entry["date_of_birth"] = dob
                    if pos_col:
                        pos = _excel_cell_str(row.get(pos_col))
                        if pos:
                            entry["position"] = pos
                    if id_card_col:
                        idc = _excel_cell_str(row.get(id_card_col))
                        if idc:
                            entry["id_card"] = idc
                    if ethnicity_col:
                        eth = _excel_cell_str(row.get(ethnicity_col))
                        if eth:
                            entry["ethnicity"] = eth
                    preview_data.append(entry)
            
                # Chuyển sang trang xác nhận
                has_parent_cols = any(
                    e.get("parent_name") or e.get("parent_phone") for e in preview_data
                )
                has_dob_cols = bool(dob_col)
                has_position_cols = bool(pos_col)
                has_id_card_cols = bool(id_card_col)
                has_ethnicity_cols = bool(ethnicity_col)
                return render_template(
                    "confirm_import.html",
                    students=preview_data,
                    file_path=filepath,
                    has_parent_cols=has_parent_cols,
                    has_dob_cols=has_dob_cols,
                    has_position_cols=has_position_cols,
                    has_id_card_cols=has_id_card_cols,
                    has_ethnicity_cols=has_ethnicity_cols,
                )

            except Exception as e:
                flash(f"Lỗi đọc file: {str(e)}", "error")
                return redirect(request.url)

        return render_template("import_students.html")


    @app.route("/download_student_template")
    @login_required
    @permission_required('view_students')
    def download_student_template():
        """Download Excel template for student import"""
        sample_data = {
            'Mã học sinh': ['36 ANHA - 001001', '36 ANHA - 001002', '36 TINA - 001001'],
            'Họ và tên': ['Nguyễn Văn A', 'Trần Thị B', 'Lê Hoàng C'],
            'Lớp': ['10 Anh A', '10 Anh A', '10 Tin A'],
            'Ngày sinh': ['15/08/2008', '03/12/2008', '20/01/2008'],
            'CCCD/CMND': ['001201012345', '001201012346', '001201012347'],
            'Dân tộc': ['Kinh', 'Tày', 'Hmong'],
            'Chức vụ': ['Lớp trưởng', 'Bí thư', ''],
            'Họ tên phụ huynh': ['Nguyễn Văn Ph', 'Trần Thị X', 'Lê Văn Y'],
            'SĐT phụ huynh': ['0912345678', '0987654321', '0901122334'],
        }
        df = pd.DataFrame(sample_data)
    
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Danh sách học sinh')
        output.seek(0)
    
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='mau_nhap_hoc_sinh.xlsx'
        )




    @app.route("/save_imported_students", methods=["POST"])
    @login_required
    @admin_required
    def save_imported_students():
        """Bước 2: Lưu vào CSDL sau khi xác nhận"""
        filepath = request.form.get("file_path")
        if not filepath or not os.path.exists(filepath):
            flash("File nhập liệu không tồn tại hoặc đã hết hạn. Vui lòng thử lại.", "error")
            return redirect(url_for('import_students'))
        
        try:
            df = pd.read_excel(filepath)
            df.columns = [str(c).strip().lower() for c in df.columns]
        
            code_col = next((c for c in df.columns if "mã" in str(c).lower() or "code" in str(c).lower()), None)
            name_col = _student_name_column(df.columns)
            class_col = next((c for c in df.columns if "lớp" in str(c).lower() or "class" in str(c).lower()), None)
            parent_name_col, parent_phone_col = _find_parent_import_columns(df.columns)
            dob_col = _find_dob_column(df.columns)
            pos_col = _find_position_column(df.columns)
            id_card_col = _find_id_card_column(df.columns)
            ethnicity_col = _find_ethnicity_column(df.columns)
        
            count = 0
            skipped = 0
            for index, row in df.iterrows():
                student_code = str(row[code_col]).strip()
                name = str(row[name_col]).strip().upper()
                s_class = str(row[class_col]).strip()
            
                if not name or name.lower() == 'nan': continue
                if not student_code or student_code.lower() == 'nan': continue
            
                # 1. Kiểm tra trùng mã trong DB
                if Student.query.filter_by(student_code=student_code).first():
                    skipped += 1
                    continue 
            
                # 2. Tự động tạo Lớp mới nếu chưa có
                if not ClassRoom.query.filter_by(name=s_class).first():
                    db.session.add(ClassRoom(name=s_class))
            
                # 3. Thêm học sinh
                pn = _excel_cell_str(row.get(parent_name_col)) if parent_name_col else None
                pp = _excel_cell_str(row.get(parent_phone_col)) if parent_phone_col else None
                dob = _format_dob_from_excel_cell(row.get(dob_col)) if dob_col else None
                pos = _excel_cell_str(row.get(pos_col)) if pos_col else None
                idc = _excel_cell_str(row.get(id_card_col)) if id_card_col else None
                eth = _excel_cell_str(row.get(ethnicity_col)) if ethnicity_col else None
                new_student = Student(
                    name=name,
                    student_class=s_class,
                    student_code=student_code,
                    parent_name=pn,
                    parent_phone=pp,
                    date_of_birth=dob,
                    position=pos,
                    id_card=idc,
                    ethnicity=eth,
                )
                new_student.set_password("123456")  # Mật khẩu mặc định
                db.session.add(new_student)
            
                count += 1
            
            db.session.commit()
        
            # Cleanup
            if os.path.exists(filepath):
                os.remove(filepath)
            
            flash(f"Kết quả nhập liệu: Thêm mới {count} học sinh. Bỏ qua {skipped} học sinh (đã tồn tại).", "success" if count > 0 else "warning")
            return redirect(url_for('manage_students'))
        
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi khi lưu: {str(e)}", "error")
            return redirect(url_for('import_students'))
            return redirect(url_for('import_students'))
            flash(f"Lỗi khi lưu: {str(e)}", "error")
            return redirect(url_for('import_students'))
