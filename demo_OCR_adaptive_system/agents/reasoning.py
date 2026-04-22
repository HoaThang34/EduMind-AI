"""Reasoning agent: xét output VLM, quyết định gọi tool, trả verdict cuối.

Dùng GPT (tool-calling) để:
  - khi output không pass validator, hoặc self_confidence thấp, hoặc có tag
    điều kiện bất thường, agent tra error_library để lấy rule + exemplar,
    rồi đưa ra quyết định: accept | reprompt_vlm | ask_teacher.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from openai import OpenAI

from config import Config
from tools import error_library, validator as val_mod
from tools.errors import PipelineAbort

log = logging.getLogger(__name__)

_oai: OpenAI | None = None


def _c() -> OpenAI:
    global _oai
    if _oai is None:
        _oai = OpenAI(api_key=Config.OPENAI_API_KEY)
    return _oai


TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "error_library_lookup",
            "description": "Tra thư viện lỗi để lấy rule + ca tương tự đã xử lý.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Mô tả lỗi hoặc đặc điểm cần tra"},
                    "content_type": {"type": "string", "enum": ["math", "diagram", "text"]},
                    "top_k": {"type": "integer", "default": 3},
                },
                "required": ["query", "content_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate",
            "description": "Chạy lại validator trên output để biết pass/fail và lý do.",
            "parameters": {
                "type": "object",
                "properties": {
                    "output": {"type": "object"},
                },
                "required": ["output"],
            },
        },
    },
]


SYSTEM = """Bạn là Reasoning Agent giám sát output của một VLM đọc ảnh viết tay.
Mục tiêu: đảm bảo output hợp lệ và đáng tin cậy trước khi trả cho người dùng.
Quy tắc:
- Nếu output đã pass validator và self_confidence >= 0.8: verdict = "accept".
- Nếu có dấu hiệu nghi ngờ (notes nêu không chắc, conditions xấu, validator fail):
    gọi error_library_lookup với query cụ thể để lấy rule + exemplar.
- Sau khi có rule/exemplar, nếu thấy nên cho VLM đọc lại với ngữ cảnh bổ sung:
    verdict = "reprompt_vlm" và trả `additional_context` là text tóm tắt rule/exemplar.
- Nếu vẫn không tự tin: verdict = "ask_teacher" và nêu `reason`.

Chỉ trả JSON cuối cùng theo schema:
{"verdict": "accept|reprompt_vlm|ask_teacher",
 "reason": "...",
 "additional_context": "..." (khi reprompt_vlm),
 "used_rule_ids": ["..."] (point_id từ error library nếu có),
 "uncertainty_score": 0.0-1.0}
"""


def _run_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "error_library_lookup":
        rows = error_library.search_rules(
            query_text=args.get("query", ""),
            content_type=args.get("content_type"),
            top_k=int(args.get("top_k", 3)),
        )
        return {"rules": rows}
    if name == "validate":
        ok, reason = val_mod.validate_output(args.get("output") or {})
        return {"pass": ok, "reason": reason}
    return {"error": f"unknown_tool:{name}"}


def review(
    vlm_output: Dict[str, Any],
    validator_pass: bool,
    validator_reason: str,
    logger=None,
) -> Dict[str, Any]:
    user_msg = {
        "role": "user",
        "content": json.dumps(
            {
                "vlm_output": vlm_output,
                "validator_pass": validator_pass,
                "validator_reason": validator_reason,
            },
            ensure_ascii=False,
        ),
    }
    messages = [{"role": "system", "content": SYSTEM}, user_msg]

    client = _c()
    max_steps = 4
    used_rule_ids: List[str] = []
    if logger:
        logger.log(
            "reasoning.start",
            status="start",
            detail=f"→ {Config.OPENAI_REASONING_MODEL} · validator={'pass' if validator_pass else validator_reason}",
        )
    try:
        for step_i in range(max_steps):
            resp = client.chat.completions.create(
                model=Config.OPENAI_REASONING_MODEL,
                messages=messages,
                tools=TOOLS_SPEC,
                tool_choice="auto",
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            msg = resp.choices[0].message
            if msg.tool_calls:
                messages.append(
                    {"role": "assistant", "content": msg.content or "", "tool_calls": [tc.model_dump() for tc in msg.tool_calls]}
                )
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    if logger:
                        logger.log(
                            f"reasoning.tool_call",
                            status="info",
                            detail=f"{tc.function.name}({json.dumps(args, ensure_ascii=False)[:100]})",
                            meta={"tool": tc.function.name, "args": args},
                        )
                    result = _run_tool(tc.function.name, args)
                    if tc.function.name == "error_library_lookup":
                        n_hits = len(result.get("rules", []))
                        if logger:
                            logger.done(
                                "reasoning.tool_result",
                                detail=f"error_library_lookup → {n_hits} rule",
                                meta={"n_hits": n_hits},
                            )
                        for r in result.get("rules", []):
                            if r.get("point_id"):
                                used_rule_ids.append(r["point_id"])
                    else:
                        if logger:
                            logger.done(
                                "reasoning.tool_result",
                                detail=f"{tc.function.name} → {json.dumps(result, ensure_ascii=False)[:80]}",
                                meta={"tool": tc.function.name},
                            )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                continue

            text = msg.content or "{}"
            try:
                verdict = json.loads(text)
            except json.JSONDecodeError:
                verdict = {"verdict": "accept", "reason": "fallback_parse_error", "uncertainty_score": 0.5}
            verdict.setdefault("used_rule_ids", used_rule_ids)
            if logger:
                logger.done(
                    "reasoning.verdict",
                    detail=f"verdict={verdict.get('verdict','?')} · uncertainty={verdict.get('uncertainty_score','?')}",
                    meta={
                        "verdict": verdict.get("verdict"),
                        "reason": verdict.get("reason"),
                        "used_rule_ids": verdict.get("used_rule_ids") or [],
                    },
                )
            return verdict
    except PipelineAbort:
        raise
    except Exception as e:
        log.exception("Reasoning agent error: %s", e)
        status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
        if logger:
            logger.error("reasoning.error", detail=f"{type(e).__name__}: {e}")
        raise PipelineAbort("reasoning.error", f"{type(e).__name__}: {e}", status_code=status) from e

    # Vượt quá max_steps mà chưa có verdict → coi như fail
    if logger:
        logger.error("reasoning.error", detail=f"không có verdict sau {max_steps} vòng")
    raise PipelineAbort("reasoning.error", f"reasoning không hội tụ sau {max_steps} vòng tool-call")
