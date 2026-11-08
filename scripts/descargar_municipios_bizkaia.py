"""Descarga los límites municipales de Bizkaia (catastro foral, Open Data Bizkaia).

Uso:
    python -I scripts/descargar_municipios_bizkaia.py [salida.geojson]

Fuente: servicio REST del catastro de la Diputación Foral de Bizkaia, capa 8
«Municipios» (ficha «parcelario-catastral» de Open Data Bizkaia):
https://geo.bizkaia.eus/arcgisserverinspire/rest/services/LurraldeAntolamendua_PlanificacionTerritorial/Katastro_Catastro_WFS/MapServer/8
Guarda el GeoJSON tal cual lo sirve el servicio (EPSG:25830, resolución completa,
~6 MB) en data/raw/bizkaia/municipios_catastro/municipios.geojson por defecto.
La simplificación para la web se hace en scripts/web_preparar_datos.py.
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

CAPA = ("https://geo.bizkaia.eus/arcgisserverinspire/rest/services/LurraldeAntolamendua_PlanificacionTerritorial/"
        "Katastro_Catastro_WFS/MapServer/8/query")
UA = {"User-Agent": "Mozilla/5.0 (investigacion datos abiertos)"}


def main() -> None:
    salida = Path(sys.argv[1] if len(sys.argv) > 1 else
                  "data/raw/bizkaia/municipios_catastro/municipios.geojson")
    salida.parent.mkdir(parents=True, exist_ok=True)
    q = urllib.parse.urlencode({"where": "1=1", "outFields": "*", "returnGeometry": "true",
                                "outSR": "25830", "f": "geojson"})
    with urllib.request.urlopen(urllib.request.Request(f"{CAPA}?{q}", headers=UA), timeout=120) as r:
        datos = r.read()
    j = json.loads(datos)
    n = len(j.get("features", []))
    if n < 100:  # Bizkaia tiene 112-113 municipios; menos indica respuesta truncada
        raise SystemExit(f"Respuesta inesperada: {n} municipios")
    salida.write_bytes(datos)
    (salida.parent / "FUENTE.txt").write_text(
        f"Descargado el {date.today().isoformat()} de\n{CAPA}\n({n} municipios, EPSG:25830)\n", encoding="utf-8")
    print(f"{n} municipios -> {salida} ({len(datos) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
