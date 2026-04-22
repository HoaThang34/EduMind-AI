"""VLM reader: ảnh -> JSON output theo schema cố định.

Dispatch theo Config.VLM_PROVIDER = "gemini" | "openai".
"""

import base64
import json
import logging
from typing import Dict, Any, List, Optional

from google import genai
from google.genai import types
from openai import OpenAI

from config import Config
from tools.errors import PipelineAbort

log = logging.getLogger(__name__)

_gclient: genai.Client | None = None
_oclient: OpenAI | None = None


def _gemini() -> genai.Client:
    global _gclient
    if _gclient is None:
        _gclient = genai.Client(api_key=Config.GEMINI_API_KEY)
    return _gclient


def _openai() -> OpenAI:
    global _oclient
    if _oclient is None:
        _oclient = OpenAI(api_key=Config.OPENAI_API_KEY)
    return _oclient


SYSTEM_INSTRUCTION = """Bạn là hệ thống OCR cho bài viết tay học sinh tiếng Việt.
Đọc ảnh và trả về JSON duy nhất theo schema:

{
  "type": "math" | "diagram" | "text",
  "text": "..." (khi type=text),
  "latex": "..." (khi type=math, LaTeX hợp lệ, dùng ^ và _ cho mũ/chỉ số, \\frac{}{} cho phân số),
  "graph": {
    "nodes": [{"id": "n1", "type": "start|process|decision|io|end", "text": "...", "bbox": [x,y,w,h]}],
    "edges": [{"from": "n1", "to": "n2", "label": "...", "direction": "n1->n2"}]
  } (khi type=diagram),
  "notes": "ghi chú vùng nào không chắc, ký tự lạ, bất thường",
  "conditions": ["wrinkled_paper", "low_contrast", "blurred", "tilted", "shadow", "ok"],
  "self_confidence": 0.0-1.0
}

Yêu cầu:
- CHỈ trả JSON, không kèm giải thích.
- Trường "type" BẮT BUỘC là MỘT trong 3 chuỗi: "math", "diagram", "text". Không được dùng giá trị khác như "handwriting", "mixed", "unknown", null.
- Nếu ảnh vừa có chữ vừa có công thức: chọn "math" khi công thức chiếm ưu thế, còn lại chọn "text".
- Nếu lưỡng lự hoặc không phân loại được: mặc định "text".
- Với "math", luôn có field "latex".
- Với "diagram", mọi edge.from/to phải trùng id trong "nodes".
- Với "text", luôn có field "text".
- notes phải nêu rõ phần nào không chắc chắn, vì sao.
"""


def _build_prompt_with_context(
    rules: List[Dict[str, Any]],
    exemplars: List[Dict[str, Any]],
) -> str:
    parts: List[str] = []
    if rules:
        parts.append("Các quy tắc đã rút ra từ feedback của giáo viên (áp dụng nếu hợp ngữ cảnh):")
        for i, r in enumerate(rules, 1):
            parts.append(f"  {i}. [{r.get('error_tag')}] {r.get('rule_text')}")
    if exemplars:
        parts.append("\nVí dụ tham khảo (bản giáo viên đã sửa đúng):")
        for i, ex in enumerate(exemplars, 1):
            try:
                ex_json = json.dumps(ex, ensure_ascii=False)
            except Exception:
                ex_json = str(ex)
            parts.append(f"  {i}. {ex_json}")
    return "\n".join(parts)


def _call_gemini(user_text: str, image_bytes: bytes, mime_type: str, logger) -> Dict[str, Any]:
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text=user_text),
            ],
        )
    ]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        temperature=0.1,
    )
    if logger:
        logger.log("vlm.call", status="start", detail=f"→ gemini:{Config.GEMINI_MODEL}")
    try:
        resp = _gemini().models.generate_content(
            model=Config.GEMINI_MODEL, contents=contents, config=config
        )
    except Exception as e:
        log.exception("Gemini call failed: %s", e)
        status = getattr(e, "code", None) or getattr(getattr(e, "response", None), "status_code", None)
        if logger:
            logger.error("vlm.call", detail=f"{type(e).__name__}: {e}")
        raise PipelineAbort("vlm.call", f"{type(e).__name__}: {e}", status_code=status) from e
    return _parse_json_or_abort(resp.text or "", logger)


