import os

for fname in ['student.py', 'grades.py', 'ai_engine.py']:
    path = os.path.join('routes', fname)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Replace global import from app with local imports
        new_lines = []
        app_imports = ''
        for line in lines:
            if line.startswith('from app import '):
                app_imports = line
            else:
                new_lines.append(line)
        
        if app_imports:
            # Inject import into functions
            final_lines = []
            for line in new_lines:
                final_lines.append(line)
                if line.startswith('def '):
                    final_lines.append('    ' + app_imports.strip() + '\n')
            
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(final_lines)
            print(f'Fixed {path}')
