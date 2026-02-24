# 🎓 EduMind AI - Hệ Thống Giáo Dục Thông Minh

![EduMind AI Banner](https://img.shields.io/badge/EduMind%20AI-Smart%20Education-blue?style=for-the-badge&logo=googlescholar)
![Python](https://img.shields.io/badge/Python-3.8%2B-green?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-lightgrey?style=for-the-badge&logo=flask)
![AI](https://img.shields.io/badge/AI-Powered-purple?style=for-the-badge&logo=openai)

**EduMind AI** là một nền tảng quản lý giáo dục toàn diện, kết hợp sức mạnh của trí tuệ nhân tạo (AI) và công nghệ thị giác máy tính (Computer Vision) để hiện đại hóa công tác quản lý nề nếp, điểm số và giao tiếp trong nhà trường. Được thiết kế chuyên biệt cho giáo viên chủ nhiệm và ban giám hiệu, EduMind AI giúp tối ưu hóa quy trình làm việc, đảm bảo tính minh bạch và bảo mật dữ liệu tuyệt đối.

---

## ✨ Tính Năng Cốt Lõi

### 🤖 Trợ Lý AI Thông Minh (Hybrid AI)
- **Chatbot Ngữ Cảnh**: Tương tác tự nhiên để tra cứu nhanh thông tin học sinh, lịch sử vi phạm và nhận tư vấn sư phạm.
- **Phân Tích Dữ Liệu Tự Động**: AI tự động tổng hợp xu hướng nề nếp, đưa ra nhận xét định kỳ và dự báo sự tiến bộ của từng cá nhân.
- **Quyền Riêng Tư (Privacy First)**: Hỗ trợ xử lý Local hoàn toàn qua [Ollama](https://ollama.com), đảm bảo dữ liệu học sinh không bị gửi lên đám mây.

### 👁️ Công Nghệ OCR & Vision
- **Số Hóa Nề Nếp**: Tự động nhận diện mã số học sinh từ ảnh chụp thẻ thông qua công nghệ OCR cải tiến, giúp ghi nhận vi phạm chỉ trong vài giây.
- **Chuẩn Hóa Thông Tin**: Hệ thống tự động chuẩn hóa và đối soát mã học sinh để giảm thiểu sai sót nhập liệu.

### 📊 Quản Lý Học Tập & Nề Nếp Chuyên Sâu
- **Hệ Thống Điểm Digital**: Theo dõi đầy đủ các cột điểm (TX, GK, HK), tự động tính trung bình môn và GPA học kỳ/năm học theo quy chuẩn giáo dục.
- **Timeline Nề Nếp**: Theo dõi chi tiết các lỗi vi phạm và điểm thưởng (Bonus records). Hệ thống tự động trừ/cộng điểm vào quỹ điểm rèn luyện của học sinh.
- **Lưu Trữ Tuần (Weekly Archive)**: Tự động chốt sổ và lưu trữ dữ liệu nề nếp theo từng tuần để phục vụ báo cáo thi đua.

### 💬 Hệ Thống Giao Tiếp & Thông Báo
- **Đa Kênh**: Bao gồm phòng chat chung giáo viên, nhắn tin riêng tư và hệ thống thông báo đẩy (Notifications) theo vai trò.
- **Cổng Học Sinh**: Học sinh có tài khoản riêng để theo dõi điểm số, nề nếp và nhận phản hồi từ giáo viên.

---

## 🛠️ Công Nghệ Sử Dụng

| Thành phần | Công nghệ |
| :--- | :--- |
| **Backend** | Python 3.x, Flask, SQLAlchemy (SQLite) |
| **Trí tuệ nhân tạo** | Ollama (Local LLM), Google Gemini API |
| **Xử lý dữ liệu** | Pandas, OpenPyXL, Unicodedata |
| **Giao diện** | HTML5, Vanilla CSS, FontAwesome, Chart.js, Driver.js |
| **Bảo mật** | Flask-Login, Session Security, Role-based Access Control (RBAC) |

---

## 🚀 Hướng Dẫn Cài Đặt

### 1. Chuẩn bị
- Đã cài đặt **Python 3.8+**.
- Cài đặt **Ollama** tại [ollama.com](https://ollama.com).

### 2. Cài đặt dự án
```bash
# Clone repository
git clone https://github.com/HoaThang34/EduMind-AI.git
cd EduMind-AI

# Chạy tệp khởi động tự động (Khuyên dùng trên Windows)
run_edu_manager.bat
```

### 3. Cấu hình AI
Tải model AI để hệ thống có thể hoạt động offline:
```bash
ollama pull gemini-3-flash-preview
```

---

## 👥 Phân Quyền Người Dùng

*   **Quản trị viên (Admin)**: Toàn quyền quản lý hệ thống, giáo viên, cấu hình tuần và xem lịch sử thay đổi (ChangeLog).
*   **Giáo viên chủ nhiệm**: Quản lý nề nếp, điểm số và thông tin học sinh của lớp được phân công.
*   **Giáo viên bộ môn**: Chấm điểm các môn học cho học sinh toàn trường.
*   **Học sinh**: Xem điểm rèn luyện cá nhân, nhận thông báo và tương tác với giáo viên.

---

## 🔒 Bảo Mật & Nhật Ký
- **ChangeLog System**: Mọi thay đổi về điểm số và lỗi vi phạm đều được hệ thống ghi lại (ai sửa, sửa lúc nào, giá trị cũ/mới là gì) để đảm bảo tính công bằng.
- **Local Processing**: Các tác vụ Vision và AI ưu tiên xử lý offline trên máy chủ trường học.

---

## 🤝 Đội Ngũ Phát Triển
Dự án được thực hiện bởi đội ngũ học sinh năng khiếu thuộc **Trường THPT Chuyên Nguyễn Tất Thành**. Chúng tôi không ngừng nỗ lực để mang lại giá trị thiết thực cho cộng đồng giáo dục.

---
**⭐ Hãy tặng chúng tôi 1 sao nếu bạn thấy dự án này hữu ích!**
