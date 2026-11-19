import urllib.request

gids = {
    'Registro': '0',
    'Tabulador': '42869201',
    'Tabulador_Casetas': '1027491320',
    'Control_Combustible': '278516955'
}

for name, gid in gids.items():
    url = f"https://docs.google.com/spreadsheets/d/1PbhYjyw1rCWvP7iaDXcwhKjMHvwuGszxlq0wseA1W0o/export?format=csv&gid={gid}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode('utf-8')
        with open(f"{name}.csv", "w", encoding="utf-8") as f:
            f.write(data)
        print(f"Downloaded {name}.csv, length: {len(data)}")
    except Exception as e:
        print(f"Failed {name}: {e}")
