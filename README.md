# EduMind AI - Hệ Thống Quản Lý Giáo Dục Thông Minh Tích Hợp AI

<div align="center">
  <img src="logo/logo.png" alt="EduMind AI Logo" width="180">
</div>

---

## Giới Thiệu

**EduMind AI** là nền tảng quản lý giáo dục toàn diện, ứng dụng **AI** và **Computer Vision** để hiện đại hóa quy trình quản trị nhà trường. Hệ thống giúp giáo viên giảm tải hành chính, tập trung vào chất lượng dạy và học.

---

## Tính Năng Chi Tiết

### 1. Hệ Thống Xác Thực & Phân Quyền

| Tính năng | Mô tả |
|------------|-------|
| Đăng nhập đa vai trò | Hỗ trợ 6 vai trò: Admin, GVCN, GVBM, GVCN+GVBM, Giáo viên nề nếp, Phụ huynh/Học sinh |
| Phân quyền chi tiết | Permission system cho phép gán quyền cụ thể từng tính năng cho giáo viên |
| Kiểm soát truy cập | GVCN chỉ xem được lớp mình, GVBM chỉ xem được môn được phân công |
| Quản lý session | Xác thực học sinh qua mã HS + mật khẩu hoặc SĐT phụ huynh |

### 2. Quản Lý Học Sinh

| Tính năng | Mô tả |
|------------|-------|
| CRUD học sinh | Thêm, sửa, xóa thông tin học sinh |
| Nhập hàng loạt | Import danh sách từ file Excel với tự động nhận diện cột |
| Thông tin mở rộng | CCCD/CMND, dân tộc, ngày sinh, chức vụ (Lớp trưởng, Bí thư...) |
| Thẻ học sinh | Sinh thẻ với QR code xác thực (itsdangerous signed token) |
| Tìm kiếm & lọc | Tìm theo tên, mã HS; lọc theo lớp, mức cảnh báo |
| Cổng học sinh | Portal riêng với đăng nhập, xem TKB, điểm, thông báo |

### 3. Quản Lý Nề Nếp & Kỷ Luật

| Tính năng | Mô tả |
|------------|-------|
| Quản lý loại vi phạm | CRUD các lỗi vi phạm với điểm trừ tương ứng |
| Thêm vi phạm đơn lẻ | Chọn học sinh và loại vi phạm từ dropdown |
| Thêm vi phạm hàng loạt | Nhập nhiều học sinh cùng lúc |
| OCR nhận diện vi phạm | Gemini Vision đọc ảnh chụp bảng ghi điểm trừ |
| Quản lý điểm cộng | Thêm thưởng với loại điểm cộng và lý do cụ thể |
| Timeline vi phạm | Xem lịch sử vi phạm theo tuần với biểu đồ |
| Reset tuần tự động | Lưu archive, reset điểm về 100 đầu mỗi tuần |
| Cảnh báo nề nếp | Màu Xanh/Vàng/Đỏ theo ngưỡng cấu hình (BGH thiết lập) |

### 4. Quản Lý Điểm

| Tính năng | Mô tả |
|------------|-------|
| Nhập điểm thủ công | Chọn môn, loại điểm (TX/GK/HK), cột, nhập điểm |
| OCR điểm từ ảnh | Gemini Vision đọc bảng điểm tay, trích xuất JSON |
| Xác nhận & lưu OCR | Soát lại kết quả OCR, sửa nếu sai, xác nhận lưu |
| Tính GPA tự động | Công thức: (TX + GK×2 + HK×3) / 6 |
| Xếp loại học lực | Giỏi/Khá/Trung bình/Yếu dựa trên GPA |
| Học bạ điện tử | Transcript với toàn bộ điểm theo học kỳ |
| Cập nhật điểm | Ghi log mọi thay đổi điểm (ai chỉnh, lúc nào, cũ → mới) |
| Khóa điểm theo cấu hình | Chỉ GV được phân công môn mới được nhập điểm |

### 5. Quản Lý Giáo Viên

