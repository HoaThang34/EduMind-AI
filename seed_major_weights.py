"""Derive MajorSubjectWeight rows (min_score + weight) for all majors.

Công thức:
- Môn chính của ngành (1): weight 0.45, min_score = entry/3 + 0.2 (cap 10).
- 2 môn phụ trong khối: weight 0.225 mỗi môn, min_score = (entry - main_score)/2.
- Môn cùng cluster (không trong khối): weight 0.03, min_score random [5.0, 7.0].
- Môn không liên quan: weight 0.0, min_score random [3.0, 4.5].

"Môn chính" = block.main mặc định, được override theo tên ngành:
  - Y/Dược/Sinh-học → Sinh hoặc Hóa (tùy block)
  - Vật lý/Điện/Hạt nhân → Lý
  - Ngôn ngữ X → môn ngoại ngữ X
  - Văn học/Báo chí → Văn, Lịch sử → Sử, v.v.
  - Hội họa/Kiến trúc/Thiết kế → Vẽ
Override chỉ apply khi môn ưu tiên có trong khối; nếu không giữ block.main.
"""
import json
import random
import re
import sys
import os
from pathlib import Path

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)


# Ordered — first keyword match wins. Keyword khớp substring của tên ngành (lowercase).
# Môn ưu tiên phải là canonical name trong admission_blocks.json.
_MAIN_OVERRIDE_RULES = [
    # Y / Dược
    ('y khoa', 'Sinh'),
    ('y học cổ truyền', 'Sinh'),
    ('y học dự phòng', 'Sinh'),
    ('y tế công cộng', 'Sinh'),
    ('răng hàm mặt', 'Sinh'),
    ('điều dưỡng', 'Sinh'),
    ('phục hồi chức năng', 'Sinh'),
    ('thú y', 'Sinh'),
    ('quản lý bệnh viện', 'Sinh'),
    ('dược', 'Hóa'),
    # Sinh học / Nông lâm
    ('công nghệ sinh học', 'Sinh'),
    ('kỹ thuật sinh học', 'Sinh'),
    ('sư phạm sinh', 'Sinh'),
    ('sinh học', 'Sinh'),
    ('nông học', 'Sinh'),
    ('lâm học', 'Sinh'),
    ('chăn nuôi', 'Sinh'),
    ('nuôi trồng thủy sản', 'Sinh'),
    ('khoa học môi trường', 'Sinh'),
    ('kỹ thuật y sinh', 'Sinh'),
    # Hóa
    ('kỹ thuật hóa', 'Hóa'),
    ('sư phạm hóa', 'Hóa'),
    ('hóa học', 'Hóa'),
    ('công nghệ thực phẩm', 'Hóa'),
    # Vật lý / Điện tử / Năng lượng
    ('sư phạm vật lý', 'Lý'),
    ('vật lý', 'Lý'),
    ('kỹ thuật hạt nhân', 'Lý'),
    ('công nghệ nano', 'Lý'),
    ('năng lượng tái tạo', 'Lý'),
    ('thiết kế vi mạch', 'Lý'),
    ('kỹ thuật điện', 'Lý'),
    ('điện tử viễn thông', 'Lý'),
    ('khoa học vũ trụ', 'Lý'),
    # Ngôn ngữ
    ('sư phạm tiếng anh', 'Anh'),
    ('ngôn ngữ anh', 'Anh'),
    ('tiếng anh', 'Anh'),
    ('ngôn ngữ nhật', 'Nhật'),
    ('tiếng nhật', 'Nhật'),
    ('ngôn ngữ hàn', 'Hàn'),
    ('tiếng hàn', 'Hàn'),
    ('ngôn ngữ trung', 'Trung'),
    ('tiếng trung', 'Trung'),
    ('ngôn ngữ pháp', 'Pháp'),
    ('tiếng pháp', 'Pháp'),
    ('ngôn ngữ nga', 'Nga'),
    ('tiếng nga', 'Nga'),
    # Văn / Xã hội
    ('sư phạm văn', 'Văn'),
    ('văn học', 'Văn'),
    ('ngữ văn', 'Văn'),
    ('báo chí', 'Văn'),
    ('truyền thông đa phương tiện', 'Văn'),
    ('lịch sử', 'Sử'),
    ('sử học', 'Sử'),
    ('địa lý', 'Địa'),
    ('địa chất', 'Địa'),
    # Nghệ thuật
    ('hội họa', 'Vẽ'),
    ('kiến trúc', 'Vẽ'),
    ('thiết kế', 'Vẽ'),
    ('mỹ thuật', 'Vẽ'),
    ('điện ảnh', 'Vẽ'),
    ('âm nhạc', 'Âm nhạc'),
    # Toán / Tin học (giữ mặc định A-block, nhưng explicit)
    ('sư phạm toán', 'Toán'),
    ('toán học', 'Toán'),
    ('sư phạm tin', 'Tin học'),
    ('tin học ứng dụng', 'Tin học'),
]


def resolve_main_subject(major_name, block_subjects, default_main):
    """Chọn môn chính của ngành. Ưu tiên rule đầu tiên match mà môn ưu tiên nằm trong khối."""
    name = (major_name or '').lower()
    for keyword, preferred in _MAIN_OVERRIDE_RULES:
        if keyword in name and preferred in block_subjects:
            return preferred
    return default_main


