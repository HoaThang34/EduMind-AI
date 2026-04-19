import json
from typing import Any

MAX_TOOL_ROUNDS = 5

SEED_PROMPT = (
    "Hãy phân tích dữ liệu học tập của em và đưa nhận xét định hướng tổng quan. "
    "Chỉ ra điểm mạnh/yếu, đánh giá ngành target nếu có, và đề xuất 2-3 hành động cụ thể."
)

CAREER_SYSTEM_PROMPT = """\
Bạn là cố vấn định hướng chọn ngành của EduMind AI.
Xưng "em" với học sinh, tự xưng "mình". Tiếng Việt tự nhiên, giọng thân thiện,
không khuôn mẫu, không máy móc.

Nguyên tắc:
- BÁM SÁT dữ liệu được cung cấp. Dẫn số cụ thể (vd "Toán 8.5").
- Không bịa. Thiếu dữ liệu thì nói rõ "mình chưa có thông tin về X".
- Nếu HS chưa có target/pinned: gợi ý HS chọn trước hoặc dùng tool search_majors
  để tìm ngành phù hợp.
- Markdown nhẹ: **bold**, xuống dòng, bullet. KHÔNG dùng heading #.
- Lần đầu (trả lời seed prompt): 150-250 từ — tổng quan + fit target + 2-3 action cụ thể.
- Lần sau: trả lời ngắn gọn, bám câu hỏi HS.

Công cụ có sẵn:
- search_majors(query?, admission_block?, major_group?, sort_by?, limit?):
  Tìm/lọc ngành theo keyword/khối/nhóm. sort_by: 'fit' (mặc định),
  'entry_score_desc', 'entry_score_asc', 'name'.
- get_major_detail(major_id): Chi tiết 1 ngành — weights, gap, điểm chuẩn nhiều năm.

Khi nào dùng tool:
- HS hỏi về ngành/lĩnh vực CHƯA có trong context → search_majors.
- HS hỏi điểm cao nhất → sort_by='entry_score_desc'.
- HS hỏi dễ đậu → sort_by='entry_score_asc'.
- HS hỏi duyệt A-Z → sort_by='name'.
- HS hỏi chi tiết 1 ngành → get_major_detail.
- ĐỪNG gọi tool nếu data đã có trong context.
- Khi HS hỏi ngành ngoài phạm vi tool biết, hướng dẫn vào /student/career/browse.

{CONTEXT_PAYLOAD}
"""

CAREER_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_majors",
            "description": "Tìm/lọc ngành theo keyword và criteria, sort theo nhiều mode.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Từ khoá tên ngành/trường/nhóm (optional, fuzzy match)"},
                    "admission_block": {"type": "string", "description": "Khối thi: A00, A01, B00, C00, D01, ..."},
                    "major_group": {"type": "string", "description": "Nhóm ngành: Kỹ thuật, Y tế, Kinh tế, Sư phạm, ..."},
                    "sort_by": {
                        "type": "string",
                        "enum": ["fit", "entry_score_desc", "entry_score_asc", "name"],
                        "description": "Mặc định 'fit'",
                    },
                    "limit": {"type": "integer", "description": "Default 10, max 20"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_major_detail",
            "description": "Chi tiết 1 ngành: weights môn, gap với điểm HS, lịch sử điểm chuẩn.",
            "parameters": {
                "type": "object",
                "properties": {"major_id": {"type": "integer"}},
                "required": ["major_id"],
            },
        },
    },
]


def get_ollama_client():
    from app_helpers import get_ollama_client as _real
    return _real()


def get_ollama_model():
    from app_helpers import get_ollama_model as _real
    return _real()


def _ollama_chat_raw(messages, tools):
    import os, httpx
    from app_helpers import get_ollama_host
    host = get_ollama_host().rstrip('/')
    body = {
        "model": get_ollama_model(),
        "messages": messages,
        "tools": tools,
        "stream": False,
    }
    r = httpx.post(f"{host}/api/chat", json=body, timeout=120.0)
    r.raise_for_status()
    return r.json()


def _major_weights(major):
    return [
        {'subject_name': w.subject_name, 'weight': w.weight, 'min_score': w.min_score}
        for w in major.weights
    ]


