"""Build URL map for the 41 universities in real_majors_2025.json.

Reads the tuyensinh247 index page /diem-chuan.html (already cached to
/tmp/ts247_index.html) and fuzzy-matches each of our 41 unis to one of the
300 schools listed there.
"""
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize import norm_uni

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

# Manual overrides / hints keyed by our uni name -> substring that must appear
# in the normalized ts247 school name. Empty dict if auto-fuzzy is fine.
HINTS = {
    "ĐH Kinh tế TP.HCM": "kinh te tphcm",
    "ĐH Sư phạm TP.HCM": "su pham tphcm",
    "ĐH Y Dược TP.HCM": "y duoc tphcm",
    "ĐHBK TP.HCM": "bach khoa hcm",
    "ĐHBK Hà Nội": "bach khoa ha noi",
    "ĐHQG Hà Nội": "quoc gia ha noi",
    "ĐH Công nghệ - ĐHQGHN": "cong nghe dhqghn",
    "ĐH Kinh tế - ĐHQGHN": "kinh te dhqghn",
    "ĐH Khoa học Tự nhiên - ĐHQGHN": "khoa hoc tu nhien",
    "ĐH Khoa học Xã hội và Nhân văn - ĐHQGHN": "khoa hoc xa hoi va nhan van",
    "ĐH Nông nghiệp Hà Nội": "nong nghiep",
    "Nhạc viện Hà Nội": "nhac vien",
    "Học viện Hành chính Quốc gia": "hanh chinh quoc gia",
    "Học viện Hàng không Việt Nam": "hang khong",
    "Học viện Kỹ thuật Mật mã": "mat ma",
    "Học viện Tài chính": "hv tai chinh",
    "ĐH Hà Nội": "ha noi hanu",  # HANU
    "ĐH FPT": "fpt",
    "RMIT Việt Nam": "rmit",
    "ĐH Luật Hà Nội": "luat ha noi",
    "ĐH Ngoại thương": "ngoai thuong",
    "ĐH Kinh tế Quốc dân": "kinh te quoc dan",
    "ĐH Y Hà Nội": "y ha noi",
    "ĐH Dược Hà Nội": "duoc ha noi",
    "ĐH Thương mại": "thuong mai",
    "ĐH Sư phạm Hà Nội": "su pham ha noi",
    "ĐH Kiến trúc Hà Nội": "kien truc ha noi",
    "ĐH Giao thông Vận tải": "giao thong van tai",
    "ĐH Công nghiệp Hà Nội": "cong nghiep ha noi",
    "ĐH Mỏ - Địa chất": "mo dia chat",
    "ĐH Thủy lợi": "thuy loi",
    "ĐH Hàng hải Việt Nam": "hang hai",
    "ĐH Lâm nghiệp": "lam nghiep",
    "ĐH Nha Trang": "nha trang",
    "ĐH Tài nguyên và Môi trường Hà Nội": "tai nguyen va moi truong ha noi",
    "ĐH Lao động - Xã hội": "lao dong",
    "ĐH TDTT Bắc Ninh": "the duc the thao bac ninh",
    "ĐH Nội vụ Hà Nội": "noi vu",
    "ĐH Sân khấu - Điện ảnh Hà Nội": "san khau",
    "ĐH Mỹ thuật Việt Nam": "my thuat viet nam",
    "ĐH Mỹ thuật Công nghiệp": "my thuat cong nghiep",
}


# Hard-coded overrides for special cases where auto-match fails or is ambiguous
HARD_OVERRIDES = {
    # Nhạc viện Hà Nội = former name of Học viện Âm nhạc Quốc gia Việt Nam
    "Nhạc viện Hà Nội": "Học Viện Âm Nhạc Quốc Gia Việt Nam",
    # ĐH Công nghệ - ĐHQGHN = QHI (not Đồng Nai)
    "ĐH Công nghệ - ĐHQGHN": "Trường Đại Học Công Nghệ – Đại Học Quốc Gia Hà Nội",
    # ĐHQG Hà Nội is a system — no single page exists; skip
    "ĐHQG Hà Nội": None,
    # ĐH Nông nghiệp Hà Nội renamed to Học viện Nông nghiệp Việt Nam
    "ĐH Nông nghiệp Hà Nội": "Học Viện Nông Nghiệp Việt Nam",
    # Học viện Hành chính Quốc gia renamed to Học viện Hành Chính và Quản trị công
    "Học viện Hành chính Quốc gia": "Học Viện Hành Chính và Quản trị công",
    # ĐH Nội vụ Hà Nội was merged into HV Hành chính Quốc gia in 2022. Still on ts247 separately.
    # ĐH Hà Nội = HANU
    "ĐH Hà Nội": "Trường Đại Học Hà Nội",
}


def match_one(our_name: str, schools: dict):
    """Return (ts247_name, url, score) best match or (None, None, 0)."""
    # Hard override first
    if our_name in HARD_OVERRIDES:
        override = HARD_OVERRIDES[our_name]
        if override is None:
            return (None, None, 0.0)
        if override in schools:
            return (override, schools[override]["url"], 1.0)
    our_norm = norm_uni(our_name)
    hint = HINTS.get(our_name)
    best = (None, None, 0.0)
    for ts_name, info in schools.items():
        ts_norm = norm_uni(ts_name)
        score = SequenceMatcher(None, our_norm, ts_norm).ratio()
        # Boost when all words of our name appear
        if all(w in ts_norm for w in our_norm.split() if len(w) > 2):
            score += 0.2
        # Hint substring match = massive boost
        if hint:
            # Check each hint token
            if all(tok in ts_norm for tok in hint.split()):
                score += 0.5
        if score > best[2]:
            best = (ts_name, info["url"], score)
    return best


def main():
    stubs = json.loads((DATA / "real_majors_2025.json").read_text(encoding="utf-8"))
    unis = sorted({k.split("|")[1] for k in stubs.keys()})

    with open("/tmp/ts247_schools.json", encoding="utf-8") as f:
        schools = json.load(f)

    url_map = {}
    for uni in unis:
        ts_name, url, score = match_one(uni, schools)
        url_map[uni] = {"ts247_name": ts_name, "url": url, "match_score": round(score, 3)}
        print(f"  {uni!r:60}  score={score:.2f}  -> {ts_name}")

    (DATA / "tuyensinh_urls.json").write_text(
        json.dumps(url_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nWrote {DATA / 'tuyensinh_urls.json'}")


if __name__ == "__main__":
    main()
