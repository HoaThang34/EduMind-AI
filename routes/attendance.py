"""Routes cho hệ thống Điểm danh bằng Nhận diện Khuôn mặt và Mã QR.

Hỗ trợ 2 chế độ:
  - Face Mode  : Nhận diện khuôn mặt qua ArcFace ONNX
  - QR Mode    : Quét mã QR trên thẻ học sinh để điểm danh
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
from urllib.parse import quote

from models import db, Student, AttendanceRecord, ClassRoom, AttendanceMonitoringSession, SessionViolationRecord, ViolationType, Violation, SystemConfig
from app_helpers import UPLOAD_FOLDER, log_change, update_student_conduct
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


def make_attendance_qr_data(student_id):
    """
    Sinh dữ liệu cho mã QR điểm danh.
    QR chứa trực tiếp student_id dạng text — KHÔNG dùng token.
    Format: "EDUATT:{student_id}"
    """
    return f"EDUATT:{student_id}"


def parse_attendance_qr(qr_data):
    """
    Đọc student_id từ nội dung QR.
    Format: "EDUATT:{student_id}"
    Trả về (student_id: int hoặc None, error: str hoặc None)
    """
    if not qr_data:
        return None, "empty"
    qr_data = qr_data.strip()
    if qr_data.startswith("EDUATT:"):
        try:
            return int(qr_data.split(":")[1]), None
        except (ValueError, IndexError):
            return None, "invalid"
    # Legacy support: nếu QR chứa trực tiếp student_id dạng số
    try:
        return int(qr_data), None
    except ValueError:
        return None, "invalid_format"


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
            violation_rules=ViolationType.query.all(),
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

            today_records = AttendanceRecord.query.filter_by(
                student_id=s.id, attendance_date=today
            ).order_by(AttendanceRecord.check_in_time).all()

            result.append({
                "id": s.id,
                "name": s.name,
                "student_code": s.student_code,
                "student_class": s.student_class,
                "has_portrait": has_portrait,
                "enrollment_count": enrollment_count,
                "is_trained": s.id in trained_ids,
                "already_checked": len(today_records) > 0,
                "check_times": [r.check_in_time.strftime("%H:%M") for r in today_records],
                "total_today": len(today_records),
                "status": today_records[-1].status if today_records else None,
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
        if not captured_photo and image_base64:
            captured_photo = _save_captured_photo(image_base64)
        record = AttendanceRecord(
            student_id=student_id, class_name=student.student_class,
            check_in_time=datetime.datetime.now(), captured_photo=captured_photo or "",
            confidence=confidence, status=status, notes=notes,
            recorded_by_id=current_user.id, attendance_date=datetime.date.today(),
        )
        db.session.add(record)
        db.session.flush()

        # ── Auto-detect: nếu có phiên theo dõi đang mở cho lớp này ──
        auto_detected = None
        now = datetime.datetime.now()
        today_date = datetime.date.today()
        now_min = now.hour * 60 + now.minute

        # Lọc theo lớp + ngày + trạng thái, sau đó so sánh CHỈ giờ-phút
        candidate_sessions = AttendanceMonitoringSession.query.filter_by(
            class_name=student.student_class,
            session_date=today_date,
            status="open",
        ).all()
        open_session = None
        for s in candidate_sessions:
            start_min = s.start_time.hour * 60 + s.start_time.minute
            end_min = s.end_time.hour * 60 + s.end_time.minute if s.end_time else 24 * 60
            if start_min <= now_min <= end_min:
                open_session = s
                break
        if open_session:
            record.monitoring_session_id = open_session.id
            viol = SessionViolationRecord(
                session_id=open_session.id,
                student_id=student_id,
                violation_type_name="___auto___",
                points_deducted=0,
                status="pending",
                notes="Tự động phát hiện khi điểm danh trong giờ theo dõi",
            )
            db.session.add(viol)
            db.session.flush()
            auto_detected = {
                "violation_id": viol.id,
                "session_id": open_session.id,
                "recorded_at": viol.recorded_at.strftime("%H:%M"),
            }

        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Đã điểm danh {student.name}.",
            "auto_detected": auto_detected,
        })

    @app.route("/api/attendance/history")
    @login_required
    def api_attendance_history():
        """API lấy lịch sử điểm danh. Hỗ trợ lọc theo mode (face/qr)."""
        class_name = request.args.get("class_name", "")
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        mode_filter = request.args.get("mode", "")  # 'face', 'qr', hoặc '' (tất cả)
        query = AttendanceRecord.query
        if class_name:
            query = query.filter_by(class_name=class_name)
        if mode_filter in ("face", "qr"):
            query = query.filter_by(attendance_mode=mode_filter)
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
        records = query.order_by(
            AttendanceRecord.attendance_date.desc(),
            AttendanceRecord.check_in_time.desc(),
        ).limit(500).all()

        # Mỗi HS mỗi ngày chỉ lấy bản ghi MỚI NHẤT
        seen = {}  # (student_id, date_str) -> record
        for r in records:
            key = (r.student_id, r.attendance_date)
            if key not in seen:
                seen[key] = r

        result = []
        for r in seen.values():
            result.append({
                "id": r.id,
                "student_id": r.student_id,
                "student_name": r.student.name if r.student else "N/A",
                "student_code": r.student.student_code if r.student else "",
                "class_name": r.class_name,
                "check_in_time": r.check_in_time.strftime("%H:%M:%S"),
                "attendance_date": r.attendance_date.strftime("%d/%m/%Y"),
                "status": r.status,
                "confidence": r.confidence,
                "captured_photo": r.captured_photo,
                "mode": r.attendance_mode or "face",
                "total_checkins_today": AttendanceRecord.query.filter_by(
                    student_id=r.student_id, attendance_date=r.attendance_date
                ).count(),
            })
        return jsonify({"records": result})

    @app.route("/api/attendance/history/<int:student_id>")
    @login_required
    def api_attendance_history_detail(student_id):
        """
        API chi tiết: tất cả lượt điểm danh của 1 học sinh.
        Trả về nhóm theo ngày.
        """
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"error": "Không tìm thấy học sinh."}), 404

        records = AttendanceRecord.query.filter_by(student_id=student_id).order_by(
            desc(AttendanceRecord.attendance_date),
            desc(AttendanceRecord.check_in_time),
        ).limit(500).all()

        # Nhóm theo ngày
        from collections import defaultdict
        by_date = defaultdict(list)
        for r in records:
            date_key = r.attendance_date.strftime("%d/%m/%Y")
            by_date[date_key].append({
                "id": r.id,
                "check_in_time": r.check_in_time.strftime("%H:%M:%S"),
                "status": r.status,
                "mode": r.attendance_mode or "face",
                "notes": r.notes or "",
            })

        return jsonify({
            "student": {
                "id": student.id,
                "name": student.name,
                "student_code": student.student_code,
                "student_class": student.student_class,
            },
            "by_date": dict(by_date),
            "total_records": len(records),
        })

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

        # Đếm theo HỌC SINH DUY NHẤT — mỗi HS chỉ tính 1 lần
        present_students = set()
        late_students = set()
        for r in today_records:
            if r.status == "Có mặt":
                present_students.add(r.student_id)
            elif r.status == "Trễ":
                late_students.add(r.student_id)

        # Ưu tiên: Có mặt > Trễ (nếu HS có cả 2, chỉ tính Có mặt)
        late_students -= present_students

        return jsonify({
            "total": total_students,
            "present": len(present_students),
            "late": len(late_students),
            "absent": total_students - len(present_students) - len(late_students),
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

    @app.route("/api/attendance/delete/bulk", methods=["POST"])
    @login_required
    def api_attendance_delete_bulk():
        """Xóa nhiều bản ghi điểm danh cùng lúc."""
        data = request.get_json() or {}
        record_ids = data.get("record_ids", [])

        if not record_ids:
            return jsonify({"error": "Không có bản ghi nào được chọn."}), 400

        if not isinstance(record_ids, list):
            return jsonify({"error": "Dữ liệu không hợp lệ."}), 400

        deleted_count = 0
        for rid in record_ids:
            record = db.session.get(AttendanceRecord, rid)
            if record:
                # Chốt quyền: Admin hoặc chính người tạo bản ghi
                if current_user.role != 'admin' and record.recorded_by_id != current_user.id:
                    continue
                # Xóa ảnh vật lý
                if record.captured_photo:
                    photo_path = os.path.join(ATTENDANCE_PHOTO_DIR, record.captured_photo)
                    if os.path.exists(photo_path):
                        try:
                            os.remove(photo_path)
                        except Exception:
                            pass
                db.session.delete(record)
                deleted_count += 1

        try:
            db.session.commit()
            return jsonify({
                "success": True,
                "message": f"Đã xóa {deleted_count} bản ghi.",
                "deleted_count": deleted_count,
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Lỗi hệ thống khi xóa: {str(e)}"}), 500

    @app.route("/api/attendance/qr/checkin", methods=["POST"])
    @login_required
    def api_attendance_qr_checkin():
        """
        Điểm danh bằng mã QR.
        Payload: { "qr_data": "<nội dung QR>" }
        QR chứa trực tiếp student_id dạng "EDUATT:{id}" — không hết hạn.
        """
        data = request.get_json() or {}
        qr_data = data.get("qr_data", "").strip()
        if not qr_data:
            return jsonify({"error": "Thiếu mã QR."}), 400

        sid, parse_err = parse_attendance_qr(qr_data)
        if not sid:
            return jsonify({"matched": False, "error": f"Mã QR không hợp lệ ({parse_err})."}), 400

        student = db.session.get(Student, sid)
        if not student:
            return jsonify({"matched": False, "error": "Không tìm thấy học sinh trong hệ thống."}), 404

        today = datetime.date.today()

        record = AttendanceRecord(
            student_id=sid,
            class_name=student.student_class,
            check_in_time=datetime.datetime.now(),
            captured_photo="",
            confidence=1.0,
            status="Có mặt",
            notes="Điểm danh qua mã QR",
            recorded_by_id=current_user.id,
            attendance_date=today,
            attendance_mode="qr",
            qr_scan_method="camera",
        )
        db.session.add(record)
        db.session.flush()

        # ── Auto-detect: nếu có phiên theo dõi đang mở cho lớp này ──
        auto_detected = None
        now = datetime.datetime.now()
        now_min = now.hour * 60 + now.minute

        candidate_sessions = AttendanceMonitoringSession.query.filter_by(
            class_name=student.student_class,
            session_date=today,
            status="open",
        ).all()
        open_session = None
        for s in candidate_sessions:
            start_min = s.start_time.hour * 60 + s.start_time.minute
            end_min = s.end_time.hour * 60 + s.end_time.minute if s.end_time else 24 * 60
            if start_min <= now_min <= end_min:
                open_session = s
                break
        if open_session:
            record.monitoring_session_id = open_session.id
            viol = SessionViolationRecord(
                session_id=open_session.id,
                student_id=sid,
                violation_type_name="___auto___",
                points_deducted=0,
                status="pending",
                notes="Tự động phát hiện khi điểm danh trong giờ theo dõi",
            )
            db.session.add(viol)
            db.session.flush()
            auto_detected = {
                "violation_id": viol.id,
                "session_id": open_session.id,
                "recorded_at": viol.recorded_at.strftime("%H:%M"),
            }

        db.session.commit()
        return jsonify({
            "matched": True,
            "already_checked": False,
            "student_id": student.id,
            "student_name": student.name,
            "student_code": student.student_code,
            "student_class": student.student_class,
            "message": f"Đã điểm danh {student.name} lúc {record.check_in_time.strftime('%H:%M:%S')}."
        })

    @app.route("/api/attendance/qr/token", methods=["GET"])
    @login_required
    def api_attendance_qr_token():
        """
        Sinh dữ liệu QR cho 1 học sinh (không dùng token — dùng trực tiếp student_id).
        Query params: student_id
        """
        student_id = request.args.get("student_id", type=int)
        if not student_id:
            return jsonify({"error": "Thiếu student_id."}), 400

        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"error": "Không tìm thấy học sinh."}), 404

        qr_data = make_attendance_qr_data(student_id)
        qr_api_url = (
            f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data="
            f"{quote(qr_data, safe='')}"
        )

        return jsonify({
            "student_id": student_id,
            "student_name": student.name,
            "student_code": student.student_code,
            "qr_data": qr_data,
            "qr_image_url": qr_api_url,
        })

    @app.route("/api/attendance/qr/auto-checkin", methods=["POST"])
    @login_required
    def api_attendance_qr_auto_checkin():
        """
        Điểm danh tự động khi trang QR được mở.
        Payload: { "qr_data": "<nội dung QR>" }
        """
        data = request.get_json() or {}
        qr_data = data.get("qr_data", "").strip()
        if not qr_data:
            return jsonify({"error": "Thiếu mã QR."}), 400

        sid, parse_err = parse_attendance_qr(qr_data)
        if not sid:
            return jsonify({"success": False, "error": f"Mã QR không hợp lệ ({parse_err})."}), 400

        student = db.session.get(Student, sid)
        if not student:
            return jsonify({"success": False, "error": "Không tìm thấy học sinh."}), 404

        today = datetime.date.today()
        record = AttendanceRecord(
            student_id=sid,
            class_name=student.student_class,
            check_in_time=datetime.datetime.now(),
            captured_photo="",
            confidence=1.0,
            status="Có mặt",
            notes="Điểm danh tự động qua mã QR",
            recorded_by_id=current_user.id,
            attendance_date=today,
            attendance_mode="qr",
            qr_scan_method="direct",
        )
        db.session.add(record)
        db.session.commit()
        return jsonify({
            "success": True,
            "already_checked": False,
            "student_name": student.name,
            "check_time": record.check_in_time.strftime("%H:%M:%S"),
        })

    @app.route("/api/attendance/qr/status/<int:student_id>")
    @login_required
    def api_attendance_qr_status(student_id):
        """
        API chỉ-đọc: lấy danh sách lượt điểm danh QR hôm nay của 1 học sinh.
        Payload: { "qr_data": "<EDUATT:{id}>" }
        KHÔNG tạo bản ghi mới.
        """
        qr_data = request.args.get("qr_data", "").strip()
        if qr_data:
            sid, _ = parse_attendance_qr(qr_data)
            if sid:
                student_id = sid

        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"error": "Không tìm thấy học sinh."}), 404

        today = datetime.date.today()
        records = AttendanceRecord.query.filter_by(
            student_id=student_id, attendance_date=today, attendance_mode="qr"
        ).order_by(AttendanceRecord.check_in_time).all()

        return jsonify({
            "student_id": student_id,
            "student_name": student.name,
            "records": [
                {
                    "check_time": r.check_in_time.strftime("%H:%M:%S"),
                    "status": r.status,
                }
                for r in records
            ],
            "total_today": len(records),
        })

    @app.route("/api/attendance/qr/url-for-student/<int:student_id>")
    @login_required
    def api_attendance_qr_url(student_id):
        """
        Trả về QR data và URL ảnh QR của 1 học sinh (dùng cho in ấn / gửi phụ huynh).
        QR chứa trực tiếp student_id — không hết hạn.
        """
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"error": "Không tìm thấy học sinh."}), 404

        qr_data = make_attendance_qr_data(student_id)
        qr_api_url = (
            f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data="
            f"{quote(qr_data, safe='')}"
        )
        return jsonify({
            "student_id": student_id,
            "student_name": student.name,
            "student_code": student.student_code,
            "qr_data": qr_data,
            "qr_image_url": qr_api_url,
        })

    # ──────────── MONITORING SESSION APIs ────────────

    @app.route("/api/attendance/monitoring/sessions")
    @login_required
    def api_monitoring_sessions():
        """API lấy danh sách phiên theo dõi (hỗ trợ lọc theo ngày, lớp, trạng thái)."""
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        class_filter = request.args.get("class_name", "")
        status_filter = request.args.get("status", "")

        query = AttendanceMonitoringSession.query

        if date_from:
            try:
                d = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(AttendanceMonitoringSession.session_date >= d)
            except ValueError:
                pass
        if date_to:
            try:
                d = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
                query = query.filter(AttendanceMonitoringSession.session_date <= d)
            except ValueError:
                pass
        if class_filter:
            query = query.filter_by(class_name=class_filter)
        if status_filter in ("open", "confirmed", "cancelled"):
            query = query.filter_by(status=status_filter)

        # Nếu là GVCN, chỉ thấy phiên của lớp mình
        if current_user.role == "homeroom_teacher" and current_user.assigned_class:
            query = query.filter_by(class_name=current_user.assigned_class)

        sessions = query.order_by(
            AttendanceMonitoringSession.session_date.desc(),
            AttendanceMonitoringSession.start_time.desc(),
        ).limit(200).all()

        result = []
        for s in sessions:
            pending_count = SessionViolationRecord.query.filter_by(
                session_id=s.id, status="pending"
            ).count()
            result.append({
                "id": s.id,
                "class_name": s.class_name,
                "start_time": s.start_time.strftime("%H:%M"),
                "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
                "session_date": s.session_date.strftime("%d/%m/%Y"),
                "status": s.status,
                "pending_violations": pending_count,
                "teacher_name": s.teacher.full_name if s.teacher else "N/A",
            })
        return jsonify({"sessions": result})

    @app.route("/api/attendance/monitoring/create-session", methods=["POST"])
    @login_required
    def api_create_monitoring_session():
        """Tạo mới một phiên theo dõi điểm danh theo giờ."""
        data = request.get_json() or {}
        class_name = data.get("class_name", "")
        start_time_str = data.get("start_time", "")   # "07:00"
        end_time_str = data.get("end_time", "")       # "08:00"
        notes = data.get("notes", "")

        if not class_name:
            return jsonify({"error": "Thiếu thông tin lớp."}), 400
        if not start_time_str:
            return jsonify({"error": "Thiếu giờ bắt đầu."}), 400

        try:
            today_date = datetime.date.today()
            start_dt = datetime.datetime.combine(today_date, datetime.time.fromisoformat(start_time_str))
            end_dt = None
            if end_time_str:
                end_dt = datetime.datetime.combine(today_date, datetime.time.fromisoformat(end_time_str))
        except ValueError:
            return jsonify({"error": "Định dạng giờ không hợp lệ (VD: 07:00)."}), 400

        today = datetime.date.today()

        # Kiểm tra: không tạo trùng phiên cùng lớp cùng giờ nếu đang mở
        existing = AttendanceMonitoringSession.query.filter_by(
            class_name=class_name,
            session_date=today,
            status="open",
        ).first()
        if existing:
            return jsonify({
                "error": f"Phiên theo dõi lớp {class_name} đang mở từ {existing.start_time.strftime('%H:%M')}. Vui lòng đóng phiên cũ trước."
            }), 409

        session = AttendanceMonitoringSession(
            teacher_id=current_user.id,
            class_name=class_name,
            start_time=start_dt,
            end_time=end_dt,
            session_date=today,
            status="open",
            notes=notes,
        )
        db.session.add(session)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Đã mở phiên theo dõi lớp {class_name} từ {start_time_str}.",
            "session_id": session.id,
        })

    @app.route("/api/attendance/monitoring/session/<int:session_id>")
    @login_required
    def api_monitoring_session_detail(session_id):
        """API lấy chi tiết 1 phiên theo dõi (gồm các vi phạm đã đánh dấu)."""
        session = db.session.get(AttendanceMonitoringSession, session_id)
        if not session:
            return jsonify({"error": "Không tìm thấy phiên."}), 404

        # Kiểm tra quyền truy cập
        if current_user.role == "homeroom_teacher" and current_user.assigned_class:
            if session.class_name != current_user.assigned_class:
                return jsonify({"error": "Bạn không có quyền xem phiên này."}), 403

        # Lấy danh sách vi phạm trong phiên
        from sqlalchemy import desc as sql_desc
        viol_records = SessionViolationRecord.query.filter_by(
            session_id=session_id
        ).order_by(SessionViolationRecord.recorded_at.desc()).all()

        students = Student.query.filter_by(student_class=session.class_name).order_by(Student.name).all()

        return jsonify({
            "session": {
                "id": session.id,
                "class_name": session.class_name,
                "start_time": session.start_time.strftime("%H:%M"),
                "end_time": session.end_time.strftime("%H:%M") if session.end_time else None,
                "session_date": session.session_date.strftime("%d/%m/%Y"),
                "status": session.status,
                "notes": session.notes or "",
                "teacher_name": session.teacher.full_name if session.teacher else "N/A",
            },
            "violation_types": [{"id": v.id, "name": v.name, "points_deducted": v.points_deducted}
                                for v in ViolationType.query.all()],
            "students": [{
                "id": s.id,
                "name": s.name,
                "student_code": s.student_code,
            } for s in students],
            "violations": [{
                "id": v.id,
                "student_id": v.student_id,
                "student_name": v.student.name if v.student else "?",
                "student_code": v.student.student_code if v.student else "",
                "violation_type_name": v.violation_type_name,
                "points_deducted": v.points_deducted,
                "status": v.status,
                "recorded_at": v.recorded_at.strftime("%H:%M"),
                "notes": v.notes or "",
            } for v in viol_records],
        })

    @app.route("/api/attendance/monitoring/add-violation", methods=["POST"])
    @login_required
    def api_add_session_violation():
        """Đánh dấu một học sinh vi phạm trong phiên theo dõi (chưa xác nhận)."""
        data = request.get_json() or {}
        session_id = data.get("session_id")
        student_id = data.get("student_id")
        violation_type_name = data.get("violation_type_name", "")
        notes = data.get("notes", "")

        if not session_id or not student_id or not violation_type_name:
            return jsonify({"error": "Thiếu thông tin bắt buộc."}), 400

        session = db.session.get(AttendanceMonitoringSession, session_id)
        if not session:
            return jsonify({"error": "Không tìm thấy phiên."}), 404
        if session.status != "open":
            return jsonify({"error": "Phiên đã đóng hoặc bị hủy, không thể thêm vi phạm."}), 400

        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"error": "Không tìm thấy học sinh."}), 404

        # Kiểm tra trùng vi phạm cùng loại trong phiên (tránh đánh dấu 2 lần cùng 1 lỗi)
        existing = SessionViolationRecord.query.filter_by(
            session_id=session_id,
            student_id=student_id,
            violation_type_name=violation_type_name,
            status="pending",
        ).first()
        if existing:
            return jsonify({"error": f"{student.name} đã được đánh dấu vi phạm '{violation_type_name}' trong phiên này."}), 409

        # Tìm điểm trừ
        rule = ViolationType.query.filter_by(name=violation_type_name).first()
        points = rule.points_deducted if rule else 0

        record = SessionViolationRecord(
            session_id=session_id,
            student_id=student_id,
            violation_type_name=violation_type_name,
            points_deducted=points,
            status="pending",
            notes=notes,
        )
        db.session.add(record)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Đã đánh dấu vi phạm '{violation_type_name}' cho {student.name}.",
            "record_id": record.id,
            "points_deducted": points,
        })

    @app.route("/api/attendance/monitoring/remove-violation", methods=["POST"])
    @login_required
    def api_remove_session_violation():
        """Xóa bỏ một bản ghi vi phạm trong phiên (chỉ pending)."""
        data = request.get_json() or {}
        record_id = data.get("record_id")
        if not record_id:
            return jsonify({"error": "Thiếu record_id."}), 400

        record = db.session.get(SessionViolationRecord, record_id)
        if not record:
            return jsonify({"error": "Không tìm thấy bản ghi."}), 404
        if record.status != "pending":
            return jsonify({"error": "Chỉ xóa được bản ghi chưa xác nhận."}), 400

        session = db.session.get(AttendanceMonitoringSession, record.session_id)
        if session and session.status != "open":
            return jsonify({"error": "Phiên đã đóng, không thể xóa."}), 400

        db.session.delete(record)
        db.session.commit()
        return jsonify({"success": True, "message": "Đã xóa bản ghi vi phạm."})

    @app.route("/api/attendance/monitoring/update-violation-type", methods=["POST"])
    @login_required
    def api_update_violation_type():
        """
        Cập nhật loại vi phạm cho bản ghi trong phiên.
        - Nếu bản ghi đang là placeholder '___auto___': cập nhật trực tiếp.
        - Nếu bản ghi đã có loại thực: xóa bản ghi cũ, tạo bản ghi mới với loại mới.
        Payload: { violation_id, violation_type_name }
        """
        data = request.get_json() or {}
        violation_id = data.get("violation_id")
        violation_type_name = data.get("violation_type_name", "").strip()

        if not violation_id:
            return jsonify({"error": "Thiếu violation_id."}), 400
        if not violation_type_name:
            return jsonify({"error": "Thiếu loại vi phạm."}), 400

        record = db.session.get(SessionViolationRecord, violation_id)
        if not record:
            return jsonify({"error": "Không tìm thấy bản ghi vi phạm."}), 404
        if record.status != "pending":
            return jsonify({"error": "Chỉ cập nhật được bản ghi chưa xác nhận."}), 400

        session = db.session.get(AttendanceMonitoringSession, record.session_id)
        if session and session.status != "open":
            return jsonify({"error": "Phiên đã đóng hoặc bị hủy, không thể cập nhật."}), 400

        student = db.session.get(Student, record.student_id)
        student_name = student.name if student else "?"

        # Tìm điểm trừ
        rule = ViolationType.query.filter_by(name=violation_type_name).first()
        points = rule.points_deducted if rule else 0

        if record.violation_type_name == "___auto___":
            # Placeholder — cập nhật trực tiếp
            record.violation_type_name = violation_type_name
            record.points_deducted = points
            record.notes = "Tự động phát hiện khi điểm danh trong giờ theo dõi"
            db.session.commit()
            return jsonify({
                "success": True,
                "message": f"Đã cập nhật vi phạm cho {student_name} thành '{violation_type_name}'.",
                "points_deducted": points,
            })
        else:
            # Đã có loại thực — xóa bản ghi cũ, tạo bản ghi mới (để đúng logic trùng loại)
            saved_session_id = record.session_id
            saved_student_id = record.student_id
            db.session.delete(record)
            db.session.flush()

            # Kiểm tra trùng với loại mới
            existing = SessionViolationRecord.query.filter_by(
                session_id=saved_session_id,
                student_id=saved_student_id,
                violation_type_name=violation_type_name,
                status="pending",
            ).first()
            if existing:
                db.session.rollback()
                return jsonify({
                    "error": f"{student_name} đã được đánh dấu vi phạm '{violation_type_name}' trong phiên này.",
                    "existing_id": existing.id,
                }), 409

            new_record = SessionViolationRecord(
                session_id=saved_session_id,
                student_id=saved_student_id,
                violation_type_name=violation_type_name,
                points_deducted=points,
                status="pending",
                notes="Cập nhật loại vi phạm trong giờ theo dõi",
            )
            db.session.add(new_record)
            db.session.commit()
            return jsonify({
                "success": True,
                "message": f"Đã đổi vi phạm của {student_name} sang '{violation_type_name}'.",
                "new_violation_id": new_record.id,
                "points_deducted": points,
            })

    @app.route("/api/attendance/monitoring/confirm-violations", methods=["POST"])
    @login_required
    def api_confirm_session_violations():
        """
        Xác nhận toàn bộ vi phạm trong phiên — chuyển thành Violation chính thức,
        trừ điểm học sinh, và đóng phiên theo dõi.
        """
        data = request.get_json() or {}
        session_id = data.get("session_id")
        close_session = data.get("close_session", True)

        if not session_id:
            return jsonify({"error": "Thiếu session_id."}), 400

        session = db.session.get(AttendanceMonitoringSession, session_id)
        if not session:
            return jsonify({"error": "Không tìm thấy phiên."}), 404
        if session.status != "open":
            return jsonify({"error": "Phiên không còn mở."}), 400

        pending = SessionViolationRecord.query.filter_by(
            session_id=session_id, status="pending"
        ).all()

        if not pending:
            return jsonify({"error": "Không có vi phạm nào để xác nhận."}), 400

        # Lấy week number hiện tại
        w_cfg = SystemConfig.query.filter_by(key="current_week").first()
        current_week = int(w_cfg.value) if w_cfg else 1

        confirmed_count = 0
        errors = []

        for record in pending:
            student = db.session.get(Student, record.student_id)
            if not student:
                errors.append(f"Không tìm thấy HS ID {record.student_id}")
                continue

            # Trừ điểm
            old_score = student.current_score or 100
            student.current_score = max(0, old_score - record.points_deducted)

            # Tạo Violation chính thức
            violation = Violation(
                student_id=record.student_id,
                violation_type_name=record.violation_type_name,
                points_deducted=record.points_deducted,
                week_number=current_week,
                lesson_book_entry_id=None,
            )
            db.session.add(violation)
            db.session.flush()  # Lấy ID của violation mới

            # Cập nhật trạng thái bản ghi trong phiên
            record.status = "confirmed"
            record.official_violation_id = violation.id

            # Log thay đổi
            log_change(
                'violation',
                f'Vi phạm (theo dõi {session.start_time.strftime("%H:%M")}-{session.end_time.strftime("%H:%M") if session.end_time else "?"}): {record.violation_type_name} (-{record.points_deducted} điểm)',
                student_id=student.id,
                student_name=student.name,
                student_class=student.student_class,
                old_value=old_score,
                new_value=student.current_score,
            )

            # Cập nhật hạnh kiểm
            update_student_conduct(student.id)
            confirmed_count += 1

        # Đóng phiên theo dõi
        if close_session:
            session.status = "confirmed"
            session.end_time = datetime.datetime.now()

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Đã xác nhận {confirmed_count} vi phạm."
                        + (f" Phiên theo dõi đã đóng." if close_session else ""),
            "confirmed_count": confirmed_count,
            "errors": errors if errors else None,
        })

    @app.route("/api/attendance/monitoring/cancel-session", methods=["POST"])
    @login_required
    def api_cancel_monitoring_session():
        """Hủy phiên theo dõi (xóa toàn bộ bản ghi vi phạm pending, đóng phiên)."""
        data = request.get_json() or {}
        session_id = data.get("session_id")
        if not session_id:
            return jsonify({"error": "Thiếu session_id."}), 400

        session = db.session.get(AttendanceMonitoringSession, session_id)
        if not session:
            return jsonify({"error": "Không tìm thấy phiên."}), 404
        if session.status != "open":
            return jsonify({"error": "Phiên không còn mở."}), 400

        # Chỉ người tạo hoặc admin mới được hủy
        if current_user.role != "admin" and session.teacher_id != current_user.id:
            return jsonify({"error": "Bạn không có quyền hủy phiên này."}), 403

        # Xóa các bản ghi pending
        pending = SessionViolationRecord.query.filter_by(
            session_id=session_id, status="pending"
        ).all()
        for p in pending:
            db.session.delete(p)

        session.status = "cancelled"
        session.end_time = datetime.datetime.now()
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Đã hủy phiên theo dõi lớp {session.class_name}."
        })
