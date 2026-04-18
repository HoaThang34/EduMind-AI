"""Seed admission_block and historical entry scores 2023-2024-2025 for all majors."""
import sys
import os
import random

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

from app import app
from models import db, UniversityMajor, MajorEntryScore

BLOCK_MAP = {
    'Kỹ thuật': 'A1', 'Công nghệ': 'A1', 'Kinh tế': 'A1',
    'Y dược': 'B00', 'Xã hội': 'D01', 'Nghệ thuật': 'C00',
}
DEFAULT_BLOCK = 'A1'
DEFAULT_SCORE_2025 = 22.0


def seed():
    with app.app_context():
        majors = UniversityMajor.query.all()
        count = 0
        for major in majors:
            if not major.admission_block:
                major.admission_block = BLOCK_MAP.get(major.major_group, DEFAULT_BLOCK)

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
