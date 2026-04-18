# Định hướng chọn ngành v2 — Design Spec

**Date:** 2026-04-18  
**Scope:** Cải tiến tính năng Định hướng chọn ngành — v2  
**Approach:** Structured v2 với data model improvements + 6 features mới

---

## Goals

1. Fix bug search/filter (tên ngành, trường) trên browse page
2. Thêm **Score Simulator** — kéo điểm giả định → fit% realtime (client-side)
3. Thêm **Versus Comparison** — so sánh 2–4 ngành chi tiết kèm điểm chuẩn lịch sử
4. Thêm **Better Filters** — khối xét tuyển, trường, sort options
5. Thêm **Connected Map** — D3.js force-directed graph, ngành cùng khối hút nhau
6. Thêm **Điểm chuẩn lịch sử** — mock data 2023/2024/2025
7. Hỗ trợ **multi-admission block** — 1 ngành nhiều khối xét tuyển (mỗi block = 1 row DB)

---

## Data Model

### 1. Thêm field `admission_block` vào `UniversityMajor`

```sql
ALTER TABLE university_major ADD COLUMN admission_block VARCHAR(20) DEFAULT 'A00';
```

Mỗi row = 1 ngành × 1 khối xét tuyển. Ví dụ "Trí tuệ nhân tạo — Bách Khoa HN":
- Row 1: `admission_block="A00"` → weights: Toán (0.45, min 9.0), Vật lý (0.30, min 8.5), Hóa học (0.25, min 8.0)
- Row 2: `admission_block="A01"` → weights: Toán (0.45, min 9.0), Vật lý (0.30, min 8.5), Tiếng Anh (0.25, min 8.5)

Các khối phổ biến: `A00` (Toán+Lý+Hóa), `A01` (Toán+Lý+Anh), `B00` (Toán+Hóa+Sinh), `C00` (Văn+Sử+Địa), `D01` (Văn+Toán+Anh), `D07` (Toán+Hóa+Anh).

**Seed strategy:** Wipe toàn bộ records trong `university_major`, `major_subject_weight`, `major_cutoff_score`, `student_pinned_major`, `student_target_major` rồi re-seed từ file mới. Đây là demo system — không có production data cần bảo toàn. `seed_majors.py` có flag `--wipe` để thực hiện.

### 2. Model mới `MajorCutoffScore`

```python
class MajorCutoffScore(db.Model):
    __tablename__ = 'major_cutoff_score'
    id = db.Column(db.Integer, primary_key=True)
    major_id = db.Column(db.Integer, db.ForeignKey('university_major.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)        # 2023, 2024, 2025
    cutoff_score = db.Column(db.Float, nullable=False)  # điểm chuẩn (thang 30)
    notes = db.Column(db.String(200))
    __table_args__ = (db.UniqueConstraint('major_id', 'year'),)
```

`UniversityMajor` thêm relationship:
```python
cutoff_scores = db.relationship('MajorCutoffScore', backref='major',
                                 cascade='all, delete-orphan', lazy=True)
```

### 3. Migration (SQLite safe)

Trong `ensure_career_tables()` (`app.py`), dùng `insp = inspect(db.engine)` (biến đã có):
```python
cols = [c['name'] for c in insp.get_columns('university_major')]
if 'admission_block' not in cols:
    db.session.execute(text(
        "ALTER TABLE university_major ADD COLUMN admission_block VARCHAR(20) DEFAULT 'A00'"
    ))
if not insp.has_table('major_cutoff_score'):
    db.session.execute(text("""
        CREATE TABLE major_cutoff_score (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            major_id INTEGER NOT NULL REFERENCES university_major(id),
            year INTEGER NOT NULL,
            cutoff_score FLOAT NOT NULL,
            notes VARCHAR(200),
            UNIQUE(major_id, year)
        )
    """))
db.session.commit()
```

---

## Mock Data Standards

### Học sinh demo — `seed_grades.py`

Profile "học sinh khá giỏi" — điểm đủ để fit tốt một số ngành, borderline với ngành khó, không đủ cho top-tier:

