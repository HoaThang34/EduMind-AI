"""Register Flask URL routes (split from monolithic app.py)."""


def register_all_routes(app):
    from .core import register as register_core
    from .violations_mgmt import register as register_violations
    from .students_mgmt import register as register_students
    from .subjects_mgmt import register as register_subjects
    from .rules_bonus import register as register_rules_bonus
    from .admin_mgmt import register as register_admin
    from .messaging import register as register_messaging
    from .lesson_book import register as register_lesson_book
    from .timetable import register as register_timetable
    from .class_fund import register as register_class_fund
    from .attendance import register as register_attendance

    register_core(app)
    register_violations(app)
    register_students(app)
    register_subjects(app)
    register_rules_bonus(app)
    register_admin(app)
    register_messaging(app)
    register_lesson_book(app)
    register_timetable(app)
    register_class_fund(app)
    register_attendance(app)
