# Career Data Realism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay điểm chuẩn mock bằng điểm thật cào từ web, sinh `MajorSubjectWeight` toàn diện (~20 môn/ngành) theo block + cluster, và fix radar chart trong browse page.

**Architecture:** (1) Mình (AI) cào điểm chuẩn 139 ngành bằng WebSearch/WebFetch → JSON tĩnh. (2) Viết lookup tĩnh cho khối thi + cluster. (3) Script Python `seed_major_weights.py` derive min_score/weight theo công thức + sinh 2800 rows. (4) Backend `_radar()` union labels để radar không rỗng. (5) Frontend placeholder khi radar trống.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, SQLite, Chart.js 4.x, Tailwind CSS. Scraping qua Claude Code tools (WebSearch, WebFetch) — không script.

**Spec:** `docs/superpowers/specs/2026-04-18-career-data-realism-design.md`

---

## Phase 0: Preparation

### Task 0.1: Backup database

**Files:**
- Create: `database.db.backup-career-realism-<timestamp>`

- [ ] **Step 1: Backup DB**

Run:
```bash
cp database.db "database.db.backup-career-realism-$(date +%Y%m%d-%H%M%S)"
ls -la database.db.backup-career-realism-*
```

Expected: Một file mới `database.db.backup-career-realism-YYYYMMDD-HHMMSS` được tạo, cùng size với `database.db`.

- [ ] **Step 2: Verify backup readable**

Run:
```bash
sqlite3 database.db.backup-career-realism-*.db "SELECT COUNT(*) FROM university_major;" 2>/dev/null || \
sqlite3 "$(ls -t database.db.backup-career-realism-* | head -1)" "SELECT COUNT(*) FROM university_major;"
```

Expected: `139`

---

### Task 0.2: Stop Flask (avoid DB locks during seed)

- [ ] **Step 1: Kill Flask on port 5001**

Run:
```bash
lsof -ti:5001 | xargs kill -9 2>/dev/null; sleep 1
lsof -ti:5001 && echo "still running" || echo "stopped"
```

Expected: `stopped`

---

## Phase 1: Static Lookup Files

### Task 1.1: Write `data/admission_blocks.json`

**Files:**
- Create: `data/admission_blocks.json`

- [ ] **Step 1: Verify data/ directory exists**

Run: `ls data/ | head -5`

Expected: Hiện ra các file JSON đã có (`majors_seed.json`, v.v.)

- [ ] **Step 2: Create admission_blocks.json**

Write file `data/admission_blocks.json`:
```json
{
  "blocks": {
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
  },
  "clusters": {
    "STEM":       ["Toán","Lý","Hóa","Sinh","Tin học","Công nghệ"],
    "Xã hội":     ["Sử","Địa","GDCD","KTPL","Triết","Ngữ văn","Văn"],
    "Ngôn ngữ":   ["Anh","Pháp","Đức","Nhật","Trung","Hàn","Nga"],
    "Nghệ thuật": ["Âm nhạc","Hội họa","Vẽ"],
    "Thể chất":   ["GDTC","QPAN"]
  },
  "group_to_clusters": {
    "Kỹ thuật":   ["STEM"],
    "Công nghệ":  ["STEM"],
    "Y dược":     ["STEM"],
    "Kinh tế":    ["STEM", "Ngôn ngữ"],
    "Xã hội":     ["Xã hội", "Ngôn ngữ"],
    "Nghệ thuật": ["Nghệ thuật", "Xã hội"]
  },
  "name_aliases": {
    "Toán": "Toán",
    "Vật lý": "Lý",
    "Lý": "Lý",
    "Hóa học": "Hóa",
    "Hóa": "Hóa",
    "Sinh học": "Sinh",
    "Sinh": "Sinh",
    "Ngữ văn": "Văn",
    "Văn": "Văn",
    "Ngoại ngữ": "Anh",
    "Tiếng Anh": "Anh",
    "Anh": "Anh",
    "Lịch sử": "Sử",
    "Sử": "Sử",
    "Địa lý": "Địa",
    "Địa": "Địa",
    "Giáo dục công dân": "GDCD",
    "GDCD": "GDCD",
    "Giáo dục Kinh tế và Pháp luật": "KTPL",
    "KTPL": "KTPL",
    "Tin học": "Tin học",
    "Công nghệ": "Công nghệ",
    "Hội họa": "Vẽ",
    "Vẽ": "Vẽ",
    "Âm nhạc": "Âm nhạc",
    "Giáo dục thể chất": "GDTC",
    "GDTC": "GDTC",
    "Giáo dục Quốc phòng và An ninh": "QPAN",
    "Giáo dục quốc phòng - An ninh": "QPAN",
    "QPAN": "QPAN",
    "Triết học": "Triết",
    "Tiếng Pháp": "Pháp",
    "Pháp": "Pháp",
    "Tiếng Đức": "Đức",
    "Đức": "Đức",
    "Tiếng Nhật": "Nhật",
    "Nhật": "Nhật",
    "Tiếng Trung": "Trung",
    "Trung": "Trung",
    "Tiếng Hàn": "Hàn",
    "Hàn": "Hàn",
    "Tiếng Nga": "Nga",
    "Nga": "Nga"
  }
}
```

