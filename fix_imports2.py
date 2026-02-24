import os

for fname in ['student.py', 'grades.py', 'ai_engine.py']:
    path = os.path.join('routes', fname)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        lines = code.split('\n')
        new_lines = []
        app_imports = ''
        for line in lines:
            if 'from app import ' in line:
                app_imports = line.strip()
            else:
                new_lines.append(line)
        
        final_lines = []
        for line in new_lines:
            final_lines.append(line)
            if 'def ' in line and not 'def student_required' in line and not 'def admin_required' in line:
                if 'def decorated_function' in line:
                    final_lines.append('        ' + app_imports)
                elif line.strip().startswith('def '):
                    indent = len(line) - len(line.lstrip())
                    final_lines.append(' ' * (indent + 4) + app_imports)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(final_lines))
        print(f'Fixed {path}')
