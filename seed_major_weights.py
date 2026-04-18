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

    # (c) Unrelated: mọi DB name chưa dùng
    unrelated_db = set(all_subject_names) - used_db_names
    for db_name in sorted(unrelated_db):
        score = round(rng.uniform(3.0, 4.5), 1)
        weights.append({'subject_name': db_name, 'min_score': score, 'weight': 0.0})

    return weights
