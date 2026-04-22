"""Rút rule ngắn bằng LLM từ cặp (vlm_output, corrected, diff_summary, tags)."""

import json
import logging
from typing import Dict, Any, List

from openai import OpenAI

from config import Config

log = logging.getLogger(__name__)

_oai: OpenAI | None = None


def _c() -> OpenAI:
    global _oai
    if _oai is None:
        _oai = OpenAI(api_key=Config.OPENAI_API_KEY)
    return _oai


SYSTEM = """Bạn là hệ thống rút ra quy tắc ngắn gọn cho mô hình OCR dựa trên lỗi và bản sửa.
Yêu cầu:
- Trả JSON: {"rule_text": "...", "applies_when": "...", "avoid": "...", "confidence": 0-1}.
- rule_text dài tối đa 240 ký tự, tiếng Việt, mang tính cảnh báo/hướng dẫn.
- Chỉ khái quát từ 1 lỗi cụ thể, không bịa thêm.
- Nếu lỗi quá nhỏ/không đáng tạo rule: confidence < 0.3.
"""


def extract_rule(
    content_type: str,
    error_tags: List[str],
    diff_summary: Dict[str, Any],
) -> Dict[str, Any]:
    user_payload = {
        "content_type": content_type,
        "error_tags": error_tags,
        "diff_summary": diff_summary,
    }
    try:
        resp = _c().chat.completions.create(
            model=Config.OPENAI_REASONING_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        log.exception("Rule extraction failed: %s", e)
        data = {"rule_text": "", "applies_when": "", "avoid": "", "confidence": 0.0}

    data.setdefault("rule_text", "")
    data.setdefault("confidence", 0.0)
    return data
