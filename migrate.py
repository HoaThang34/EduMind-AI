"""
Safe migration script — chạy được nhiều lần, KHÔNG BAO GIỜ xóa data.
Dùng script này thay vì rebuild_db.py khi cần thêm bảng/cột mới.

Cách dùng:
    python migrate.py
"""
import sqlite3
import os

from app import app
from models import db

DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "database.db")


def columns(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def tables(cur):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cur.fetchall()}


def add_column(cur, table, col, col_type):
    if col not in columns(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        print(f"  + {table}.{col}")


def run():
    # 1. Tạo tất cả bảng còn thiếu (idempotent — không đụng bảng đã có)
    with app.app_context():
        db.create_all()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    existing_tables = tables(cur)

    # 2. student — các cột thêm sau v1
    if "student" in existing_tables:
        add_column(cur, "student", "portrait_filename", "VARCHAR(255)")
        add_column(cur, "student", "date_of_birth",     "VARCHAR(30)")
        add_column(cur, "student", "position",          "VARCHAR(50)")
        add_column(cur, "student", "id_card",           "VARCHAR(20)")
        add_column(cur, "student", "ethnicity",         "VARCHAR(50)")
        add_column(cur, "student", "password",          "VARCHAR(100)")
        add_column(cur, "student", "conduct",           "VARCHAR(20)")
        add_column(cur, "student", "warning_level",     "VARCHAR(20)")
        add_column(cur, "student", "academic_rank",     "VARCHAR(20)")
        add_column(cur, "student", "academic_warning_level", "VARCHAR(20)")

    # 3. university_major — cột thêm cho career feature
    if "university_major" in existing_tables:
        add_column(cur, "university_major", "admission_block", "TEXT")
        add_column(cur, "university_major", "entry_score",     "REAL")

    # 4. lesson_book_week — cột thêm sau v1
    if "lesson_book_week" in existing_tables:
        add_column(cur, "lesson_book_week", "timetable_slot_id", "INTEGER")

    # 5. violation — cột liên kết lesson book
    if "violation" in existing_tables:
        add_column(cur, "violation", "lesson_book_entry_id", "INTEGER")

    # 6. timetable_slot — week_number
    if "timetable_slot" in existing_tables:
        add_column(cur, "timetable_slot", "week_number", "INTEGER")

    # 7. student_notification — sender
    if "student_notification" in existing_tables:
        add_column(cur, "student_notification", "sender_id",   "INTEGER")
        add_column(cur, "student_notification", "sender_name", "VARCHAR(100)")

    conn.commit()
    conn.close()
    print("Migration complete — không có data nào bị xóa.")


if __name__ == "__main__":
    run()
