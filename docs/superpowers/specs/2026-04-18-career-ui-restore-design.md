# Career UI Restore & Data Recovery — Design Spec

**Date:** 2026-04-18
**Status:** Approved
**Approach:** B — Viết lại template từ base f4cc1be, ghép tính năng mới lên

---

## Context

Sau loạt commit từ `9958efa` → `97f265c`, hệ thống career guidance gặp 2 vấn đề:

1. **Data mất:** Bảng `university_major`, `major_subject_weight`, `major_entry_score` đều 0 records. Nguyên nhân: `rebuild_db.py` đã chạy nhưng không gọi seed scripts.
2. **UI regression:** 3 template (`browse`, `compare`, `map`) bị đổi từ Tailwind sang Bootstrap 5, trông generic, mất mini radar chart và pin/target buttons. 2 template (`student_career.html`, `admin_majors.html`) vẫn giữ Tailwind.

---

## Part 1: Data Recovery

### 1.1 Backup
- Copy `database.db` → `database.db.backup-YYYYMMDD-HHMMSS` trước mọi thao tác

### 1.2 Ensure schema
- Chạy `migrate.py` (idempotent, chỉ thêm bảng/cột, KHÔNG xóa data)
- Đảm bảo các cột `admission_block`, `entry_score` trên `university_major` tồn tại
- Đảm bảo bảng `major_entry_score` tồn tại

### 1.3 Seed data
- Chạy `seed_majors.py` → seed ~150 ngành từ `data/majors_seed.json` (insert if not exists)
- Chạy `seed_entry_scores.py` → seed điểm chuẩn lịch sử

### 1.4 Fix rebuild_db.py
- Thêm import + gọi `seed_majors` và `seed_entry_scores` sau khi tạo bảng
- Đảm bảo rebuild luôn kết thúc với data ngành đầy đủ

---

## Part 2: Browse Page — Viết lại từ base f4cc1be

### 2.1 Base template
Lấy `student_career_browse.html` từ commit f4cc1be làm khung:
- Tailwind CSS + Be Vietnam Pro font
- CSS Grid `repeat(auto-fill, minmax(260px, 1fr))` gap 12px
- Mini radar chart 120px trong mỗi card (Chart.js radar)
- Pin/target buttons với `.btn-action` / `.btn-action.active` / `.btn-action.active-target`
- Tag system: `.tag-ok` (green), `.tag-warn` (yellow), `.tag-fail` (red)
- Fit bar với gradient colors
- Toast notification

### 2.2 Tính năng mới ghép thêm

**Filter bar mở rộng:**
- Giữ nguyên: search input, group filter, fit filter
- Thêm: filter trường đại học (`<select>` cùng style Tailwind)
- Thêm: filter khối xét tuyển (`<select>` cùng style Tailwind)
- Thay fit `<select>` bằng range slider + label (Tailwind styled)

**Sort pills:**
- Dưới filter bar: "Phù hợp nhất", "ĐC cao→thấp", "ĐC thấp→cao", "Tên A-Z"
- Style: custom classes `text-[10px] px-2 py-1 rounded-md cursor-pointer`
- Active: `bg-[#0070f3] text-white`, inactive: `bg-[#f0f0f0] text-gray-500`

**Active filter chips:**
- Hiện chip có nút xóa khi filter đang active
- Style: `bg-[#0070f3] text-white text-[10px] px-2 py-0.5 rounded`

**Card layout mở rộng:**
```
┌──────────────────────────┐
│ Tên ngành           85%  │  header + fit score (giữ f4cc1be)
│ Trường ĐH               │
│ A1 | ĐC: 24.5    [☐]    │  khối, ĐC (mới) + compare checkbox (mới)
│ [Nhóm ngành]             │  group tag (giữ f4cc1be)
├──────────────────────────┤
│ ████████████░░░  85%     │  fit bar + tag (giữ f4cc1be)
├──────────────────────────┤
│     [mini radar 120px]   │  radar chart (giữ f4cc1be)
├──────────────────────────┤
│ Xu hướng: ~~spark~~ ↑+1.2│  sparkline + trend label (mới)
├──────────────────────────┤
│ [📌 Ghim]  [⭐ Mục tiêu] │  action buttons (giữ f4cc1be)
└──────────────────────────┘
```

