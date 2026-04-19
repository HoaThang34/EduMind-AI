"""Parser for tuyensinh247.com per-university admission scores page.

Usage:
    from ts247_parser import parse_html
    majors = parse_html(open('/tmp/ts247_bka.html').read())

Returns dict {major_name: {'block': str|None, 'mark': float}}.
"""
import re
import codecs


_PATTERN = re.compile(
    r'\{"id":\d+,"school_id":\d+,"code":"([^"]+)","display_code":[^,]*,"name":"([^"]+)",'
    r'"block":"?([^",]*)"?,"mark":([\d.]+)[^{}]*?"admission_alias":"diem-thi-thpt"\}'
)


def _decode_pushes(html: str) -> str:
    pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.DOTALL)
    if not pushes:
        return ""
    blob = "".join(pushes)
    try:
        decoded_bytes, _ = codecs.escape_decode(blob.encode("utf-8"))
        return decoded_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return blob


def parse_html(html: str) -> dict:
    fixed = _decode_pushes(html)
    results = {}
    for code, name, block, mark in _PATTERN.findall(fixed):
        mark_f = float(mark)
        if name not in results or mark_f > results[name]["mark"]:
            results[name] = {"block": block or None, "mark": mark_f, "code": code}
    return results


if __name__ == "__main__":
    import sys
    import json

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        html = f.read()
    majors = parse_html(html)
    print(json.dumps(majors, ensure_ascii=False, indent=2))
    print(f"\nTotal majors: {len(majors)}", file=sys.stderr)
