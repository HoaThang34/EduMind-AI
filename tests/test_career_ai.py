import os
os.environ['EDUMIND_DB_URI'] = 'sqlite:///:memory:'

import pytest
from unittest.mock import patch, MagicMock
from models import ChatConversation


class TestScopeColumn:
    def test_chat_conversation_has_scope_column(self):
        assert hasattr(ChatConversation, 'scope'), \
            "ChatConversation must have a scope column for career_advisor filtering"


class TestCareerAIModule:
    def test_system_prompt_has_placeholder(self):
        from career_ai import CAREER_SYSTEM_PROMPT
        assert "{CONTEXT_PAYLOAD}" in CAREER_SYSTEM_PROMPT

    def test_seed_prompt_nonempty(self):
        from career_ai import SEED_PROMPT
        assert len(SEED_PROMPT) > 50

    def test_tools_defined(self):
        from career_ai import CAREER_TOOLS
        names = [t["function"]["name"] for t in CAREER_TOOLS]
        assert "search_majors" in names
        assert "get_major_detail" in names

    def test_max_tool_rounds_reasonable(self):
        from career_ai import MAX_TOOL_ROUNDS
        assert 3 <= MAX_TOOL_ROUNDS <= 10


class TestBuildCareerContext:
    def test_context_includes_student_name_and_class(self, app):
        from career_ai import build_career_context
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            ctx = build_career_context(student)
            assert 'Học Sinh Test' in ctx
            assert '12A1' in ctx

    def test_context_includes_subject_averages_or_empty_note(self, app):
        from career_ai import build_career_context
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            ctx = build_career_context(student)
            assert 'Chưa có điểm' in ctx or 'Toán' in ctx

    def test_context_mentions_no_target_when_absent(self, app):
        from career_ai import build_career_context
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            ctx = build_career_context(student)
            assert 'chưa chọn' in ctx.lower() or 'chưa có target' in ctx.lower()

    def test_context_mentions_no_pinned_when_absent(self, app):
        from career_ai import build_career_context
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            ctx = build_career_context(student)
            assert 'chưa pin' in ctx.lower() or 'không pin' in ctx.lower()

    def test_context_under_token_budget(self, app):
        from career_ai import build_career_context
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            ctx = build_career_context(student)
            assert len(ctx) < 1500


class TestSearchMajorsTool:
    @pytest.fixture
    def more_majors(self, app):
        with app.app_context():
            import datetime
            from models import UniversityMajor, MajorSubjectWeight, db as _db
            extras = [
                ('Khoa học máy tính', 'ĐH KHTN', 'Kỹ thuật', 'A00', 26.5),
                ('Kinh tế đối ngoại', 'ĐH Ngoại Thương', 'Kinh tế', 'A01', 27.2),
                ('Y đa khoa', 'ĐH Y Hà Nội', 'Y tế', 'B00', 28.1),
                ('Không điểm chuẩn', 'ĐH X', 'Kỹ thuật', 'A00', None),
            ]
            for name, uni, grp, block, score in extras:
                m = UniversityMajor(
                    name=name, university=uni, major_group=grp,
                    admission_block=block, entry_score=score,
                    created_at=datetime.datetime.utcnow(),
                )
                _db.session.add(m)
                _db.session.flush()
                _db.session.add(MajorSubjectWeight(
                    major_id=m.id, subject_name='Toán', weight=0.5, min_score=8.0))
                _db.session.add(MajorSubjectWeight(
                    major_id=m.id, subject_name='Lý', weight=0.5, min_score=7.5))
            _db.session.commit()
            yield
            for name, _, _, _, _ in extras:
                for m in UniversityMajor.query.filter_by(name=name).all():
                    MajorSubjectWeight.query.filter_by(major_id=m.id).delete()
                    _db.session.delete(m)
            _db.session.commit()

    def test_search_returns_sorted_by_fit_default(self, app, more_majors):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            result = dispatch_career_tool('search_majors', {}, student)
            assert result['sorted_by'] == 'fit'
            pcts = [r['fit_pct'] for r in result['results']]
            assert pcts == sorted(pcts, reverse=True)

    def test_search_filters_admission_block(self, app, more_majors):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            result = dispatch_career_tool('search_majors', {'admission_block': 'B00'}, student)
            assert all(r['admission_block'] == 'B00' for r in result['results'])

    def test_search_filters_major_group(self, app, more_majors):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            result = dispatch_career_tool('search_majors', {'major_group': 'Y tế'}, student)
            assert all(r['major_group'] == 'Y tế' for r in result['results'])

    def test_search_sort_entry_score_desc_nulls_last(self, app, more_majors):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            result = dispatch_career_tool(
                'search_majors', {'sort_by': 'entry_score_desc', 'limit': 20}, student)
            scores = [r['entry_score'] for r in result['results']]
            none_idx = [i for i, s in enumerate(scores) if s is None]
            if none_idx:
                assert none_idx[0] == len(scores) - len([s for s in scores if s is None])
            real = [s for s in scores if s is not None]
            assert real == sorted(real, reverse=True)

    def test_search_sort_entry_score_asc(self, app, more_majors):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            result = dispatch_career_tool(
                'search_majors', {'sort_by': 'entry_score_asc'}, student)
            real = [r['entry_score'] for r in result['results'] if r['entry_score'] is not None]
            assert real == sorted(real)

    def test_search_sort_by_name_alphabetical(self, app, more_majors):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            result = dispatch_career_tool('search_majors', {'sort_by': 'name'}, student)
            names = [r['name'] for r in result['results']]
            assert names == sorted(names)

    def test_search_limit_default_10_cap_20(self, app, more_majors):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            result = dispatch_career_tool('search_majors', {'limit': 100}, student)
            assert result['count'] <= 20

    def test_search_query_fuzzy(self, app, more_majors):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            result = dispatch_career_tool('search_majors', {'query': 'y đa khoa'}, student)
            names = [r['name'] for r in result['results']]
            assert any('Y đa khoa' in n for n in names)


