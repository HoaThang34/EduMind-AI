"""Rule-based validators cho LaTeX, graph, text output."""

import re
from typing import Dict, Any, Tuple, List


def validate_latex(latex: str) -> Tuple[bool, str]:
    if not latex or not isinstance(latex, str):
        return False, "latex_empty"

    # cân bằng ngoặc {}
    depth = 0
    for ch in latex:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth < 0:
            return False, "unbalanced_braces"
    if depth != 0:
        return False, "unbalanced_braces"

    # \frac cần đủ 2 đối số {}{}
    for m in re.finditer(r"\\frac\b", latex):
        rest = latex[m.end():]
        if not re.match(r"\s*\{[^{}]*\}\s*\{[^{}]*\}", rest) and not re.match(r"\s*\{", rest):
            return False, "frac_missing_args"

    # ^ và _ không nên đứng cuối hoặc lặp liên tiếp
    if re.search(r"[\^_]{2,}", latex):
        return False, "consecutive_sub_sup"
    if latex.rstrip().endswith("^") or latex.rstrip().endswith("_"):
        return False, "dangling_sub_sup"

    return True, "ok"


def validate_graph(graph: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(graph, dict):
        return False, "graph_not_object"
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return False, "nodes_or_edges_not_list"
    if not nodes:
        return False, "empty_nodes"

    node_ids = set()
    for n in nodes:
        nid = n.get("id") if isinstance(n, dict) else None
        if not nid:
            return False, "node_missing_id"
        if nid in node_ids:
            return False, f"duplicate_node_id:{nid}"
        node_ids.add(nid)

    for e in edges:
        if not isinstance(e, dict):
            return False, "edge_not_object"
        src = e.get("from")
        dst = e.get("to")
        if not src or not dst:
            return False, "edge_missing_endpoint"
        if src not in node_ids:
            return False, f"edge_from_unknown:{src}"
        if dst not in node_ids:
            return False, f"edge_to_unknown:{dst}"

    return True, "ok"


def validate_text(text: str) -> Tuple[bool, str]:
    if not isinstance(text, str):
        return False, "text_not_string"
    if len(text.strip()) == 0:
        return False, "text_empty"
    return True, "ok"


def validate_output(output: Dict[str, Any]) -> Tuple[bool, str]:
    """Route theo type trong output. Nếu type lạ → thử suy luận từ field có sẵn."""
    output = output or {}
    raw_t = output.get("type")
    t = (raw_t or "").strip().lower() if isinstance(raw_t, str) else ""

    if t not in ("math", "diagram", "text"):
        # VLM trả type lạ (null, "handwriting", "mixed",...). Suy luận từ field có sẵn,
        # sửa lại output.type để downstream (db, UI) thấy type hợp lệ.
        if isinstance(output.get("latex"), str) and output["latex"].strip():
            t = "math"
        elif isinstance(output.get("graph"), dict) and (output["graph"].get("nodes") or []):
            t = "diagram"
        elif isinstance(output.get("text"), str) and output["text"].strip():
            t = "text"
        else:
            return False, f"unknown_type:{raw_t}"
        output["type"] = t

    if t == "math":
        return validate_latex(output.get("latex", ""))
    if t == "diagram":
        return validate_graph(output.get("graph") or {})
    return validate_text(output.get("text", ""))
