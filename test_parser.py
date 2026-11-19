from gemini_parser import SiniestrosAIParser
import json

parser = SiniestrosAIParser()

# Test 1: Mensaje informal
m1 = "Inbursa reporte 7057081 choque en Tulancingo, atendí una Ram, casetas 195"
res1 = parser.parse_reporte_texto(m1)
print("TEST 1 (Inbursa):\n", json.dumps(res1, indent=2, ensure_ascii=False))

# Test 2: Mensaje SPT
m2 = "SPT 67436 local Urvan"
res2 = parser.parse_reporte_texto(m2)
print("\nTEST 2 (SPT):\n", json.dumps(res2, indent=2, ensure_ascii=False))

# Test 3: Gasolina
m3 = "Cargué $800 de magna 34.5 litros"
res3 = parser.parse_gasolina(texto=m3)
print("\nTEST 3 (Gasolina):\n", json.dumps(res3, indent=2, ensure_ascii=False))