| Tính năng | Mô tả |
|------------|-------|
| CRUD giáo viên | Thêm, sửa, xóa tài khoản giáo viên |
| Phân công lớp | Gán giáo viên dạy lớp nào (TeacherClassAssignment) |
| Phân công môn | Gán môn giảng dạy cho GVBM |
| Quản lý quyền | Gán/revoke permissions cho từng giáo viên |
| Vai trò đa dạng | Admin, GVCN, GVBM, Both, Nhân viên nề nếp |

### 6. Thời Khóa Biểu

| Tính năng | Mô tả |
|------------|-------|
| Tạo TKB trực quan | Grid view theo thứ × tiết |
| Quản lý theo tuần | Mỗi tuần có thể có TKB khác (ISO week 1-53) |
| Nhập TKB Excel | Import từ file Excel với định dạng chuẩn |
| AI sinh TKB | Gemini tạo TKB hợp lý từ dữ liệu đầu vào |
| Preview & xác nhận | Xem trước TKB AI trước khi lưu |
| Gán phòng & GV | Mỗi slot có thể gán giáo viên, phòng |
| Nhiều lớp | Quản lý TKB cho tất cả lớp trong trường |
| Năm học & học kỳ | Lọc TKB theo năm học |

### 7. Sổ Đầu Bài Điện Tử

| Tính năng | Mô tả |
|------------|-------|
| Grid view theo tuần | Hiển thị lưới Thứ × Tiết, click để nhập |
| Form truyền thống | Nhập chi tiết: chủ đề, mục tiêu, phương pháp, đánh giá |
| Ghi chú tuần | Meta thông tin cho cả tuần |
| Liên kết TKB | Tự động điền lớp, môn, tiết từ thời khóa biểu |
| Điểm danh sổ đầu bài | Ghi nhận sĩ số có mặt/vắng mặt |
| Ghi log vi phạm | Liên kết vi phạm với tiết học cụ thể |

### 8. Điểm Danh Thông Minh

| Tính năng | Mô tả |
|------------|-------|
| Face Recognition | ArcFace ONNX nhận diện khuôn mặt 512-dim |
| QR Code | Quét mã QR trên thẻ học sinh để điểm danh |
| Monitoring Session | Mở phiên theo dõi trong khung giờ, đánh dấu vi phạm realtime |
| Session Violation | Ghi nhận vi phạm trong phiên, xác nhận sau để tạo chính thức |
| Ảnh chụp điểm danh | Lưu ảnh chụp từ camera khi điểm danh |
| Độ tin cậy | Hiển thị confidence score (cosine similarity) |
| Ghi log chi tiết | Ai điểm danh, lúc nào, phương thức nào |
| Hỗ trợ toàn trường | Monitoring session riêng cho lớp hoặc toàn trường |

### 9. Chatbot AI Đa Năng

| Tính năng | Mô tả |
|------------|-------|
| Intent Detection | Tự động phát hiện chủ đề: Nội quy, Ứng xử, Hỗ trợ GV, Default |
| RAG System | Retrieval Augmented Generation từ nhiều bảng (HS, GV, Lớp, Môn, VP) |
| Tra cứu học sinh | Hỏi bằng ngôn ngữ tự nhiên, AI trả thông tin chi tiết |
| Thống kê tự động | Đếm HS, GV, thống kê học lực yếu - trực tiếp từ DB |
| Quản lý tác vụ | Thêm/sửa/xóa HS, gửi thông báo - có xác nhận 2 bước |
| Conversation Memory | Lưu lịch sử hội thoại, hỗ trợ chat liên tục |
| Dry-run mode | Xem trước thay đổi trước khi thực thi |
| Khuyến nghị tự động | AI đưa ra lời khuyên dựa trên dữ liệu |

### 10. Tính Năng AI Nâng Cao

