"""Derive MajorSubjectWeight rows (min_score + weight) for all majors.

Công thức:
- Môn khối (3): main = entry/3 + 0.2, 2 môn phụ chia đều phần còn lại. Weight 0.30.
- Môn cùng cluster (không trong khối): random [5.0, 7.0], seed theo major_id. Weight 0.03.
- Môn không liên quan: random [3.0, 4.5], seed theo major_id. Weight 0.0.
"""
import json
import random
import sys
import os
from pathlib import Path

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)


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
    main_subj = block_info['main']
    main_score = round(min(entry / 3 + 0.2, 10.0), 1)
    other_score = round((entry - main_score) / 2, 1)

    rng = random.Random(major.id)
    weights = []
    used_db_names = set()  # các DB name đã được assign

    # (a) Block subjects
    for canon in block_info['subjects']:
        db_name = to_db_name(canon)
        if not db_name or db_name in used_db_names:
            continue
        used_db_names.add(db_name)
        score = main_score if canon == main_subj else other_score
        weights.append({'subject_name': db_name, 'min_score': score, 'weight': 0.30})

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
