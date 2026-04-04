"""Quỹ lớp: thu từ phụ huynh, chi tiêu, số dư theo năm học."""
import datetime
import re
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import desc

from models import db, ClassRoom, ClassFundCollection, ClassFundExpense, Student, SystemConfig


def _default_school_year():
    row = SystemConfig.query.filter_by(key="school_year").first()
    return row.value.strip() if row and row.value else "2025-2026"


def _parse_amount_vnd(raw):
    if raw is None:
        return None
    s = re.sub(r"[^\d]", "", str(raw).strip())
    if not s:
        return None
    try:
        n = int(s)
    except ValueError:
        return None
    if n < 0:
        return None
    return n


def _selectable_classes():
    if not current_user.is_authenticated:
        return []
    if current_user.role == "admin":
        return [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
    if current_user.role == "homeroom_teacher" and current_user.assigned_class:
        return [current_user.assigned_class]
    return []


def _can_manage_class(class_name):
    if not current_user.is_authenticated or not class_name:
        return False
    if current_user.role == "admin":
        return True
    if current_user.role == "homeroom_teacher":
        return current_user.assigned_class == class_name
    return False


def register(app):
    @app.route("/class_fund", methods=["GET"])
    @login_required
    def class_fund():
        classes = _selectable_classes()
        if not classes:
            flash("Chỉ quản trị viên hoặc giáo viên chủ nhiệm mới quản lý được quỹ lớp.", "error")
            return redirect(url_for("home"))

        default_year = _default_school_year()
        school_year = request.args.get("school_year", default_year).strip() or default_year
        class_name = request.args.get("class_name", "").strip()

        if current_user.role == "homeroom_teacher":
            class_name = current_user.assigned_class
        elif not class_name:
            class_name = classes[0]

        if class_name not in classes:
            flash("Lớp không hợp lệ hoặc bạn không có quyền.", "error")
            return redirect(url_for("class_fund", school_year=school_year, class_name=classes[0]))

        collections = (
            ClassFundCollection.query.filter_by(class_name=class_name, school_year=school_year)
            .order_by(desc(ClassFundCollection.collection_date), desc(ClassFundCollection.id))
            .all()
        )
        expenses = (
            ClassFundExpense.query.filter_by(class_name=class_name, school_year=school_year)
            .order_by(desc(ClassFundExpense.expense_date), desc(ClassFundExpense.id))
            .all()
        )
        total_in = sum(c.amount_vnd for c in collections)
        total_out = sum(e.amount_vnd for e in expenses)
        balance = total_in - total_out

        students = (
            Student.query.filter_by(student_class=class_name).order_by(Student.name).all()
        )

        return render_template(
            "class_fund.html",
            classes=classes,
            class_name=class_name,
            school_year=school_year,
            default_school_year=default_year,
            collections=collections,
            expenses=expenses,
            total_in=total_in,
            total_out=total_out,
            balance=balance,
            students=students,
            today=datetime.date.today().isoformat(),
        )

    @app.route("/class_fund/collection", methods=["POST"])
    @login_required
    def class_fund_add_collection():
        classes = _selectable_classes()
        if not classes:
            abort(403)
        class_name = request.form.get("class_name", "").strip()
        school_year = request.form.get("school_year", _default_school_year()).strip() or _default_school_year()
        if not _can_manage_class(class_name) or class_name not in classes:
            flash("Không có quyền ghi nhận khoản thu cho lớp này.", "error")
            return redirect(url_for("class_fund"))

        amount = _parse_amount_vnd(request.form.get("amount_vnd"))
        purpose = (request.form.get("purpose") or "").strip()
        if amount is None or not purpose:
            flash("Số tiền và tên khoản thu là bắt buộc.", "error")
            return redirect(url_for("class_fund", class_name=class_name, school_year=school_year))

        payer_name = (request.form.get("payer_name") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None
        raw_date = (request.form.get("collection_date") or "").strip()
        try:
            collection_date = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else datetime.date.today()
        except ValueError:
            collection_date = datetime.date.today()

        student_id = request.form.get("student_id", type=int)
        if student_id:
            st = db.session.get(Student, student_id)
            if not st or st.student_class != class_name:
                flash("Học sinh không thuộc lớp đang chọn.", "error")
                return redirect(url_for("class_fund", class_name=class_name, school_year=school_year))
        else:
            student_id = None

        rec = ClassFundCollection(
            class_name=class_name,
            school_year=school_year,
            amount_vnd=amount,
            purpose=purpose,
            student_id=student_id,
            payer_name=payer_name,
            collection_date=collection_date,
            notes=notes,
            created_by_id=current_user.id,
        )
        db.session.add(rec)
        db.session.commit()
        flash("Đã ghi nhận khoản thu từ phụ huynh.", "success")
        return redirect(url_for("class_fund", class_name=class_name, school_year=school_year))

    @app.route("/class_fund/expense", methods=["POST"])
    @login_required
    def class_fund_add_expense():
        classes = _selectable_classes()
        if not classes:
            abort(403)
        class_name = request.form.get("class_name", "").strip()
        school_year = request.form.get("school_year", _default_school_year()).strip() or _default_school_year()
        if not _can_manage_class(class_name) or class_name not in classes:
            flash("Không có quyền ghi chi cho lớp này.", "error")
            return redirect(url_for("class_fund"))

        amount = _parse_amount_vnd(request.form.get("amount_vnd"))
        title = (request.form.get("title") or "").strip()
        if amount is None or not title:
            flash("Số tiền và nội dung chi là bắt buộc.", "error")
            return redirect(url_for("class_fund", class_name=class_name, school_year=school_year))

        notes = (request.form.get("notes") or "").strip() or None
        raw_date = (request.form.get("expense_date") or "").strip()
        try:
            expense_date = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else datetime.date.today()
        except ValueError:
            expense_date = datetime.date.today()

        rec = ClassFundExpense(
            class_name=class_name,
            school_year=school_year,
            amount_vnd=amount,
            title=title,
            expense_date=expense_date,
            notes=notes,
            created_by_id=current_user.id,
        )
        db.session.add(rec)
        db.session.commit()
        flash("Đã ghi nhận khoản chi.", "success")
        return redirect(url_for("class_fund", class_name=class_name, school_year=school_year))

    @app.route("/class_fund/collection/<int:cid>/delete", methods=["POST"])
    @login_required
    def class_fund_delete_collection(cid):
        classes = _selectable_classes()
        if not classes:
            abort(403)
        rec = db.session.get(ClassFundCollection, cid)
        if not rec:
            flash("Không tìm thấy bản ghi.", "error")
            return redirect(url_for("class_fund"))
        if not _can_manage_class(rec.class_name):
            flash("Không có quyền xóa.", "error")
            return redirect(url_for("class_fund"))
        class_name, school_year = rec.class_name, rec.school_year
        db.session.delete(rec)
        db.session.commit()
        flash("Đã xóa khoản thu.", "success")
        return redirect(url_for("class_fund", class_name=class_name, school_year=school_year))

    @app.route("/class_fund/expense/<int:eid>/delete", methods=["POST"])
    @login_required
    def class_fund_delete_expense(eid):
        classes = _selectable_classes()
        if not classes:
            abort(403)
        rec = db.session.get(ClassFundExpense, eid)
        if not rec:
            flash("Không tìm thấy bản ghi.", "error")
            return redirect(url_for("class_fund"))
        if not _can_manage_class(rec.class_name):
            flash("Không có quyền xóa.", "error")
            return redirect(url_for("class_fund"))
        class_name, school_year = rec.class_name, rec.school_year
        db.session.delete(rec)
        db.session.commit()
        flash("Đã xóa khoản chi.", "success")
        return redirect(url_for("class_fund", class_name=class_name, school_year=school_year))