class TestGetMajorDetailTool:
    def test_get_detail_returns_full_fields(self, app):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student, UniversityMajor
            student = Student.query.filter_by(student_code='TS001').first()
            major = UniversityMajor.query.filter_by(name='Trí tuệ nhân tạo').first()
            result = dispatch_career_tool(
                'get_major_detail', {'major_id': major.id}, student)
            assert result['major_id'] == major.id
            assert result['name'] == 'Trí tuệ nhân tạo'
            assert result['university'] == 'HUST'
            assert result['admission_block'] == 'A1'
            assert result['entry_score_current'] == 28.5
            assert 'weights' in result
            assert 'entry_history' in result
            assert 'fit_pct' in result

    def test_get_detail_weights_include_gap_vs_student(self, app):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student, UniversityMajor
            student = Student.query.filter_by(student_code='TS001').first()
            major = UniversityMajor.query.filter_by(name='Trí tuệ nhân tạo').first()
            result = dispatch_career_tool(
                'get_major_detail', {'major_id': major.id}, student)
            for w in result['weights']:
                assert 'subject' in w
                assert 'weight' in w
                assert 'min_score' in w
                assert 'student_score' in w
                assert 'gap' in w
                assert 'status' in w

    def test_get_detail_entry_history_sorted_by_year(self, app):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student, UniversityMajor
            student = Student.query.filter_by(student_code='TS001').first()
            major = UniversityMajor.query.filter_by(name='Trí tuệ nhân tạo').first()
            result = dispatch_career_tool(
                'get_major_detail', {'major_id': major.id}, student)
            years = [e['year'] for e in result['entry_history']]
            assert years == sorted(years)

    def test_get_detail_invalid_id_returns_error(self, app):
        from career_ai import dispatch_career_tool
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            result = dispatch_career_tool(
                'get_major_detail', {'major_id': 999999}, student)
            assert 'error' in result
            assert 'Không tìm thấy' in result['error'] or 'not found' in result['error'].lower()


