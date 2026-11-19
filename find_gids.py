import re

with open('sheet_source.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Look for patterns around 'Registro', 'Control Combustible', etc.
for word in ['Registro', 'Control Combustible', 'Tabulador', 'Tabulador Casetas']:
    idx = 0
    while True:
        pos = html.find(word, idx)
        if pos == -1:
            break
        print(f"--- Found {word} at {pos} ---")
        print(html[max(0, pos-100):min(len(html), pos+150)])
        idx = pos + len(word)
        if idx > pos + 1000:
            break
