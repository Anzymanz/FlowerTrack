from pathlib import Path
text = Path('exports.py').read_text(encoding='utf-8')
print('def norm idx', text.find('\n    def norm'))
print('parts append', text.find('parts.append("""'))
