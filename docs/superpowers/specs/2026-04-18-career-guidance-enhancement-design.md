# Career Guidance Enhancement — Design Spec
**Date:** 2026-04-18
**Module:** `routes/career.py`, `templates/student_career*.html`
**Approach:** Data-first — schema migration trước, features sau

---

## Overview

Nâng cấp toàn diện module hướng nghiệp (`/student/career`) với 7 tính năng mới:
1. Score Simulator — nhập điểm dự kiến để xem fit thay đổi
2. Connected Map — bản đồ ngành force-directed theo cosine similarity
3. Comparison Page — radar overlay + versus table + line chart lịch sử
4. Filter nâng cấp — top bar + chip filters, fix search bug
5. Sparkline trong browse cards
6. Multi-admission-block support — 1 ngành nhiều khối xét tuyển
7. Historical entry scores — điểm chuẩn 2023-2024-2025

---

## Section 1: Data Model

### Thay đổi `UniversityMajor`

Thêm 2 fields:
- `admission_block` (String 20, nullable) — khối xét tuyển, ví dụ "A1", "D01", "B00"
- `entry_score` (Float, nullable) — điểm chuẩn năm hiện tại (2025)

Unique constraint đổi từ `(name, university)` → `(name, university, admission_block)`.

Hiển thị trong UI: `"Trí tuệ nhân tạo — Bách khoa"` với sub-label `"Khối A1 | ĐC: 28.5"`.

Một ngành có nhiều khối xét tuyển được tách thành nhiều records:
- `Trí tuệ nhân tạo | HUST | A1 | 28.5`
- `Trí tuệ nhân tạo | HUST | D01 | 27.0`

### Table mới: `MajorEntryScore`

```python
class MajorEntryScore(db.Model):
    __tablename__ = 'major_entry_score'
    __table_args__ = (db.UniqueConstraint('major_id', 'year'),)
    id = db.Column(db.Integer, primary_key=True)
    major_id = db.Column(db.Integer, db.ForeignKey('university_major.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)  # 2023, 2024, 2025
    score = db.Column(db.Float, nullable=False)
```

Relationship thêm vào `UniversityMajor`:
```python
entry_scores = db.relationship('MajorEntryScore', backref='major',
                                cascade='all, delete-orphan', lazy=True)
```

### Migration Strategy

- Alembic migration: thêm `admission_block`, `entry_score` vào `university_major`; tạo bảng `major_entry_score`
- Records cũ (`admission_block = NULL`) vẫn hoạt động bình thường
- Seed script `seed_entry_scores.py` tạo mock data 2023/2024/2025 cho tất cả majors hiện có (variation ±1.5 điểm mỗi năm)
- Seed script phải gán `admission_block` cho tất cả records ngay khi migrate (không để NULL tồn tại) để tránh conflict unique constraint
- Danh sách môn trong Score Simulator lấy từ union của tất cả `subject_name` trong `MajorSubjectWeight` (không phải grades học sinh)
- Admin cập nhật `admission_block` qua trang `/admin/majors`

---

## Section 2: Backend API

### Fix filter bug

`/api/student/career/browse` — chuyển từ Python loop sang SQLAlchemy filter:
```python
if q:
    query = query.filter(or_(
        UniversityMajor.name.ilike(f'%{q}%'),
        UniversityMajor.university.ilike(f'%{q}%')
    ))
if university:
    query = query.filter_by(university=university)
if admission_block:
    query = query.filter_by(admission_block=admission_block)
if major_group:
    query = query.filter_by(major_group=major_group)
```

### Endpoints mới

| Endpoint | Method | Params | Response |
|---|---|---|---|
| `/api/student/career/simulate` | POST | `{scores: {Toán: 8.5, Lý: 7.0, ...}}` | `[{major_id, name, university, fit_pct, gaps}]` sorted by fit_pct |
| `/api/student/career/compare` | GET | `major_ids=1,2,3` (tối đa 4) | `[{major, radar, weights, entry_scores, fit_pct}]` |
| `/api/student/career/score-history` | GET | `major_ids=1,2,3` | `{major_id: [{year, score}]}` |
| `/api/student/career/map-data` | GET | — | `[{id, name, university, major_group, entry_score, weight_vector: {Toán: 0.4, Lý: 0.3, ...}}]` |

**Score simulator:** Reuse `calculate_fit_score()` từ `app_helpers.py`, thay `averages` bằng dict điểm giả định từ request body.

**Connected map:** Backend trả raw weight vectors (dict môn→weight). Frontend D3.js tính cosine similarity O(n²) và chạy force simulation — tránh tính ở server mỗi request.

---

## Section 3: Frontend Pages & Components

### 3.1 Browse Page — nâng cấp (`student_career_browse.html`)

**Top filter bar:**
- Search input (fix bug: gọi `/api/student/career/browse?q=...`)
- Dropdown: Trường (lấy distinct universities từ DB)
- Dropdown: Khối xét tuyển (A1, B00, D01,...)
- Dropdown: Nhóm ngành (major_group)
- Slider: % phù hợp tối thiểu (0–100, default 0)
- Sort pills: "Phù hợp nhất" | "ĐC cao→thấp" | "Tên A-Z"
- Active filters hiện dưới dạng chips có nút ×

**Grid 2 cột, mỗi card:**
- Tên ngành (bold) + tên trường
- Sub-label: khối xét tuyển + điểm chuẩn 2025
- Fit% progress bar (màu theo mức: đỏ <50%, vàng 50-70%, xanh >70%)
- Mini sparkline Chart.js inline (3 điểm: 2023→2024→2025)
- Checkbox góc trên phải để thêm vào comparison
- Nút pin/unpin