- [ ] **Step 3: Validate JSON**

Run:
```bash
python3 -c "import json; d = json.load(open('data/admission_blocks.json')); print(f'blocks={len(d[\"blocks\"])}, clusters={len(d[\"clusters\"])}, aliases={len(d[\"name_aliases\"])}')"
```

Expected: `blocks=15, clusters=5, aliases=43`

- [ ] **Step 4: Commit**

```bash
git add data/admission_blocks.json
git commit -m "feat(career): add admission blocks + cluster lookup for weight derivation"
```

---

## Phase 2: Scrape Real Entry Scores

> **Note:** Phase này là phần tôi (AI) trực tiếp làm bằng WebSearch/WebFetch, không có code. Chia thành 7 batch × 20 ngành để kiểm soát context và có checkpoint review giữa batches.

### Task 2.0: Initialize output file

**Files:**
- Create: `data/real_majors_2025.json`

- [ ] **Step 1: Get list of majors from DB**

Run:
```bash
python3 -c "
from app import app
from models import UniversityMajor
with app.app_context():
    majors = UniversityMajor.query.order_by(UniversityMajor.major_group, UniversityMajor.university, UniversityMajor.name).all()
    import json
    result = {f'{m.name}|{m.university}': {'block': None, 'scores': {}, 'source': None, 'verified': False, 'major_group': m.major_group} for m in majors}
    with open('data/real_majors_2025.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'Initialized {len(result)} entries')
" 2>/dev/null
```

Expected: `Initialized 139 entries`

- [ ] **Step 2: Verify file**

Run:
```bash
python3 -c "import json; d = json.load(open('data/real_majors_2025.json')); print(f'total={len(d)}, first 3 keys:'); [print(' ', k) for k in list(d.keys())[:3]]"
```

Expected: `total=139` + 3 keys dạng `Ngành|Trường`

---

**Context management note:** Phase 2 có thể tốn ~300-400 tool calls (3 × 139). Nếu context gần đầy:
- Compact bằng cách restart conversation sau mỗi 2 batch, đọc lại `data/real_majors_2025.json` để biết progress
- Hoặc chạy Phase 2 trong subagent riêng (dispatch qua subagent-driven-development)

### Task 2.1–2.7: Scrape in batches of 20

Mỗi batch làm theo mẫu sau (Task 2.1 là ví dụ; 2.2–2.7 tương tự với slice khác):

**Files:**
- Modify: `data/real_majors_2025.json`

- [ ] **Step 1: Pick 20 majors chưa verified**

Run:
```bash
python3 -c "
import json
d = json.load(open('data/real_majors_2025.json'))
pending = [k for k, v in d.items() if not v['verified']][:20]
for k in pending:
    print(k)
"
```

Expected: In ra 20 dòng `Ngành|Trường`

- [ ] **Step 2: Cho mỗi ngành, search + parse**

Cho mỗi key `Ngành|Trường`:
1. `WebSearch("<Ngành> <Trường> điểm chuẩn 2025")`
2. Nếu kết quả có trang `tuyensinh247.com`, `vnexpress.net/giao-duc`, `tienphong.vn`: `WebFetch` URL đó với prompt: *"Trích xuất điểm chuẩn 2023, 2024, 2025 và khối thi chính (A00/A01/B00/D01/...) của ngành X tại trường Y. Trả về dạng JSON: {block, score_2023, score_2024, score_2025, source_url}."*
3. Nếu không có kết quả rõ → thử WebSearch lần 2 với variant tên (vd bỏ "Đại học" / "Trường ĐH")
4. Nếu 3 lần thử vẫn không có → đánh dấu `verified: false`, `note: "Không tìm được nguồn"`

**Cap:** tối đa 3 tool calls / ngành.

- [ ] **Step 3: Update JSON**

Sau mỗi ngành parse xong, update entry:
```python
d[key] = {
  "block": "A01",
  "scores": {"2023": 28.8, "2024": 28.5, "2025": 29.2},
  "source": "https://tuyensinh247.com/...",
  "verified": True,
  "major_group": d[key]["major_group"]
}
# hoặc nếu fail:
d[key]["verified"] = False
d[key]["note"] = "Không tìm được nguồn"
```

Ghi lại file JSON ngay sau mỗi 20 ngành (1 batch) để tránh mất tiến độ.

- [ ] **Step 4: Progress report**

Sau batch:
```bash
python3 -c "
import json
d = json.load(open('data/real_majors_2025.json'))
ok = sum(1 for v in d.values() if v['verified'])
fail = len(d) - ok
print(f'Progress: {ok}/{len(d)} verified, {fail} pending/failed')
"
```

