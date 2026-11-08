"""Copia las librerías de la web a web/vendor/ para que funcione sin CDN.

Uso:
    python -I scripts/web_descargar_librerias.py

Versiones fijadas (las mismas que usa web/js/cargador.js como alternativa por CDN).
Descarga de jsDelivr (paquetes de npm) y escribe web/vendor/VERSIONES.txt con el SHA-256
de cada fichero, para poder comprobar que no cambian entre descargas.
"""
import hashlib
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CDN = "https://cdn.jsdelivr.net/npm/"
LIBRERIAS = {
    # destino: ruta en npm (paquete@versión exacta/fichero)
    "d3.min.js": "d3@7.9.0/dist/d3.min.js",
    "scrollama.min.js": "scrollama@3.2.0/build/scrollama.min.js",
    "maplibre-gl.js": "maplibre-gl@4.7.1/dist/maplibre-gl.js",
    "maplibre-gl.css": "maplibre-gl@4.7.1/dist/maplibre-gl.css",
    "pmtiles.js": "pmtiles@4.4.1/dist/pmtiles.js",
    "basemaps.js": "@protomaps/basemaps@5.7.2/dist/basemaps.js",
    "LICENCIA-d3.txt": "d3@7.9.0/LICENSE",
    "LICENCIA-scrollama.txt": "scrollama@3.2.0/LICENSE",
    "LICENCIA-maplibre-gl.txt": "maplibre-gl@4.7.1/LICENSE.txt",
}
# Los paquetes de npm de pmtiles y @protomaps/basemaps no incluyen la licencia (BSD-3-Clause):
# se toma del repositorio oficial de cada uno.
LICENCIAS_GITHUB = {
    "LICENCIA-pmtiles.txt": "https://raw.githubusercontent.com/protomaps/PMTiles/main/LICENSE",
    "LICENCIA-protomaps-basemaps.txt": "https://raw.githubusercontent.com/protomaps/basemaps/main/LICENSE.md",
}


def main() -> None:
    destino = RAIZ / "web" / "vendor"
    destino.mkdir(parents=True, exist_ok=True)
    lineas = []
    for nombre, ruta in {**LIBRERIAS, **LICENCIAS_GITHUB}.items():
        url = ruta if ruta.startswith("https://") else CDN + ruta
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            datos = r.read()
        (destino / nombre).write_bytes(datos)
        lineas.append(f"{nombre}\t{ruta}\t{hashlib.sha256(datos).hexdigest()}")
        print(f"{nombre}: {len(datos) / 1024:.0f} KB")
    (destino / "VERSIONES.txt").write_text("fichero\torigen (npm o URL)\tsha256\n" + "\n".join(lineas) + "\n",
                                          encoding="utf-8")


if __name__ == "__main__":
    main()
