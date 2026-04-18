import json
import pytest


class TestBrowseFilter:
    def test_search_by_name(self, student_session):
        r = student_session.get('/api/student/career/browse?q=tr%C3%AD+tu%E1%BB%87')
        data = r.get_json()
        assert r.status_code == 200
        assert any('Trí tuệ nhân tạo' in m['name'] for m in data['majors'])

    def test_search_by_university(self, student_session):
        r = student_session.get('/api/student/career/browse?q=HUST')
        data = r.get_json()
        assert r.status_code == 200
        assert all('HUST' in m['university'] for m in data['majors'])

    def test_filter_by_admission_block(self, student_session):
        r = student_session.get('/api/student/career/browse?admission_block=A1')
        data = r.get_json()
        assert r.status_code == 200
        assert all(m['admission_block'] == 'A1' for m in data['majors'])

    def test_filter_by_university_param(self, student_session):
        r = student_session.get('/api/student/career/browse?university=HUST')
        data = r.get_json()
        assert r.status_code == 200
        assert all(m['university'] == 'HUST' for m in data['majors'])


class TestSimulate:
    def test_simulate_returns_fit_scores(self, student_session):
        payload = {'scores': {'Toán': 9.0, 'Lý': 8.0, 'Hóa': 7.5}}
        r = student_session.post('/api/student/career/simulate',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        data = r.get_json()
        assert r.status_code == 200
        assert 'majors' in data
        assert len(data['majors']) > 0
        assert 'fit_pct' in data['majors'][0]

    def test_simulate_sorted_by_fit(self, student_session):
        payload = {'scores': {'Toán': 9.0, 'Lý': 8.0, 'Hóa': 7.5}}
        r = student_session.post('/api/student/career/simulate',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        data = r.get_json()
        fits = [m['fit_pct'] for m in data['majors']]
        assert fits == sorted(fits, reverse=True)


class TestCompare:
    def test_compare_returns_radar_and_scores(self, student_session, app):
        with app.app_context():
            from models import UniversityMajor
            major = UniversityMajor.query.first()
            mid = major.id
        r = student_session.get(f'/api/student/career/compare?major_ids={mid}')
        data = r.get_json()
        assert r.status_code == 200
        assert 'majors' in data
        m = data['majors'][0]
        assert 'radar' in m
        assert 'entry_scores' in m
        assert 'fit_pct' in m

    def test_compare_rejects_more_than_4(self, student_session):
        r = student_session.get('/api/student/career/compare?major_ids=1,2,3,4,5')
        assert r.status_code == 400


class TestScoreHistory:
    def test_score_history_returns_3_years(self, student_session, app):
        with app.app_context():
            from models import UniversityMajor
            major = UniversityMajor.query.first()
            mid = major.id
        r = student_session.get(f'/api/student/career/score-history?major_ids={mid}')
        data = r.get_json()
        assert r.status_code == 200
        scores = list(data.values())[0]
        assert len(scores) == 3
        years = [s['year'] for s in scores]
        assert 2023 in years and 2025 in years


class TestMapData:
    def test_map_data_returns_weight_vectors(self, student_session):
        r = student_session.get('/api/student/career/map-data')
        data = r.get_json()
        assert r.status_code == 200
        assert 'majors' in data
        assert len(data['majors']) > 0
        m = data['majors'][0]
        assert 'weight_vector' in m
        assert 'entry_score' in m