Expected progression: batch 1→20, batch 2→40, ..., batch 7→139.

- [ ] **Step 5: Commit after each batch**

```bash
git add data/real_majors_2025.json
git commit -m "data(career): scrape batch <N>/7 — <count> majors verified"
```

**Checkpoint for reviewer after each batch:** user review JSON sample (3-5 entries), xác nhận số liệu hợp lý, source link mở được, block đúng format. Nếu phát hiện ngành sai → note lại, sửa ở batch cuối hoặc bỏ qua.

---

### Task 2.8: Final verification

- [ ] **Step 1: Count verified**

Run:
```bash
python3 -c "
import json
d = json.load(open('data/real_majors_2025.json'))
ok = sum(1 for v in d.values() if v['verified'])
print(f'{ok}/{len(d)} verified')
assert ok >= 100, f'Only {ok} verified, need >= 100 per acceptance criteria'
print('PASS')
"
```

Expected: `PASS` (≥ 100/139 verified)

- [ ] **Step 2: Verify block coverage**

Run:
```bash
python3 -c "
import json
from collections import Counter
d = json.load(open('data/real_majors_2025.json'))
blocks = Counter(v['block'] for v in d.values() if v['verified'])
print(blocks)
"
```

Expected: Có đủ các khối A00, A01, B00, C00, D01 (không còn chỉ 'A1' và 'C00')

---

## Phase 3: Seed Script with TDD

### Task 3.1: Setup test file

**Files:**
- Create: `tests/test_seed_major_weights.py`

- [ ] **Step 1: Check pytest works**

Run: `python3 -m pytest tests/ --co -q 2>&1 | tail -5`

Expected: Danh sách test đã có, không error import.

- [ ] **Step 2: Create test file with first failing test**

Write `tests/test_seed_major_weights.py`:
```python
"""Tests for seed_major_weights — sinh min_score/weight cho ~20 môn/ngành."""
import pytest
import json
from pathlib import Path


@pytest.fixture
def blocks_data():
    return json.loads(Path('data/admission_blocks.json').read_text(encoding='utf-8'))


DB_SUBJECTS = ["Toán","Vật lý","Hóa học","Sinh học","Ngữ văn","Ngoại ngữ",
               "Lịch sử","Địa lý","Giáo dục công dân","Giáo dục Kinh tế và Pháp luật",
               "Tin học","Công nghệ","Giáo dục thể chất",
               "Giáo dục Quốc phòng và An ninh","Triết học",
               "Tiếng Pháp","Tiếng Đức","Tiếng Nhật","Tiếng Trung","Tiếng Hàn","Tiếng Nga",
               "Âm nhạc","Hội họa"]


def test_derive_weights_for_A01_STEM_major(blocks_data):
    """KHMT (A01, 29.2): Toán main ~9.9, Vật lý/Ngoại ngữ ~9.6.
    Output dùng DB name (Vật lý, Ngoại ngữ) không phải tên ngắn."""
    from seed_major_weights import derive_weights
    
    class FakeMajor:
        id = 999
        name = "Test"
        admission_block = "A01"
        entry_score = 29.2
        major_group = "Công nghệ"
    
    weights = derive_weights(FakeMajor(), blocks_data, DB_SUBJECTS)
    
    assert weights is not None
    by_subj = {w['subject_name']: w for w in weights}
    
    # Block subjects (DB names, not short)
    assert 9.7 <= by_subj['Toán']['min_score'] <= 10.0
    assert by_subj['Toán']['weight'] == 0.30
    assert 9.3 <= by_subj['Vật lý']['min_score'] <= 9.8
    assert by_subj['Vật lý']['weight'] == 0.30
    assert 9.3 <= by_subj['Ngoại ngữ']['min_score'] <= 9.8
    assert by_subj['Ngoại ngữ']['weight'] == 0.30
    
    # Short names must NOT appear when DB has the long version
    assert 'Lý' not in by_subj
    assert 'Anh' not in by_subj
    assert 'Văn' not in by_subj
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_seed_major_weights.py -v`

Expected: FAIL — `ImportError: No module named 'seed_major_weights'`

---

### Task 3.2: Implement `seed_major_weights.derive_weights()` (minimal)

**Files:**
- Create: `seed_major_weights.py`

- [ ] **Step 1: Write minimal implementation to pass first test**