def _current_semester_avgs(student):
    from app_helpers import calculate_subject_averages
    from models import SystemConfig
    from routes.career import _EXCLUDED_SUBJECTS
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    semester = int(configs.get('current_semester', '1'))
    school_year = configs.get('school_year', '2025-2026')
    averages = calculate_subject_averages(student.id, semester, school_year)
    filtered = {s: v for s, v in averages.items() if s not in _EXCLUDED_SUBJECTS}
    return filtered, semester, school_year


def build_career_context(student) -> str:
    from app_helpers import calculate_fit_score
    from models import StudentTargetMajor, StudentPinnedMajor
    from routes.career import _EXCLUDED_SUBJECTS

    filtered_avgs, semester, school_year = _current_semester_avgs(student)

    lines = [
        "==== DỮ LIỆU HỌC SINH ====",
        f"Họ tên: {student.name} | Lớp {student.student_class or 'chưa có'} "
        f"| Học kỳ {semester} / {school_year}",
        "",
    ]

    if filtered_avgs:
        avg_text = " | ".join(f"{s}: {v}" for s, v in sorted(filtered_avgs.items()))
        lines.append(f"Điểm TB các môn (đã lọc môn phụ): {avg_text}")
    else:
        lines.append("Điểm TB các môn: Chưa có điểm học kỳ hiện tại.")
    lines.append("")

    target = StudentTargetMajor.query.filter_by(student_id=student.id).first()
    if target and target.major:
        m = target.major
        wlist = _major_weights(m)
        fit = calculate_fit_score(filtered_avgs, wlist) if wlist else {'fit_pct': 0, 'gaps': []}
        neg_gaps = [
            f"{g['subject_name']} {g['gap']}"
            for g in fit['gaps']
            if g['gap'] < 0 and g['subject_name'] not in _EXCLUDED_SUBJECTS
        ][:3]
        gap_text = f" | Gap: {', '.join(neg_gaps)}" if neg_gaps else ""
        entry = f" | Điểm chuẩn: {m.entry_score}" if m.entry_score else ""
        lines.append(
            f"NGÀNH TARGET:\n"
            f"- {m.name} - {m.university} (id={m.id})\n"
            f"- Khối {m.admission_block or 'N/A'}{entry} | Fit {fit['fit_pct']}%{gap_text}"
        )
    else:
        lines.append("NGÀNH TARGET: HS chưa chọn ngành target.")
    lines.append("")

    pins = (StudentPinnedMajor.query
            .filter_by(student_id=student.id)
            .limit(5).all())
    if pins:
        lines.append("PINNED (tối đa 5):")
        for p in pins:
            if not p.major:
                continue
            wlist = _major_weights(p.major)
            if not wlist:
                continue
            fit = calculate_fit_score(filtered_avgs, wlist)
            lines.append(
                f"- {p.major.name} - {p.major.university} (id={p.major.id}): "
                f"Fit {fit['fit_pct']}%"
            )
    else:
        lines.append("PINNED: HS chưa pin ngành nào.")

    return "\n".join(lines)


def _tool_search_majors(args: dict, student) -> dict:
    from app_helpers import calculate_fit_score
    from models import UniversityMajor
    from routes.career import _fuzzy_match

    filtered_avgs, _, _ = _current_semester_avgs(student)

    query = (args.get('query') or '').strip()
    admission_block = (args.get('admission_block') or '').strip()
    major_group = (args.get('major_group') or '').strip()
    sort_by = args.get('sort_by') or 'fit'
    if sort_by not in ('fit', 'entry_score_desc', 'entry_score_asc', 'name'):
        sort_by = 'fit'
    limit = int(args.get('limit') or 10)
    limit = max(1, min(limit, 20))

    q = UniversityMajor.query
    if admission_block:
        q = q.filter(UniversityMajor.admission_block == admission_block)
    if major_group:
        q = q.filter(UniversityMajor.major_group == major_group)
    majors = q.all()
    if query:
        majors = [m for m in majors if _fuzzy_match(query, m)]

    rows = []
    for m in majors:
        wlist = _major_weights(m)
        if not wlist:
            continue
        fit = calculate_fit_score(filtered_avgs, wlist)
        rows.append({
            'major_id': m.id,
            'name': m.name,
            'university': m.university,
            'major_group': m.major_group,
            'admission_block': m.admission_block,
            'fit_pct': fit['fit_pct'],
            'entry_score': m.entry_score,
        })

    if sort_by == 'fit':
        rows.sort(key=lambda r: r['fit_pct'], reverse=True)
    elif sort_by == 'entry_score_desc':
        rows.sort(key=lambda r: (r['entry_score'] is None, -(r['entry_score'] or 0)))
    elif sort_by == 'entry_score_asc':
        rows.sort(key=lambda r: (r['entry_score'] is None, r['entry_score'] or 0))
    elif sort_by == 'name':
        rows.sort(key=lambda r: r['name'])

    rows = rows[:limit]
    return {'sorted_by': sort_by, 'count': len(rows), 'results': rows}


