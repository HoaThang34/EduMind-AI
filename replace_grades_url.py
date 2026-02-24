import os

def replace_grades_urls(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    replacements = [
        ('url_for("manage_grades"', 'url_for("grades.manage_grades"'),
        ("url_for('manage_grades'", "url_for('grades.manage_grades'"),
        ('url_for("student_grades"', 'url_for("grades.student_grades"'),
        ("url_for('student_grades'", "url_for('grades.student_grades'"),
        ('url_for("delete_grade"', 'url_for("grades.delete_grade"'),
        ("url_for('delete_grade'", "url_for('grades.delete_grade'"),
        ('url_for("update_grade"', 'url_for("grades.update_grade"'),
        ("url_for('update_grade'", "url_for('grades.update_grade'"),
        ('url_for("transcript"', 'url_for("grades.transcript"'),
        ("url_for('transcript'", "url_for('grades.transcript'"),
    ]
    
    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)
        
    if content != new_content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {path}')

replace_grades_urls('app.py')
replace_grades_urls('routes/grades.py')
for root, _, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            replace_grades_urls(os.path.join(root, file))
print("Done grades replacements")
