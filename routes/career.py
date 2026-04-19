from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from models import db, Student, UniversityMajor, MajorSubjectWeight, StudentPinnedMajor, StudentTargetMajor, SystemConfig, MajorEntryScore
from app_helpers import calculate_subject_averages, calculate_fit_score
import datetime
import unicodedata
import re

career_bp = Blueprint('career', __name__)


def _student():
    sid = session.get('student_id')
    return Student.query.get(sid) if sid else None


def _cfg():
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    return int(configs.get('current_semester', '1')), configs.get('school_year', '2025-2026')


def _weights_list(major):
    return [{'subject_name': w.subject_name, 'weight': w.weight, 'min_score': w.min_score}
            for w in major.weights]


def _normalize(s):
    if not s:
        return ''
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.replace('đ', 'd').replace('Đ', 'D').lower()


def _acronym(s):
    return ''.join(w[0] for w in re.split(r'\s+', _normalize(s).strip()) if w)


def _fuzzy_match(q, major):
    qn = _normalize(q).replace(' ', '')
    if not qn:
        return True
    hay = _normalize(major.name + ' ' + major.university).replace(' ', '')
    if qn in hay:
        return True
    acr = _acronym(major.university) + _acronym(major.name)
    return qn in acr


_EXCLUDED_SUBJECTS = {'Tiếng Pháp', 'Tiếng Nhật', 'Tiếng Nga', 'Tiếng Hàn',
                       'Tiếng Trung', 'Tiếng Đức'}

def _radar(major_id, averages, axes='union'):
    """Radar: axes='union' = môn khối ∪ môn HS có điểm; axes='core' = chỉ môn weight>=0.03."""
    weights = MajorSubjectWeight.query.filter_by(major_id=major_id).all()
    req = {w.subject_name: w.min_score for w in weights}
    wlist = [{'subject_name': w.subject_name, 'weight': w.weight, 'min_score': w.min_score}
             for w in weights]
    core = {w.subject_name for w in weights if w.weight >= 0.03} - _EXCLUDED_SUBJECTS
    if axes == 'core':
        labels = sorted(core)
    else:
        labels = sorted((core | set(averages.keys())) - _EXCLUDED_SUBJECTS)
    stu_scores = [averages.get(s, 0.0) for s in labels]
    maj_scores = [req.get(s, 0.0) for s in labels]
    return labels, stu_scores, maj_scores, wlist


@career_bp.route('/student/career')
def career_main():
    student = _student()
    if not student:
        return redirect(url_for('student.student_login'))
    sem, yr = _cfg()
    averages = calculate_subject_averages(student.id, sem, yr)

    target = StudentTargetMajor.query.filter_by(student_id=student.id).first()
    target_major = target.major if target else None
    target_data = None
    if target_major:
        fit = calculate_fit_score(averages, _weights_list(target_major))
        target_data = {'major': target_major, 'fit_pct': fit['fit_pct'], 'gaps': fit['gaps']}

    pins = StudentPinnedMajor.query.filter_by(student_id=student.id).all()
    pinned_data = []
    for p in pins:
        fit = calculate_fit_score(averages, _weights_list(p.major))
        pinned_data.append({'major': p.major, 'fit_pct': fit['fit_pct']})

    default_major = target_major or UniversityMajor.query.first()
    if default_major:
        labels, stu_scores, maj_scores, _ = _radar(default_major.id, averages)
    else:
        labels, stu_scores, maj_scores = [], [], []

    return render_template('student_career.html',
        student=student, target_data=target_data, pinned_data=pinned_data,
        radar_labels=labels, radar_student=stu_scores, radar_major=maj_scores,
        default_major=default_major)


@career_bp.route('/api/student/career/radar-data')
def api_radar_data():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    major_id = request.args.get('major_id', type=int)
    major = UniversityMajor.query.get_or_404(major_id)
    sem, yr = _cfg()
    averages = calculate_subject_averages(student.id, sem, yr)
    labels, stu_scores, maj_scores, wlist = _radar(major_id, averages)
    fit = calculate_fit_score(averages, wlist)
    return jsonify({
        'labels': labels, 'student_scores': stu_scores, 'major_scores': maj_scores,
        'fit_pct': fit['fit_pct'], 'gaps': fit['gaps'],
        'major': {'id': major.id, 'name': major.name, 'university': major.university},
    })


