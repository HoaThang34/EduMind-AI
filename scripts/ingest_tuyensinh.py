"""Ingest scraped tuyensinh247 data into UniversityMajor table.

Source: data/scraped_tuyensinh.json (dict uni -> {major_name: {code, block, mark}})
Policy:
- Normalize major names, keep pairs where name appears ≥2 unis (~589 pairs).
- Upsert UniversityMajor by (name_norm, university): update entry_score/block/source,
  create row if missing. Major_group inferred from name.
- Doesn't delete existing rows.

Run AFTER this script: python3 seed_major_weights.py (regen weights).
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, basedir)


def norm_name(s):
    s = re.sub(r'\(.*?\)', '', s).strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'^(Ngành|Chuyên ngành)\s+', '', s, flags=re.I)
    s = re.sub(r'\s*-\s*(IELTS|Chương trình|Pohe|Phổ thông|Tiên tiến|Chất lượng cao|Chuẩn|Chính quy).*$', '', s, flags=re.I)
    return s.strip()


GROUP_RULES = [
    # (keyword_lowercase, group)
    ('y khoa', 'Y Dược'),
    ('y học', 'Y Dược'),
    ('răng hàm', 'Y Dược'),
    ('điều dưỡng', 'Y Dược'),
    ('dược', 'Y Dược'),
    ('y tế', 'Y Dược'),
    ('phục hồi chức năng', 'Y Dược'),
    ('bệnh viện', 'Y Dược'),
    ('hộ sinh', 'Y Dược'),
    ('xét nghiệm y', 'Y Dược'),
    ('kỹ thuật y', 'Y Dược'),
    ('sư phạm', 'Sư phạm'),
    ('giáo dục mầm non', 'Sư phạm'),
    ('giáo dục tiểu học', 'Sư phạm'),
    ('giáo dục đặc biệt', 'Sư phạm'),
    ('giáo dục thể chất', 'Sư phạm'),
    ('giáo dục chính trị', 'Sư phạm'),
    ('quản lý giáo dục', 'Sư phạm'),
    ('luật', 'Luật - Hành chính'),
    ('hành chính', 'Luật - Hành chính'),
    ('quản lý nhà nước', 'Luật - Hành chính'),
    ('lưu trữ', 'Luật - Hành chính'),
    ('chính trị', 'Luật - Hành chính'),
    ('nông', 'Nông Lâm'),
    ('lâm', 'Nông Lâm'),
    ('thủy sản', 'Nông Lâm'),
    ('chăn nuôi', 'Nông Lâm'),
    ('thú y', 'Nông Lâm'),
    ('trồng trọt', 'Nông Lâm'),
    ('mỹ thuật', 'Nghệ thuật'),
    ('hội họa', 'Nghệ thuật'),
    ('âm nhạc', 'Nghệ thuật'),
    ('điện ảnh', 'Nghệ thuật'),
    ('sân khấu', 'Nghệ thuật'),
    ('thiết kế', 'Nghệ thuật'),
    ('kiến trúc', 'Nghệ thuật'),
    ('đồ họa', 'Nghệ thuật'),
    ('thời trang', 'Nghệ thuật'),
    ('quay phim', 'Nghệ thuật'),
    ('nhiếp ảnh', 'Nghệ thuật'),
    ('biên đạo', 'Nghệ thuật'),
    ('thanh nhạc', 'Nghệ thuật'),
    ('kinh tế', 'Kinh tế - Quản trị'),
    ('quản trị', 'Kinh tế - Quản trị'),
    ('tài chính', 'Kinh tế - Quản trị'),
    ('ngân hàng', 'Kinh tế - Quản trị'),
    ('kế toán', 'Kinh tế - Quản trị'),
    ('kiểm toán', 'Kinh tế - Quản trị'),
    ('marketing', 'Kinh tế - Quản trị'),
    ('thương mại', 'Kinh tế - Quản trị'),
    ('logistics', 'Kinh tế - Quản trị'),
    ('bất động sản', 'Kinh tế - Quản trị'),
    ('bảo hiểm', 'Kinh tế - Quản trị'),
    ('khởi nghiệp', 'Kinh tế - Quản trị'),
    ('du lịch', 'Kinh tế - Quản trị'),
    ('khách sạn', 'Kinh tế - Quản trị'),
    ('nhân lực', 'Kinh tế - Quản trị'),
    ('đầu tư', 'Kinh tế - Quản trị'),
    ('ngôn ngữ', 'Xã hội - Nhân văn'),
    ('tiếng ', 'Xã hội - Nhân văn'),
    ('văn học', 'Xã hội - Nhân văn'),
    ('ngữ văn', 'Xã hội - Nhân văn'),
    ('lịch sử', 'Xã hội - Nhân văn'),
    ('sử học', 'Xã hội - Nhân văn'),
    ('địa lý', 'Xã hội - Nhân văn'),
    ('triết', 'Xã hội - Nhân văn'),
    ('xã hội', 'Xã hội - Nhân văn'),
    ('tâm lý', 'Xã hội - Nhân văn'),
    ('báo chí', 'Xã hội - Nhân văn'),
    ('truyền thông', 'Xã hội - Nhân văn'),
    ('quan hệ quốc tế', 'Xã hội - Nhân văn'),
    ('nhân học', 'Xã hội - Nhân văn'),
    ('văn hóa', 'Xã hội - Nhân văn'),
    ('quốc tế học', 'Xã hội - Nhân văn'),
    ('việt nam học', 'Xã hội - Nhân văn'),
    ('đông phương', 'Xã hội - Nhân văn'),
    ('biên phiên dịch', 'Xã hội - Nhân văn'),
    ('thư viện', 'Xã hội - Nhân văn'),
    ('thông tin-thư viện', 'Xã hội - Nhân văn'),
    ('tôn giáo', 'Xã hội - Nhân văn'),
    # Kỹ thuật - Công nghệ (catch-all cuối)
    ('công nghệ', 'Kỹ thuật - Công nghệ'),
    ('kỹ thuật', 'Kỹ thuật - Công nghệ'),
    ('cơ khí', 'Kỹ thuật - Công nghệ'),
    ('cơ điện', 'Kỹ thuật - Công nghệ'),
    ('điện tử', 'Kỹ thuật - Công nghệ'),
    ('điện', 'Kỹ thuật - Công nghệ'),
    ('xây dựng', 'Kỹ thuật - Công nghệ'),
    ('giao thông', 'Kỹ thuật - Công nghệ'),
    ('vận tải', 'Kỹ thuật - Công nghệ'),
    ('hàng không', 'Kỹ thuật - Công nghệ'),
    ('hàng hải', 'Kỹ thuật - Công nghệ'),
    ('máy tính', 'Kỹ thuật - Công nghệ'),
    ('phần mềm', 'Kỹ thuật - Công nghệ'),
    ('trí tuệ nhân tạo', 'Kỹ thuật - Công nghệ'),
    ('khoa học dữ liệu', 'Kỹ thuật - Công nghệ'),
    ('tự động hóa', 'Kỹ thuật - Công nghệ'),
    ('robot', 'Kỹ thuật - Công nghệ'),
    ('vật liệu', 'Kỹ thuật - Công nghệ'),
    ('hóa học', 'Kỹ thuật - Công nghệ'),
    ('vật lý', 'Kỹ thuật - Công nghệ'),
    ('sinh học', 'Kỹ thuật - Công nghệ'),
    ('môi trường', 'Kỹ thuật - Công nghệ'),
    ('năng lượng', 'Kỹ thuật - Công nghệ'),
    ('dầu khí', 'Kỹ thuật - Công nghệ'),
    ('địa chất', 'Kỹ thuật - Công nghệ'),
    ('trắc địa', 'Kỹ thuật - Công nghệ'),
    ('khai thác mỏ', 'Kỹ thuật - Công nghệ'),
    ('toán học', 'Kỹ thuật - Công nghệ'),
    ('thống kê', 'Kỹ thuật - Công nghệ'),
    ('thực phẩm', 'Kỹ thuật - Công nghệ'),
    ('hệ thống thông tin', 'Kỹ thuật - Công nghệ'),
    ('an toàn thông tin', 'Kỹ thuật - Công nghệ'),
    ('viễn thông', 'Kỹ thuật - Công nghệ'),
    ('mạng', 'Kỹ thuật - Công nghệ'),
]


def classify_group(name):
    n = name.lower()
    for kw, grp in GROUP_RULES:
        if kw in n:
            return grp
    return 'Kỹ thuật - Công nghệ'  # fallback


def pick_first_valid_block(raw, known_blocks):
    """Scraped block có thể là 'A00; A01; D01; D07' — lấy block đầu tiên có trong admission_blocks."""
    if not raw:
        return None
    for tok in re.split(r'[;,]', raw):
        tok = tok.strip()
        if tok in known_blocks:
            return tok
    return None


def main():
    scraped = json.loads(Path('data/scraped_tuyensinh.json').read_text(encoding='utf-8'))
    blocks_data = json.loads(Path('data/admission_blocks.json').read_text(encoding='utf-8'))
    known_blocks = set(blocks_data['blocks'].keys())

    # Flatten + normalize
    pairs = []
    for uni, majors in scraped.items():
        for orig, info in majors.items():
            nn = norm_name(orig)
            if not nn:
                continue
            block = pick_first_valid_block(info.get('block'), known_blocks)
            pairs.append({'name': nn, 'university': uni, 'mark': info['mark'], 'block': block})

    # Keep only names with ≥2 uni instances
    cnt = Counter(p['name'] for p in pairs)
    kept = [p for p in pairs if cnt[p['name']] >= 2]
    print(f'Scraped pairs: {len(pairs)}, kept (≥2 unis): {len(kept)}')

    from app import app
    from models import db, UniversityMajor, MajorEntryScore

    with app.app_context():
        created = updated = 0
        for p in kept:
            m = UniversityMajor.query.filter_by(name=p['name'], university=p['university']).first()
            if m:
                m.entry_score = p['mark']
                if p['block']:
                    m.admission_block = p['block']
                updated += 1
            else:
                m = UniversityMajor(
                    name=p['name'],
                    university=p['university'],
                    major_group=classify_group(p['name']),
                    entry_score=p['mark'],
                    admission_block=p['block'] or 'A00',
                )
                db.session.add(m)
                db.session.flush()
                created += 1

            # Upsert MajorEntryScore 2025
            es = MajorEntryScore.query.filter_by(major_id=m.id, year=2025).first()
            if es:
                es.score = p['mark']
            else:
                db.session.add(MajorEntryScore(major_id=m.id, year=2025, score=p['mark']))

        db.session.commit()
        total = UniversityMajor.query.count()
        print(f'✅ Created {created}, updated {updated}. DB now: {total} UniversityMajor rows.')


if __name__ == '__main__':
    main()
