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
    "LICENCIA-d3.txt": "d3@7.9.0/LICENSE",
    "LICENCIA-scrollama.txt": "scrollama@3.2.0/LICENSE",
    "LICENCIA-maplibre-gl.txt": "maplibre-gl@4.7.1/LICENSE.txt",
}


def main() -> None:
    destino = RAIZ / "web" / "vendor"
    destino.mkdir(parents=True, exist_ok=True)
    lineas = []
    for nombre, ruta in LIBRERIAS.items():
        req = urllib.request.Request(CDN + ruta, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            datos = r.read()
        (destino / nombre).write_bytes(datos)
        lineas.append(f"{nombre}\t{ruta}\t{hashlib.sha256(datos).hexdigest()}")
        print(f"{nombre}: {len(datos) / 1024:.0f} KB")
    (destino / "VERSIONES.txt").write_text("fichero\torigen (npm)\tsha256\n" + "\n".join(lineas) + "\n",
                                          encoding="utf-8")


if __name__ == "__main__":
    main()
