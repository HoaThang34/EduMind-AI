import os
import glob

def upgrade_template(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip already updated core templates
    filename = os.path.basename(filepath)
    if filename in ['base.html', 'login.html', 'student_login.html', 'dashboard.html', 'manage_students.html', 'index.html', 'welcome.html']:
        return

    # Color replacements
    replacements = {
        'text-slate-800': 'text-foreground',
        'text-slate-900': 'text-foreground',
        'text-slate-700': 'text-foreground',
        'text-slate-600': 'text-muted-foreground',
        'text-slate-500': 'text-muted-foreground',
        'text-slate-400': 'text-muted-foreground',
        'text-slate-300': 'text-muted-foreground',
        
        'border-slate-200': 'border-[hsl(240,5.9%,90%)]',
        'border-slate-100': 'border-[hsl(240,5.9%,90%)]',
        'border-white/40': 'border-[hsl(240,5.9%,90%)]',
        'border-white/50': 'border-[hsl(240,5.9%,90%)]',
        'border-white/60': 'border-[hsl(240,5.9%,90%)]',
        
        'bg-slate-50': 'bg-accent',
        'bg-slate-100': 'bg-accent',
        'bg-white/50': 'bg-white',
        'bg-white/60': 'bg-white',
        'bg-white/80': 'bg-white',
        
        'rounded-3xl': 'rounded-xl',
        'rounded-2xl': 'rounded-xl',
        'rounded-[2rem]': 'rounded-xl',
        'rounded-[2.5rem]': 'rounded-xl',
        
        'shadow-2xl': 'shadow-card',
        'shadow-xl': 'shadow-card',
        'shadow-lg': 'shadow-card',
        
        'font-extrabold': 'font-bold',
        'text-3xl font-bold': 'text-2xl font-semibold tracking-tight',

        # Button and input basic replacements
        'bg-indigo-600 hover:bg-indigo-700 text-white': 'btn-primary',
        'focus:ring-indigo-500 focus:border-indigo-500': 'input-shadcn',
        'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm': 'input-shadcn py-2',
        
        # Table borders
        'divide-slate-100': 'divide-[hsl(240,5.9%,90%)]',
        'divide-slate-200': 'divide-[hsl(240,5.9%,90%)]',
        'divide-slate-50': 'divide-[hsl(240,5.9%,90%)]',

        # specific table updates to shadcn
        '<table class="min-w-full divide-y divide-[hsl(240,5.9%,90%)]">': '<table class="table-shadcn">',
        '<thead class="bg-accent">': '<thead>'
    }

    original_content = content
    for old, new in replacements.items():
        content = content.replace(old, new)
        
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {filename}")

if __name__ == '__main__':
    template_dir = r"c:\Users\Admin\Desktop\EDU-MANAGER\templates"
    for filepath in glob.glob(os.path.join(template_dir, "*.html")):
        upgrade_template(filepath)
