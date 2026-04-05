"""Routes cho hệ thống Điểm danh bằng Nhận diện Khuôn mặt.

Sử dụng DeepFace-style engine (ArcFace ONNX + OpenCV DNN).
Face data lấy từ ảnh thẻ (portrait_filename) của học sinh + mẫu camera.
"""
import os
import base64
import datetime
import uuid
import pickle

import cv2
import numpy as np

from flask import (
    render_template, request, jsonify, url_for,
)
from flask_login import login_required, current_user
from sqlalchemy import desc

from models import db, Student, AttendanceRecord, ClassRoom
from app_helpers import UPLOAD_FOLDER, log_change
from routes.face_engine import get_engine, cosine_similarity

# Thư mục lưu ảnh điểm danh
ATTENDANCE_PHOTO_DIR = os.path.join(UPLOAD_FOLDER, "attendance_photos")
os.makedirs(ATTENDANCE_PHOTO_DIR, exist_ok=True)

# Thư mục lưu mẫu khuôn mặt (nhiều mẫu/HS)
ENROLLMENT_DIR = os.path.join(UPLOAD_FOLDER, "face_enrollment")
os.makedirs(ENROLLMENT_DIR, exist_ok=True)

# Thư mục model cache — lưu embeddings (thay thế cho LBPH model cũ)
FACE_MODEL_DIR = os.path.join(UPLOAD_FOLDER, "face_models")
os.makedirs(FACE_MODEL_DIR, exist_ok=True)

# Ngưỡng similarity (ArcFace standard: 0.4)
RECOGNITION_THRESHOLD = 0.40


# ─────────────────────────── helpers ────────────────────────────

def _get_enrollment_path(student_id):
    """Đường dẫn thư mục chứa mẫu khuôn mặt của 1 HS."""
    path = os.path.join(ENROLLMENT_DIR, str(student_id))
    os.makedirs(path, exist_ok=True)
    return path