Write `seed_major_weights.py`:
```python
"""Derive MajorSubjectWeight rows (min_score + weight) for all majors.

Công thức:
- Môn khối (3): main = entry/3 + 0.2, 2 môn phụ chia đều phần còn lại. Weight 0.30.
- Môn cùng cluster (không trong khối): random [5.0, 7.0], seed theo major_id. Weight 0.03.
- Môn không liên quan: random [3.0, 4.5], seed theo major_id. Weight 0.0.
"""
import json
import random
import sys
import os
from pathlib import Path

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)


def derive_weights(major, blocks_data, all_subject_names):
    """Tính weights cho 1 major. Trả về list[dict] hoặc None nếu không derive được.

    `all_subject_names` là tên môn canonical trong DB (vd 'Vật lý', 'Ngữ văn').
    Output subject_name CŨNG là tên DB (để khớp với averages khi fit calc).
    Block lookup dùng tên ngắn ('Lý', 'Văn') — alias qua name_aliases.

    Args:
        major: object có .id, .admission_block, .entry_score, .major_group
        blocks_data: dict load từ data/admission_blocks.json (phải có 'name_aliases')
        all_subject_names: list[str] — tên các môn có trong DB (Subject.name)
    """
    block_info = blocks_data['blocks'].get(major.admission_block)
    if not block_info or not major.entry_score:
        return None

    aliases = blocks_data['name_aliases']

    # Map canonical name → DB name (lấy DB name làm output).
    # Vd "Lý" → "Vật lý" nếu DB có "Vật lý".
    canonical_to_db = {}
    for db_name in all_subject_names:
        canon = aliases.get(db_name, db_name)
        # Chỉ giữ 1 mapping/canon (ưu tiên DB name đầu tiên gặp)
        if canon not in canonical_to_db:
            canonical_to_db[canon] = db_name

    def to_db_name(canonical):
        return canonical_to_db.get(canonical)  # None nếu không có trong DB

    entry = major.entry_score
    main_subj = block_info['main']
    main_score = round(min(entry / 3 + 0.2, 10.0), 1)
    other_score = round((entry - main_score) / 2, 1)

    rng = random.Random(major.id)
    weights = []
    used_db_names = set()  # các DB name đã được assign

    # (a) Block subjects
    for canon in block_info['subjects']:
        db_name = to_db_name(canon)
        if not db_name or db_name in used_db_names:
            continue
        used_db_names.add(db_name)
        score = main_score if canon == main_subj else other_score
        weights.append({'subject_name': db_name, 'min_score': score, 'weight': 0.30})

    # (b) Related cluster subjects
    clusters_for_group = blocks_data['group_to_clusters'].get(major.major_group, ['STEM'])
    related_canon = set()
    for cname in clusters_for_group:
        related_canon |= set(blocks_data['clusters'].get(cname, []))
    related_canon -= set(block_info['subjects'])

    for canon in sorted(related_canon):
        db_name = to_db_name(canon)
        if not db_name or db_name in used_db_names:
            continue
        used_db_names.add(db_name)
        score = round(rng.uniform(5.0, 7.0), 1)
        weights.append({'subject_name': db_name, 'min_score': score, 'weight': 0.03})

    # (c) Unrelated: mọi DB name chưa dùng
    unrelated_db = set(all_subject_names) - used_db_names
    for db_name in sorted(unrelated_db):
        score = round(rng.uniform(3.0, 4.5), 1)
        weights.append({'subject_name': db_name, 'min_score': score, 'weight': 0.0})

    return weights
```

- [ ] **Step 2: Run test**

Run: `python3 -m pytest tests/test_seed_major_weights.py::test_derive_weights_for_A01_STEM_major -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add seed_major_weights.py tests/test_seed_major_weights.py
git commit -m "feat(career): seed_major_weights derive_weights() with A01 block test"
```

---

### Task 3.3: Add test for related + unrelated bands

**Files:**
- Modify: `tests/test_seed_major_weights.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_seed_major_weights.py`:
```python
def test_derive_weights_related_and_unrelated_bands(blocks_data):
    """STEM major A01: Hóa học/Sinh học/Tin học trong [5,7]. Ngữ văn/Lịch sử/Địa lý trong [3, 4.5]."""
    from seed_major_weights import derive_weights
    
    class FakeMajor:
        id = 42
        name = "Test"
        admission_block = "A01"
        entry_score = 26.0
        major_group = "Công nghệ"
    
    weights = derive_weights(FakeMajor(), blocks_data, DB_SUBJECTS)
    by_subj = {w['subject_name']: w for w in weights}
    
    # Related (STEM): Hóa học, Sinh học, Tin học, Công nghệ
    for subj in ['Hóa học', 'Sinh học', 'Tin học', 'Công nghệ']:
        assert 5.0 <= by_subj[subj]['min_score'] <= 7.0, f"{subj}={by_subj[subj]['min_score']} not in [5,7]"
        assert by_subj[subj]['weight'] == 0.03, f"{subj} weight should be 0.03"
    
    # Unrelated: Lịch sử, Địa lý, Giáo dục công dân, Âm nhạc, Hội họa
    for subj in ['Lịch sử', 'Địa lý', 'Giáo dục công dân', 'Âm nhạc', 'Hội họa']:
        assert 3.0 <= by_subj[subj]['min_score'] <= 4.5, f"{subj}={by_subj[subj]['min_score']} not in [3, 4.5]"
        assert by_subj[subj]['weight'] == 0.0, f"{subj} weight should be 0.0"
```

- [ ] **Step 2: Run test**

Run: `python3 -m pytest tests/test_seed_major_weights.py::test_derive_weights_related_and_unrelated_bands -v`