**Compare flow:**
- Checkbox trên mỗi card, tối đa 4 ngành
- Lưu vào sessionStorage
- Nút "So sánh (N)" xuất hiện khi >=2 ngành được chọn
- Style: `bg-[#0070f3] text-white text-sm px-3 py-1.5 rounded-md`

**Mô phỏng điểm modal:**
- Custom modal (giống pattern `targetModal` ở `student_career.html`)
- Thay thế Bootstrap modal hoàn toàn
- Range sliders cho từng môn, cập nhật realtime
- Nút reset về điểm thật

---

## Part 3: Compare Page — Viết lại Tailwind

### 3.1 Layout
- Nav: cùng pattern Tailwind (`bg-white border-b border-[#e5e5e5] px-6 py-3 flex items-center gap-4`)
- Container: `max-w-7xl mx-auto px-4 py-6`
- Card sections: `.card` class (bg:#fff, border: 1px solid #e5e5e5, border-radius: 8px)

### 3.2 Components
- **Selected chips:** `text-xs px-2.5 py-1 rounded-md text-white` + close button
- **Add search:** Custom dropdown (absolute positioned, border-[#e5e5e5], rounded-md)
- **Radar chart:** Card với header `text-xs font-semibold text-gray-500 uppercase` (giống admin table header)
- **Line chart:** Card tương tự
- **Versus table:** `w-full text-sm`, thead `bg-[#fafafa] text-[11px] text-gray-400 uppercase`, tbody `divide-y divide-[#f0f0f0]` — giống pattern admin_majors.html

### 3.3 JS Logic
Giữ nguyên 100% logic: Chart.js radar/line, versus table render, add/remove majors, sessionStorage.

---

## Part 4: Map Page — Viết lại Tailwind

### 4.1 Theme
Giữ dark background (`#0f172a`) — phù hợp cho data visualization.

### 4.2 Controls (trái)
- Back button: `text-sm px-2.5 py-1.5 bg-[#1e293b] text-white rounded-md border border-[#334155]`
- Search: `text-sm border border-[#334155] bg-[#1e293b] text-white rounded-md px-3 py-1.5`
- Group badges: `text-[10px] px-2 py-0.5 rounded cursor-pointer` với group colors
- Fit-only toggle: custom checkbox + label `text-xs text-gray-300`
- Zoom buttons: `text-sm px-2.5 py-1.5 bg-[#1e293b] text-white rounded-md border border-[#334155]`

### 4.3 Detail panel (phải)
- Background: `rgba(15,23,42,0.95)` border-left `#334155`
- Typography: Tailwind `text-sm`, `text-xs`, `text-gray-400`
- Badges: custom `text-[10px] px-2 py-0.5 rounded bg-[#334155] text-gray-300`
- Buttons: `text-xs px-2.5 py-1.5 rounded-md border` (outline style)

### 4.4 JS Logic
Giữ nguyên 100% D3.js logic: force simulation, zoom, drag, cosine similarity, group filters.

---

## Part 5: rebuild_db.py

- Import `seed_majors` from `seed_majors.py`
- Import seed function from `seed_entry_scores.py`
- Gọi cả hai sau `db.create_all()` và seed system data
- Đảm bảo thứ tự: system data → majors → entry scores

---

## Design Constraints

- **Framework:** Tailwind CSS only (qua CDN), KHÔNG dùng Bootstrap
- **Font:** Be Vietnam Pro (Google Fonts)
- **Icons:** Font Awesome 6.4
- **Charts:** Chart.js 4.x (radar, line, sparkline)
- **Map:** D3.js v7
- **Colors:** `#f5f5f5` bg, `#e5e5e5` borders, `#0070f3` primary, `#f97316` secondary
- **Tag system:** `.tag-ok` (#dcfce7/#166534), `.tag-warn` (#fef9c3/#854d0e), `.tag-fail` (#fee2e2/#991b1b)
- **Grid:** CSS Grid `minmax(260px, 1fr)` cho card grid
- **No emoji in UI:** Thay emoji bằng Font Awesome icons (vd: thay "🔍" bằng `<i class="fas fa-search">`, thay "🎯" bằng `<i class="fas fa-crosshairs">`)

## Files Changed

1. `templates/student_career_browse.html` — viết lại hoàn toàn
2. `templates/student_career_compare.html` — viết lại hoàn toàn
3. `templates/student_career_map.html` — viết lại hoàn toàn
4. `rebuild_db.py` — thêm seed calls
5. Database: seed data (không đổi schema)
