from pathlib import Path
text = Path('exports.py').read_text(encoding='utf-8')
start = text.find('parts.append("""')
pos = start
print('start', start)
while True:
    idx = text.find('\n    def norm', pos+1)
    if idx == -1:
        break
    print('def norm at', idx)
    pos = idx
