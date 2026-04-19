"""Seed admission_block and historical entry scores 2023-2024-2025 for all majors."""
import sys
import os
import random

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

from app import app
from models import db, UniversityMajor, MajorEntryScore

BLOCK_MAP = {
    'Kỹ thuật - Công nghệ': ['A00', 'A01', 'A00', 'A01', 'A00'],
    'Kinh tế - Quản trị':   ['A01', 'D01', 'D01', 'A01', 'D07'],
    'Y Dược':               ['B00', 'B00', 'B08', 'D07'],
    'Xã hội - Nhân văn':    ['C00', 'D01', 'D14', 'C00'],
    'Luật - Hành chính':    ['C00', 'D01', 'C00'],
    'Nghệ thuật':           ['H00', 'V00', 'V01'],
    'Sư phạm':              ['A01', 'C00', 'D01', 'B00'],
    'Nông Lâm':             ['B00', 'A00', 'B00'],
}
DEFAULT_BLOCK = 'A01'
DEFAULT_SCORE_2025 = 22.0
VALID_BLOCKS = {'A00','A01','A02','B00','B08','C00','C03','C15','D01','D07','D14','V00','V01','H00','T00'}


def seed():
    with app.app_context():
        majors = UniversityMajor.query.all()
        count = 0
        for major in majors:
            if not major.admission_block or major.admission_block not in VALID_BLOCKS:
                choices = BLOCK_MAP.get(major.major_group, [DEFAULT_BLOCK])
                major.admission_block = random.Random(major.id).choice(choices)

            base = major.entry_score or DEFAULT_SCORE_2025
            if not major.entry_score:
                major.entry_score = round(base + random.uniform(-2, 3), 1)
                base = major.entry_score

            for year, delta in [(2023, -1.5), (2024, -0.75)]:
                exists = MajorEntryScore.query.filter_by(major_id=major.id, year=year).first()
                if not exists:
                    db.session.add(MajorEntryScore(
                        major_id=major.id, year=year,
                        score=round(base + delta + random.uniform(-0.5, 0.5), 1)
                    ))

            exists_2025 = MajorEntryScore.query.filter_by(major_id=major.id, year=2025).first()
            if not exists_2025:
                db.session.add(MajorEntryScore(major_id=major.id, year=2025, score=base))

            count += 1

        db.session.commit()
        print(f"Seeded {count} majors with admission_block + entry scores.")


if __name__ == '__main__':
    seed()