def _call_openai(user_text: str, image_bytes: bytes, mime_type: str, logger) -> Dict[str, Any]:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]
    if logger:
        logger.log("vlm.call", status="start", detail=f"→ openai:{Config.OPENAI_VLM_MODEL}")
    # Tham số temperature không hỗ trợ đầy đủ trên gpt-5.x → chỉ set nếu model là gpt-4*
    kwargs: Dict[str, Any] = {
        "model": Config.OPENAI_VLM_MODEL,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    if Config.OPENAI_VLM_MODEL.startswith("gpt-4"):
        kwargs["temperature"] = 0.1
    try:
        resp = _openai().chat.completions.create(**kwargs)
    except Exception as e:
        log.exception("OpenAI VLM call failed: %s", e)
        status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
        if logger:
            logger.error("vlm.call", detail=f"{type(e).__name__}: {e}")
        raise PipelineAbort("vlm.call", f"{type(e).__name__}: {e}", status_code=status) from e
    return _parse_json_or_abort(resp.choices[0].message.content or "", logger)


def _parse_json_or_abort(raw: str, logger) -> Dict[str, Any]:
    raw = (raw or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("VLM trả về không phải JSON: %s", raw[:200])
        if logger:
            logger.error("vlm.call", detail="JSON decode error")
        raise PipelineAbort("vlm.call", f"VLM trả về không phải JSON hợp lệ: {e}") from e
    if logger:
        logger.done(
            "vlm.call",
            detail=(
                f"type={data.get('type','?')} · conf={data.get('self_confidence','?')}"
                + (f" · notes=1" if (data.get('notes') or '').strip() else "")
            ),
            meta={
                "type": data.get("type"),
                "self_confidence": data.get("self_confidence"),
                "conditions": data.get("conditions") or [],
                "provider": Config.VLM_PROVIDER,
            },
        )
    return data


def read_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    rules: Optional[List[Dict[str, Any]]] = None,
    exemplars: Optional[List[Dict[str, Any]]] = None,
    extra_instruction: str = "",
    logger=None,
) -> Dict[str, Any]:
    context_block = _build_prompt_with_context(rules or [], exemplars or [])
    user_text = "Đọc ảnh này và trả về JSON theo đúng schema. Nếu có quy tắc/ví dụ, tuân theo."
    if context_block:
        user_text = context_block + "\n\n" + user_text
    if extra_instruction:
        user_text += "\n\n" + extra_instruction

    provider = Config.VLM_PROVIDER
    if provider not in ("gemini", "openai"):
        raise PipelineAbort(
            "vlm.prepare_prompt",
            f"VLM_PROVIDER không hợp lệ: {provider!r} (chọn 'gemini' hoặc 'openai')",
        )

    if logger:
        model_name = Config.GEMINI_MODEL if provider == "gemini" else Config.OPENAI_VLM_MODEL
        logger.log(
            "vlm.prepare_prompt",
            status="info",
            detail=(
                f"[{provider}:{model_name}] image {len(image_bytes)/1024:.1f} KB · "
                f"rules={len(rules or [])} · exemplars={len(exemplars or [])}"
                + (" · reprompt" if extra_instruction else "")
            ),
            meta={
                "provider": provider,
                "model": model_name,
                "n_rules": len(rules or []),
                "n_exemplars": len(exemplars or []),
                "has_extra": bool(extra_instruction),
            },
        )

    if provider == "gemini":
        return _call_gemini(user_text, image_bytes, mime_type, logger)
    return _call_openai(user_text, image_bytes, mime_type, logger)
