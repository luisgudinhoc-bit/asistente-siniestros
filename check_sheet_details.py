import urllib.request
import re

url = 'https://docs.google.com/spreadsheets/d/1PbhYjyw1rCWvP7iaDXcwhKjMHvwuGszxlq0wseA1W0o/edit?usp=sharing'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode('utf-8')
    with open('sheet_source.html', 'w', encoding='utf-8') as f:
        f.write(html)
    
    # search for names
    names = re.findall(r'\[(\d+),\"([^\"]+)\",\d+', html)
    print("Found names:", names)
    
    # search for Tabulador, Registro, Control Combustible
    for word in ['Registro', 'Control Combustible', 'Tabulador', 'Tabulador Casetas']:
        print(f"Contains '{word}':", word in html)
except Exception as e:
    print('Err:', e)
