# Career Data Realism — Design Spec

**Date:** 2026-04-18
**Status:** Approved
**Approach:** 1 — Cào điểm chuẩn thật + sinh min_score/weight toàn diện theo công thức + fix radar

---

## Context

Module "Định hướng chọn ngành" hiện có 3 vấn đề làm đánh giá phù hợp nghề (fit score) và radar chart bị lệch so với thiết kế ban đầu:

1. **Điểm chuẩn giả:** `seed_entry_scores.py` sinh điểm ngẫu nhiên quanh base 22.0. 139/139 ngành đều có entry_score nhưng không phản ánh thực tế Việt Nam 2023–2025.
2. **Khối thi quá thô:** DB chỉ có 2 giá trị `'A1'` và `'C00'`. Thực tế VN có A00, A01, A02, B00, B08, C00, C03, C15, D01, D07, D14, V00, V01, H00, T00...
3. **MajorSubjectWeight chỉ 3 môn/ngành:** Radar chỉ 3 trục, không cho thấy "profile toàn diện" của ngành. Các môn không thuộc khối bị bỏ trống → radar không toàn cảnh.
4. **Bug render:** Browse page có `<canvas id="mini-...">` nhưng radar không render do `labels` rỗng (phụ thuộc `averages.keys()` — học sinh chưa đủ điểm → trống).

---

## Goals

- Điểm chuẩn 2023/2024/2025 lấy từ nguồn công khai (không bịa)
- Mỗi ngành có "hồ sơ điểm yêu cầu" trải toàn bộ ~20 môn, phân bổ hợp lý:
  - Môn trong khối: cao, tính ngược từ entry_score
  - Môn cùng cluster ngành (STEM/Xã hội/...): trung bình 5–7
  - Môn không liên quan: baseline 3–4.5 (tự nhiên, không flat 3)
- Fit score sử dụng weight có ý nghĩa: môn khối dominate, môn khác vẫn hiển thị trên radar nhưng không inflate/deflate fit
- Radar browse page render đủ ~7–8 trục cho mọi ngành

## Non-Goals

- Không cào bổ sung ngành mới (giữ 139 ngành hiện có, không mở rộng lên 150)
- Không động tới điểm học sinh Hồ Lực Nguyên đã seed trước
- Không đổi schema DB (`MajorSubjectWeight` giữ nguyên 4 cột)
- Không đổi framework UI (Tailwind only, không Bootstrap)

---

## Architecture

```
[Mình + WebSearch/WebFetch]
   │
   ▼
data/real_majors_2025.json              (mình ghi tay từ kết quả search)
data/admission_blocks.json              (lookup tĩnh, mình viết tay)
   │
   ▼
seed_major_weights.py                   (1 script Python)
   │  ├── Load 2 JSON trên
   │  ├── Với mỗi UniversityMajor: compute min_score + weight cho ~20 môn
   │  ├── DELETE existing weights của major đó
   │  └── INSERT mới
   ▼
MajorSubjectWeight table                (~2800 rows: 139 × ~20)
UniversityMajor.entry_score, admission_block  (cập nhật từ JSON)
MajorEntryScore table                   (3 năm × 139 ngành, từ JSON)
   │
   ▼
routes/career.py::_radar()              (fix union labels)
templates/student_career_browse.html    (verify render)
```

---

## Part 1: Data Acquisition

### 1.1 Nguồn cào
Ưu tiên theo thứ tự:
1. `tuyensinh247.com` — có bảng điểm theo trường × ngành × năm
2. `vnexpress.net/giao-duc/tuyen-sinh` — bài báo tổng hợp
3. `tienphong.vn` — bài báo
4. `tuoitre.vn/giao-duc` — backup

### 1.2 Quy trình
- Lấy danh sách 139 ngành × trường từ DB: `SELECT name, university FROM university_major`
- Với mỗi cặp (ngành, trường): WebSearch `"<ngành> <trường> điểm chuẩn 2025"`
- Parse lấy `block, 2023, 2024, 2025`
- Ngành không tìm được sau 3 lần thử → skip, ghi log, `verified=false`
- Cap tool calls: 3/ngành max để kiểm soát context

