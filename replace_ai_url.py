import os

def replace_ai_urls(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    replacements = [
        ('url_for("chatbot"', 'url_for("ai_engine.chatbot"'),
        ("url_for('chatbot'", "url_for('ai_engine.chatbot'"),
        ('url_for("assistant_chatbot"', 'url_for("ai_engine.assistant_chatbot"'),
        ("url_for('assistant_chatbot'", "url_for('ai_engine.assistant_chatbot'"),
        ('url_for("generate_report"', 'url_for("ai_engine.generate_report"'),
        ("url_for('generate_report'", "url_for('ai_engine.generate_report'"),
        ('url_for("generate_parent_report"', 'url_for("ai_engine.generate_parent_report"'),
        ("url_for('generate_parent_report'", "url_for('ai_engine.generate_parent_report'"),
    ]
    
    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)
        
    if content != new_content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {path}')

replace_ai_urls('app.py')
replace_ai_urls('routes/ai_engine.py')
for root, _, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            replace_ai_urls(os.path.join(root, file))
print("Done AI replacements")