def _tool_get_major_detail(args: dict, student) -> dict:
    from app_helpers import calculate_fit_score
    from models import UniversityMajor
    from routes.career import _EXCLUDED_SUBJECTS

    major_id = args.get('major_id')
    if major_id is None:
        return {"error": "major_id là bắt buộc"}
    try:
        major_id = int(major_id)
    except (TypeError, ValueError):
        return {"error": "major_id phải là số nguyên"}

    major = UniversityMajor.query.get(major_id)
    if not major:
        return {"error": f"Không tìm thấy ngành có ID {major_id}"}

    filtered_avgs, _, _ = _current_semester_avgs(student)

    wlist = _major_weights(major)
    fit = calculate_fit_score(filtered_avgs, wlist) if wlist else {'fit_pct': 0, 'gaps': []}

    weights_out = []
    for g in fit['gaps']:
        if g['subject_name'] in _EXCLUDED_SUBJECTS:
            continue
        weights_out.append({
            'subject': g['subject_name'],
            'weight': g['weight'],
            'min_score': g['min_score'],
            'student_score': g['student_score'],
            'gap': g['gap'],
            'status': g['status'],
        })

    history = sorted(
        [{'year': es.year, 'score': es.score} for es in major.entry_scores],
        key=lambda x: x['year'],
    )

    return {
        'major_id': major.id,
        'name': major.name,
        'university': major.university,
        'faculty': major.faculty or '',
        'admission_block': major.admission_block,
        'entry_score_current': major.entry_score,
        'entry_history': history,
        'weights': weights_out,
        'fit_pct': fit['fit_pct'],
    }


def dispatch_career_tool(name: str, args: dict, student) -> dict:
    if name == "search_majors":
        return _tool_search_majors(args, student)
    if name == "get_major_detail":
        return _tool_get_major_detail(args, student)
    return {"error": f"Unknown tool: {name}"}


def _extract_tool_calls(msg):
    if isinstance(msg, dict):
        return msg.get("tool_calls")
    return getattr(msg, "tool_calls", None)


def _extract_content(msg) -> str:
    if isinstance(msg, dict):
        return msg.get("content") or ""
    return getattr(msg, "content", "") or ""


def _call_spec(call):
    fn = call["function"] if isinstance(call, dict) else call.function
    name = fn["name"] if isinstance(fn, dict) else fn.name
    raw_args = fn["arguments"] if isinstance(fn, dict) else fn.arguments
    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {}
    else:
        args = dict(raw_args or {})
    return name, args


def run_career_ai_chat(student, conversation_history, user_message):
    ctx = build_career_context(student)
    system = CAREER_SYSTEM_PROMPT.format(CONTEXT_PAYLOAD=ctx)
    messages = [{"role": "system", "content": system}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    tool_rounds = 0

    for _ in range(MAX_TOOL_ROUNDS):
        resp = _ollama_chat_raw(messages, CAREER_TOOLS)
        msg = resp["message"]
        tool_calls = _extract_tool_calls(msg)
        if not tool_calls:
            return _extract_content(msg).strip(), tool_rounds

        tool_rounds += 1
        assistant_msg = dict(msg) if isinstance(msg, dict) else msg
        assistant_msg.setdefault("role", "assistant")
        messages.append(assistant_msg)
        for call in tool_calls:
            name, args = _call_spec(call)
            result = dispatch_career_tool(name, args, student)
            messages.append({
                "role": "tool",
                "name": name,
                "content": json.dumps(result, ensure_ascii=False),
            })

    return (
        "Xin lỗi, em cần tra cứu nhiều quá, hãy hỏi cụ thể hơn giúp mình.",
        tool_rounds,
    )
