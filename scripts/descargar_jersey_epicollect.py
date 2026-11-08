"""Descarga las entradas públicas del proyecto Epicollect5 «<año>-jersey-asian-hornet-reports».
Uso: python -I descargar_jersey_epicollect.py <año> <carpeta_salida>
Guarda entries_<año>.json (lista de entradas). API pública: https://five.epicollect.net/api/export/entries/<slug>
"""
import json, sys, time, urllib.request
from pathlib import Path
anio, out = sys.argv[1], Path(sys.argv[2])
slug = f"{anio}-jersey-asian-hornet-reports"
todas, page = [], 1
while True:
    url = f"https://five.epicollect.net/api/export/entries/{slug}?per_page=500&page={page}"
    with urllib.request.urlopen(url, timeout=120) as r:
        d = json.load(r)
    todas += d["data"]["entries"]
    if page >= d["meta"]["last_page"]:
        break
    page += 1
    time.sleep(1)
out.mkdir(parents=True, exist_ok=True)
(out / f"entries_{anio}.json").write_text(json.dumps(todas, ensure_ascii=False))
print(anio, len(todas), "entradas")
