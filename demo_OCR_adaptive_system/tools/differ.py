"""Auto-diff output thô vs bản corrected, gán error_tags."""

import difflib
import re
from typing import Dict, Any, List


def _diff_strings(a: str, b: str) -> List[Dict[str, Any]]:
    sm = difflib.SequenceMatcher(a=a or "", b=b or "")
    ops = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ops.append({
            "op": tag,
            "from": (a or "")[i1:i2],
            "to": (b or "")[j1:j2],
        })
    return ops


def _tag_latex_diff(ops: List[Dict[str, Any]]) -> List[str]:
    tags = set()
    for op in ops:
        added = op.get("to", "") or ""
        removed = op.get("from", "") or ""
        combined = added + " " + removed

        if "^" in added and "^" not in removed:
            tags.add("missing_superscript")
        if "_" in added and "_" not in removed:
            tags.add("missing_subscript")
        if "\\frac" in added and "\\frac" not in removed:
            tags.add("missing_frac")
        if removed.strip() in {"l", "I"} and added.strip() in {"1"}:
            tags.add("confuse_1_l")
        if removed.strip() in {"O", "o"} and added.strip() in {"0"}:
            tags.add("confuse_0_O")
        if re.search(r"\\?times|\*|×", combined) and added != removed:
            tags.add("confuse_multiplication")
        if re.search(r"\\sqrt", added) and "\\sqrt" not in removed:
            tags.add("missing_sqrt")

    return sorted(tags) or ["generic_latex_edit"]


def _tag_graph_diff(vlm_g: Dict[str, Any], corr_g: Dict[str, Any]) -> List[str]:
    tags = set()
    vn = {n.get("id"): n for n in (vlm_g.get("nodes") or [])}
    cn = {n.get("id"): n for n in (corr_g.get("nodes") or [])}
    if set(vn.keys()) != set(cn.keys()):
        tags.add("node_set_mismatch")

    def _edge_key(e):
        return (e.get("from"), e.get("to"), e.get("direction", ""))

    ve = {_edge_key(e) for e in (vlm_g.get("edges") or [])}
    ce = {_edge_key(e) for e in (corr_g.get("edges") or [])}
    if ve != ce:
        tags.add("edge_mismatch")
        # hướng bị lật
        flipped = any(
            (e[1], e[0], e[2]) in ce and e not in ce for e in ve
        )
        if flipped:
            tags.add("edge_direction_flipped")

    # label khác nhau
    for nid, node in cn.items():
        if nid in vn and (node.get("text") or "") != (vn[nid].get("text") or ""):
            tags.add("node_label_mismatch")
            break

    return sorted(tags) or ["generic_graph_edit"]


def diff_and_tag(vlm_output: Dict[str, Any], corrected: Dict[str, Any]) -> Dict[str, Any]:
    """Trả về diff_summary + error_tags."""
    t = (vlm_output or {}).get("type") or (corrected or {}).get("type") or "text"
    summary: Dict[str, Any] = {"type": t}
    tags: List[str] = []

    if t == "math":
        a = (vlm_output or {}).get("latex", "")
        b = (corrected or {}).get("latex", "")
        ops = _diff_strings(a, b)
        summary["latex_ops"] = ops
        summary["latex_before"] = a
        summary["latex_after"] = b
        tags = _tag_latex_diff(ops)

    elif t == "diagram":
        vg = (vlm_output or {}).get("graph") or {}
        cg = (corrected or {}).get("graph") or {}
        summary["graph_before"] = vg
        summary["graph_after"] = cg
        tags = _tag_graph_diff(vg, cg)

    else:  # text
        a = (vlm_output or {}).get("text", "")
        b = (corrected or {}).get("text", "")
        summary["text_before"] = a
        summary["text_after"] = b
        summary["text_ops"] = _diff_strings(a, b)
        tags = ["text_edit"]
        if len(b) > len(a) * 1.3:
            tags.append("text_underread")
        elif len(a) > len(b) * 1.3:
            tags.append("text_overread")

    return {"summary": summary, "error_tags": tags}
