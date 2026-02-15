import os

templates_dir = r'c:\scutta-2026-1\app\templates'

replacements = [
    ('bg-main', 'bg-fuchsia-500 hover:bg-fuchsia-600 text-white'),
    ('text-blue-600', 'text-fuchsia-500'),
    ('text-blue-500', 'text-fuchsia-500'),
    ('bg-blue-500 ', 'bg-fuchsia-500 '),
    ('hover:bg-blue-600', 'hover:bg-fuchsia-600'),
    ('hover:bg-blue-700', 'hover:bg-fuchsia-700'),
    ('border-blue-500', 'border-fuchsia-400'),
    ('focus:ring-blue-500', 'focus:ring-fuchsia-500'),
    ('bg-blue-50', 'bg-fuchsia-50'),
    ('hover:border-blue-500', 'hover:border-fuchsia-300'),
    ('form-radio text-blue-600', 'form-radio accent-fuchsia-500'),
    ('form-radio text-red-600', 'form-radio accent-fuchsia-500'),
    ('bg-white p-6 rounded-lg shadow-sm', 'card'),
]

for f in os.listdir(templates_dir):
    if not f.endswith('.html'):
        continue
    path = os.path.join(templates_dir, f)
    with open(path, 'r', encoding='utf-8') as fh:
        content = fh.read()
    
    changed = False
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            changed = True
    
    if changed:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(content)
        print(f'Updated: {f}')
    else:
        print(f'No changes: {f}')

print('DONE')
