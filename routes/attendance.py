"""Routes cho hệ thống Điểm danh bằng Nhận diện Khuôn mặt.

Sử dụng OpenCV LBPH Face Recognizer — nhẹ, không cần TensorFlow hay dlib.
Face data lấy từ ảnh thẻ (portrait_filename) của học sinh.
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

# Thư mục lưu ảnh điểm danh
ATTENDANCE_PHOTO_DIR = os.path.join(UPLOAD_FOLDER, "attendance_photos")
os.makedirs(ATTENDANCE_PHOTO_DIR, exist_ok=True)

# Thư mục lưu mẫu khuôn mặt (nhiều mẫu/HS)
ENROLLMENT_DIR = os.path.join(UPLOAD_FOLDER, "face_enrollment")
os.makedirs(ENROLLMENT_DIR, exist_ok=True)

# Thư mục model cache
FACE_MODEL_DIR = os.path.join(UPLOAD_FOLDER, "face_models")
os.makedirs(FACE_MODEL_DIR, exist_ok=True)

# OpenCV Cascade cho phát hiện khuôn mặt
CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)


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


def _extract_face(img, size=(200, 200)):
    """Phát hiện và cắt khuôn mặt lớn nhất. Trả về (face_gray, face_color, box)."""
    if img is None:
        return None, None, None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )
    if len(faces) == 0:
        return None, None, None
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    x, y, w, h = faces[0]
    face_gray = gray[y:y+h, x:x+w]
    face_gray = cv2.resize(face_gray, size)
    return face_gray, img[y:y+h, x:x+w], (int(x), int(y), int(w), int(h))


def _get_model_path(class_name="_GLOBAL_"):
    """Đường dẫn file model LBPH (mặc định cho toàn trường)."""
    safe_name = class_name.replace(" ", "_").replace("/", "_")
    return os.path.join(FACE_MODEL_DIR, f"lbph_{safe_name}.yml")


def _get_label_map_path(class_name="_GLOBAL_"):
    """Đường dẫn file label map (mặc định cho toàn trường)."""
    safe_name = class_name.replace(" ", "_").replace("/", "_")
    return os.path.join(FACE_MODEL_DIR, f"labels_{safe_name}.pkl")


def _train_model_for_class(class_name=None):
    """
    Huấn luyện LBPH Recognizer. 
    Nếu class_name=None hoặc "_GLOBAL_", huấn luyện cho toàn bộ học sinh trường.
    """
    if not class_name or class_name == "_GLOBAL_":
        students = Student.query.all()
        save_name = "_GLOBAL_"
    else:
        students = Student.query.filter_by(student_class=class_name).all()
        save_name = class_name

    faces = []
    labels = []
    label_map = {}  # label_int → student_id
    current_label = 0

    for s in students:
        sample_paths = []
        
        # 1. Ảnh thẻ
        p_path = _get_portrait_path(s)
        if p_path: sample_paths.append(p_path)
            
        # 2. Mẫu chụp từ camera
        e_dir = _get_enrollment_path(s.id)
        for f in os.listdir(e_dir):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                sample_paths.append(os.path.join(e_dir, f))

        if not sample_paths:
            continue

        label_map[current_label] = s.id
        
        for p in sample_paths:
            img = cv2.imread(p)
            if img is None: continue
            
            # Nếu là file từ enrollment thì nó đã là mặt xám resize rồi, 
            # nhưng ta vẫn chạy detect cho chắc ăn nếu là ảnh portrait
            face_gray, _, _ = _extract_face(img)
            if face_gray is None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                face_gray = cv2.resize(gray, (200, 200))
                
            faces.append(face_gray)
            labels.append(current_label)
            
        current_label += 1

    if not faces:
        return 0

    recognizer = cv2.face.LBPHFaceRecognizer_create(
        radius=2, neighbors=8, grid_x=8, grid_y=8, threshold=120.0
    )
    recognizer.train(faces, np.array(labels))
    recognizer.save(_get_model_path(save_name))

    with open(_get_label_map_path(save_name), "wb") as f:
        pickle.dump(label_map, f)

    return len(label_map)


def _load_model(class_name):
    """Load model LBPH đã train cho lớp."""
    model_path = _get_model_path(class_name)
    labels_path = _get_label_map_path(class_name)
    if not os.path.exists(model_path) or not os.path.exists(labels_path):
        return None, None
    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(model_path)
        with open(labels_path, "rb") as f:
            label_map = pickle.load(f)
        return recognizer, label_map
    except Exception:
        return None, None


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

        # Kiểm tra model toàn trường (mặc định mới)
        model_ready = os.path.exists(_get_model_path("_GLOBAL_"))

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
        
        labels_path = _get_label_map_path(class_name if class_name else "_GLOBAL_")
        trained_ids = []
        if os.path.exists(labels_path):
            with open(labels_path, "rb") as f:
                lmap = pickle.load(f)
                trained_ids = list(lmap.values())
        
        result = []
        for s in students:
            has_portrait = bool(s.portrait_filename) and _get_portrait_path(s) is not None
            e_dir = _get_enrollment_path(s.id)
            enrollment_count = len([f for f in os.listdir(e_dir) if f.lower().endswith(('.jpg', '.png'))])

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
        """Huấn luyện model (Ưu tiên toàn trường)."""
        data = request.get_json() or {}
        class_name = data.get("class_name", "_GLOBAL_")
        try:
            trained_count = _train_model_for_class(class_name)
            return jsonify({
                "success": True,
                "message": f"Đã huấn luyện dữ liệu khuôn mặt cho {trained_count} học sinh (Phạm vi: toàn trường).",
                "trained": trained_count
            })
        except Exception as e:
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
        face_gray, _, _ = _extract_face(img)
        if face_gray is None:
            return jsonify({"error": "Không phát hiện khuôn mặt sắc nét. Hãy thử lại."}), 400
        e_dir = _get_enrollment_path(student_id)
        filename = f"sample_{uuid.uuid4().hex[:6]}.jpg"
        cv2.imwrite(os.path.join(e_dir, filename), face_gray)
        count = len([f for f in os.listdir(e_dir) if f.lower().endswith('.jpg')])
        return jsonify({
            "success": True, 
            "message": f"Đã lưu mẫu khuôn mặt (Mẫu thứ {count})",
            "enrollment_count": count
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
            except: pass
        return jsonify({"success": True, "message": "Đã xóa toàn bộ mẫu của học sinh."})

    @app.route("/api/attendance/recognize", methods=["POST"])
    @login_required
    def api_attendance_recognize():
        """Nhận diện khuôn mặt từ ảnh camera dựa trên dữ liệu toàn trường."""
        data = request.get_json() or {}
        image_base64 = data.get("image_base64", "")
        if not image_base64:
            return jsonify({"error": "Thiếu dữ liệu ảnh."}), 400
        
        # Luôn load model toàn trường
        recognizer, label_map = _load_model("_GLOBAL_")
        if recognizer is None:
            # Fallback nếu chưa có model toàn trường thì thử dùng model theo lớp nếu có gửi lên
            class_name = data.get("class_name", "")
            if class_name:
                recognizer, label_map = _load_model(class_name)

        if recognizer is None:
            return jsonify({"matched": False, "error": "Chưa huấn luyện dữ liệu khuôn mặt toàn trường."})
        camera_img = _base64_to_cv2(image_base64)
        face_gray, _, box = _extract_face(camera_img)
        if face_gray is None:
            return jsonify({"matched": False, "error": "Không phát hiện khuôn mặt."})
        
        label, confidence_raw = recognizer.predict(face_gray)
        THRESHOLD = 100.0
        if confidence_raw < THRESHOLD and label in label_map:
            student_id = label_map[label]
            student = db.session.get(Student, student_id)
            if not student:
                return jsonify({"matched": False, "error": "Lỗi dữ liệu.", "box": box})
            confidence = max(0, min(1, 1 - (confidence_raw / 150)))
            captured_filename = _save_captured_photo(image_base64)
            return jsonify({
                "matched": True,
                "student_id": student.id,
                "student_name": student.name,
                "student_code": student.student_code,
                "confidence": round(confidence, 2),
                "captured_photo": captured_filename,
                "box": box
            })
        return jsonify({"matched": False, "error": "Không nhận diện được học sinh.", "box": box})

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
            except ValueError: pass
        if date_to:
            try:
                d = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
                query = query.filter(AttendanceRecord.attendance_date <= d)
            except ValueError: pass
        records = query.order_by(desc(AttendanceRecord.check_in_time)).limit(200).all()
        result = []
        for r in records:
            result.append({
                "id": r.id, "student_name": r.student.name if r.student else "N/A",
                "student_code": r.student.student_code if r.student else "",
                "class_name": r.class_name, "check_in_time": r.check_in_time.strftime("%H:%M:%S"),
                "attendance_date": r.attendance_date.strftime("%d/%m/%Y"),
                "status": r.status, "confidence": r.confidence, "captured_photo": r.captured_photo,
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
            today_records = AttendanceRecord.query.filter_by(class_name=class_name, attendance_date=today).all()
        else:
            total_students = Student.query.count()
            today_records = AttendanceRecord.query.filter_by(attendance_date=today).all()

        present = sum(1 for r in today_records if r.status == "Có mặt")
        late = sum(1 for r in today_records if r.status == "Trễ")
        return jsonify({
            "total": total_students, "present": present, "late": late,
            "absent": total_students - len(today_records),
        })

    @app.route("/api/attendance/model_status")
    @login_required
    def api_attendance_model_status():
        class_name = request.args.get("class_name", "")
        ready = os.path.exists(_get_model_path(class_name)) if class_name else False
        return jsonify({"ready": ready})

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
                    try: os.remove(photo_path)
                    except: pass
            
            db.session.delete(record)
            db.session.commit()
            return jsonify({"success": True, "message": "Đã xóa dữ liệu điểm danh."})
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Lỗi hệ thống khi xóa: {str(e)}"}), 500