Expected: PASS (do implementation đã đúng).

- [ ] **Step 3: Commit**

```bash
git add tests/test_seed_major_weights.py
git commit -m "test(career): verify related/unrelated score bands"
```

---

### Task 3.4: Add test for deterministic seed

**Files:**
- Modify: `tests/test_seed_major_weights.py`

- [ ] **Step 1: Add failing test**

Append:
```python
def test_derive_weights_deterministic(blocks_data):
    """Gọi 2 lần với cùng major_id → output giống nhau."""
    from seed_major_weights import derive_weights
    
    class FakeMajor:
        id = 777
        admission_block = "D01"
        entry_score = 25.0
        major_group = "Kinh tế"
    
    w1 = derive_weights(FakeMajor(), blocks_data, DB_SUBJECTS)
    w2 = derive_weights(FakeMajor(), blocks_data, DB_SUBJECTS)
    assert w1 == w2
```

- [ ] **Step 2: Run**

Run: `python3 -m pytest tests/test_seed_major_weights.py::test_derive_weights_deterministic -v`

Expected: PASS (random.Random(major.id) đã seed đúng).

- [ ] **Step 3: Commit**

```bash
git add tests/test_seed_major_weights.py
git commit -m "test(career): verify deterministic seeding by major_id"
```

---

### Task 3.5: Add test for None block / None entry_score

**Files:**
- Modify: `tests/test_seed_major_weights.py`

- [ ] **Step 1: Add failing test**

Append:
```python
def test_derive_weights_returns_none_on_unknown_block(blocks_data):
    from seed_major_weights import derive_weights
    class FakeMajor:
        id = 1; admission_block = "UNKNOWN"; entry_score = 20.0; major_group = "Kỹ thuật"
    assert derive_weights(FakeMajor(), blocks_data, ["Toán"]) is None


def test_derive_weights_returns_none_on_missing_entry_score(blocks_data):
    from seed_major_weights import derive_weights
    class FakeMajor:
        id = 1; admission_block = "A01"; entry_score = None; major_group = "Kỹ thuật"
    assert derive_weights(FakeMajor(), blocks_data, ["Toán"]) is None
```

- [ ] **Step 2: Run**

Run: `python3 -m pytest tests/test_seed_major_weights.py -v`

Expected: Cả 2 PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_seed_major_weights.py
git commit -m "test(career): guard against unknown block / missing entry_score"
```

---

### Task 3.6: Implement `seed()` main function

**Files:**
- Modify: `seed_major_weights.py`

- [ ] **Step 1: Append `seed()` function**

Append to `seed_major_weights.py`:
```python
def _update_major_from_real_data(major, real_data, blocks_data):
    """Update entry_score, admission_block, MajorEntryScore từ real_majors_2025.json."""
    from models import db, MajorEntryScore
    key = f"{major.name}|{major.university}"
    entry = real_data.get(key)
    if not entry or not entry.get('verified'):
        return False

    block = entry.get('block')
    if block and block in blocks_data['blocks']:
        major.admission_block = block

    scores = entry.get('scores', {})
    if '2025' in scores:
        major.entry_score = scores['2025']

    # Upsert MajorEntryScore for 2023/2024/2025
    for year_str, score in scores.items():
        year = int(year_str)
        existing = MajorEntryScore.query.filter_by(major_id=major.id, year=year).first()
        if existing:
            existing.score = score
        else:
            db.session.add(MajorEntryScore(major_id=major.id, year=year, score=score))

    return True


def seed():
    from app import app
    from models import db, UniversityMajor, MajorSubjectWeight, Subject

    blocks_data = json.loads(Path('data/admission_blocks.json').read_text(encoding='utf-8'))
    real_data_path = Path('data/real_majors_2025.json')
    real_data = json.loads(real_data_path.read_text(encoding='utf-8')) if real_data_path.exists() else {}

    with app.app_context():
        all_subject_names = [s.name for s in Subject.query.all()]
        majors = UniversityMajor.query.all()
        print(f"Processing {len(majors)} majors...")

        updated = skipped = 0
        for i, major in enumerate(majors, 1):
            # 1) update entry_score / block from real data
            _update_major_from_real_data(major, real_data, blocks_data)

            # 2) derive weights
            weights = derive_weights(major, blocks_data, all_subject_names)
            if weights is None:
                skipped += 1
                continue

            # 3) idempotent: delete + insert
            MajorSubjectWeight.query.filter_by(major_id=major.id).delete()
            for w in weights:
                db.session.add(MajorSubjectWeight(
                    major_id=major.id,
                    subject_name=w['subject_name'],
                    weight=w['weight'],
                    min_score=w['min_score']
                ))
            updated += 1

            if i % 20 == 0:
                print(f"  ...{i}/{len(majors)}")
                db.session.commit()

        db.session.commit()
        print(f"✅ Updated {updated} majors, skipped {skipped} (no block / no entry_score)")


