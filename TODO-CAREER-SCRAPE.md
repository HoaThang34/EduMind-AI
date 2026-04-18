# TODO: Scrape real entry scores (Phase 2)

**Trạng thái:** HOÃN — chạy tay sau khi quota Anthropic reset.

**Lý do hoãn:** Background subagent hit "out of extra usage · resets 3am (Asia/Saigon)" ngày 2026-04-18 sau khi mới init 139 stubs (commit `49cc140`). 0/139 ngành được scrape.

**File đã có:** `data/real_majors_2025.json` (139 stubs, `verified: false`).

**Cách chạy lại:**
1. Đảm bảo quota đã reset.
2. Mở Claude Code, prompt: *"Chạy Phase 2 của plan `docs/superpowers/plans/2026-04-18-career-data-realism.md` — scrape 139 ngành từ `data/real_majors_2025.json`, chia 7 batch × 20 ngành, dùng WebSearch + WebFetch. Source ưu tiên: tuyensinh247.com, vnexpress.net, tienphong.vn. Cap 3 tool calls/ngành. Commit sau mỗi batch. Acceptance ≥100/139 verified."*
3. Sau khi scrape xong, chạy lại `python3 seed_major_weights.py` để cập nhật `entry_score` + `admission_block` + `MajorEntryScore` + regenerate `MajorSubjectWeight` bằng điểm thật.

**Ảnh hưởng hiện tại:** Phase 3–6 đã chạy với `entry_score` mock (22.0 ± random từ `seed_entry_scores.py`). Logic derive weights, radar, fit score đều đúng; chỉ là giá trị điểm chuẩn chưa phản ánh thực tế. Khi scrape xong, chỉ cần re-run `seed_major_weights.py`, không cần sửa code.
