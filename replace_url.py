import os
def replace_in_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = content.replace('url_for("login")', 'url_for("auth.login")')
    new_content = new_content.replace("url_for('login')", "url_for('auth.login')")
    new_content = new_content.replace('url_for("logout")', 'url_for("auth.logout")')
    new_content = new_content.replace("url_for('logout')", "url_for('auth.logout')")
    if content != new_content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {path}')

replace_in_file('app.py')
for root, _, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            replace_in_file(os.path.join(root, file))
replace_in_file('routes/auth.py')
print("Done")