if __name__ == '__main__':
    seed()
```

- [ ] **Step 2: Quick smoke test — dry run on 5 majors**

Run:
```bash
python3 -c "
from app import app
from models import UniversityMajor, MajorSubjectWeight, Subject
from seed_major_weights import derive_weights
import json
from pathlib import Path

blocks = json.loads(Path('data/admission_blocks.json').read_text(encoding='utf-8'))
with app.app_context():
    subs = [s.name for s in Subject.query.all()]
    sample = UniversityMajor.query.limit(5).all()
    for m in sample:
        w = derive_weights(m, blocks, subs)
        print(f'{m.name}: {len(w) if w else \"SKIP\"} weights')
" 2>/dev/null
```

Expected: 5 dòng, mỗi dòng có ~20+ weights hoặc SKIP (nếu block không nhận diện được).

- [ ] **Step 3: Run seed() on full DB**

Run:
```bash
python3 seed_major_weights.py 2>/dev/null
```

Expected: Output dạng `Updated N majors, skipped M` với N ≥ 100.

- [ ] **Step 4: Verify result**

Run:
```bash
python3 -c "
from app import app
from models import MajorSubjectWeight, UniversityMajor
with app.app_context():
    total = MajorSubjectWeight.query.count()
    majors_with = MajorSubjectWeight.query.distinct(MajorSubjectWeight.major_id).count()
    print(f'Total weight rows: {total}')
    print(f'Majors with weights: {majors_with}')
    # sample
    m = UniversityMajor.query.filter(UniversityMajor.name.ilike('%Khoa học Máy tính%')).first()
    if m:
        ws = sorted(m.weights, key=lambda w: -w.weight)
        print(f'\nSample {m.name} ({m.admission_block}, ĐC {m.entry_score}):')
        for w in ws[:8]:
            print(f'  {w.subject_name:20s} min={w.min_score:4.1f} weight={w.weight:.2f}')
" 2>/dev/null
```

Expected:
- Total weight rows ≥ 2500
- Sample KHMT: Toán min ~9.9 weight 0.30, **Vật lý/Ngoại ngữ** (DB names) min ~9.6 weight 0.30, liên quan 5–7 weight 0.03, khác 3–4.5 weight 0.00
- Không có subject_name nào là 'Lý', 'Anh', 'Văn' (phải là DB names)

- [ ] **Step 4b: Verify fit calc matches student averages**

Run:
```bash
python3 -c "
from app import app
from models import UniversityMajor, MajorSubjectWeight
from app_helpers import calculate_subject_averages, calculate_fit_score
with app.app_context():
    avgs = calculate_subject_averages(36, 1, '2025-2026')  # HLN
    print('HLN averages keys:', list(avgs.keys())[:5])
    m = UniversityMajor.query.filter(UniversityMajor.name.ilike('%Khoa học Máy tính%')).first()
    wlist = [{'subject_name': w.subject_name, 'weight': w.weight, 'min_score': w.min_score} for w in m.weights]
    print('Major weight subject_names (first 5):', [w['subject_name'] for w in wlist[:5]])
    fit = calculate_fit_score(avgs, wlist)
    print(f'HLN fit for KHMT: {fit[\"fit_pct\"]}%')
" 2>/dev/null
```

Expected: Keys của averages và subject_name trong weights **khớp nhau** (cùng dạng DB: 'Toán', 'Vật lý', 'Ngoại ngữ', ...). Fit_pct > 0% (không phải 0%, chứng tỏ match đúng).

- [ ] **Step 5: Commit**

```bash
git add seed_major_weights.py
git commit -m "feat(career): seed() generates ~20 weights/major from real scores + block lookup"
```

---

## Phase 4: Backend Radar Fix

### Task 4.1: Add failing test for `_radar()` union

**Files:**
- Create: `tests/test_career_radar.py`

- [ ] **Step 1: Write test**

Write `tests/test_career_radar.py`:
```python
"""Tests for routes.career._radar() — radar labels must be union of student + major."""
import pytest
from app import app
from models import db, UniversityMajor, MajorSubjectWeight


@pytest.fixture
def sample_major():
    with app.app_context():
        m = UniversityMajor(name="Test Major", university="Test Uni",
                            major_group="Công nghệ", admission_block="A01",
                            entry_score=27.0)
        db.session.add(m)
        db.session.flush()
        db.session.add_all([
            MajorSubjectWeight(major_id=m.id, subject_name="Toán", weight=0.30, min_score=9.2),
            MajorSubjectWeight(major_id=m.id, subject_name="Lý", weight=0.30, min_score=8.9),
            MajorSubjectWeight(major_id=m.id, subject_name="Anh", weight=0.30, min_score=8.9),
            MajorSubjectWeight(major_id=m.id, subject_name="Hóa", weight=0.03, min_score=6.0),
            MajorSubjectWeight(major_id=m.id, subject_name="Văn", weight=0.0, min_score=3.5),
        ])
        db.session.commit()
        yield m
        db.session.delete(m)
        db.session.commit()