@career_bp.route('/api/student/career/browse')
def api_browse():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    sem, yr = _cfg()
    averages = calculate_subject_averages(student.id, sem, yr)

    group = request.args.get('group', '')
    min_fit = request.args.get('min_fit', 0, type=float)
    q = request.args.get('q', '').strip()
    university = request.args.get('university', '').strip()
    admission_block = request.args.get('admission_block', '').strip()

    query = UniversityMajor.query
    if university:
        query = query.filter(UniversityMajor.university == university)
    if admission_block:
        query = query.filter(UniversityMajor.admission_block == admission_block)
    if group:
        query = query.filter(UniversityMajor.major_group == group)
    majors = query.all()
    if q:
        majors = [m for m in majors if _fuzzy_match(q, m)]

    pinned_ids = {p.major_id for p in StudentPinnedMajor.query.filter_by(student_id=student.id)}
    target = StudentTargetMajor.query.filter_by(student_id=student.id).first()
    target_id = target.major_id if target else None

    results = []
    for major in majors:
        wlist = _weights_list(major)
        if not wlist:
            continue
        fit = calculate_fit_score(averages, wlist)
        if fit['fit_pct'] < min_fit:
            continue
        labels, stu_scores, maj_scores, _ = _radar(major.id, averages, axes='union')
        entry_scores_sorted = sorted(
            [{'year': es.year, 'score': es.score} for es in major.entry_scores],
            key=lambda x: x['year']
        )
        results.append({
            'id': major.id, 'name': major.name, 'university': major.university,
            'faculty': major.faculty, 'major_group': major.major_group,
            'admission_block': major.admission_block,
            'entry_score': major.entry_score,
            'fit_pct': fit['fit_pct'],
            'is_pinned': major.id in pinned_ids,
            'is_target': major.id == target_id,
            'radar': {'labels': labels, 'student_scores': stu_scores, 'major_scores': maj_scores},
            'entry_scores': entry_scores_sorted,
        })
    results.sort(key=lambda x: x['fit_pct'], reverse=True)
    return jsonify({'majors': results})


@career_bp.route('/api/student/career/my-averages')
def api_my_averages():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    sem, yr = _cfg()
    return jsonify({'averages': calculate_subject_averages(student.id, sem, yr)})


@career_bp.route('/api/student/career/simulate', methods=['POST'])
def api_simulate():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    scores = request.json.get('scores', {})
    if not scores:
        return jsonify({'error': 'scores required'}), 400

    majors = UniversityMajor.query.all()
    results = []
    for major in majors:
        wlist = _weights_list(major)
        if not wlist:
            continue
        fit = calculate_fit_score(scores, wlist)
        results.append({
            'id': major.id, 'name': major.name, 'university': major.university,
            'admission_block': major.admission_block,
            'entry_score': major.entry_score,
            'fit_pct': fit['fit_pct'],
            'gaps': fit['gaps'],
        })
    results.sort(key=lambda x: x['fit_pct'], reverse=True)
    return jsonify({'majors': results})


@career_bp.route('/api/student/career/compare')
def api_compare():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    raw = request.args.get('major_ids', '')
    try:
        ids = [int(x) for x in raw.split(',') if x.strip()]
    except ValueError:
        return jsonify({'error': 'invalid major_ids'}), 400
    if len(ids) > 4:
        return jsonify({'error': 'max 4 majors'}), 400

    sem, yr = _cfg()
    averages = calculate_subject_averages(student.id, sem, yr)

    results = []
    for mid in ids:
        major = UniversityMajor.query.get(mid)
        if not major:
            continue
        wlist = _weights_list(major)
        fit = calculate_fit_score(averages, wlist)
        labels, stu_scores, maj_scores, _ = _radar(mid, averages)
        entry_scores_sorted = sorted(
            [{'year': es.year, 'score': es.score} for es in major.entry_scores],
            key=lambda x: x['year']
        )
        results.append({
            'id': major.id, 'name': major.name, 'university': major.university,
            'faculty': major.faculty, 'major_group': major.major_group,
            'admission_block': major.admission_block,
            'entry_score': major.entry_score,
            'fit_pct': fit['fit_pct'],
            'gaps': fit['gaps'],
            'weights': wlist,
            'radar': {'labels': labels, 'student_scores': stu_scores, 'major_scores': maj_scores},
            'entry_scores': entry_scores_sorted,
        })
    return jsonify({'majors': results, 'student_scores': averages})


@career_bp.route('/api/student/career/score-history')
def api_score_history():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    raw = request.args.get('major_ids', '')
    try:
        ids = [int(x) for x in raw.split(',') if x.strip()]
    except ValueError:
        return jsonify({'error': 'invalid major_ids'}), 400

    result = {}
    for mid in ids:
        scores = MajorEntryScore.query.filter_by(major_id=mid).order_by(MajorEntryScore.year).all()
        result[mid] = [{'year': s.year, 'score': s.score} for s in scores]
    return jsonify(result)


@career_bp.route('/api/student/career/map-data')
def api_map_data():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    sem, yr = _cfg()
    averages = calculate_subject_averages(student.id, sem, yr)

    majors = UniversityMajor.query.all()
    result = []
    for major in majors:
        wlist = _weights_list(major)
        if not wlist:
            continue
        weight_vector = {w['subject_name']: w['weight'] for w in wlist}
        fit = calculate_fit_score(averages, wlist)
        result.append({
            'id': major.id, 'name': major.name, 'university': major.university,
            'major_group': major.major_group,
            'admission_block': major.admission_block,
            'entry_score': major.entry_score or 20.0,
            'fit_pct': fit['fit_pct'],
            'weight_vector': weight_vector,
        })
    student_vector = {subj: avg for subj, avg in averages.items()}
    return jsonify({'majors': result, 'student_vector': student_vector})