def _save_captured_photo(base64_data):
    """Lưu ảnh chụp từ camera (base64) thành file JPG."""
    try:
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
        image_bytes = base64.b64decode(base64_data)
        filename = f"attendance_{uuid.uuid4().hex[:12]}.jpg"
        filepath = os.path.join(ATTENDANCE_PHOTO_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return filename
    except Exception as e:
        print(f"[Attendance] Lỗi lưu ảnh: {e}")
        return None


def _base64_to_cv2(base64_data):
    """Chuyển base64 thành OpenCV image (numpy array)."""
    try:
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
        img_bytes = base64.b64decode(base64_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def _get_portrait_path(student):
    """Lấy đường dẫn tuyệt đối đến ảnh thẻ học sinh."""
    if not student or not student.portrait_filename:
        return None
    path = os.path.join(UPLOAD_FOLDER, "student_portraits", student.portrait_filename)
    return path if os.path.exists(path) else None


# ─────────────────────────── model I/O ────────────────────────────

def _get_embeddings_path(class_name="_GLOBAL_"):
    """Đường dẫn file embeddings."""
    safe_name = class_name.replace(" ", "_").replace("/", "_")
    return os.path.join(FACE_MODEL_DIR, f"arcface_{safe_name}.pkl")


def _get_student_list_path(class_name="_GLOBAL_"):
    """Đường dẫn file danh sách student_id tương ứng embedding."""
    safe_name = class_name.replace(" ", "_").replace("/", "_")
    return os.path.join(FACE_MODEL_DIR, f"arcface_students_{safe_name}.pkl")


def _train_model_for_class(class_name=None):
    """
    Trích xuất ArcFace embeddings cho tất cả học sinh.
    Nếu class_name=None hoặc "_GLOBAL_", xử lý toàn bộ học sinh trường.
    """
    if not class_name or class_name == "_GLOBAL_":
        students = Student.query.all()
        save_name = "_GLOBAL_"
    else:
        students = Student.query.filter_by(student_class=class_name).all()
        save_name = class_name

    engine = get_engine()
    student_ids = []
    embeddings_list = []  # list of np.arrays
    errors = []

    for s in students:
        sample_paths = []

        # 1. Ảnh thẻ
        p_path = _get_portrait_path(s)
        if p_path:
            sample_paths.append(p_path)

        # 2. Mẫu chụp từ camera
        e_dir = _get_enrollment_path(s.id)
        if os.path.exists(e_dir):
            for f in os.listdir(e_dir):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    sample_paths.append(os.path.join(e_dir, f))

        if not sample_paths:
            continue

        # Trích xuất embedding từ ảnh đầu tiên
        best_embedding = None
        for p in sample_paths:
            img = cv2.imread(p)
            if img is None:
                continue
            emb, _ = engine.extract_embedding(img)
            if emb is not None:
                best_embedding = emb
                break

        if best_embedding is not None:
            student_ids.append(s.id)
            embeddings_list.append(best_embedding)
        else:
            errors.append(f"HS {s.id} ({s.name}): không trích xuất được embedding")

    if errors:
        print(f"[Attendance] Training warnings: {errors}")

    if not student_ids:
        return 0

    # Lưu embeddings và student_ids
    embeddings_path = _get_embeddings_path(save_name)
    student_list_path = _get_student_list_path(save_name)

    with open(embeddings_path, "wb") as f:
        pickle.dump(embeddings_list, f)

    with open(student_list_path, "wb") as f:
        pickle.dump(student_ids, f)

    print(f"[Attendance] ArcFace model trained: {len(student_ids)} students")

    return len(student_ids)


def _load_embeddings(class_name):
    """Load embeddings và student_ids đã train."""
    embeddings_path = _get_embeddings_path(class_name)
    student_list_path = _get_student_list_path(class_name)

    if not os.path.exists(embeddings_path) or not os.path.exists(student_list_path):
        return None, None

    try:
        with open(embeddings_path, "rb") as f:
            embeddings_list = pickle.load(f)
        with open(student_list_path, "rb") as f:
            student_ids = pickle.load(f)
        return embeddings_list, student_ids
    except Exception as e:
        print(f"[Attendance] Lỗi load embeddings: {e}")
        return None, None


def _recognize_face(embedding, embeddings_list, student_ids):
    """
    So sánh embedding đầu vào với database.
    Trả về (student_id, cosine_similarity) hoặc (None, 0).
    """
    if embedding is None or embeddings_list is None or student_ids is None:
        return None, 0.0

    best_idx = -1
    best_score = 0.0

    for i, stored_emb in enumerate(embeddings_list):
        score = cosine_similarity(embedding, stored_emb)
        if score > best_score:
            best_score = score
            best_idx = i

    if best_score >= RECOGNITION_THRESHOLD and best_idx >= 0:
        return student_ids[best_idx], best_score

    return None, 0.0


# ─────────────────────────── Flask routes ────────────────────────────

def register(app):

    @app.route("/attendance")
    @login_required
    def attendance():
        """Trang điểm danh chính."""
        classes = [c.name for c in ClassRoom.query.order_by(ClassRoom.name).all()]
        selected_class = request.args.get("class_name", "")
        if not selected_class and current_user.role == "homeroom_teacher" and current_user.assigned_class:
            selected_class = current_user.assigned_class
        elif not selected_class and classes:
            selected_class = classes[0]

        # Kiểm tra model toàn trường
        model_ready = os.path.exists(_get_embeddings_path("_GLOBAL_"))

        return render_template(
            "attendance.html",
            classes=classes,
            selected_class=selected_class,
            model_ready=model_ready,
        )

    @app.route("/api/attendance/students")
    @login_required
    def api_attendance_students():
        """API lấy danh sách học sinh kèm trạng thái training chi tiết."""
        class_name = request.args.get("class_name", "")

        query = Student.query
        if class_name:
            query = query.filter_by(student_class=class_name)

        students = query.order_by(Student.name).all()
        today = datetime.date.today()

        # Kiểm tra student nào đã có embedding
        trained_ids = []
        embeddings_path = _get_embeddings_path(class_name if class_name else "_GLOBAL_")
        if os.path.exists(embeddings_path):
            _, sids = _load_embeddings(class_name if class_name else "_GLOBAL_")
            if sids:
                trained_ids = sids

        result = []
        for s in students:
            has_portrait = bool(s.portrait_filename) and _get_portrait_path(s) is not None
            e_dir = _get_enrollment_path(s.id)
            enrollment_count = 0
            if os.path.exists(e_dir):
                enrollment_count = len([
                    f for f in os.listdir(e_dir)
                    if f.lower().endswith(('.jpg', '.png'))
                ])

            already_checked = AttendanceRecord.query.filter_by(
                student_id=s.id, attendance_date=today
            ).first()

            result.append({
                "id": s.id,
                "name": s.name,
                "student_code": s.student_code,
                "student_class": s.student_class,
                "has_portrait": has_portrait,
                "enrollment_count": enrollment_count,
                "is_trained": s.id in trained_ids,
                "already_checked": bool(already_checked),
                "check_time": already_checked.check_in_time.strftime("%H:%M") if already_checked else None,
                "status": already_checked.status if already_checked else None,
            })

        return jsonify({"students": result})

    @app.route("/api/attendance/train", methods=["POST"])
    @login_required
    def api_attendance_train():
        """Huấn luyện model ArcFace (Ưu tiên toàn trường)."""
        data = request.get_json() or {}
        class_name = data.get("class_name", "_GLOBAL_")
        try:
            trained_count = _train_model_for_class(class_name)
            return jsonify({
                "success": True,
                "message": f"Đã huấn luyện ArcFace cho {trained_count} học sinh (Phạm vi: toàn trường).",
                "trained": trained_count
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"Lỗi huấn luyện: {str(e)}"}), 500

    @app.route("/api/attendance/enroll_camera", methods=["POST"])
    @login_required
    def api_attendance_enroll_camera():
        """Lưu mẫu khuôn mặt của 1 học sinh trực tiếp từ camera."""
        data = request.get_json() or {}
        student_id = data.get("student_id")
        image_base64 = data.get("image_base64")
        if not student_id or not image_base64:
            return jsonify({"error": "Thiếu thông tin."}), 400

        img = _base64_to_cv2(image_base64)
        engine = get_engine()
        faces = engine.detect_faces(img)

        if not faces:
            return jsonify({"error": "Không phát hiện khuôn mặt sắc nét. Hãy thử lại."}), 400

        # Lấ khuôn mặt lớn nhất
        best = max(faces, key=lambda f: f['box'][2] * f['box'][3])
        face_crop = best['face']
        box = best['box']

        # Lưu ảnh khuôn mặt đã crop (màu) để tăng chất lượng training
        e_dir = _get_enrollment_path(student_id)
        filename = f"sample_{uuid.uuid4().hex[:6]}.jpg"
        cv2.imwrite(os.path.join(e_dir, filename), face_crop)

        enrollment_count = 0
        if os.path.exists(e_dir):
            enrollment_count = len([
                f for f in os.listdir(e_dir)
                if f.lower().endswith(('.jpg', '.png'))
            ])

        return jsonify({
            "success": True,
            "message": f"Đã lưu mẫu khuôn mặt (Mẫu thứ {enrollment_count})",
            "enrollment_count": enrollment_count
        })

    @app.route("/api/attendance/reset_enrollment", methods=["POST"])
    @login_required
    def api_attendance_reset_enrollment():
        """Xóa toàn bộ mẫu camera của 1 học sinh."""
        data = request.get_json() or {}
        student_id = data.get("student_id")
        if not student_id:
            return jsonify({"error": "Thiếu student_id."}), 400
        e_dir = _get_enrollment_path(student_id)
        if os.path.exists(e_dir):
            import shutil
            try:
                shutil.rmtree(e_dir)
                os.makedirs(e_dir, exist_ok=True)
            except Exception:
                pass
        return jsonify({"success": True, "message": "Đã xóa toàn bộ mẫu của học sinh."})

    @app.route("/api/attendance/recognize", methods=["POST"])
    @login_required
    def api_attendance_recognize():
        """Nhận diện khuôn mặt từ ảnh camera dựa trên ArcFace embeddings (toàn trường)."""
        data = request.get_json() or {}
        image_base64 = data.get("image_base64", "")
        if not image_base64:
            return jsonify({"matched": False, "error": "Thiếu dữ liệu ảnh."}), 400

        # Luôn load embeddings toàn trường
        embeddings_list, student_ids = _load_embeddings("_GLOBAL_")
        if embeddings_list is None:
            # Fallback: thử embeddings theo lớp nếu có
            class_name = data.get("class_name", "")
            if class_name:
                embeddings_list, student_ids = _load_embeddings(class_name)

        if embeddings_list is None or student_ids is None:
            return jsonify({
                "matched": False,
                "error": "Chưa huấn luyện dữ liệu khuôn mặt toàn trường."
            })

        camera_img = _base64_to_cv2(image_base64)
        engine = get_engine()
        embedding, box = engine.extract_embedding(camera_img)

        if embedding is None:
            return jsonify({
                "matched": False,
                "error": "Không phát hiện khuôn mặt."
            })

        matched_id, similarity = _recognize_face(embedding, embeddings_list, student_ids)

        if matched_id is not None:
            student = db.session.get(Student, matched_id)
            if not student:
                return jsonify({
                    "matched": False,
                    "error": "Lỗi dữ liệu.",
                    "box": box
                })

            # similarity trong [0, 1], chuyển thành confidence
            confidence = round(max(0.0, min(1.0, (similarity - RECOGNITION_THRESHOLD) /
                                           (1.0 - RECOGNITION_THRESHOLD))), 2)
            if confidence < 0.1:
                confidence = 0.1

            captured_filename = _save_captured_photo(image_base64)
            return jsonify({
                "matched": True,
                "student_id": student.id,
                "student_name": student.name,
                "student_code": student.student_code,
                "confidence": confidence,
                "similarity": round(similarity, 4),
                "captured_photo": captured_filename,
                "box": box
            })

        return jsonify({
            "matched": False,
            "error": "Không nhận diện được học sinh.",
            "box": box
        })

    @app.route("/api/attendance/checkin", methods=["POST"])
    @login_required
    def api_attendance_checkin():
        """Ghi nhận điểm danh cho học sinh."""
        data = request.get_json() or {}
        student_id = data.get("student_id")
        captured_photo = data.get("captured_photo", "")
        confidence = data.get("confidence", 0)
        status = data.get("status", "Có mặt")
        notes = data.get("notes", "")
        image_base64 = data.get("image_base64", "")
        if not student_id:
            return jsonify({"error": "Thiếu student_id."}), 400
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"error": "Không tìm thấy học sinh."}), 404
        if AttendanceRecord.query.filter_by(student_id=student_id, attendance_date=datetime.date.today()).first():
            return jsonify({"error": f"{student.name} đã điểm danh hôm nay."})
        if not captured_photo and image_base64:
            captured_photo = _save_captured_photo(image_base64)
        record = AttendanceRecord(
            student_id=student_id, class_name=student.student_class,
            check_in_time=datetime.datetime.now(), captured_photo=captured_photo or "",
            confidence=confidence, status=status, notes=notes,
            recorded_by_id=current_user.id, attendance_date=datetime.date.today(),
        )
        db.session.add(record)
        db.session.commit()
        return jsonify({"success": True, "message": f"Đã điểm danh {student.name}."})

    @app.route("/api/attendance/history")
    @login_required
    def api_attendance_history():
        """API lấy lịch sử điểm danh."""
        class_name = request.args.get("class_name", "")
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        query = AttendanceRecord.query
        if class_name:
            query = query.filter_by(class_name=class_name)
        if date_from:
            try:
                d = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(AttendanceRecord.attendance_date >= d)
            except ValueError:
                pass
        if date_to:
            try:
                d = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
                query = query.filter(AttendanceRecord.attendance_date <= d)
            except ValueError:
                pass
        records = query.order_by(desc(AttendanceRecord.check_in_time)).limit(200).all()
        result = []
        for r in records:
            result.append({
                "id": r.id,
                "student_name": r.student.name if r.student else "N/A",
                "student_code": r.student.student_code if r.student else "",
                "class_name": r.class_name,
                "check_in_time": r.check_in_time.strftime("%H:%M:%S"),
                "attendance_date": r.attendance_date.strftime("%d/%m/%Y"),
                "status": r.status,
                "confidence": r.confidence,
                "captured_photo": r.captured_photo,
            })
        return jsonify({"records": result})

    @app.route("/uploads/attendance_photos/<path:filename>")
    @login_required
    def attendance_photo(filename):
        from flask import send_from_directory
        return send_from_directory(ATTENDANCE_PHOTO_DIR, filename)

    @app.route("/api/attendance/stats")
    @login_required
    def api_attendance_stats():
        class_name = request.args.get("class_name", "")
        today = datetime.date.today()

        if class_name:
            total_students = Student.query.filter_by(student_class=class_name).count()
            today_records = AttendanceRecord.query.filter_by(
                class_name=class_name, attendance_date=today
            ).all()
        else:
            total_students = Student.query.count()
            today_records = AttendanceRecord.query.filter_by(attendance_date=today).all()

        present = sum(1 for r in today_records if r.status == "Có mặt")
        late = sum(1 for r in today_records if r.status == "Trễ")
        return jsonify({
            "total": total_students,
            "present": present,
            "late": late,
            "absent": total_students - len(today_records),
        })

    @app.route("/api/attendance/model_status")
    @login_required
    def api_attendance_model_status():
        """Kiểm tra trạng thái model ArcFace."""
        class_name = request.args.get("class_name", "")
        embeddings_path = _get_embeddings_path(
            class_name if class_name else "_GLOBAL_"
        )
        ready = os.path.exists(embeddings_path)

        from routes.face_engine import DEFAULT_THRESHOLD as DF_THRESHOLD
        extra_info = {
            "model": "ArcFace (InsightFace buffalo_l)",
            "engine": "ONNX Runtime",
            "detector": "YOLOv8-face ONNX / Haar Cascade fallback",
            "threshold": RECOGNITION_THRESHOLD,
        }

        return jsonify({"ready": ready, "info": extra_info})

    @app.route("/api/attendance/delete/<int:record_id>", methods=["DELETE"])
    @login_required
    def api_attendance_delete(record_id):
        """Xóa một bản ghi điểm danh."""
        record = db.session.get(AttendanceRecord, record_id)
        if not record:
            return jsonify({"error": "Không tìm thấy dữ liệu điểm danh."}), 404

        # Chốt quyền: Admin hoặc chính người tạo bản ghi
        if current_user.role != 'admin' and record.recorded_by_id != current_user.id:
            return jsonify({"error": "Bạn không có quyền xóa dữ liệu này."}), 403

        try:
            # Xóa ảnh vật lý để tiết kiệm bộ nhớ
            if record.captured_photo:
                photo_path = os.path.join(ATTENDANCE_PHOTO_DIR, record.captured_photo)
                if os.path.exists(photo_path):
                    try:
                        os.remove(photo_path)
                    except Exception:
                        pass

            db.session.delete(record)
            db.session.commit()
            return jsonify({"success": True, "message": "Đã xóa dữ liệu điểm danh."})
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Lỗi hệ thống khi xóa: {str(e)}"}), 500
