"""Tests for seed_major_weights — sinh min_score/weight cho ~20 môn/ngành."""
import pytest
import json
from pathlib import Path


@pytest.fixture
def blocks_data():
    return json.loads(Path('data/admission_blocks.json').read_text(encoding='utf-8'))


DB_SUBJECTS = ["Toán","Vật lý","Hóa học","Sinh học","Ngữ văn","Ngoại ngữ",
               "Lịch sử","Địa lý","Giáo dục công dân","Giáo dục Kinh tế và Pháp luật",
               "Tin học","Công nghệ","Giáo dục thể chất",
               "Giáo dục Quốc phòng và An ninh","Triết học",
               "Tiếng Pháp","Tiếng Đức","Tiếng Nhật","Tiếng Trung","Tiếng Hàn","Tiếng Nga",
               "Âm nhạc","Hội họa"]


def test_derive_weights_for_A01_STEM_major(blocks_data):
    """KHMT (A01, 29.2): Toán main ~9.9, Vật lý/Ngoại ngữ ~9.6.
    Output dùng DB name (Vật lý, Ngoại ngữ) không phải tên ngắn."""
    from seed_major_weights import derive_weights

    class FakeMajor:
        id = 999
        name = "Test"
        admission_block = "A01"
        entry_score = 29.2
        major_group = "Công nghệ"

    weights = derive_weights(FakeMajor(), blocks_data, DB_SUBJECTS)

    assert weights is not None
    by_subj = {w['subject_name']: w for w in weights}

    # Block subjects (DB names, not short)
    assert 9.7 <= by_subj['Toán']['min_score'] <= 10.0
    assert by_subj['Toán']['weight'] == 0.30
    assert 9.3 <= by_subj['Vật lý']['min_score'] <= 9.8
    assert by_subj['Vật lý']['weight'] == 0.30
    assert 9.3 <= by_subj['Ngoại ngữ']['min_score'] <= 9.8
    assert by_subj['Ngoại ngữ']['weight'] == 0.30

    # Short names must NOT appear when DB has the long version
    assert 'Lý' not in by_subj
    assert 'Anh' not in by_subj
    assert 'Văn' not in by_subj


def test_derive_weights_related_and_unrelated_bands(blocks_data):
    """STEM major A01: Hóa học/Sinh học/Tin học trong [5,7]. Ngữ văn/Lịch sử/Địa lý trong [3, 4.5]."""
    from seed_major_weights import derive_weights

    class FakeMajor:
        id = 42
        name = "Test"
        admission_block = "A01"
        entry_score = 26.0
        major_group = "Công nghệ"

    weights = derive_weights(FakeMajor(), blocks_data, DB_SUBJECTS)
    by_subj = {w['subject_name']: w for w in weights}

    # Related (STEM): Hóa học, Sinh học, Tin học, Công nghệ
    for subj in ['Hóa học', 'Sinh học', 'Tin học', 'Công nghệ']:
        assert 5.0 <= by_subj[subj]['min_score'] <= 7.0, f"{subj}={by_subj[subj]['min_score']} not in [5,7]"
        assert by_subj[subj]['weight'] == 0.03, f"{subj} weight should be 0.03"

    # Unrelated: Lịch sử, Địa lý, Giáo dục công dân, Âm nhạc, Hội họa
    for subj in ['Lịch sử', 'Địa lý', 'Giáo dục công dân', 'Âm nhạc', 'Hội họa']:
        assert 3.0 <= by_subj[subj]['min_score'] <= 4.5, f"{subj}={by_subj[subj]['min_score']} not in [3, 4.5]"
        assert by_subj[subj]['weight'] == 0.0, f"{subj} weight should be 0.0"


def test_derive_weights_deterministic(blocks_data):
    """Gọi 2 lần với cùng major_id → output giống nhau."""
    from seed_major_weights import derive_weights

    class FakeMajor:
        id = 777
        admission_block = "D01"
        entry_score = 25.0
        major_group = "Kinh tế"

    w1 = derive_weights(FakeMajor(), blocks_data, DB_SUBJECTS)
    w2 = derive_weights(FakeMajor(), blocks_data, DB_SUBJECTS)
    assert w1 == w2


def test_derive_weights_returns_none_on_unknown_block(blocks_data):
    from seed_major_weights import derive_weights
    class FakeMajor:
        id = 1; admission_block = "UNKNOWN"; entry_score = 20.0; major_group = "Kỹ thuật"
    assert derive_weights(FakeMajor(), blocks_data, ["Toán"]) is None


def test_derive_weights_returns_none_on_missing_entry_score(blocks_data):
    from seed_major_weights import derive_weights
    class FakeMajor:
        id = 1; admission_block = "A01"; entry_score = None; major_group = "Kỹ thuật"
    assert derive_weights(FakeMajor(), blocks_data, ["Toán"]) is None


def test_derive_weights_dedups_alias_siblings(blocks_data):
    """Nếu DB có cả 'Ngữ văn' và 'Văn' (cùng alias → 'Văn'), chỉ sinh 1 entry."""
    from seed_major_weights import derive_weights

    class FakeMajor:
        id = 10; admission_block = "A01"; entry_score = 25.0; major_group = "Công nghệ"

    dup_subjects = ["Toán", "Vật lý", "Ngoại ngữ", "Ngữ văn", "Văn",
                    "Giáo dục Quốc phòng và An ninh", "Giáo dục quốc phòng - An ninh"]
    weights = derive_weights(FakeMajor(), blocks_data, dup_subjects)
    names = [w['subject_name'] for w in weights]

    assert len(names) == len(set(names)), f"Duplicates in output: {names}"
    van_rows = [n for n in names if n in ('Văn', 'Ngữ văn')]
    assert len(van_rows) == 1, f"Expected 1 Văn-alias row, got {van_rows}"
    qpan_rows = [n for n in names if n in ('Giáo dục Quốc phòng và An ninh',
                                            'Giáo dục quốc phòng - An ninh')]
    assert len(qpan_rows) == 1, f"Expected 1 QPAN-alias row, got {qpan_rows}"