| Tính năng | Mô tả |
|------------|-------|
| ArcFace Face Recognition | Nhận diện khuôn mặt 512-dim với ONNX Runtime |
| Gemini Vision OCR | Đọc điểm, vi phạm từ ảnh bảng |
| Predictive Analytics | Dự báo xu hướng học tập (tích cực/ổn định/tiêu cực) |
| Cảnh báo sớm | Phát hiện nguy cơ về học lực, hành vi, tâm lý |
| Voice-to-Text Normalization | Chuẩn hóa nhận xét từ Voice sang ngôn ngữ sư phạm |
| Ollama Local LLM | Chạy LLM locally, giảm phụ thuộc internet |
| Auto Fallback | Ollama fail → tự động chuyển sang Gemini API |
| RAG Multi-table | Truy xuất ngữ cảnh từ Students, Teachers, Subjects, Classes, Violations |

### 11. Nhận Xét & Báo Cáo

| Tính năng | Mô tả |
|------------|-------|
| Nhận xét tự động | AI viết nhận xét ngắn gọn cho phụ huynh |
| Phân tích biểu đồ | Nhận xét dựa trên GPA, phân bố điểm, nề nếp |
| Báo cáo tuần | Thống kê vi phạm, xếp hạng lớp theo nề nếp |
| Xuất Excel | Export báo cáo vi phạm, điểm ra file Excel |
| Weekly Parent Report | Tổng hợp tuần gửi phụ huynh |
| Báo cáo xu hướng | AI phân tích tiến bộ qua nhiều tuần |

### 12. Thông Báo & Giao Tiếp

| Tính năng | Mô tả |
|------------|-------|
| Thông báo nội bộ | Gửi thông báo giữa giáo viên |
| Thông báo học sinh | Gửi thông báo đến từng HS hoặc cả lớp |
| Broadcast toàn trường | Admin gửi thông báo đến tất cả học sinh |
| Group Chat | Phòng chat chung cho giáo viên |
| Private Message | Tin nhắn riêng giữa 2 giáo viên |
| Lịch sử thông báo | Xem lại các thông báo đã nhận |
| Đánh dấu đã đọc | Trạng thái read/unread cho thông báo |

### 13. Quỹ Lớp

| Tính năng | Mô tả |
|------------|-------|
| Thu tiền | Ghi nhận khoản thu từ phụ huynh |
| Chi tiêu | Quản lý chi tiêu quỹ lớp |
| Số dư | Tự động tính số dư = Thu - Chi |
| Theo dõi theo năm | Mỗi năm học có sổ quỹ riêng |
| Gắn học sinh | Liên kết khoản thu với học sinh cụ thể |
| GVCN quản lý | Chỉ GVCN hoặc Admin được quản lý quỹ lớp |

### 14. Dashboard & Thống Kê

| Tính năng | Mô tả |
|------------|-------|
| KPI Cards | Tổng HS, lớp, vi phạm tuần, điểm TB |
| Biểu đồ tròn | Phân bố nề nếp (Tốt/Khá/Cần cố gắng) |
| Biểu đồ cột | Top vi phạm trong tuần |
| Phân tích AI | Dashboard gọi AI phân tích nề nếp |
| Lọc theo lớp | Xem dashboard của lớp cụ thể |
| Reset tuần warning | Cảnh báo khi sắp hết tuần |

### 15. Cấu Hình Hệ Thống

| Tính năng | Mô tả |
|------------|-------|
| Cấu hình trường | Tên trường, năm học, học kỳ, tuần hiện tại |
| Conduct Settings | Ngưỡng điểm Tốt/Khá/TB/Yếu, ngưỡng cảnh báo |
| Academic Settings | Ngưỡng GPA Vàng/Đỏ cho học lực |
| Changelog | Lịch sử mọi thay đổi (điểm, vi phạm, điểm cộng) |
| Quản lý môn học | CRUD môn học với cấu hình cột điểm |
| Phân công môn-lớp | Mỗi lớp có danh sách môn học riêng |

---

## Kiến Trúc AI

### 1. Face Recognition Pipeline