| Môn | TX | GK | HK | TB tính được |
|-----|-----|-----|-----|-------------|
| Toán | 8.5 | 8.5 | 8.5 | **8.5** |
| Vật lý | 8.2 | 8.0 | 8.3 | **8.18** |
| Hóa học | 7.8 | 7.5 | 7.9 | **7.77** |
| Sinh học | 7.0 | 7.0 | 7.2 | **7.07** |
| Ngữ văn | 7.5 | 7.5 | 7.8 | **7.63** |
| Tiếng Anh | 8.8 | 8.5 | 9.0 | **8.80** |
| Lịch sử | 7.0 | 7.2 | 7.5 | **7.23** |
| Địa lý | 7.5 | 7.5 | 7.8 | **7.63** |
| Giáo dục công dân | 9.0 | 9.0 | 9.2 | **9.07** |

Kết quả điểm khối: A00=8.15, A01=8.49, B00=7.78, C00=7.50, D01=8.31, D07=8.36  
→ Học sinh này fit tốt CNTT, Kinh tế; borderline với Y; không đủ top-tier như Y khoa ĐHYHN.

### Ngành — Phân tầng điểm yêu cầu

**Tier 1 — Top-tier (cutoff 27–30):**

| Ngành | Trường | Block | Min scores | Cutoff 2025 |
|-------|--------|-------|-----------|-------------|
| Y khoa | ĐH Y Hà Nội | B00 | Hóa 9.2, Sinh 9.0, Toán 8.5 | 29.20 |
| Dược học | ĐH Dược HN | B00 | Hóa 9.0, Sinh 8.8, Toán 8.0 | 28.50 |
| Trí tuệ nhân tạo | ĐHBK HN | A00 | Toán 9.0, Vật lý 8.5, Hóa 8.0 | 28.15 |
| Trí tuệ nhân tạo | ĐHBK HN | A01 | Toán 9.0, Vật lý 8.5, Anh 8.5 | 28.15 |
| Khoa học Máy tính | ĐHQG HN (UET) | A00 | Toán 9.0, Vật lý 8.5, Hóa 8.0 | 27.85 |
| Khoa học Máy tính | ĐHQG HN (UET) | A01 | Toán 9.0, Vật lý 8.5, Anh 8.5 | 27.85 |
| Kinh doanh QT | ĐH Ngoại Thương | D01 | Văn 8.5, Toán 8.5, Anh 9.0 | 28.35 |
| Tài chính - Ngân hàng | ĐH Ngoại Thương | A01 | Toán 8.5, Vật lý 8.0, Anh 8.8 | 27.60 |

**Tier 2 — Cạnh tranh (cutoff 24–27):**

| Ngành | Trường | Block | Min scores | Cutoff 2025 |
|-------|--------|-------|-----------|-------------|
| Công nghệ thông tin | FPT University | A00 | Toán 8.0, Vật lý 7.5, Hóa 7.0 | 26.00 |
| Công nghệ thông tin | FPT University | A01 | Toán 8.0, Vật lý 7.5, Anh 8.0 | 26.00 |
| Kỹ thuật Phần mềm | ĐHQG HN (UET) | A00 | Toán 8.5, Vật lý 8.0, Hóa 7.5 | 26.80 |
| Marketing | ĐH Kinh tế QD | D01 | Văn 8.0, Toán 7.5, Anh 8.5 | 26.50 |
| Quản trị Kinh doanh | ĐH Kinh tế QD | D01 | Văn 7.5, Toán 8.0, Anh 8.5 | 26.00 |
| Tài chính | ĐH Kinh tế QD | A01 | Toán 8.5, Vật lý 7.5, Anh 8.0 | 26.30 |
| Luật | ĐH Luật HN | C00 | Văn 8.5, Sử 8.0, Địa 7.5 | 25.80 |
| Luật | ĐH Luật HN | D01 | Văn 8.5, Toán 7.5, Anh 8.0 | 25.80 |
| Ngôn ngữ Anh | ĐH Ngoại Ngữ - ĐHQG | D01 | Văn 8.0, Toán 7.5, Anh 9.0 | 26.20 |
| Y tế Công cộng | ĐH Y Hà Nội | B00 | Hóa 8.0, Sinh 8.0, Toán 7.5 | 25.50 |
| Điều dưỡng | ĐH Y Hà Nội | B00 | Hóa 7.5, Sinh 7.5, Toán 7.0 | 24.00 |
| Công nghệ Sinh học | ĐHBK HN | B00 | Toán 8.0, Hóa 8.0, Sinh 7.5 | 25.20 |
| Kỹ thuật Điện | ĐHBK HN | A00 | Toán 8.5, Vật lý 8.0, Hóa 7.5 | 26.10 |
| Cơ điện tử | ĐHBK HN | A00 | Toán 8.5, Vật lý 8.0, Hóa 7.5 | 25.90 |
| Kế toán | ĐH Kinh tế QD | A01 | Toán 8.0, Vật lý 7.0, Anh 8.0 | 25.50 |
| Ngân hàng | ĐH Ngân hàng TP.HCM | A01 | Toán 8.0, Vật lý 7.0, Anh 8.0 | 25.00 |