def test_radar_union_includes_core_when_student_has_no_grades(sample_major):
    from routes.career import _radar
    with app.app_context():
        labels, stu, maj, _ = _radar(sample_major.id, {})
    assert set(labels) >= {"Toán", "Lý", "Anh", "Hóa"}, f"got {labels}"
    assert "Văn" not in labels  # weight=0 không nằm trong core
    assert all(s == 0.0 for s in stu)


def test_radar_union_includes_student_subjects_outside_weights(sample_major):
    from routes.career import _radar
    with app.app_context():
        averages = {"Toán": 8.0, "Sinh": 7.5, "Sử": 6.0}
        labels, stu, maj, _ = _radar(sample_major.id, averages)
    assert "Sinh" in labels  # student có điểm nhưng không trong weights
    assert "Sử" in labels
    assert stu[labels.index("Sinh")] == 7.5
    assert maj[labels.index("Sinh")] == 0.0  # ngành không yêu cầu Sinh
```

- [ ] **Step 2: Run test**

Run: `python3 -m pytest tests/test_career_radar.py -v 2>&1 | tail -20`

Expected: FAIL — test đầu: `assert set(labels) >= {"Toán", "Lý", "Anh", "Hóa"}` fail vì `_radar()` hiện chỉ lấy `averages.keys()`.

---

### Task 4.2: Fix `_radar()` to union labels

**Files:**
- Modify: `routes/career.py:24-34`

- [ ] **Step 1: Edit `_radar()`**

Edit `routes/career.py:24-34`:

Old:
```python
def _radar(major_id, averages):
    """Full radar: axes = tất cả môn học sinh có điểm.
    Major layer = min_score của ngành cho môn đó, 0 nếu ngành không yêu cầu môn đó."""
    weights = MajorSubjectWeight.query.filter_by(major_id=major_id).all()
    req = {w.subject_name: w.min_score for w in weights}
    wlist = [{'subject_name': w.subject_name, 'weight': w.weight, 'min_score': w.min_score}
             for w in weights]
    labels = list(averages.keys())
    stu_scores = [averages[s] for s in labels]
    maj_scores = [req.get(s, 0.0) for s in labels]
    return labels, stu_scores, maj_scores, wlist
```

New:
```python
def _radar(major_id, averages):
    """Radar: axes = union(môn khối/liên quan của ngành, môn HS có điểm).
    Môn 'core' là môn có weight >= 0.03 (khối + liên quan). Môn weight=0 không hiển thị trên radar."""
    weights = MajorSubjectWeight.query.filter_by(major_id=major_id).all()
    req = {w.subject_name: w.min_score for w in weights}
    wlist = [{'subject_name': w.subject_name, 'weight': w.weight, 'min_score': w.min_score}
             for w in weights]
    core = {w.subject_name for w in weights if w.weight >= 0.03}
    labels = sorted(core | set(averages.keys()))
    stu_scores = [averages.get(s, 0.0) for s in labels]
    maj_scores = [req.get(s, 0.0) for s in labels]
    return labels, stu_scores, maj_scores, wlist