class TestRunCareerAIChat:
    def test_no_tool_calls_returns_content(self, app):
        from career_ai import run_career_ai_chat
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            fake_resp = {"message": {"role": "assistant", "content": "Chào em!"}}
            with patch('career_ai._ollama_chat_raw') as mock_chat:
                mock_chat.return_value = fake_resp
                reply, rounds = run_career_ai_chat(student, [], "hello")
                assert reply == "Chào em!"
                assert rounds == 0

    def test_single_tool_round_then_final(self, app):
        from career_ai import run_career_ai_chat
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            tool_call_resp = {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {"name": "search_majors", "arguments": {"limit": 3}}
                    }],
                }
            }
            final_resp = {"message": {"role": "assistant", "content": "Kết quả là..."}}
            with patch('career_ai._ollama_chat_raw') as mock_chat:
                mock_chat.side_effect = [tool_call_resp, final_resp]
                reply, rounds = run_career_ai_chat(student, [], "tìm ngành giúp em")
                assert reply == "Kết quả là..."
                assert rounds == 1
                assert mock_chat.call_count == 2

    def test_max_rounds_safety_net(self, app):
        from career_ai import run_career_ai_chat, MAX_TOOL_ROUNDS
        with app.app_context():
            from models import Student
            student = Student.query.filter_by(student_code='TS001').first()
            loop_resp = {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {"name": "search_majors", "arguments": {}}
                    }],
                }
            }
            with patch('career_ai._ollama_chat_raw') as mock_chat:
                mock_chat.return_value = loop_resp
                reply, rounds = run_career_ai_chat(student, [], "loop forever")
                assert "tra cứu nhiều quá" in reply
                assert rounds == MAX_TOOL_ROUNDS


class TestAICareerNewEndpoint:
    def test_new_creates_session_and_saves_initial_assistant_message(
            self, student_session, app):
        fake_resp = {"message": {"role": "assistant", "content": "Chào em, nhận xét..."}}
        with patch('career_ai._ollama_chat_raw') as mock_chat:
            mock_chat.return_value = fake_resp

            r = student_session.post('/api/career/ai/new')
            assert r.status_code == 200
            data = r.get_json()
            assert 'session_id' in data
            assert data['commentary'] == "Chào em, nhận xét..."

            with app.app_context():
                from models import ChatConversation, Student
                student = Student.query.filter_by(student_code='TS001').first()
                rows = ChatConversation.query.filter_by(
                    session_id=data['session_id'],
                    scope='career_advisor',
                    student_id=student.id,
                ).all()
                assert len(rows) == 1
                assert rows[0].role == 'assistant'
                assert rows[0].message == "Chào em, nhận xét..."
                import json as _json
                meta = _json.loads(rows[0].context_data or '{}')
                assert meta.get('is_initial') is True

    def test_new_rotates_session_id_between_calls(self, student_session, app):
        fake_resp = {"message": {"role": "assistant", "content": "ok"}}
        with patch('career_ai._ollama_chat_raw') as mock_chat:
            mock_chat.return_value = fake_resp

            r1 = student_session.post('/api/career/ai/new')
            r2 = student_session.post('/api/career/ai/new')
            assert r1.get_json()['session_id'] != r2.get_json()['session_id']

    def test_new_requires_student_login(self, client):
        r = client.post('/api/career/ai/new')
        assert r.status_code == 401


class TestAICareerMessageEndpoint:
    def _seed_session(self, student_session, app):
        with patch('career_ai._ollama_chat_raw') as mock_chat:
            mock_chat.return_value = {
                "message": {"role": "assistant", "content": "initial"}}
            r = student_session.post('/api/career/ai/new')
        return r.get_json()['session_id']

    def test_message_saves_user_and_assistant(self, student_session, app):
        sid = self._seed_session(student_session, app)
        fake_resp = {"message": {"role": "assistant", "content": "Reply nè"}}
        with patch('career_ai._ollama_chat_raw') as mock_chat:
            mock_chat.return_value = fake_resp
            r = student_session.post(
                '/api/career/ai/message', json={'message': 'Hỏi gì đó'})
            assert r.status_code == 200
            assert r.get_json()['reply'] == "Reply nè"

        with app.app_context():
            from models import ChatConversation, Student
            student = Student.query.filter_by(student_code='TS001').first()
            rows = (ChatConversation.query
                    .filter_by(session_id=sid, student_id=student.id,
                               scope='career_advisor')
                    .order_by(ChatConversation.created_at.asc()).all())
            assert len(rows) == 3
            roles = [r.role for r in rows]
            assert roles == ['assistant', 'user', 'assistant']
            assert rows[1].message == 'Hỏi gì đó'
            assert rows[2].message == 'Reply nè'

    def test_message_returns_400_when_no_session(self, student_session):
        with student_session.session_transaction() as s:
            s.pop('career_chat_session_id', None)
        r = student_session.post('/api/career/ai/message', json={'message': 'hi'})
        assert r.status_code == 400
        assert r.get_json()['error'] == 'session_expired'

    def test_message_returns_400_on_missing_message(self, student_session, app):
        self._seed_session(student_session, app)
        r = student_session.post('/api/career/ai/message', json={})
        assert r.status_code == 400

    def test_message_requires_student_login(self, client):
        r = client.post('/api/career/ai/message', json={'message': 'x'})
        assert r.status_code == 401