```
Ảnh đầu vào
    ↓
OpenCV DNN ResNet-SSD (Detection)
    ↓
5-point Landmark → Affine Transform (Alignment)
    ↓
ArcFace ONNX buffalo_l (Embedding 512-dim)
    ↓
Cosine Similarity (threshold: 0.40)
    ↓
Kết quả: student_id + confidence
```

### 2. Chatbot Intent Routing

```
Tin nhắn người dùng
    ↓
Keyword Detection
    ↓
├── "nội quy/vi phạm" → SCHOOL_RULES_PROMPT
├── "ứng xử/kỹ năng" → BEHAVIOR_GUIDE_PROMPT
├── "nhận xét/soạn" → TEACHER_ASSISTANT_PROMPT
└── Default → DEFAULT_ASSISTANT_PROMPT
    ↓
RAG Context Builder (Students, Teachers, Classes, Subjects, Violations)
    ↓
LLM Response (Ollama / Gemini)
```

### 3. OCR Pipeline

```
Ảnh bảng điểm/vi phạm
    ↓
Gemini Vision API (is_json=False)
    ↓
Parse JSON response
    ↓
Validate & Normalize
    ↓
Confirm Dialog → Database
```

---

## Công Nghệ Sử Dụng

| Lĩnh vực | Công nghệ |
|----------|-----------|
| Backend | Python, Flask |
| Database | SQLite |
| AI/LLM | Ollama, Gemini API, Google Generative AI |
| Vision | OpenCV, ONNX Runtime, Torch |
| Face Recognition | ArcFace buffalo_l (ONNX) |
| Frontend | HTML, CSS, JavaScript |
| Auth | Flask-Login, itsdangerous |
| Charts | Chart.js |
| ORM | Flask-SQLAlchemy |

---

## Đối Tượng Sử Dụng

| Đối tượng | Vai trò |
|-----------|---------|
| Ban Giám Hiệu | Dashboard toàn trường, cấu hình hệ thống, báo cáo |
| Giáo Viên Chủ Nhiệm | Quản lý lớp, nề nếp, điểm danh, sổ đầu bài, quỹ lớp |
| Giáo Viên Bộ Môn | Nhập điểm, quản lý môn học |
| Giáo Viên Nề Nếp | Ghi nhận vi phạm, điểm cộng |
| Học Sinh | Cổng tra cứu: TKB, điểm, thông báo |
| Phụ Huynh | Nhận báo cáo từ giáo viên |

---

## Cấu Trúc Database Chính

- **Teacher** - Tài khoản giáo viên + vai trò + phân công
- **Student** - Học sinh + điểm nề nếp + thông tin phụ huynh
- **Subject** - Môn học + cấu hình cột điểm
- **Grade** - Điểm (TX/GK/HK) theo học sinh, môn, học kỳ
- **Violation / ViolationType** - Vi phạm + loại vi phạm
- **BonusRecord / BonusType** - Điểm cộng + loại điểm cộng
- **AttendanceRecord / AttendanceMonitoringSession** - Điểm danh + phiên theo dõi
- **TimetableSlot** - Thời khóa biểu theo tuần ISO
- **LessonBookEntry / LessonBookSlot** - Sổ đầu bài
- **ClassFundCollection / ClassFundExpense** - Quỹ lớp
- **Notification / StudentNotification** - Thông báo
- **GroupChatMessage / PrivateMessage** - Tin nhắn
- **ChatConversation** - Lịch sử chatbot
- **ChangeLog** - Lịch sử thay đổi hệ thống
- **Permission / TeacherPermission** - Hệ thống phân quyền
- **WeeklyArchive** - Lưu trữ dữ liệu cuối tuần

---

## 👥 Đội Ngũ Phát Triển

- **Tác giả:** **Agent_LLM Team**
- **Thành Viên:**
  1. **Hòa Quang Thắng**
  2. **Hồ Lực Nguyên**
- **Đơn vị:** [Trường THPT Chuyên Nguyễn Tất Thành - Tỉnh Lào Cai](https://www.facebook.com/ChuyenNTTLaoCai)