def derive_weights(major, blocks_data, all_subject_names):
    """Tính weights cho 1 major. Trả về list[dict] hoặc None nếu không derive được.

    `all_subject_names` là tên môn canonical trong DB (vd 'Vật lý', 'Ngữ văn').
    Output subject_name CŨNG là tên DB (để khớp với averages khi fit calc).
    Block lookup dùng tên ngắn ('Lý', 'Văn') — alias qua name_aliases.

    Args:
        major: object có .id, .admission_block, .entry_score, .major_group
        blocks_data: dict load từ data/admission_blocks.json (phải có 'name_aliases')
        all_subject_names: list[str] — tên các môn có trong DB (Subject.name)
    """
    block_info = blocks_data['blocks'].get(major.admission_block)
    if not block_info or not major.entry_score:
        return None

    aliases = blocks_data['name_aliases']

    # Map canonical name → DB name (lấy DB name làm output).
    # Vd "Lý" → "Vật lý" nếu DB có "Vật lý".
    canonical_to_db = {}
    for db_name in all_subject_names:
        canon = aliases.get(db_name, db_name)
        # Chỉ giữ 1 mapping/canon (ưu tiên DB name đầu tiên gặp)
        if canon not in canonical_to_db:
            canonical_to_db[canon] = db_name

    def to_db_name(canonical):
        return canonical_to_db.get(canonical)  # None nếu không có trong DB

    entry = major.entry_score
    main_subj = resolve_main_subject(major.name, block_info['subjects'], block_info['main'])
    main_score = round(min(entry / 3 + 0.2, 10.0), 1)
    other_score = round((entry - main_score) / 2, 1)

    rng = random.Random(major.id)
    weights = []
    used_db_names = set()  # các DB name đã được assign

    # (a) Block subjects: main 0.45, 2 phụ 0.225 mỗi môn (tổng block = 0.9)
    for canon in block_info['subjects']:
        db_name = to_db_name(canon)
        if not db_name or db_name in used_db_names:
            continue
        used_db_names.add(db_name)
        is_main = (canon == main_subj)
        weights.append({
            'subject_name': db_name,
            'min_score': main_score if is_main else other_score,
            'weight': 0.45 if is_main else 0.225,
        })

    # (b) Related cluster subjects
    clusters_for_group = blocks_data['group_to_clusters'].get(major.major_group, ['STEM'])
    related_canon = set()
    for cname in clusters_for_group:
        related_canon |= set(blocks_data['clusters'].get(cname, []))
    related_canon -= set(block_info['subjects'])

    for canon in sorted(related_canon):
        db_name = to_db_name(canon)
        if not db_name or db_name in used_db_names:
            continue
        used_db_names.add(db_name)
        score = round(rng.uniform(5.0, 7.0), 1)
        weights.append({'subject_name': db_name, 'min_score': score, 'weight': 0.03})

    # (c) Unrelated: mọi DB name chưa dùng, bỏ duplicate alias
    used_canon = {aliases.get(n, n) for n in used_db_names}
    for db_name in sorted(set(all_subject_names) - used_db_names):
        canon = aliases.get(db_name, db_name)
        if canon in used_canon:
            continue
        used_canon.add(canon)
        score = round(rng.uniform(3.0, 4.5), 1)
        weights.append({'subject_name': db_name, 'min_score': score, 'weight': 0.0})

    return weights


def _update_major_from_real_data(major, real_data, blocks_data):
    """Update entry_score, admission_block, MajorEntryScore từ real_majors_2025.json."""
    from models import db, MajorEntryScore
    key = f"{major.name}|{major.university}"
    entry = real_data.get(key)
    if not entry or not entry.get('verified'):
        return False

    block = entry.get('block')
    if block and block in blocks_data['blocks']:
        major.admission_block = block

    scores = entry.get('scores', {})
    if '2025' in scores:
        major.entry_score = scores['2025']

    # Upsert MajorEntryScore for 2023/2024/2025
    for year_str, score in scores.items():
        year = int(year_str)
        existing = MajorEntryScore.query.filter_by(major_id=major.id, year=year).first()
        if existing:
            existing.score = score
        else:
            db.session.add(MajorEntryScore(major_id=major.id, year=year, score=score))

    return True


def seed():
    from app import app
    from models import db, UniversityMajor, MajorSubjectWeight, Subject

    blocks_data = json.loads(Path('data/admission_blocks.json').read_text(encoding='utf-8'))
    real_data_path = Path('data/real_majors_2025.json')
    real_data = json.loads(real_data_path.read_text(encoding='utf-8')) if real_data_path.exists() else {}

    with app.app_context():
        all_subject_names = [s.name for s in Subject.query.all()]
        majors = UniversityMajor.query.all()
        print(f"Processing {len(majors)} majors...")

        updated = skipped = 0
        for i, major in enumerate(majors, 1):
            # 1) update entry_score / block from real data
            _update_major_from_real_data(major, real_data, blocks_data)

            # 2) derive weights
            weights = derive_weights(major, blocks_data, all_subject_names)
            if weights is None:
                skipped += 1
                continue

            # 3) idempotent: delete + insert
            MajorSubjectWeight.query.filter_by(major_id=major.id).delete()
            for w in weights:
                db.session.add(MajorSubjectWeight(
                    major_id=major.id,
                    subject_name=w['subject_name'],
                    weight=w['weight'],
                    min_score=w['min_score']
                ))
            updated += 1

            if i % 20 == 0:
                print(f"  ...{i}/{len(majors)}")
                db.session.commit()

        db.session.commit()
        print(f"✅ Updated {updated} majors, skipped {skipped} (no block / no entry_score)")


if __name__ == '__main__':
    seed()
