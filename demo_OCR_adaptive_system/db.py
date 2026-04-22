import sqlite3
import json
import time
from contextlib import contextmanager
from config import Config


SCHEMA = """
CREATE TABLE IF NOT EXISTS inferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_hash TEXT NOT NULL,
    image_path TEXT NOT NULL,
    version TEXT NOT NULL,             -- 'v1' | 'v2' | 'vN'
    content_type TEXT,                 -- math | diagram | text
    vlm_output TEXT NOT NULL,          -- JSON
    notes TEXT,
    conditions TEXT,
    used_rules TEXT,                   -- JSON list rule_ids used as context
    used_exemplars TEXT,               -- JSON list correction_ids used
    validator_pass INTEGER,
    validator_reason TEXT,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inference_id INTEGER,
    image_hash TEXT NOT NULL,
    image_path TEXT NOT NULL,
    content_type TEXT,
    vlm_output TEXT NOT NULL,
    corrected_output TEXT NOT NULL,
    diff_summary TEXT,                 -- JSON
    error_tags TEXT,                   -- JSON list of strings
    teacher_note TEXT,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (inference_id) REFERENCES inferences(id)
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qdrant_point_id TEXT,              -- uuid str trong Qdrant
    content_type TEXT,
    error_tag TEXT,
    rule_text TEXT NOT NULL,           -- câu rule ngắn
    source_correction_ids TEXT,        -- JSON list
    times_applied INTEGER DEFAULT 0,
    times_helpful INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',      -- active | disabled
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inf_hash ON inferences(image_hash);
CREATE INDEX IF NOT EXISTS idx_corr_hash ON corrections(image_hash);
CREATE INDEX IF NOT EXISTS idx_rules_tag ON rules(error_tag);
"""


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def now_ts() -> int:
    return int(time.time())


def log_inference(
    image_hash: str,
    image_path: str,
    version: str,
    content_type: str,
    vlm_output: dict,
    notes: str,
    conditions: list,
    used_rules: list,
    used_exemplars: list,
    validator_pass: bool,
    validator_reason: str,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO inferences
               (image_hash, image_path, version, content_type, vlm_output, notes,
                conditions, used_rules, used_exemplars, validator_pass, validator_reason, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                image_hash,
                image_path,
                version,
                content_type,
                json.dumps(vlm_output, ensure_ascii=False),
                notes or "",
                json.dumps(conditions or [], ensure_ascii=False),
                json.dumps(used_rules or [], ensure_ascii=False),
                json.dumps(used_exemplars or [], ensure_ascii=False),
                1 if validator_pass else 0,
                validator_reason or "",
                now_ts(),
            ),
        )
        conn.commit()
        return cur.lastrowid


def save_correction(
    inference_id: int,
    image_hash: str,
    image_path: str,
    content_type: str,
    vlm_output: dict,
    corrected_output: dict,
    diff_summary: dict,
    error_tags: list,
    teacher_note: str,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO corrections
               (inference_id, image_hash, image_path, content_type, vlm_output,
                corrected_output, diff_summary, error_tags, teacher_note, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                inference_id,
                image_hash,
                image_path,
                content_type,
                json.dumps(vlm_output, ensure_ascii=False),
                json.dumps(corrected_output, ensure_ascii=False),
                json.dumps(diff_summary, ensure_ascii=False),
                json.dumps(error_tags or [], ensure_ascii=False),
                teacher_note or "",
                now_ts(),
            ),
        )
        conn.commit()
        return cur.lastrowid


def save_rule(
    qdrant_point_id: str,
    content_type: str,
    error_tag: str,
    rule_text: str,
    source_correction_ids: list,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO rules
               (qdrant_point_id, content_type, error_tag, rule_text,
                source_correction_ids, times_applied, times_helpful, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                qdrant_point_id,
                content_type,
                error_tag,
                rule_text,
                json.dumps(source_correction_ids or [], ensure_ascii=False),
                0,
                0,
                "active",
                now_ts(),
            ),
        )
        conn.commit()
        return cur.lastrowid


def bump_rule_usage(rule_id: int, helpful: bool):
    with get_conn() as conn:
        if helpful:
            conn.execute(
                "UPDATE rules SET times_applied = times_applied + 1, times_helpful = times_helpful + 1 WHERE id = ?",
                (rule_id,),
            )
        else:
            conn.execute(
                "UPDATE rules SET times_applied = times_applied + 1 WHERE id = ?",
                (rule_id,),
            )
        conn.commit()


def delete_all_rules() -> int:
    """Xoá toàn bộ rules trong SQLite. Trả về số rows đã xoá."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM rules")
        conn.commit()
        return cur.rowcount or 0


def delete_rules_by_ids(ids: list[int]) -> tuple[int, list[str]]:
    """Xoá các rule theo id, trả (số rows, list qdrant_point_id để client xoá Qdrant)."""
    if not ids:
        return 0, []
    placeholders = ",".join(["?"] * len(ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT qdrant_point_id FROM rules WHERE id IN ({placeholders})", ids
        ).fetchall()
        point_ids = [r["qdrant_point_id"] for r in rows if r["qdrant_point_id"]]
        cur = conn.execute(f"DELETE FROM rules WHERE id IN ({placeholders})", ids)
        conn.commit()
        return (cur.rowcount or 0), point_ids


def list_rules(limit: int = 50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM rules WHERE status='active' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_corrections(image_hash: str | None = None, limit: int = 50):
    with get_conn() as conn:
        if image_hash:
            rows = conn.execute(
                "SELECT * FROM corrections WHERE image_hash = ? ORDER BY created_at DESC LIMIT ?",
                (image_hash, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM corrections ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_inference(inference_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM inferences WHERE id = ?", (inference_id,)).fetchone()
        return dict(row) if row else None


def list_inferences_by_hash(image_hash: str, limit: int = 20):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM inferences WHERE image_hash = ? ORDER BY created_at ASC LIMIT ?",
            (image_hash, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def stats_summary() -> dict:
    with get_conn() as conn:
        total_inf = conn.execute("SELECT COUNT(*) c FROM inferences").fetchone()["c"]
        total_corr = conn.execute("SELECT COUNT(*) c FROM corrections").fetchone()["c"]
        total_rules = conn.execute("SELECT COUNT(*) c FROM rules WHERE status='active'").fetchone()["c"]
        pass_rate = conn.execute(
            "SELECT AVG(validator_pass) r FROM inferences"
        ).fetchone()["r"] or 0.0
        return {
            "inferences": total_inf,
            "corrections": total_corr,
            "active_rules": total_rules,
            "validator_pass_rate": round(float(pass_rate), 3),
        }
