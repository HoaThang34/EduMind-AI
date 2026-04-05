# EduMind AI - Hệ Thống Quản Lý Giáo Dục Thông Minh Tích Hợp AI

<div align="center">
  <img src="logo/logo.png" alt="EduMind AI Logo" width="180">
</div>

---

## Giới Thiệu

**EduMind AI** là nền tảng quản lý giáo dục toàn diện, ứng dụng **AI** và **Computer Vision** để hiện đại hóa quy trình quản trị nhà trường. Hệ thống giúp giáo viên giảm tải hành chính, tập trung vào chất lượng dạy và học.

---

## Tính Năng Nổi Bật

### 📸 Điểm Danh & Nề Nếp

- Nhận diện mã học sinh qua OCR từ ảnh chụp nhanh
- Ghi nhận vi phạm, điểm thưởng trong vài giây
- Loại bỏ hoàn toàn thủ tục ghi chép thủ công

### 🤖 Chatbot AI

- Tra cứu dữ liệu học sinh bằng ngôn ngữ tự nhiên
- Phân tích xu hướng học tập
- Tự động tạo nhận xét định kỳ

### 📊 Quản Lý Điểm

- Quản lý điểm tập trung theo từng môn học
- Tự động tính GPA
- Xuất báo cáo trực quan theo giai đoạn

### 💬 Thông Báo & Giao Tiếp

- Thông báo đẩy real-time
- Kênh giao tiếp nội bộ giữa giáo viên và học sinh

### 🔒 Bảo Mật

- Xử lý dữ liệu tại chỗ (Local Processing)
- Mô hình AI chạy offline
- Bảo vệ thông tin nhạy cảm của học sinh

---

## Công Nghệ AI Sử Dụng

### 1. Nhận Diện Khuôn Mặt (Face Recognition)

**ArcFace** là công nghệ nền tảng cho hệ thống điểm danh tự động:


| Tầng      | Công nghệ                           | Mô tả                                   |
| --------- | ----------------------------------- | --------------------------------------- |
| Detection | OpenCV DNN ResNet-SSD               | Phát hiện vùng khuôn mặt trong ảnh      |
| Alignment | 5-point landmark → Affine transform | Căn chỉnh khuôn mặt về pose chuẩn       |
| Embedding | ArcFace ONNX (512-dim)              | Trích xuất vector đặc trưng             |
| Matching  | Cosine similarity                   | So sánh độ tương đồng (threshold: 0.40) |


**ONNX Runtime** được sử dụng thay vì TensorFlow để tối ưu hiệu suất và không phụ thuộc GPU.

### 2. Chatbot AI (Context-Aware Conversation)

**Intent Detection System** với routing tự động theo từ khóa:

- **SCHOOL_RULES_PROMPT**: Nội quy & Kỷ luật (theo Thông tư 19/2025)
- **BEHAVIOR_GUIDE_PROMPT**: Mentor Kỹ năng sống (SMART, Pomodoro, Eisenhower)
- **TEACHER_ASSISTANT_PROMPT**: Hỗ trợ Giáo viên soạn nhận xét
- **DEFAULT_ASSISTANT_PROMPT**: Tổng quát với conversation memory
- **STUDENT_RULE_PROMPT**: Hỗ trợ Học sinh (Gen Z friendly)

### 3. Gemini Vision OCR

Tích hợp **Gemini API** để:

- Đọc điểm từ ảnh chụp bảng điểm tay
- Parse cấu trúc JSON để lưu vào database
- Hỗ trợ các loại điểm: TX (Thường xuyên), GK (Giữa kỳ), HK (Cuối kỳ)

### 4. Predictive Analytics (Dự Báo Xu Hướng)

**Gemini API** phân tích dữ liệu lịch sử để:

- Dự báo xu hướng học tập (tích cực/ổn định/tiêu cực)
- Cảnh báo sớm nguy cơ (Học lực, Hành vi, Tâm lý)
- Đề xuất hành động cụ thể cho giáo viên

### 5. Ollama Local LLM Integration

Hỗ trợ **Ollama** để chạy LLM locally:

- Giảm phụ thuộc internet
- Bảo mật dữ liệu nội bộ
- Fallback tự động sang Gemini API khi cần

### 6. Voice-to-Text Normalization

Chuyển đổi giọng nói/chat thô thành nhận xét sư phạm chuyên nghiệp:

- Sửa lỗi chính tả từ Voice-to-Text
- Nâng cấp từ ngữ đời thường → ngôn ngữ sư phạm
- Giữ nguyên ý nghĩa cốt lõi của giáo viên

---

## Công Nghệ Khác


| Lĩnh vực | Công nghệ                                |
| -------- | ---------------------------------------- |
| Backend  | Python, Flask                            |
| Database | SQLite                                   |
| AI/LLM   | Ollama, Gemini API, Google Generative AI |
| Vision   | OpenCV, ONNX Runtime, Torch              |
| Frontend | HTML, CSS, JavaScript                    |


---

## Đối Tượng Sử Dụng


| Đối tượng     | Vai trò                         |
| ------------- | ------------------------------- |
| Ban Giám Hiệu | Theo dõi tổng quát toàn trường  |
| Giáo Viên     | Tối ưu chấm điểm, quản lý lớp   |
| Học Sinh      | Tra cứu điểm, nề nếp, thông báo |


---

## 👥 Đội Ngũ Phát Triển (Authorship)

- **Tác giả:** **Agent_LLM Team**
- **Thành Viên:**
  1. **Hòa Quang Thắng**
  2. **Hồ Lực Nguyên**
- **Đơn vị:** [Trường THPT Chuyên Nguyễn Tất Thành - Tỉnh Lào Cai](https://www.facebook.com/ChuyenNTTLaoCai)

