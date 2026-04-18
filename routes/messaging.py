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
    GroupChatMessage, PrivateMessage, ChangeLog, StudentNotification,
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


    # === UNIFIED CHAT ROUTES ===

    @app.route("/chat")
    @login_required
    def unified_chat():
        """Trang chat thống nhất (gộp group chat và private chat)"""
        chat_type = request.args.get('type', 'group')  # 'group' or 'private'
        chat_id = request.args.get('id', type=int)
        
        # Lấy danh sách conversations private
        messages = PrivateMessage.query.filter(
            or_(
                PrivateMessage.sender_id == current_user.id,
                PrivateMessage.receiver_id == current_user.id
            )
        ).all()
    
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
    
        sorted_convs = sorted(conversations.items(), key=lambda x: x[1]['last_time'], reverse=True)
        
        # Lấy tin nhắn cuối của group chat
        group_last_msg = GroupChatMessage.query.order_by(GroupChatMessage.created_at.desc()).first()
        group_last_message = group_last_msg.message if group_last_msg else "Chưa có tin nhắn"
        
        # Danh sách tất cả giáo viên để chọn chat mới
        all_teachers = Teacher.query.filter(Teacher.id != current_user.id).order_by(Teacher.full_name).all()
        
        # Lấy tin nhắn hiển thị
        current_messages = []
        current_user_info = None
        if chat_type == 'group':
            current_messages = GroupChatMessage.query.order_by(GroupChatMessage.created_at.asc()).limit(100).all()
        elif chat_type == 'private' and chat_id:
            other = Teacher.query.get_or_404(chat_id)
            current_user_info = other
            if other.id == current_user.id:
                flash("Không thể chat với chính mình!", "error")
                return redirect(url_for('unified_chat', type='group'))
            
            current_messages = PrivateMessage.query.filter(
                or_(
                    and_(PrivateMessage.sender_id == current_user.id, PrivateMessage.receiver_id == chat_id),
                    and_(PrivateMessage.sender_id == chat_id, PrivateMessage.receiver_id == current_user.id)
                )
            ).order_by(PrivateMessage.created_at.asc()).all()
            
            # Đánh dấu tin nhắn đã đọc
            unread = PrivateMessage.query.filter_by(
                receiver_id=current_user.id,
                sender_id=chat_id,
                is_read=False
            ).all()
            for msg in unread:
                msg.is_read = True
            if unread:
                db.session.commit()
        else:
            # Mặc định hiển thị group chat
            chat_type = 'group'
            current_messages = GroupChatMessage.query.order_by(GroupChatMessage.created_at.asc()).limit(100).all()
        
        return render_template("unified_chat.html", 
                              current_type=chat_type,
                              current_id=chat_id,
                              current_user_info=current_user_info,
                              messages=current_messages,
                              conversations=sorted_convs,
                              group_last_message=group_last_message,
                              all_teachers=all_teachers)

    @app.route("/api/chat/send", methods=["POST"])
    @login_required
    def unified_send_message():
        """API gửi tin nhắn thống nhất"""
        data = request.json
        chat_type = data.get("type")  # 'group' or 'private'
        message_text = data.get("message", "").strip()
        
        if not message_text:
            return jsonify({"success": False, "error": "Tin nhắn trống"}), 400
        
        if chat_type == 'group':
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
        elif chat_type == 'private':
            receiver_id = data.get("receiver_id")
            
            if not receiver_id:
                return jsonify({"success": False, "error": "Thiếu receiver_id"}), 400
            
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
        else:
            return jsonify({"success": False, "error": "Invalid chat type"}), 400

    @app.route("/api/chat/messages")
    @login_required
    def unified_get_messages():
        """API lấy tin nhắn thống nhất"""
        chat_type = request.args.get('type')  # 'group' or 'private'
        chat_id = request.args.get('id', type=int)
        
        if chat_type == 'group':
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
        elif chat_type == 'private' and chat_id:
            messages = PrivateMessage.query.filter(
                or_(
                    and_(PrivateMessage.sender_id == current_user.id, PrivateMessage.receiver_id == chat_id),
                    and_(PrivateMessage.sender_id == chat_id, PrivateMessage.receiver_id == current_user.id)
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
        else:
            return jsonify({"success": False, "error": "Invalid parameters"}), 400

    # === STUDENT NOTIFICATION ROUTES ===

    @app.route("/student_notifications/send", methods=["GET", "POST"])
    @login_required
    def send_student_notification():
        """Soạn và gửi thông báo tới học sinh"""
        # Giới hạn chỉ Admin và GVCN có thể gửi (hoặc theo yêu cầu: GVCN + BGH)
        if current_user.role not in ['admin', 'homeroom_teacher']:
            flash("Bạn không có quyền thực hiện chức năng này!", "error")
            return redirect(url_for('dashboard'))

        if request.method == "POST":
            target = request.form.get("target")  # all, class, individual
            title = request.form.get("title")
            message = request.form.get("message")
            notif_type = request.form.get("notification_type", "announcement")
            
            if not title or not message:
                flash("Vui lòng nhập đầy đủ tiêu đề và nội dung!", "error")
            else:
                target_students = []
                if target == "all":
                    if current_user.role != 'admin':
                        flash("Chỉ Admin mới có thể gửi thông báo toàn trường!", "error")
                        return redirect(url_for('send_student_notification'))
                    target_students = Student.query.all()
                elif target == "class":
                    class_name = request.form.get("class_name")
                    if not class_name:
                        flash("Vui lòng chọn lớp!", "error")
                    else:
                        # GVCN chỉ được gửi cho lớp mình (nếu không phải admin)
                        if current_user.role == 'homeroom_teacher' and class_name != current_user.assigned_class:
                            flash("Bạn chỉ có thể gửi thông báo cho lớp mình chủ nhiệm!", "error")
                        else:
                            target_students = Student.query.filter_by(student_class=class_name).all()
                elif target == "individual":
                    student_id = request.form.get("student_id")
                    if not student_id:
                        flash("Vui lòng chọn học sinh!", "error")
                    else:
                        student = Student.query.get(student_id)
                        if student:
                            # GVCN chỉ được gửi cho HS lớp mình
                            if current_user.role == 'homeroom_teacher' and student.student_class != current_user.assigned_class:
                                flash("Bạn chỉ có thể gửi thông báo cho học sinh lớp mình chủ nhiệm!", "error")
                            else:
                                target_students = [student]

                if target_students:
                    for student in target_students:
                        notif = StudentNotification(
                            student_id=student.id,
                            title=title,
                            message=message,
                            notification_type=notif_type,
                            sender_id=current_user.id
                        )
                        db.session.add(notif)
                    db.session.commit()
                    log_change(
                        change_type="student_notification",
                        description=f"Gửi thông báo: {title} tới {len(target_students)} học sinh ({target})"
                    )
                    flash(f"Đã gửi thông báo tới {len(target_students)} học sinh thành công!", "success")
                    return redirect(url_for('student_notifications_history'))

        # Lấy dữ liệu cho form
        classes = db.session.query(Student.student_class).distinct().all()
        classes = [c[0] for c in classes]
        
        # Nếu là GVCN, chỉ lấy HS lớp mình (nếu target individual)
        if current_user.role == 'homeroom_teacher':
            students = Student.query.filter_by(student_class=current_user.assigned_class).order_by(Student.name).all()
        else:
            students = Student.query.order_by(Student.student_class, Student.name).all()

        return render_template("messaging/send_student_notification.html", 
                             classes=classes, 
                             students=students)

    @app.route("/student_notifications/history")
    @login_required
    def student_notifications_history():
        """Lịch sử thông báo đã gửi cho học sinh"""
        if current_user.role not in ['admin', 'homeroom_teacher']:
            flash("Bạn không có quyền thực hiện chức năng này!", "error")
            return redirect(url_for('dashboard'))

        # Lấy các thông báo do user này gửi
        sent_notifs = StudentNotification.query.filter_by(sender_id=current_user.id)\
            .order_by(StudentNotification.created_at.desc()).all()
            
        return render_template("messaging/student_notifications_history.html", notifications=sent_notifs)

    @app.route("/student_notifications/<int:nid>/recall", methods=["POST"])
    @login_required
    def student_notification_recall(nid):
        """Thu hồi (xoá) thông báo đã gửi tới học sinh"""
        notif = StudentNotification.query.get_or_404(nid)
        
        # Chỉ người gửi hoặc admin mới có quyền thu hồi
        if notif.sender_id != current_user.id and current_user.role != 'admin':
            flash("Bạn không có quyền thu hồi thông báo này!", "error")
            return redirect(url_for('student_notifications_history'))
            
        title = notif.title
        student_name = notif.student.name
        
        db.session.delete(notif)
        db.session.commit()
        
        log_change(
            change_type="student_notification_recall",
            description=f"Thu hồi thông báo: {title} đã gửi tới {student_name}"
        )
        
        flash("Đã thu hồi thông báo thành công!", "success")
        return redirect(url_for('student_notifications_history'))
