import os

def replace_student_urls(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    replacements = [
        ('url_for("student_login")', 'url_for("student.student_login")'),
        ("url_for('student_login')", "url_for('student.student_login')"),
        ('url_for("student_logout")', 'url_for("student.student_logout")'),
        ("url_for('student_logout')", "url_for('student.student_logout')"),
        ('url_for("student_dashboard")', 'url_for("student.student_dashboard")'),
        ("url_for('student_dashboard')", "url_for('student.student_dashboard')"),
    ]
    
    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)
        
    if content != new_content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {path}')

replace_student_urls('app.py')
replace_student_urls('routes/student.py')
for root, _, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            replace_student_urls(os.path.join(root, file))
print("Done student replacements")