**Tier 3 — Trung bình (cutoff 18–24):**

| Ngành | Trường | Block | Min scores | Cutoff 2025 |
|-------|--------|-------|-----------|-------------|
| Sư phạm Toán | ĐHSP HN | A00 | Toán 7.5, Vật lý 7.0, Hóa 6.5 | 23.50 |
| Sư phạm Ngữ văn | ĐHSP HN | C00 | Văn 8.0, Sử 7.0, Địa 6.5 | 23.00 |
| Giáo dục Tiểu học | ĐHSP HN | D01 | Văn 7.5, Toán 7.0, Anh 7.0 | 22.50 |
| Kỹ thuật Xây dựng | ĐH Xây dựng HN | A00 | Toán 7.5, Vật lý 7.0, Hóa 6.5 | 22.00 |
| Kỹ thuật Môi trường | ĐH Xây dựng HN | A00 | Toán 7.0, Vật lý 6.5, Hóa 7.0 | 20.50 |
| Địa lý | ĐHSP HN | C00 | Văn 7.0, Sử 6.5, Địa 7.5 | 21.00 |
| Lịch sử | ĐHSP HN | C00 | Văn 7.5, Sử 7.5, Địa 6.5 | 21.50 |
| Công nghệ Thực phẩm | ĐH Bách Khoa HCM | B00 | Toán 7.5, Hóa 7.5, Sinh 7.0 | 22.50 |
| Nông nghiệp | ĐH Nông nghiệp HN | B00 | Toán 6.5, Hóa 6.5, Sinh 6.5 | 19.00 |
| Thú y | ĐH Nông nghiệp HN | B00 | Toán 7.0, Hóa 7.0, Sinh 7.0 | 21.00 |
| Du lịch | ĐH Văn hóa HN | D01 | Văn 7.5, Toán 6.5, Anh 7.5 | 22.00 |
| Báo chí | Học viện BC&TT | C00 | Văn 8.0, Sử 7.0, Địa 6.5 | 23.50 |
| Quan hệ Quốc tế | Học viện Ngoại giao | D01 | Văn 8.0, Toán 7.5, Anh 8.5 | 24.00 |
| Điện tử Viễn thông | ĐH Bách Khoa HCM | A00 | Toán 8.0, Vật lý 7.5, Hóa 7.0 | 23.50 |
| Kỹ thuật Hóa học | ĐHBK HN | A00 | Toán 7.5, Vật lý 7.0, Hóa 7.5 | 22.80 |

> **Nguyên tắc:** Σ(min_scores 3 môn) + ~2.0 điểm ưu tiên khu vực/đối tượng ≈ cutoff. Tức là `min_score_avg ≈ (cutoff - 2.0) / 3`. Một học sinh đạt đúng min_score mỗi môn sẽ có fit% ~85–90% (không phải 100% vì formula dùng `min(student, required)`). Học sinh demo sẽ đạt fit% ~90–95% với Tier 2, ~75–85% với Tier 1, để tạo ra variance thực tế.