class TestAICareerHistoryEndpoint:
    def _seed_and_send(self, student_session, user_msg, assistant_msg):
        with patch('career_ai._ollama_chat_raw') as mock_chat:
            mock_chat.return_value = {
                "message": {"role": "assistant", "content": assistant_msg}}
            r = student_session.post('/api/career/ai/new')
            sid = r.get_json()['session_id']
            student_session.post('/api/career/ai/message', json={'message': user_msg})
        return sid

    def test_history_lists_sessions_of_current_student(self, student_session, app):
        sid1 = self._seed_and_send(student_session, 'câu 1', 'trả lời 1')
        sid2 = self._seed_and_send(student_session, 'câu 2', 'trả lời 2')
        r = student_session.get('/api/career/ai/history')
        assert r.status_code == 200
        data = r.get_json()
        ids = {s['session_id'] for s in data['sessions']}
        assert sid1 in ids
        assert sid2 in ids

    def test_history_most_recent_first(self, student_session, app):
        sid1 = self._seed_and_send(student_session, 'một', 'reply1')
        sid2 = self._seed_and_send(student_session, 'hai', 'reply2')
        r = student_session.get('/api/career/ai/history')
        sessions = r.get_json()['sessions']
        assert sessions[0]['session_id'] == sid2

    def test_history_title_uses_first_user_message(self, student_session, app):
        self._seed_and_send(student_session, 'Em muốn học ngành Y', 'ok')
        r = student_session.get('/api/career/ai/history')
        sessions = r.get_json()['sessions']
        assert any('Em muốn học ngành Y' in (s.get('title') or '') for s in sessions)

    def test_history_excludes_other_scopes(self, student_session, app):
        self._seed_and_send(student_session, 'career q', 'career a')
        with app.app_context():
            from models import ChatConversation, Student, db
            student = Student.query.filter_by(student_code='TS001').first()
            other = ChatConversation(
                session_id='not-career-session', student_id=student.id,
                role='user', message='teacher scope', scope='teacher_assistant',
            )
            db.session.add(other)
            db.session.commit()
        r = student_session.get('/api/career/ai/history')
        ids = {s['session_id'] for s in r.get_json()['sessions']}
        assert 'not-career-session' not in ids

    def test_history_requires_login(self, client):
        r = client.get('/api/career/ai/history')
        assert r.status_code == 401


class TestAICareerSessionDetailEndpoint:
    def _seed(self, student_session):
        with patch('career_ai._ollama_chat_raw') as mock_chat:
            mock_chat.return_value = {
                "message": {"role": "assistant", "content": "hello"}}
            r = student_session.post('/api/career/ai/new')
            sid = r.get_json()['session_id']
            student_session.post('/api/career/ai/message', json={'message': 'q1'})
        return sid

    def test_session_detail_returns_ordered_messages(self, student_session, app):
        sid = self._seed(student_session)
        r = student_session.get(f'/api/career/ai/session/{sid}')
        assert r.status_code == 200
        data = r.get_json()
        assert data['session_id'] == sid
        msgs = data['messages']
        assert len(msgs) == 3
        assert msgs[0]['role'] == 'assistant' and msgs[0].get('is_initial') is True
        assert msgs[1]['role'] == 'user'
        assert msgs[2]['role'] == 'assistant'

    def test_session_detail_blocks_cross_tenant(self, student_session, client, app):
        sid = self._seed(student_session)
        with app.app_context():
            from models import Student, db
            from werkzeug.security import generate_password_hash
            other = Student(
                name='Khác', student_code='OTHER1', student_class='12A2',
                password=generate_password_hash('pw'),
            )
            db.session.add(other)
            db.session.commit()
            other_id = other.id
        with client.session_transaction() as s:
            s['student_id'] = other_id
        r = client.get(f'/api/career/ai/session/{sid}')
        assert r.status_code == 403

    def test_session_detail_requires_login(self, client):
        r = client.get('/api/career/ai/session/anything')
        assert r.status_code == 401