```

- [ ] **Step 2: Run tests**

Run: `python3 -m pytest tests/test_career_radar.py -v 2>&1 | tail -10`

Expected: Cả 2 test PASS.

- [ ] **Step 3: Run existing career tests**

Run: `python3 -m pytest tests/test_career_api.py -v 2>&1 | tail -15`

Expected: Tất cả PASS (không hỏng test cũ).

- [ ] **Step 4: Commit**

```bash
git add routes/career.py tests/test_career_radar.py
git commit -m "fix(career): radar labels now union of student subjects + major core subjects"
```

---

## Phase 5: Frontend Placeholder

### Task 5.1: Update browse page radar guard

**Files:**
- Modify: `templates/student_career_browse.html:229-244`

- [ ] **Step 1: Edit `initMiniRadar`**

Edit `templates/student_career_browse.html`, dòng 229-244:

Old:
```javascript
// ── Mini radar ──────────────────────────────────────────────────────
function initMiniRadar(m) {
  const canvas = document.getElementById('mini-'+m.id);
  if (!canvas || !m.radar || m.radar.labels.length===0) return;
  miniCharts[m.id] = new Chart(canvas.getContext('2d'), {
```

New:
```javascript
// ── Mini radar ──────────────────────────────────────────────────────
function initMiniRadar(m) {
  const canvas = document.getElementById('mini-'+m.id);
  if (!canvas) return;
  if (!m.radar || m.radar.labels.length < 3) {
    canvas.parentElement.innerHTML = '<div class="text-[10px] text-gray-400 text-center self-center">Chưa có dữ liệu radar</div>';
    return;
  }
  miniCharts[m.id] = new Chart(canvas.getContext('2d'), {
```

- [ ] **Step 2: Start Flask & test manually**

Run:
```bash
FLASK_RUN_PORT=5001 nohup python3 -c "from app import app; app.run(debug=True, port=5001)" > /tmp/flask_5001.log 2>&1 &
sleep 3
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/student/career/browse
```

Expected: `302` (redirect to login — nếu chưa đăng nhập) hoặc `200`.

- [ ] **Step 3: Login as HLN + check browse page**

Mở browser http://127.0.0.1:5001/student/login, đăng nhập HLN (student_code=`35TOANB - 001024`, password mặc định).

Navigate `/student/career/browse`. Kiểm tra:
- Mỗi card ngành có mini radar 120×120 render đúng (3–8 trục)
- Không còn card trống phần radar
- Nếu có ngành không có weights → hiện "Chưa có dữ liệu radar" thay vì trống

- [ ] **Step 4: Kill Flask**

Run: `lsof -ti:5001 | xargs kill -9 2>/dev/null; sleep 1`

- [ ] **Step 5: Commit**

```bash
git add templates/student_career_browse.html
git commit -m "fix(career-ui): show placeholder when major radar has <3 axes"
```

---

## Phase 6: Integration with rebuild_db.py

### Task 6.1: Add `seed_major_weights` call to rebuild

**Files:**
- Modify: `rebuild_db.py:14-15, 167-171`

- [ ] **Step 1: Add import**

Edit `rebuild_db.py:14-15`:

Old:
```python
from seed_majors import seed as seed_majors
from seed_entry_scores import seed as seed_entry_scores
```

New:
```python
from seed_majors import seed as seed_majors
from seed_entry_scores import seed as seed_entry_scores
from seed_major_weights import seed as seed_major_weights
```

- [ ] **Step 2: Add call after `seed_entry_scores()`**

Edit `rebuild_db.py:167-171`:

Old:
```python
        # 5. Seed university majors + entry scores
        print("Seeding university majors...")
        seed_majors()
        print("Seeding entry scores...")
        seed_entry_scores()
```

New:
```python
        # 5. Seed university majors + entry scores + weights
        print("Seeding university majors...")
        seed_majors()
        print("Seeding entry scores...")
        seed_entry_scores()
        print("Seeding major weights (real scores + block distribution)...")
        seed_major_weights()
```

- [ ] **Step 3: Verify syntax**

Run: `python3 -c "import rebuild_db; print('import OK')"`

Expected: `import OK`

- [ ] **Step 4: Commit**

```bash
git add rebuild_db.py
git commit -m "chore(career): wire seed_major_weights into rebuild_db flow"
```

---

### Task 6.2: Full acceptance check

- [ ] **Step 1: Run all career tests**

Run: `python3 -m pytest tests/test_career_api.py tests/test_career_radar.py tests/test_seed_major_weights.py -v 2>&1 | tail -25`

Expected: Tất cả PASS.

- [ ] **Step 2: Start Flask + manual smoke**

Run:
```bash
FLASK_RUN_PORT=5001 nohup python3 -c "from app import app; app.run(debug=True, port=5001)" > /tmp/flask_5001.log 2>&1 &
sleep 3
```

- [ ] **Step 3: HLN login & verify**

Browser steps (manual — user tự làm):
1. Đăng nhập HLN (`35TOANB - 001024`)
2. Vào `/student/career` → radar tổng hiển thị 7+ trục
3. Vào `/student/career/browse` → mỗi card ngành có mini radar
4. Ngành KHMT Bách Khoa (A-block) fit > 80%
5. Ngành Luật / Báo chí (C-block) fit < 60%

Nếu ok → task 6.2 hoàn tất.

- [ ] **Step 4: Kill Flask**

Run: `lsof -ti:5001 | xargs kill -9 2>/dev/null`

- [ ] **Step 5: Commit nothing (đây là verification only)**

---

## Rollback Plan

Nếu phát hiện vấn đề sau khi seed:

```bash
# 1. Stop Flask
lsof -ti:5001 | xargs kill -9 2>/dev/null

# 2. Restore backup
LATEST_BACKUP=$(ls -t database.db.backup-career-realism-* | head -1)
cp "$LATEST_BACKUP" database.db

# 3. Revert commits
git log --oneline -20  # tìm commit trước khi bắt đầu
git revert <commit-range>
```

---

## Acceptance Criteria Recap (từ spec)

1. ✅ `data/real_majors_2025.json` có ≥ 100/139 ngành `verified=true` (Task 2.8)
2. ✅ `data/admission_blocks.json` đúng 15 khối + 5 cluster (Task 1.1 Step 3)
3. ✅ `MajorSubjectWeight.query.count() >= 2500` (Task 3.6 Step 4)
4. ✅ KHMT Bách Khoa: Toán ~9.9, Lý/Anh ~9.6, Văn/Sử 3–4.5 (Task 3.6 Step 4)
5. ✅ Browse page: mỗi card có mini radar ≥ 3 trục (Task 5.1 Step 3)
6. ✅ HLN fit A-block > C-block (Task 6.2 Step 3)
