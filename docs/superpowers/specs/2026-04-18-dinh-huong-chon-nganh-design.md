# Định hướng chọn ngành — Design Spec

**Ngày:** 2026-04-18  
**Trạng thái:** Đã duyệt  
**Phạm vi:** Student portal — tính năng mới, không ảnh hưởng các tính năng hiện có

---

## 1. Tổng quan

Tính năng giúp học sinh so sánh năng lực học tập (dựa trên điểm thực tế trong hệ thống) với yêu cầu đầu vào của các ngành đại học, thông qua radar chart overlay trực quan. Học sinh có thể đặt ngành mục tiêu, ghim các ngành quan tâm, và duyệt toàn bộ ~150 ngành có sẵn.

---

## 2. Navigation

Thêm nút thứ 3 ngang hàng với "Học Tập & Rèn Luyện" và "Trợ lý AI & Chatbot" trên student dashboard:

```
[ Học Tập & Rèn Luyện ]  [ Trợ lý AI & Chatbot ]  [ Định hướng chọn ngành ]
```

---

## 3. Trang chính — `/student/career`

### Layout
Split layout 2 cột: radar (trái, rộng hơn) + sidebar (phải, 340px).

### Radar chart (trái)
- Thư viện: **Chart.js** (radar type)
- Axes: tất cả môn học của học sinh trong hệ thống (full radar, không lọc)
- **Overlay 2 lớp:**
  - Lớp 1 (xanh, nét liền): điểm trung bình mỗi môn của học sinh
  - Lớp 2 (cam, nét đứt): yêu cầu của ngành đang xem
- Dropdown "Đang so sánh với [tên ngành]" phía trên radar → đổi ngành cập nhật radar realtime qua API, không reload trang
- Điểm học sinh mỗi môn = `(avg_TX + avg_GK×2 + avg_HK×3) / 6` theo công thức hiện có trong `app_helpers.py`

### Sidebar (phải)

**Ngành mục tiêu:**
- Tên ngành, trường đại học
- Fit % + progress bar
- Danh sách môn ngành cần: điểm hs / yêu cầu + status tag (Đạt / −X điểm)
- State banner: tóm tắt gap quan trọng nhất cần cải thiện
- Nút "Đổi mục tiêu"

**Ngành đã ghim:**
- List với tên, trường, fit % + minibar
- Click vào 1 ngành → load lên radar ngay (không reload)
- Nút bỏ ghim
- Nút "+ Thêm ngành" → link sang trang browse

---

## 4. Trang duyệt ngành — `/student/career/browse`

- **Chỉ chart view** (không có list view): mỗi card hiển thị mini radar overlay (hs vs ngành)
- Sort mặc định: fit % giảm dần
- Filter: nhóm ngành (Kỹ thuật, Kinh tế, Y dược, Xã hội,...), trường, mức fit (>60%, >70%, >80%)
- Search: tên ngành hoặc tên trường
- Mỗi card có nút "Ghim" và "Đặt làm mục tiêu"
- Mini radar trên card dùng Chart.js với canvas nhỏ (~120px)

---

## 5. Công thức Fit %

```
fit % = Σ(min(điểm_hs_môn_i, yêu_cầu_môn_i) × trọng_số_i)
        ─────────────────────────────────────────────────────── × 100
        Σ(yêu_cầu_môn_i × trọng_số_i)
```

- **Cap tại yêu cầu:** điểm vượt yêu cầu không inflate fit score
- Môn học sinh chưa có điểm → tính = 0
- Fit % được tính server-side, cache theo session (recalculate khi điểm thay đổi)

---

## 6. Database — Bảng mới

### `university_major`
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| id | INTEGER PK | |
| name | VARCHAR(150) | Tên ngành |
| university | VARCHAR(150) | Tên trường |
| faculty | VARCHAR(150) | Khoa/Viện |
| major_group | VARCHAR(50) | Nhóm ngành (Kỹ thuật, Kinh tế,...) |
| description | TEXT | Mô tả ngắn |
| created_at | DATETIME | |

### `major_subject_weight`
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| id | INTEGER PK | |
| major_id | INTEGER FK | → university_major |
| subject_name | VARCHAR(100) | Khớp với tên môn trong hệ thống |
| weight | FLOAT | Trọng số (tổng các môn = 1.0) |
| min_score | FLOAT | Điểm yêu cầu (0–10) |

### `student_pinned_major`
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| id | INTEGER PK | |
| student_id | INTEGER FK | → student |
| major_id | INTEGER FK | → university_major |
| pinned_at | DATETIME | |

### `student_target_major`
| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| id | INTEGER PK | |
| student_id | INTEGER FK | → student (UNIQUE) |
| major_id | INTEGER FK | → university_major |
| set_at | DATETIME | |

Không thay đổi bảng điểm hiện có. Đọc từ bảng `Grade` có sẵn.

---

## 7. Mock data

- **~150 ngành** phổ biến tại các trường ĐH lớn ở Việt Nam (HUST, UET, NEU, FTU, UEH, VNU, Y Hà Nội, RMIT,...)
- Generate bằng Claude API → lưu file `data/majors_seed.json`
- Import vào DB qua script `seed_majors.py` khi setup
- Điểm học sinh test: inject mock grades thẳng vào bảng `Grade` hiện có

---

## 8. Admin — `/admin/majors`

- Bảng danh sách ngành: tên, trường, số môn, created_at
- Form thêm/sửa ngành: tên, trường, khoa, nhóm ngành, mô tả
- Sub-form môn học: thêm từng môn + trọng số + điểm tối thiểu
- Xóa ngành (cascade xóa weights, pins, targets liên quan)

---

## 9. API endpoints mới

| Method | Route | Mục đích |
|--------|-------|---------|
| GET | `/api/student/career/radar-data?major_id=X` | Trả về điểm hs + yêu cầu ngành để render radar |
| GET | `/api/student/career/fit?major_id=X` | Tính fit % cho 1 ngành |
| GET | `/api/student/career/browse` | Danh sách ngành + fit % (có filter/sort) |
| POST | `/api/student/career/pin` | Ghim ngành |
| DELETE | `/api/student/career/pin/<major_id>` | Bỏ ghim |
| POST | `/api/student/career/target` | Đặt ngành mục tiêu |

---

## 10. Visual style

- Light theme, Vercel-inspired
- Background: `#f5f5f5`, card: `#fff`, border: `1px solid #e5e5e5`
- Font: Inter / system-ui
- Radar student layer: `#0070f3` (xanh)
- Radar major layer: `#f97316` (cam, đứt nét)
- Status tags: xanh lá (đạt), đỏ (thiếu), vàng (gần đạt)
- Nhất quán với student portal hiện có (light theme)