### 1.3 Output — `data/real_majors_2025.json`
```json
{
  "Khoa học Máy tính|Đại học Bách Khoa Hà Nội": {
    "block": "A01",
    "scores": {"2023": 28.8, "2024": 28.5, "2025": 29.2},
    "source": "tuyensinh247.com/dai-hoc-bach-khoa-ha-noi",
    "verified": true
  },
  "Ngành ít phổ biến|Trường X": {
    "block": null,
    "scores": {},
    "verified": false,
    "note": "Không tìm thấy nguồn"
  }
}
```

---

## Part 2: Admission Blocks Lookup — `data/admission_blocks.json`

### 2.1 Block → subjects (chính + 2 phụ)
```json
{
  "A00": {"subjects": ["Toán", "Lý", "Hóa"], "main": "Toán"},
  "A01": {"subjects": ["Toán", "Lý", "Anh"], "main": "Toán"},
  "A02": {"subjects": ["Toán", "Lý", "Sinh"], "main": "Toán"},
  "B00": {"subjects": ["Toán", "Hóa", "Sinh"], "main": "Toán"},
  "B08": {"subjects": ["Toán", "Sinh", "Anh"], "main": "Toán"},
  "C00": {"subjects": ["Văn", "Sử", "Địa"], "main": "Văn"},
  "C03": {"subjects": ["Toán", "Văn", "Sử"], "main": "Văn"},
  "C15": {"subjects": ["Văn", "Toán", "KHXH"], "main": "Văn"},
  "D01": {"subjects": ["Toán", "Văn", "Anh"], "main": "Toán"},
  "D07": {"subjects": ["Toán", "Hóa", "Anh"], "main": "Toán"},
  "D14": {"subjects": ["Văn", "Sử", "Anh"], "main": "Văn"},
  "V00": {"subjects": ["Toán", "Lý", "Vẽ"], "main": "Vẽ"},
  "V01": {"subjects": ["Toán", "Văn", "Vẽ"], "main": "Vẽ"},
  "H00": {"subjects": ["Văn", "Vẽ", "Vẽ"], "main": "Vẽ"},
  "T00": {"subjects": ["Toán", "Sinh", "Năng khiếu"], "main": "Toán"}
}
```

### 2.2 Cluster → subjects
```json
{
  "STEM":       ["Toán","Lý","Hóa","Sinh","Tin học","Công nghệ"],
  "Xã hội":     ["Sử","Địa","GDCD","KTPL","Triết","Ngữ văn","Văn"],
  "Ngôn ngữ":   ["Anh","Pháp","Đức","Nhật","Trung","Hàn","Nga"],
  "Nghệ thuật": ["Âm nhạc","Hội họa","Vẽ"],
  "Thể chất":   ["GDTC","QPAN"]
}
```

### 2.3 `major_group` → cluster chính (fallback nếu block không nhận diện được)
```python
GROUP_TO_CLUSTERS = {
  "Kỹ thuật":   ["STEM"],
  "Công nghệ":  ["STEM"],
  "Y dược":     ["STEM"],
  "Kinh tế":    ["STEM", "Ngôn ngữ"],
  "Xã hội":     ["Xã hội", "Ngôn ngữ"],
  "Nghệ thuật": ["Nghệ thuật", "Xã hội"],
}
```

---

## Part 3: Weight Derivation — `seed_major_weights.py`

### 3.1 Input
- Load `data/real_majors_2025.json` và `data/admission_blocks.json`
- Load danh sách Subject trong DB (tên subject)
- Load UniversityMajor từ DB

### 3.2 Công thức

**Bước 1:** Cập nhật `UniversityMajor`:
- Nếu JSON có entry verified: ghi đè `entry_score = scores["2025"]`, `admission_block = block`
- Cập nhật `MajorEntryScore` cho 2023, 2024, 2025

