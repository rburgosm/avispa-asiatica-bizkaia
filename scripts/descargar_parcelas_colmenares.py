"""Descarga del parcelario catastral de Bizkaia las parcelas donde hay colmenares.

Uso: descargar_parcelas_colmenares.py <carpeta_explotaciones_ganaderas> <salida.geojson>

Lee los CSV «explotaciones-ganaderas-AAAA.csv», toma las filas de especie «Abejas» con
polígono y parcela, y pide cada parcela (municipio, polígono, parcela) al servicio REST
del parcelario catastral (capa 6 «Parcelas», ficha parcelario-catastral de Open Data
Bizkaia). Guarda un GeoJSON en EPSG:25830 con los campos muni_cod, pol, par.
"""
import io
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

REST = ("https://geo.bizkaia.eus/arcgisserverinspire/rest/services/LurraldeAntolamendua_PlanificacionTerritorial/"
        "Katastro_Catastro_WFS/MapServer/6/query")
UA = {"User-Agent": "Mozilla/5.0 (investigacion datos abiertos)"}


def leer(p: Path) -> pd.DataFrame:
    t = p.read_bytes().decode("utf-8-sig")
    if "Ã" in t[:300000]:
        t = t.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
    d = pd.read_csv(io.StringIO(t), dtype=str)
    d.columns = [c.split("/")[-1].strip() for c in d.columns]
    return d


def main() -> None:
    carpeta, salida = Path(sys.argv[1]), Path(sys.argv[2])
    claves = set()
    for f in sorted(carpeta.glob("explotaciones-ganaderas-*.csv")):
        d = leer(f)
        a = d[d.ESPECIE.str.contains("Abej", na=False)].dropna(subset=["POLIGONO", "PARCELA"])
        for _, r in a.iterrows():
            cod = int(str(r.CODIGO).strip('="'))
            claves.add((cod, int(float(r.POLIGONO)), int(float(r.PARCELA))))
    print(f"Parcelas distintas a pedir: {len(claves)}")
    feats, faltan = [], []
    for cod, pol, par in sorted(claves):
        q = urllib.parse.urlencode({
            "where": f"Codigo_Municipio={cod} AND Codigo_Poligono={pol} AND Codigo_Parcela={par}",
            "outFields": "Codigo_Municipio,Codigo_Poligono,Codigo_Parcela", "outSR": 25830,
            "returnGeometry": "true", "f": "geojson"})
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{REST}?{q}", headers=UA), timeout=60) as r:
                fc = json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {cod}/{pol}/{par}: {e}")
            faltan.append((cod, pol, par))
            continue
        if not fc.get("features"):
            faltan.append((cod, pol, par))
        for ft in fc.get("features", []):
            ft["properties"] = {"muni_cod": cod, "pol": pol, "par": par}
            feats.append(ft)
        time.sleep(0.25)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps({"type": "FeatureCollection",
                                  "crs": {"type": "name", "properties": {"name": "EPSG:25830"}},
                                  "features": feats}), encoding="utf-8")
    print(f"Recintos guardados: {len(feats)}; parcelas sin respuesta: {len(faltan)} {faltan[:20]}")


if __name__ == "__main__":
    main()