**Nút nổi (floating):**
- "Mô phỏng điểm" (mở Score Simulator modal)
- "So sánh (n)" xuất hiện khi chọn ≥2 ngành, navigate sang `/student/career/compare`

### 3.2 Score Simulator (modal overlay)

Trigger: nút "Mô phỏng điểm" trên browse page.

**Layout:**
- Title: "Nếu điểm của bạn là..."
- Slider + input number cho từng môn (danh sách lấy từ union của tất cả subjects trong weight vectors)
- Giá trị mặc định = điểm thật của học sinh hiện tại
- Debounce 300ms → POST `/api/student/career/simulate` → cập nhật fit% tất cả cards realtime (không reload page)
- Nút "Reset về điểm thật"
- Khi modal mở, browse grid vẫn visible phía sau (semi-transparent overlay)

### 3.3 Comparison Page — trang mới (`student_career_compare.html`)

Route: `GET /student/career/compare?major_ids=1,2,3`

**Layout dọc:**

1. **Header**: danh sách ngành đang so sánh (tối đa 4), mỗi ngành có nút ×. Ô "+" mở search để thêm ngành.

2. **Radar overlay chart** (Chart.js): tất cả ngành + học sinh cùng 1 chart. Mỗi ngành 1 màu khác nhau, học sinh = màu trắng/xám.

3. **Line chart lịch sử điểm chuẩn** (Chart.js): mỗi ngành 1 đường, trục X = năm (2023-2025), đường ngang đứt = điểm hiện tại học sinh.

4. **Versus table**: 
   - Rows cố định: Fit%, Điểm chuẩn 2025, Khối xét tuyển, Xu hướng ĐC, + 1 row per subject (Toán, Lý, Hóa,...)
   - Columns = ngành
   - Highlight ô tốt nhất trong mỗi row (background xanh nhạt)
   - Ô yêu cầu môn: màu đỏ nếu học sinh chưa đạt, xanh nếu đạt

### 3.4 Connected Map — trang mới (`student_career_map.html`)

Route: `GET /student/career/map`

**Layout:**
- Full-width D3.js canvas (height: 80vh)
- Node: `circle`, radius ∝ `entry_score`, fill màu theo `major_group`
- Edge: hiện đường nối khi cosine similarity > 0.7, opacity ∝ similarity score
- Force params: `charge = -200`, `linkDistance = 80`, `collision = radius + 10`

**Detail panel (right side, 280px):**
- Hiện khi click node
- Nội dung: tên ngành, trường, khối, fit%, top 3 môn yêu cầu (tên + min_score), entry score 2025
- Nút "Thêm vào so sánh" (lưu vào sessionStorage)
- Nút "Xem chi tiết" → navigate sang career_main với major pre-selected

**Controls (top-left overlay):**
- Zoom in/out buttons
- Search input: highlight node theo tên ngành/trường
- Toggle chips theo major_group (Kỹ thuật, Kinh tế, Y dược,...)
- Checkbox "Chỉ hiện ngành phù hợp" (lọc theo fit% > 50%)

**Cosine similarity** tính ở frontend:
```js
function cosineSim(a, b, subjects) {
  const dot = subjects.reduce((s, k) => s + (a[k]||0)*(b[k]||0), 0);
  const normA = Math.sqrt(subjects.reduce((s, k) => s + (a[k]||0)**2, 0));
  const normB = Math.sqrt(subjects.reduce((s, k) => s + (b[k]||0)**2, 0));
  return normA && normB ? dot / (normA * normB) : 0;
}
```

---

## Section 4: Navigation & Integration

### Điểm truy cập

- `student_career.html` (trang chính): thêm 3 nút — "Khám phá ngành" → browse, "Bản đồ ngành" → map, "So sánh ngành" → compare
- Browse page: nút "Mô phỏng điểm" + checkbox → "So sánh (n)" floating button
- Map page: detail panel có nút "So sánh" → thêm vào sessionStorage → redirect compare
- Compare page: nút "Thêm ngành" với search, ưu tiên gợi ý từ pinned majors

### State Management

- `sessionStorage['compare_major_ids']` — JSON array, tối đa 4 IDs, đồng bộ giữa browse/compare/map
- Score simulator state: JS variable trong module, reset khi đóng modal

### Admin Page cập nhật (`admin_majors.html`)

- Form thêm ngành: thêm field `admission_block` (text input) và `entry_score` (number)
- Bảng danh sách: thêm cột "Khối" và "ĐC 2025"
- Nút "Lịch sử điểm" per row → inline form nhập score theo năm (2023/2024/2025)
- API: thêm `PATCH /admin/majors/<id>` và `POST /admin/majors/<id>/entry-scores`

### Thư viện JS

- `D3.js v7` — connected map force simulation (CDN)
- `Chart.js v4` — radar overlay, line chart, sparkline (CDN, nếu chưa có)

---

## Implementation Order (Approach A — Data-first)

1. Alembic migration + seed script
2. Fix filter bug + thêm filter params vào browse API
3. Score Simulator modal + `/api/student/career/simulate`
4. Browse page UI nâng cấp (top bar, chips, sparkline)
5. Comparison page + `/api/student/career/compare` + `/api/student/career/score-history`
6. Connected Map page + `/api/student/career/map-data`
7. Admin page cập nhật
8. Navigation integration (nút từ career_main)
