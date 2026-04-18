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
