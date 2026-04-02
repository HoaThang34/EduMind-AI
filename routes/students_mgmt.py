"""Routes: students_mgmt."""
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
    @app.route("/manage_students")
    @login_required
    def manage_students():
        # Lấy danh sách học sinh (filtered by role)
        students = get_accessible_students().order_by(Student.student_code.asc()).all()
        class_list = ClassRoom.query.order_by(ClassRoom.name).all()
        return render_template("manage_students.html", students=students, class_list=class_list)

    @app.route("/add_student", methods=["POST"])
    @login_required
    def add_student():
        db.session.add(Student(name=request.form["student_name"], student_code=request.form["student_code"], student_class=request.form["student_class"]))
        db.session.commit()
        flash("Thêm học sinh thành công", "success")
        return redirect(url_for("manage_students"))

    @app.route("/delete_student/<int:student_id>", methods=["POST"])
    @login_required
    def delete_student(student_id):
        s = db.session.get(Student, student_id)
        if s:
            Violation.query.filter_by(student_id=student_id).delete()
            db.session.delete(s)
            db.session.commit()
            flash("Đã xóa học sinh", "success")
        return redirect(url_for("manage_students"))

    @app.route("/edit_student/<int:student_id>", methods=["GET", "POST"])
    @login_required
    def edit_student(student_id):
        s = db.session.get(Student, student_id)
        if not s:
            flash("Không tìm thấy học sinh", "error")
            return redirect(url_for("manage_students"))
        
        if request.method == "POST":
            s.name = request.form["student_name"]
            s.student_code = request.form["student_code"]
            s.student_class = request.form["student_class"]
            db.session.commit()
            flash("Cập nhật thành công", "success")
            return redirect(url_for("manage_students"))
        
        return render_template("edit_student.html", student=s)

    @app.route("/add_class", methods=["POST"])
    @login_required
    def add_class():
        if not ClassRoom.query.filter_by(name=request.form["class_name"]).first():
            db.session.add(ClassRoom(name=request.form["class_name"]))
            db.session.commit()
        return redirect(url_for("manage_students"))
    #chỉnh sửa lớp học

    @app.route("/edit_class/<int:class_id>", methods=["POST"])
    @login_required
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
        return redirect(url_for("manage_students"))
    @app.route("/import_students", methods=["GET", "POST"])
    @login_required
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
                code_col = next((c for c in df.columns if "mã" in c or "code" in c), None)
                name_col = next((c for c in df.columns if "tên" in c or "name" in c), None)
                class_col = next((c for c in df.columns if "lớp" in c or "class" in c), None)
            
                if not code_col or not name_col or not class_col:
                    if os.path.exists(filepath): os.remove(filepath)
                    flash("File Excel cần có 3 cột: 'Mã học sinh', 'Họ và tên', 'Lớp'", "error")
                    return redirect(request.url)

                # Lặp qua từng dòng trong Excel
                for index, row in df.iterrows():
                    student_code = str(row[code_col]).strip()
                    name = str(row[name_col]).strip()
                    s_class = str(row[class_col]).strip()
                
                    # Bỏ qua dòng trống
                    if not name or name.lower() == 'nan': 
                        continue
                    if not student_code or student_code.lower() == 'nan':
                        continue
                
                    preview_data.append({
                        "name": name,
                        "class": s_class,
                        "student_code": student_code
                    })
            
                # Chuyển sang trang xác nhận
                return render_template("confirm_import.html", students=preview_data, file_path=filepath)

            except Exception as e:
                flash(f"Lỗi đọc file: {str(e)}", "error")
                return redirect(request.url)

        return render_template("import_students.html")


    @app.route("/download_student_template")
    @login_required
    def download_student_template():
        """Download Excel template for student import"""
        sample_data = {
            'Mã học sinh': ['36 ANHA - 001001', '36 ANHA - 001002', '36 TINA - 001001'],
            'Họ và tên': ['Nguyễn Văn A', 'Trần Thị B', 'Lê Hoàng C'],
            'Lớp': ['10 Anh A', '10 Anh A', '10 Tin A']
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
    def save_imported_students():
        """Bước 2: Lưu vào CSDL sau khi xác nhận"""
        filepath = request.form.get("file_path")
        if not filepath or not os.path.exists(filepath):
            flash("File nhập liệu không tồn tại hoặc đã hết hạn. Vui lòng thử lại.", "error")
            return redirect(url_for('import_students'))
        
        try:
            df = pd.read_excel(filepath)
            df.columns = [str(c).strip().lower() for c in df.columns]
        
            code_col = next((c for c in df.columns if "mã" in c or "code" in c), None)
            name_col = next((c for c in df.columns if "tên" in c or "name" in c), None)
            class_col = next((c for c in df.columns if "lớp" in c or "class" in c), None)
        
            count = 0
            skipped = 0
            for index, row in df.iterrows():
                student_code = str(row[code_col]).strip()
                name = str(row[name_col]).strip()
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
                new_student = Student(name=name, student_class=s_class, student_code=student_code)
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
