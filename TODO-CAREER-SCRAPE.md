# TODO: Scrape real entry scores (Phase 2)

**Trạng thái:** HOÃN — quota Anthropic reset 14:00 Asia/Saigon (attempt lần 2 ngày 2026-04-19).

**Lịch sử:**
- 2026-04-18: subagent hit quota reset 3am → 0/139 scraped (init 139 stubs, commit `49cc140`).
- 2026-04-19: subagent lần 2 hit "resets 2pm (Asia/Saigon)" → cũng 0/139. Parser đã validate trên ĐHBK HN (65 majors extracted sạch bằng regex trên Next.js `self.__next_f.push` blob).

**File đã có:** `data/real_majors_2025.json` (139 stubs, `verified: false`).

**Parser đã validate (tuyensinh247.com):**
```python
import re, codecs, subprocess
html = subprocess.run(['curl','-sL','-A','Mozilla/5.0', URL], capture_output=True, timeout=30).stdout.decode('utf-8','ignore')
pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.DOTALL)
blob = ''.join(pushes)
decoded, _ = codecs.escape_decode(blob.encode('utf-8'))
fixed = decoded.decode('utf-8','ignore')
pattern = re.compile(r'\{"id":\d+,"school_id":\d+,"code":"([^"]+)","display_code":[^,]*,"name":"([^"]+)","block":"?([^",]*)"?,"mark":([\d.]+)[^{}]*?"admission_alias":"diem-thi-thpt"\}')
# (code, name, block, mark) cho từng ngành THPT
```

**Cách chạy lại sau khi quota reset:**
1. Mở Claude Code, prompt: *"Tiếp tục scrape tuyensinh247.com cho 41 trường trong `data/real_majors_2025.json`. Dùng parser đã validate trong TODO-CAREER-SCRAPE.md. Strategy: (1) WebSearch 1–2 lần/trường tìm URL `site:tuyensinh247.com diem chuan <uni>`, (2) curl + regex parse, (3) fuzzy-match stub major names (difflib ratio ≥ 0.75) rồi set `scores.2025`, `block`, `source=tuyensinh247.com`, `verified=true`. Cache HTML vào `/tmp/ts247_<slug>.html`. Cap 80 WebSearch. ĐỪNG chạy `seed_major_weights.py`."*
2. Review JSON diff xong chạy `python3 seed_major_weights.py` để cập nhật entry_score + block + MajorEntryScore + regenerate MajorSubjectWeight (với công thức weight mới 0.45/0.225 + main subject override theo tên ngành).

**Ảnh hưởng hiện tại:** Phase 3–6 dùng `entry_score` mock (22.0 ± random). Logic derive weights, radar, fit score đều đúng; điểm chuẩn chưa thật. Weight đã update 2026-04-19 (main 0.45, phụ 0.225, override theo tên ngành) — khi scrape xong chỉ cần re-run seed_major_weights.py.