### Quy tắc `min_score` theo cutoff tier

| Cutoff range | min_score range per môn |
|-------------|------------------------|
| 27–30 | 8.5–9.5 |
| 24–27 | 7.5–8.5 |
| 20–24 | 6.5–7.5 |
| 18–20 | 6.0–6.5 |

---

## Features

### Feature 1: Bug Fix — Search Filter

**Root cause cần confirm:** `api_browse` filter `q` dùng Python `.lower()` nhưng tiếng Việt có dấu có thể không match nếu query string bị encode khác. 

**Fix:**
```python
q = request.args.get('q', '').strip().lower()
# và comparison:
if q and q not in major.name.lower() and q not in major.university.lower():
    continue
```
Đảm bảo cả name và university đều `.lower()` trước khi so. Flask auto-decode URL params nên `encodeURIComponent` từ JS không gây vấn đề — bug thực tế cần debug khi implement để xác định chính xác.

### Feature 2: Score Simulator

**Vị trí:** Panel collapsible phía trên filter bar trên browse page. Toggle bằng nút "🎚 Mô phỏng điểm".

**Route `career_browse` cần update:** Pass thêm `subject_averages` vào template:
```python
subject_averages = calculate_subject_averages(student.id, cfg['semester'], cfg['school_year'])
return render_template('student_career_browse.html', ..., subject_averages=subject_averages)
```

**Cách hoạt động:**
- Mỗi subject có 1 slider (range 0–10, step 0.1). Default = điểm thực (từ `subject_averages` embed vào JS).
- Khi kéo slider → JS recalculate fit% cho mỗi card visible.
- Client-side formula: `fit_pct = clamp(Σ(min(sim, req) × w) / Σ(req × w) × 100, 0, 100)`.
- Mỗi card có attribute `data-weights='[{"s":"Toán","w":0.45,"m":9.0},...]'` (compact JSON).
- Badge "📊 Đang mô phỏng" trên filter bar khi active; nút "↺ Reset" về điểm thực.
- Fit% trên card cập nhật instant, không gọi API.

### Feature 3: Better Filters

Filter bar redesign:

| Filter | Kiểu | Params API |
|--------|------|-----------|
| Search | text input, debounce 300ms | `q` |
| Khối xét tuyển | dropdown | `block` (A00/A01/B00/C00/D01/D07) |
| Nhóm ngành | dropdown | `group` |
| Trường | dropdown, scrollable max-height 300px | `university` |
| Sort | dropdown | `sort` (fit_desc/fit_asc/cutoff_desc/cutoff_asc) |

`api_browse` thêm:
- param `block`: filter theo `admission_block`
- param `sort`: fit_desc (default) | fit_asc | cutoff_desc | cutoff_asc. Sort cutoff dùng năm 2025 (LEFT JOIN với `MajorCutoffScore` year=2025, NULL xuống cuối).

### Feature 4: Versus Comparison Page

**Routes:**
- `GET /student/career/compare` → render template
- `GET /api/student/career/compare?ids=1,2,3,4` → JSON

**State management:** `localStorage` key `compareIds` (JSON array of ints, max 4). Trên browse page, mỗi card có nút "⊕ So sánh" toggle. Khi `compareIds.length >= 2`, hiện floating bar fixed bottom: "⚔️ So sánh 3 ngành →". Click → navigate to `/student/career/compare`.

**JSON response `api_compare`:**
```json
{
  "majors": [
    {
      "id": 1,
      "name": "Trí tuệ nhân tạo",
      "university": "Bách Khoa HN",
      "admission_block": "A00",
      "major_group": "Kỹ thuật - Công nghệ",
      "fit_pct": 74.2,
      "cutoff_scores": {"2023": 27.84, "2024": 28.15, "2025": 28.50},
      "gaps": [{"subject_name": "Toán", "student_score": 8.5, "min_score": 9.0, "gap": -0.5, "status": "warn"}]
    }
  ]
}
```

