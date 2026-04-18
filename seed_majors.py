"""Import ~150 university majors from data/majors_seed.json into the database."""
import json
import os
import sys

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

from app import app
from models import db, UniversityMajor, MajorSubjectWeight
import datetime


def seed():
    seed_file = os.path.join(basedir, 'data', 'majors_seed.json')
    with open(seed_file, encoding='utf-8') as f:
        majors_data = json.load(f)

    added = 0
    skipped = 0
    with app.app_context():
        for item in majors_data:
            exists = UniversityMajor.query.filter_by(
                name=item['name'], university=item['university']
            ).first()
            if exists:
                skipped += 1
                continue

            major = UniversityMajor(
                name=item['name'],
                university=item['university'],
                faculty=item.get('faculty', ''),
                major_group=item.get('major_group', ''),
                description=item.get('description', ''),
                created_at=datetime.datetime.utcnow(),
            )
            db.session.add(major)
            db.session.flush()

            for w in item.get('weights', []):
                db.session.add(MajorSubjectWeight(
                    major_id=major.id,
                    subject_name=w['subject_name'],
                    weight=float(w['weight']),
                    min_score=float(w['min_score']),
                ))
            added += 1

        db.session.commit()

    print(f"Done: {added} majors added, {skipped} skipped (already exist).")


if __name__ == '__main__':
    seed()