@career_bp.route('/api/student/career/pin', methods=['POST'])
def api_pin():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    major_id = request.json.get('major_id')
    if not UniversityMajor.query.get(major_id):
        return jsonify({'error': 'not found'}), 404
    if not StudentPinnedMajor.query.filter_by(student_id=student.id, major_id=major_id).first():
        db.session.add(StudentPinnedMajor(
            student_id=student.id, major_id=major_id, pinned_at=datetime.datetime.utcnow()))
        db.session.commit()
    return jsonify({'ok': True})


@career_bp.route('/api/student/career/pin/<int:major_id>', methods=['DELETE'])
def api_unpin(major_id):
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    pin = StudentPinnedMajor.query.filter_by(student_id=student.id, major_id=major_id).first()
    if pin:
        db.session.delete(pin)
        db.session.commit()
    return jsonify({'ok': True})


@career_bp.route('/api/student/career/target', methods=['POST'])
def api_set_target():
    student = _student()
    if not student:
        return jsonify({'error': 'unauthorized'}), 401
    major_id = request.json.get('major_id')
    if not UniversityMajor.query.get(major_id):
        return jsonify({'error': 'not found'}), 404
    existing = StudentTargetMajor.query.filter_by(student_id=student.id).first()
    if existing:
        existing.major_id = major_id
        existing.set_at = datetime.datetime.utcnow()
    else:
        db.session.add(StudentTargetMajor(
            student_id=student.id, major_id=major_id, set_at=datetime.datetime.utcnow()))
    db.session.commit()
    return jsonify({'ok': True})


@career_bp.route('/student/career/browse')
def career_browse():
    student = _student()
    if not student:
        return redirect(url_for('student.student_login'))
    groups = [g[0] for g in db.session.query(UniversityMajor.major_group).distinct().all() if g[0]]
    return render_template('student_career_browse.html', student=student, groups=groups)


@career_bp.route('/student/career/compare')
def career_compare():
    student = _student()
    if not student:
        return redirect(url_for('student.student_login'))
    major_ids = request.args.get('major_ids', '')
    return render_template('student_career_compare.html',
                           student=student, major_ids=major_ids)


@career_bp.route('/student/career/map')
def career_map():
    student = _student()
    if not student:
        return redirect(url_for('student.student_login'))
    return render_template('student_career_map.html', student=student)


@career_bp.route('/admin/majors')
def admin_majors():
    from flask_login import current_user
    if not current_user.is_authenticated or current_user.role != 'admin':
        return redirect(url_for('auth.login'))
    majors = UniversityMajor.query.order_by(UniversityMajor.university).all()
    return render_template('admin_majors.html', majors=majors)


@career_bp.route('/admin/majors/add', methods=['POST'])
def admin_add_major():
    from flask_login import current_user
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    data = request.json
    major = UniversityMajor(
        name=data['name'], university=data['university'],
        faculty=data.get('faculty', ''), major_group=data.get('major_group', ''),
        description=data.get('description', ''), created_at=datetime.datetime.utcnow())
    db.session.add(major)
    db.session.flush()
    for w in data.get('weights', []):
        db.session.add(MajorSubjectWeight(
            major_id=major.id, subject_name=w['subject_name'],
            weight=float(w['weight']), min_score=float(w['min_score'])))
    db.session.commit()
    return jsonify({'ok': True, 'id': major.id})


@career_bp.route('/admin/majors/<int:major_id>', methods=['DELETE'])
def admin_delete_major(major_id):
    from flask_login import current_user
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    major = UniversityMajor.query.get_or_404(major_id)
    db.session.delete(major)
    db.session.commit()
    return jsonify({'ok': True})


@career_bp.route('/admin/majors/<int:major_id>', methods=['PATCH'])
def admin_update_major(major_id):
    from flask_login import current_user
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    major = UniversityMajor.query.get_or_404(major_id)
    data = request.json
    if 'admission_block' in data:
        major.admission_block = data['admission_block']
    if 'entry_score' in data:
        major.entry_score = float(data['entry_score']) if data['entry_score'] else None
    db.session.commit()
    return jsonify({'ok': True})


@career_bp.route('/admin/majors/<int:major_id>/entry-scores', methods=['POST'])
def admin_add_entry_score(major_id):
    from flask_login import current_user
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    UniversityMajor.query.get_or_404(major_id)
    data = request.json
    year = int(data['year'])
    score = float(data['score'])
    existing = MajorEntryScore.query.filter_by(major_id=major_id, year=year).first()
    if existing:
        existing.score = score
    else:
        db.session.add(MajorEntryScore(major_id=major_id, year=year, score=score))
    db.session.commit()
    return jsonify({'ok': True})