**Bước 2:** Với mỗi major, compute min_score + weight cho từng môn:

```python
def derive_weights(major, blocks_data, clusters_data):
    block = blocks_data.get(major.admission_block)
    if not block:
        # Fallback: dùng cluster từ major_group, chọn block mặc định
        return None  # skip, log warning

    entry = major.entry_score
    main_subj = block["main"]
    main_score = round(min(entry/3 + 0.2, 10.0), 1)
    other_score = round((entry - main_score) / 2, 1)

    rng = Random(major.id)  # deterministic seed
    weights = []

    # (a) Môn khối (3)
    for subj in block["subjects"]:
        score = main_score if subj == main_subj else other_score
        weights.append({"subject_name": subj, "min_score": score, "weight": 0.30})

    # (b) Môn cùng cluster (không trong khối)
    major_clusters = GROUP_TO_CLUSTERS.get(major.major_group, ["STEM"])
    related = set()
    for c in major_clusters:
        related |= set(clusters_data[c])
    related -= set(block["subjects"])

    for subj in sorted(related):
        score = round(rng.uniform(5.0, 7.0), 1)
        weights.append({"subject_name": subj, "min_score": score, "weight": 0.03})

    # (c) Môn không liên quan
    all_subjects = set(s.name for s in Subject.query.all())
    unrelated = all_subjects - related - set(block["subjects"])
    for subj in sorted(unrelated):
        score = round(rng.uniform(3.0, 4.5), 1)
        weights.append({"subject_name": subj, "min_score": score, "weight": 0.0})

    return weights
```

**Bước 3:** Idempotent write:
```python
MajorSubjectWeight.query.filter_by(major_id=major.id).delete()
for w in weights:
    db.session.add(MajorSubjectWeight(major_id=major.id, **w))
db.session.commit()
```

### 3.3 Safety
- Backup DB trước chạy: `cp database.db database.db.backup-<timestamp>`
- Wrap trong `app.app_context()`
- Log theo batch 20 major/lần, report progress
- Ngành không có block nhận diện được → skip, in warning, giữ weights cũ

### 3.4 Subject name normalization

DB hiện có trùng lặp tên môn (cần map khi so sánh):
- "Ngữ văn" (id 6, code NV) ↔ "Văn" (id 14, code VAN) — block lookup dùng "Văn"
- "Ngoại ngữ" (id 5, code NN) ↔ "Tiếng Anh" (id 15, code ANH) — block lookup dùng "Anh"
- "Giáo dục Quốc phòng và An ninh" (id 2, QPAN) ↔ "Giáo dục quốc phòng - An ninh" (id 26, GDPQ)

Strategy: `seed_major_weights.py` duyệt subject trong DB theo `code` chính thức (TOAN, LY, HOA, SINH, VAN, ANH, ...) và map block subject name → code. Bảng alias:
```python
SUBJECT_ALIAS = {
  "Toán": "TOAN", "Lý": "LY", "Hóa": "HOA", "Sinh": "SINH",
  "Văn": "VAN", "Anh": "ANH", "Sử": "SU", "Địa": "DIA",
  "GDCD": "GDCD", "KTPL": "KTPL", "Tin học": "TIN", "Công nghệ": "CN",
  "Vẽ": "HH",  # Hội họa
  "Năng khiếu": None,  # skip, không có môn tương ứng
  "KHXH": None,  # tổ hợp, skip
  "Pháp": "PHAP", "Đức": "DUC", "Nhật": "NHAT",
  "Trung": "TRUNG", "Hàn": "HAN", "Nga": "NGA",
  "Âm nhạc": "AM", "Hội họa": "HH",
  "GDTC": "GDTC", "QPAN": "QPAN",
  "Ngữ văn": "VAN", "Tiếng Anh": "ANH", "Ngoại ngữ": "ANH",
}
```

