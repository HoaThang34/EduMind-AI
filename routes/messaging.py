"""Routes: messaging."""
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
    @app.route("/notifications")
    @login_required
    def notifications():
        """Xem danh sách thông báo"""
        notifs = Notification.query.filter_by(recipient_id=current_user.id)\
            .order_by(Notification.created_at.desc()).all()
        return render_template("notifications.html", notifications=notifs)

    @app.route("/api/mark_notification_read/<int:notif_id>", methods=["POST"])
    @login_required
    def mark_notification_read(notif_id):
        """Đánh dấu thông báo đã đọc"""
        notif = Notification.query.get(notif_id)
        if notif and notif.recipient_id == current_user.id:
            notif.is_read = True
            db.session.commit()
            return jsonify({"success": True})
        return jsonify({"success": False}), 403


    # === GROUP CHAT ROUTES ===

    @app.route("/group_chat")
    @login_required
    def group_chat():
        """Phòng chat chung"""
        messages = GroupChatMessage.query.order_by(GroupChatMessage.created_at.asc()).limit(100).all()
        return render_template("group_chat.html", messages=messages)

    @app.route("/api/group_chat/send", methods=["POST"])
    @login_required
    def send_group_message():
        """API gửi tin nhắn"""
        message_text = request.json.get("message", "").strip()
        if not message_text:
            return jsonify({"success": False, "error": "Tin nhắn trống"}), 400
    
        msg = GroupChatMessage(
            sender_id=current_user.id,
            message=message_text
        )
        db.session.add(msg)
        db.session.commit()
    
        return jsonify({
            "success": True,
            "message": {
                "id": msg.id,
                "sender_id": msg.sender_id,
                "sender_name": current_user.full_name,
                "message": msg.message,
                "created_at": msg.created_at.strftime("%H:%M %d/%m")
            }
        })

    @app.route("/api/group_chat/messages")
    @login_required
    def get_group_messages():
        """API lấy danh sách tin nhắn"""
        messages = GroupChatMessage.query.order_by(GroupChatMessage.created_at.asc()).limit(100).all()
        return jsonify({
            "messages": [
                {
                    "id": m.id,
                    "sender_id": m.sender_id,
                    "sender_name": m.sender.full_name,
                    "message": m.message,
                    "created_at": m.created_at.strftime("%H:%M %d/%m")
                }
                for m in messages
            ]
        })


    # === PRIVATE CHAT ROUTES ===

    @app.route("/private_chats")
    @login_required
    def private_chats():
        """Danh sách conversations (người đã chat)"""
        # Lấy tất cả tin nhắn mà user tham gia (gửi hoặc nhận)
        messages = PrivateMessage.query.filter(
            or_(
                PrivateMessage.sender_id == current_user.id,
                PrivateMessage.receiver_id == current_user.id
            )
        ).all()
    
        # Tạo dict: other_user_id -> latest_message
        conversations = {}
        for msg in messages:
            other_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
            if other_id not in conversations or msg.created_at > conversations[other_id]['last_time']:
                unread_count = PrivateMessage.query.filter_by(
                    sender_id=other_id,
                    receiver_id=current_user.id,
                    is_read=False
                ).count()
                conversations[other_id] = {
                    'user': Teacher.query.get(other_id),
                    'last_message': msg.message,
                    'last_time': msg.created_at,
                    'unread_count': unread_count
                }
    
        # Sort by last_time
        sorted_convs = sorted(conversations.items(), key=lambda x: x[1]['last_time'], reverse=True)
    
        # Danh sách tất cả giáo viên để chọn chat mới
        all_teachers = Teacher.query.filter(Teacher.id != current_user.id).order_by(Teacher.full_name).all()
    
        return render_template("private_chats.html", conversations=sorted_convs, all_teachers=all_teachers)

    @app.route("/private_chat/<int:teacher_id>")
    @login_required
    def private_chat(teacher_id):
        """Chat với 1 giáo viên cụ thể"""
        other = Teacher.query.get_or_404(teacher_id)
    
        if other.id == current_user.id:
            flash("Không thể chat với chính mình!", "error")
            return redirect(url_for('private_chats'))
    
        # Lấy tất cả tin nhắn giữa 2 người
        messages = PrivateMessage.query.filter(
            or_(
                and_(PrivateMessage.sender_id == current_user.id, PrivateMessage.receiver_id == teacher_id),
                and_(PrivateMessage.sender_id == teacher_id, PrivateMessage.receiver_id == current_user.id)
            )
        ).order_by(PrivateMessage.created_at.asc()).all()
    
        # Đánh dấu tin nhắn của người kia gửi đến mình là đã đọc
        unread = PrivateMessage.query.filter_by(
            receiver_id=current_user.id,
            sender_id=teacher_id,
            is_read=False
        ).all()
        for msg in unread:
            msg.is_read = True
        if unread:
            db.session.commit()
    
        return render_template("private_chat.html", other=other, messages=messages)

    @app.route("/api/private_chat/send", methods=["POST"])
    @login_required
    def send_private_message():
        """API gửi tin nhắn riêng"""
        receiver_id = request.json.get("receiver_id")
        message_text = request.json.get("message", "").strip()
    
        if not receiver_id or not message_text:
            return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    
        if int(receiver_id) == current_user.id:
            return jsonify({"success": False, "error": "Không thể gửi cho chính mình"}), 400
    
        msg = PrivateMessage(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            message=message_text
        )
        db.session.add(msg)
        db.session.commit()
    
        return jsonify({
            "success": True,
            "message": {
                "id": msg.id,
                "sender_id": msg.sender_id,
                "sender_name": current_user.full_name,
                "message": msg.message,
                "created_at": msg.created_at.strftime("%H:%M %d/%m")
            }
        })

    @app.route("/api/private_chat/messages/<int:teacher_id>")
    @login_required
    def get_private_messages(teacher_id):
        """API lấy tin nhắn với 1 người"""
        messages = PrivateMessage.query.filter(
            or_(
                and_(PrivateMessage.sender_id == current_user.id, PrivateMessage.receiver_id == teacher_id),
                and_(PrivateMessage.sender_id == teacher_id, PrivateMessage.receiver_id == current_user.id)
            )
        ).order_by(PrivateMessage.created_at.asc()).all()
    
        return jsonify({
            "messages": [
                {
                    "id": m.id,
                    "sender_id": m.sender_id,
                    "sender_name": m.sender.full_name,
                    "message": m.message,
                    "created_at": m.created_at.strftime("%H:%M %d/%m")
                }
                for m in messages
            ]
        })