**Layout bảng (columns = ngành, rows = tiêu chí):**

| Row | Nội dung |
|-----|---------|
| Header | Tên ngành + trường + nút × |
| Fit % | Progress bar gradient + số % (highlight max) |
| Khối xét tuyển | Badge màu theo block |
| Điểm chuẩn 2025 | Số (bold, highlight max) |
| Điểm chuẩn 2024 | Số |
| Điểm chuẩn 2023 | Số |
| Xu hướng | Mini Chart.js line (3 điểm, inline canvas 120×40px) |
| Môn A (nếu ngành có) | `điểm_hs / min_score` + status badge |
| Môn B | ... |
| ... | |
| Nhóm ngành | Text |
| Actions | Nút Ghim + Đặt mục tiêu per column |

Môn rows: union tất cả môn của các ngành đang so sánh; nếu ngành không yêu cầu môn đó → hiện "—".

### Feature 5: Connected Map

**Routes:**
- `GET /student/career/map` → render template
- `GET /api/student/career/map-data` → `{nodes, links}`

**Node schema:**
```json
{
  "id": 1,
  "type": "major",
  "name": "Trí tuệ nhân tạo",
  "university": "ĐH Bách Khoa Hà Nội",
  "admission_block": "A00",
  "major_group": "Kỹ thuật - Công nghệ",
  "fit_pct": 74.2,
  "cutoff_2025": 28.50,
  "is_pinned": false,
  "is_target": false
}
```

**Links — giải quyết vấn đề performance:**  
Thay vì link mọi cặp cùng block (O(n²)), dùng **virtual centroid nodes**: mỗi `admission_block` có 1 invisible centroid node, và mỗi major node có link tới centroid của block nó thuộc. Kết quả: nodes cùng block tụ về centroid mà không cần O(n²) links.

```json
{
  "nodes": [
    {"id": "A00", "type": "centroid", "label": "Khối A00", "x_init": 300, "y_init": 200},
    {"id": 1, "type": "major", "name": "Trí tuệ nhân tạo", ...}
  ],
  "links": [
    {"source": 1, "target": "A00"},
    {"source": 2, "target": "A00"},
    ...
  ]
}
```

**D3.js v7 force simulation:**
```js
d3.forceSimulation(nodes)
  .force('link', d3.forceLink(links).id(d => d.id).distance(d => d.target.type === 'centroid' ? 80 : 30))
  .force('charge', d3.forceManyBody().strength(d => d.type === 'centroid' ? 0 : -60))
  .force('collide', d3.forceCollide().radius(d => d.type === 'centroid' ? 0 : nodeRadius(d) + 4))
  .force('center', d3.forceCenter(width / 2, height / 2))
```

Centroid nodes: invisible (opacity 0), không clickable, chỉ dùng làm attraction point.

**Visual encoding:**
- Color per block: A00=`#6366f1`, A01=`#0ea5e9`, B00=`#22c55e`, C00=`#f97316`, D01=`#a855f7`, D07=`#ec4899`
- Node radius = `6 + fit_pct / 100 * 14` (6–20px)
- Target: outer ring stroke `#fbbf24`
- Pinned: dashed stroke `#fbbf24`
- Hover → tooltip: tên, trường, block badge, fit%, điểm chuẩn 2025, nút Ghim/Mục tiêu

**Navigation:** Thêm tab row trên trang browse: `[📋 Danh sách]  [🗺 Bản đồ ngành]` → Bản đồ link tới `/student/career/map`.

### Feature 6: Điểm chuẩn lịch sử

Hiển thị:
1. **Versus page** — 3 data rows + mini line chart per column (Chart.js, canvas 160×45px)
2. **Map tooltip** — "Điểm chuẩn: 2025: 28.50 | 2024: 28.15 | 2023: 27.84"

**`api_compare` response** đã include `cutoff_scores` dict.

