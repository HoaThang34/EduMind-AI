# Tính năng Định hướng Chọn ngành

Hệ thống giúp học sinh THPT phân tích năng lực bản thân, so khớp với yêu cầu các ngành đại học, và ra quyết định chọn ngành. Dữ liệu **617 ngành** từ **38 trường** đại học, scrape từ Tuyensinh247. Toàn bộ tính toán chạy offline trên server, không gọi AI hay API bên ngoài.

---

## Mục lục

- [Cơ chế tính toán](#cơ-chế-tính-toán)
- [Models trong DB](#models-trong-db)
- [API Endpoints](#api-endpoints)
- [Giao diện](#giao-diện)
- [Pipeline dữ liệu](#pipeline-dữ-liệu)
- [Công nghệ](#công-nghệ)
- [Danh sách hàm tính toán](#danh-sách-hàm-tính-toán)

---

## Cơ chế tính toán

### Điểm trung bình môn

```
TB_môn = (avg_TX + 2 × avg_GK + 3 × avg_HK) / 6
```

Hàm `calculate_subject_averages` trong `app_helpers.py`. Chỉ tính khi đủ 3 loại điểm (Thường xuyên / Giữa kỳ / Học kỳ).

### Điểm phù hợp ngành (fit score)

```
Với mỗi môn có weight:
    numerator   += min(điểm_HS, min_score) × weight
    denominator += min_score × weight

fit_pct = min((numerator / denominator) × 100, 100)
```

Hàm `calculate_fit_score` trong `app_helpers.py`. Điểm vượt ngưỡng `min_score` không làm tăng fit — chỉ đo mức "đạt yêu cầu có trọng số".

### Suy trọng số ngành (derive weights)

Hàm `derive_weights` trong `seed_major_weights.py`. Từ `admission_block` (khối thi) + `entry_score` (điểm chuẩn) của ngành:

| Nhóm môn | Weight | min_score |
|----------|--------|-----------|
| Môn chính (khối thi) | 0.45 | `min(entry/3 + 0.2, 10)` |
| 2 môn phụ (khối thi) | 0.225 mỗi môn | `(entry - main_score) / 2` |
| Môn cluster liên quan (theo nhóm ngành) | 0.03 | Random [5.0 – 7.0] |
| Môn còn lại | 0 | Random [3.0 – 4.5] |

Môn chính được chọn bởi `resolve_main_subject` — ưu tiên theo keyword tên ngành (vd. ngành "Công nghệ thông tin" → Toán), nếu không khớp thì dùng `main` mặc định của khối.

Random dùng seed cố định `random.Random(major.id)` → kết quả deterministic.

---

## Models trong DB

5 model mới, định nghĩa trong `models.py`:

### UniversityMajor (`university_major`)

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| id | INTEGER PK | |
| name | VARCHAR | Tên ngành |
| university | VARCHAR | Tên trường |
| faculty | VARCHAR | Khoa |
| major_group | VARCHAR | Nhóm ngành (Kỹ thuật, Y Dược, ...) |
| admission_block | VARCHAR | Khối xét tuyển (A00, D01, ...) |
| entry_score | FLOAT | Điểm chuẩn hiện tại |
| description | TEXT | Mô tả |
| created_at | DATETIME | |

Ràng buộc: `UNIQUE(name, university, admission_block)`.

### MajorSubjectWeight (`major_subject_weight`)

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| major_id | FK → university_major | |
| subject_name | VARCHAR | Tên môn (khớp `Subject.name`) |
| weight | FLOAT | Trọng số (tổng theo ngành ≈ 1.0) |
| min_score | FLOAT | Điểm sàn yêu cầu |

### MajorEntryScore (`major_entry_score`)

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| major_id | FK → university_major | |
| year | INTEGER | Năm (2023, 2024, 2025) |
| score | FLOAT | Điểm chuẩn năm đó |

### StudentPinnedMajor (`student_pinned_major`)

HS ghim ngành quan tâm. `UNIQUE(student_id, major_id)` — nhiều ngành / HS.

### StudentTargetMajor (`student_target_major`)

Ngành mục tiêu. `UNIQUE(student_id)` — tối đa 1 ngành / HS.

---

## API Endpoints

### Trang HTML (GET)

| URL | Mô tả |
|-----|-------|
| `/student/career` | Trang chính — radar, gaps, mục tiêu |
| `/student/career/browse` | Duyệt danh sách ngành |
| `/student/career/compare` | So sánh tối đa 4 ngành |
| `/student/career/map` | Bản đồ ngành (D3 force graph) |
| `/admin/majors` | Admin quản lý ngành |

### API JSON — Học sinh

| Method | URL | Mô tả |
|--------|-----|-------|
| GET | `/api/student/career/radar-data?major_id=` | Dữ liệu radar + fit + gaps cho 1 ngành |
| GET | `/api/student/career/browse?q=&group=&university=&admission_block=&min_fit=` | Tìm/lọc ngành |
| GET | `/api/student/career/my-averages` | Điểm TB từng môn của HS |
| POST | `/api/student/career/simulate` | Mô phỏng "nếu đạt điểm X → fit Y%" |
| GET | `/api/student/career/compare?major_ids=1,2,3` | So sánh nhiều ngành (tối đa 4) |
| GET | `/api/student/career/score-history?major_ids=` | Lịch sử điểm chuẩn qua các năm |
| GET | `/api/student/career/map-data` | Dữ liệu bản đồ (weight vectors + fit) |
| POST | `/api/student/career/pin` | Ghim ngành `{ major_id }` |
| DELETE | `/api/student/career/pin/<major_id>` | Bỏ ghim |
| POST | `/api/student/career/target` | Đặt ngành mục tiêu `{ major_id }` |

### API JSON — Admin

| Method | URL | Mô tả |
|--------|-----|-------|
| POST | `/admin/majors/add` | Tạo ngành + weights |
| PATCH | `/admin/majors/<id>` | Sửa admission_block / entry_score |
| DELETE | `/admin/majors/<id>` | Xóa ngành |
| POST | `/admin/majors/<id>/entry-scores` | Thêm/sửa điểm chuẩn theo năm |

---

## Giao diện

### Career Hub (`student_career.html`)

- Radar Chart.js: năng lực HS vs yêu cầu ngành
- Dropdown chọn ngành so sánh
- Bảng gaps (ok / warn / fail)
- Card ngành mục tiêu (thanh fit, danh sách gap, trạng thái đạt/chưa đạt)
- Card ngành đã ghim
- Modal đặt ngành mục tiêu (ô tìm, danh sách cuộn)

### Browse (`student_career_browse.html`)

- Thanh lọc đa tiêu chí: tìm kiếm, trường, khối, nhóm ngành, thanh trượt % fit
- Lưới thẻ ngành (lazy-load batch 30 với IntersectionObserver)
- Mỗi thẻ: mini radar + sparkline xu hướng điểm + thanh fit + ghim/mục tiêu
- Modal mô phỏng điểm (slider theo môn, tính fit realtime)
- Chọn tối đa 4 ngành để so sánh

### Compare (`student_career_compare.html`)

- Radar overlay nhiều ngành + đường điểm HS
- Line chart xu hướng điểm chuẩn 2022–2026
- Bảng chi tiết (fit, điểm, khối, từng môn, highlight "tốt nhất")
- Modal thêm/bớt ngành

### Map (`student_career_map.html`)

- D3.js force simulation: node HS ở giữa, node ngành bao quanh
- Màu theo nhóm ngành, kích thước theo fit
- Zoom LOD (ẩn/hiện nhãn theo mức zoom)
- Kéo thả node, click xem chi tiết
- Panel phải: thông tin ngành + nút thêm so sánh
- Lọc theo nhóm ngành, tìm kiếm, ẩn fit < 50%

### Admin Majors (`admin_majors.html`)

- Bảng danh sách ngành + inline edit (điểm chuẩn, khối)
- Form thêm ngành (trọng số môn động)
- Tìm kiếm client-side

---

## Pipeline dữ liệu

### Pipeline chính

Dữ liệu được scrape từ Tuyensinh247, lọc và nạp vào DB. Hiện tại có **617 ngành** từ **38 trường** đại học.

```
data/tuyensinh_urls.json ──► scripts/build_url_map.py
                              (fuzzy match tên trường ↔ Tuyensinh247)
        │
        ▼
  scripts/ts247_parser.py    (parse HTML → dict ngành/điểm/khối)
        │
        ▼
  data/scraped_tuyensinh.json (38 trường, 1002 entries)
        │
        ▼
  scripts/ingest_tuyensinh.py ──► upsert UniversityMajor
        │                          + MajorEntryScore(2025)
        │                          (lọc ngành xuất hiện ≥ 2 trường)
        ▼
  seed_entry_scores.py ──► MajorEntryScore (2023-2025)
        │                   + gán admission_block nếu thiếu
        ▼
  seed_major_weights.py ──► MajorSubjectWeight
        │                    (derive từ khối + điểm chuẩn)
        ├── đọc data/admission_blocks.json
        └── đọc data/real_majors_2025.json (nếu verified)
```

### File dữ liệu

| File | Nội dung |
|------|----------|
| `data/scraped_tuyensinh.json` | Điểm chuẩn scrape từ 38 trường (1002 entries) |
| `data/admission_blocks.json` | Khối thi (A00, D01...) + clusters + name_aliases |
| `data/real_majors_2025.json` | Metadata điểm thật bổ sung (cần verified=true) |
| `data/tuyensinh_urls.json` | URL Tuyensinh247 theo trường |
| `data/majors_seed.json` | Seed ban đầu (đã thay thế bởi data scrape) |

### Migration

- `migrate.py` — An toàn, chỉ ALTER TABLE thêm cột mới (admission_block, entry_score, ...)
- `migrate_career.py` — Tạo bảng `major_entry_score` nếu chưa có
- `rebuild_db.py --force` — Xóa sạch DB, tạo lại, chạy toàn bộ seed pipeline

---

## Công nghệ

| Lớp | Stack |
|-----|-------|
| Backend | Flask + SQLAlchemy (SQLite) |
| Frontend | Tailwind CSS |
| Chart | Chart.js 4.4.0 (radar, line, sparkline) |
| Graph | D3.js v7 (force simulation, zoom, drag) |
| Icon | Font Awesome 6 |
| Thuật toán | Weighted min-cap scoring, fuzzy search (normalize Unicode + acronym) |
| Data | Scrape Tuyensinh247 + JSON seed, deterministic random |

---

## Danh sách hàm tính toán

| Hàm | File | Chức năng |
|-----|------|-----------|
| `calculate_fit_score` | `app_helpers.py` | Tính % phù hợp ngành (weighted min-cap) |
| `calculate_subject_averages` | `app_helpers.py` | TB môn = (TX + 2×GK + 3×HK) / 6 |
| `derive_weights` | `seed_major_weights.py` | Suy weight + min_score từ khối + điểm chuẩn |
| `resolve_main_subject` | `seed_major_weights.py` | Chọn môn chính theo keyword tên ngành |
| `_radar` | `routes/career.py` | Tính axes radar (union môn core + môn HS) |
| `_fuzzy_match` | `routes/career.py` | Tìm kiếm không dấu + viết tắt |
| `_filter_gaps` | `routes/career.py` | Tính gap (ok/warn/fail), loại trừ ngoại ngữ |
| `_normalize` | `routes/career.py` | Chuẩn hóa Unicode NFD, bỏ dấu, lowercase |
| `_acronym` | `routes/career.py` | Lấy chữ cái đầu mỗi từ (cho fuzzy search) |
| `norm` / `norm_uni` | `scripts/normalize.py` | Chuẩn hóa tên ngành / trường cho matching |