`MajorSubjectWeight.subject_name` ghi theo `Subject.name` canonical (tra từ code → Subject).

---

## Part 4: Fit/Radar Logic Update — `routes/career.py`

### 4.1 Fix `_radar()`
```python
def _radar(major_id, averages):
    weights = MajorSubjectWeight.query.filter_by(major_id=major_id).all()
    req = {w.subject_name: w.min_score for w in weights}
    # Core = môn khối + môn liên quan (weight >= 0.03)
    core = {w.subject_name for w in weights if w.weight >= 0.03}
    labels = sorted(core | set(averages.keys()))
    stu_scores = [averages.get(s, 0.0) for s in labels]
    maj_scores = [req.get(s, 0.0) for s in labels]
    return labels, stu_scores, maj_scores, weights
```

### 4.2 Fit score behavior
- `calculate_fit_score()` không đổi
- Môn `weight=0` (unrelated) không ảnh hưởng numerator/denominator → fit chỉ tính trên môn khối + cluster
- Radar vẫn hiển thị min_score baseline 3–4.5 cho unrelated subjects

---

## Part 5: Browse Page Render Verify — `templates/student_career_browse.html`

### 5.1 Không cần code mới
JS đã có `initMiniRadar(m)` tại dòng 229-244. Guard `if (!canvas || !m.radar || m.radar.labels.length===0) return;` là nguyên nhân bỏ qua — sẽ tự chạy đúng sau khi backend trả labels >= 3.

### 5.2 Placeholder fallback
Sửa guard để hiện placeholder thay vì bỏ qua:
```js
if (!m.radar || m.radar.labels.length===0) {
  canvas.parentElement.innerHTML = '<div class="text-[10px] text-gray-400">Chưa có dữ liệu</div>';
  return;
}
```

---

## Files Changed

### New files
1. `data/real_majors_2025.json` — scrape output (mình ghi tay từ WebSearch)
2. `data/admission_blocks.json` — static lookup
3. `seed_major_weights.py` — sinh MajorSubjectWeight

### Modified files
1. `routes/career.py` — fix `_radar()` dùng union labels
2. `templates/student_career_browse.html` — placeholder khi radar trống (tiny fix)
3. `rebuild_db.py` — thêm gọi `seed_major_weights` sau `seed_entry_scores`

### Untouched (per user instruction)
- `models.py` — schema nguyên
- Điểm Hồ Lực Nguyên đã seed
- Templates khác
- Tailwind / framework UI

---

## Migration Safety

- Backup `database.db` trước mỗi chạy script
- Script idempotent (DELETE rồi INSERT)
- Rollback: restore từ backup nếu output kỳ quặc
- Fail mode: ngành nào lỗi → skip, log, script vẫn chạy tiếp
- Test trước với subset 5 ngành (KHMT, Y đa khoa, Luật, Sư phạm Toán, Kiến trúc) — review min_score output có hợp lý không, rồi mới chạy full

---

## Out of Scope

- Thêm ngành mới để tròn 150
- Re-mock điểm học sinh khác (chỉ HLN đã mock)
- Thêm trang admin chỉnh min_score bằng tay
- Viết test unit cho `seed_major_weights.py`
- Cache radar data để giảm query

---

## Acceptance Criteria

1. `data/real_majors_2025.json` có ≥ 100/139 ngành `verified=true`
2. `data/admission_blocks.json` chứa đúng 15 khối + 5 cluster
3. `seed_major_weights.py` chạy xong: `MajorSubjectWeight.query.count() >= 2500`
4. KHMT Bách Khoa: Toán min ~9.9, Lý/Anh min ~9.6, Văn/Sử min 3–4.5
5. Browse page: load HLN, mỗi card ngành hiện mini radar với ≥ 3 trục
6. Fit score của HLN cho các ngành A-block (KHMT, Toán ứng dụng, Vật lý kỹ thuật) cao hơn rõ rệt các ngành C-block (Luật, Báo chí)