**Seed format `majors_seed.json`:**
```json
{
  "name": "Trí tuệ nhân tạo",
  "university": "ĐH Bách Khoa Hà Nội",
  "faculty": "Viện CNTT & TT",
  "major_group": "Kỹ thuật - Công nghệ",
  "admission_block": "A00",
  "cutoff_scores": [
    {"year": 2023, "cutoff_score": 27.84},
    {"year": 2024, "cutoff_score": 28.15},
    {"year": 2025, "cutoff_score": 28.50}
  ],
  "weights": [
    {"subject_name": "Toán", "weight": 0.45, "min_score": 9.0},
    {"subject_name": "Vật lý", "weight": 0.30, "min_score": 8.5},
    {"subject_name": "Hóa học", "weight": 0.25, "min_score": 8.0}
  ]
}
```

---

## Routes Summary

| Method | Path | Mục đích |
|--------|------|---------|
| GET | `/student/career` | Trang chính (unchanged) |
| GET | `/student/career/browse` | Browse page (updated + simulator) |
| GET | `/student/career/compare` | Versus page (new) |
| GET | `/student/career/map` | Connected map (new) |
| GET | `/api/student/career/browse` | List majors, thêm `block`/`sort` params |
| GET | `/api/student/career/compare` | `?ids=1,2,3` → JSON (new) |
| GET | `/api/student/career/map-data` | Nodes + links (new) |
| GET | `/api/student/career/radar-data` | Unchanged |
| POST | `/api/student/career/pin` | Unchanged |
| DELETE | `/api/student/career/pin/<id>` | Unchanged |
| POST | `/api/student/career/target` | Unchanged |

---

## File Map

| File | Action | Chi tiết |
|------|--------|---------|
| `models.py` | Modify | Thêm `MajorCutoffScore`, thêm `admission_block` + `cutoff_scores` relationship vào `UniversityMajor` |
| `app.py` | Modify | Migration thêm column `admission_block` + tạo bảng `major_cutoff_score` |
| `routes/career.py` | Modify | Fix filter bug; thêm `block`/`sort` params vào `api_browse`; pass `subject_averages` cho browse template; thêm 4 routes mới |
| `data/majors_seed.json` | Replace | Toàn bộ dữ liệu mới: đủ 5 blocks, 3 tiers, cutoff thực tế, ~50 ngành đa dạng |
| `seed_majors.py` | Modify | Flag `--wipe` để xóa sạch + re-seed; import `cutoff_scores` vào `MajorCutoffScore` |
| `seed_grades.py` | Modify | Update scores theo profile khá giỏi (TX/GK/HK thực tế như bảng trên) |
| `templates/student_career_browse.html` | Modify | Score Simulator panel, redesign filter bar, tab nav, nút "⊕ So sánh", floating compare bar |
| `templates/student_career_compare.html` | Create | Versus bảng + mini line charts |
| `templates/student_career_map.html` | Create | D3.js connected map với centroid clustering |
| `tests/test_career.py` | Modify | Thêm tests: filter bug, api_compare, api_map_data, score simulator formula |

---

## Technical Constraints

- SQLite: chỉ dùng `ALTER TABLE ... ADD COLUMN` (không DROP, không RENAME)
- D3.js v7 CDN — không npm/build step
- Score Simulator: weights compact JSON trong `data-weights` attr — không API call
- Compare state: `localStorage` — không server session
- `subject_name` trong `MajorSubjectWeight` phải khớp chính xác `Subject.name` trong DB. Tên chính xác: `Toán`, `Vật lý`, `Hóa học`, `Sinh học`, `Văn` (không phải "Ngữ văn"), `Tiếng Anh`, `Lịch sử`, `Địa lý`, `Giáo dục công dân`. Các bảng tier trong spec dùng tên tắt ("Văn", "Sử", "Địa", "Anh") để dễ đọc — file `majors_seed.json` thực tế phải dùng tên đầy đủ đúng DB.
- PC-first design

---

## Out of Scope

- Major detail pages
- Export PDF / print
- Push notifications
- AI Career Advisor / Strength Profile Card (v3)
- Mobile-responsive design
