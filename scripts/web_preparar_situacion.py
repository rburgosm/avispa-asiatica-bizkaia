"""Mapa de situación de la web: la península ibérica con Bizkaia resaltada (web/data/situacion.geojson).

Uso (después de scripts/web_preparar_datos.py):
    python -I scripts/web_preparar_situacion.py [carpeta_web_data]

Fuente: Natural Earth 1:50 m, países (dominio público), versión fijada del repositorio oficial
nvkelso/natural-earth-vector. Se recorta a la península y el sur de Francia, se simplifica con
shapely y se añade el contorno de Bizkaia (unión de web/data/municipios.geojson).
"""
import json
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

RAIZ = Path(__file__).resolve().parent.parent
NE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/"
      "geojson/ne_50m_admin_0_countries.geojson")
CAJA = (-10.0, 35.8, 4.0, 44.6)
TOLERANCIA = 0.05  # grados


def main() -> None:
    web = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "web/data"
    destino = RAIZ / "data/raw/naturalearth/ne_50m_admin_0_countries.geojson"
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(NE, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            destino.write_bytes(r.read())
    p = gpd.read_file(destino)[["ADMIN", "geometry"]]
    p = p.clip(box(*CAJA))
    p = p[~p.is_empty]
    p["geometry"] = p.geometry.simplify(TOLERANCIA, preserve_topology=True)
    p["tipo"] = "pais"
    b = gpd.read_file(web / "municipios.geojson")
    biz = gpd.GeoDataFrame({"ADMIN": ["Bizkaia"], "tipo": ["bizkaia"]},
                           geometry=[b.union_all().simplify(0.005)], crs=b.crs)
    out = gpd.GeoDataFrame(pd_concat([p, biz]), crs="EPSG:4326").rename(columns={"ADMIN": "nombre"})
    texto = out.to_json(drop_id=True)
    g = json.loads(texto)
    g["caja"] = CAJA
    g["fuente"] = "Natural Earth 1:50 m (dominio público), v5.1.2"

    def r(c):
        return [round(c[0], 2), round(c[1], 2)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    for f in g["features"]:
        f["geometry"]["coordinates"] = r(f["geometry"]["coordinates"])
    (web / "situacion.geojson").write_text(json.dumps(g, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"situacion.geojson: {len(g['features'])} elementos, {(web / 'situacion.geojson').stat().st_size / 1024:.0f} KB")


def pd_concat(lista):
    import pandas as pd
    return pd.concat(lista, ignore_index=True)


if __name__ == "__main__":
    main()
