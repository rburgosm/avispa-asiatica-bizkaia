"""Versiones .gz de los ficheros de texto de la web (para `gzip_static on;` de nginx o equivalente)
y medida del peso de la primera carga y del total.

Uso:
    python -I scripts/web_comprimir.py

Comprime con gzip (nivel 9) los .json, .geojson, .js, .css, .html, .svg y .csv de web/ (no los
.webp, .woff2 ni .pmtiles, que ya van comprimidos) y escribe web/data/pesos.json con:
- primera carga: lo que se pide antes de la primera interacción (portada, librerías básicas,
  contenido y datos del mapa de la narración), comprimido;
- total: todo lo que puede llegar a pedir la página, comprimido.
"""
import gzip
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"
TEXTO = {".json", ".geojson", ".js", ".css", ".html", ".svg", ".csv", ".txt", ".pbf"}
# Primera pintura e interacción: portada (texto e imagen estática) con su CSS y sus letras
INTERACTIVA = [
    "index.html", "css/estilo.css", "js/cargador.js", "data/portada.webp",
    "vendor/fonts/source-serif-4-latin-400-normal.woff2", "vendor/fonts/source-serif-4-latin-600-normal.woff2",
]
# Mapa vivo de la portada (llega después, sin bloquear): librerías básicas, módulos y datos del mapa
PRIMERA = [
    "index.html", "css/estilo.css", "js/cargador.js", "js/app.js", "js/util.js",
    "js/componentes/mapa.js", "js/componentes/mapa_narrativo.js", "js/componentes/mapa_detalle.js",
    "js/componentes/fondo_mapa.js", "js/componentes/contador.js", "js/componentes/anotaciones.js",
    "vendor/d3.min.js", "vendor/scrollama.min.js",
    "vendor/fonts/source-serif-4-latin-400-normal.woff2", "vendor/fonts/source-serif-4-latin-600-normal.woff2",
    "vendor/fonts/source-sans-3-latin-400-normal.woff2", "vendor/fonts/source-sans-3-latin-600-normal.woff2",
    "data/portada.webp", "content/es.json", "data/imagenes.json",
    "data/nidos.json", "data/municipios.geojson", "data/situacion.geojson", "data/nido_hilo.json",
    "data/censo_ilustracion.json", "data/densidad.geojson", "data/lugares.geojson", "data/contorno.geojson",
    "data/relieve.json", "data/relieve.webp",
]


def main() -> None:
    pesos = {}
    for f in sorted(WEB.rglob("*")):
        if not f.is_file() or f.suffix == ".gz":
            continue
        rel = f.relative_to(WEB).as_posix()
        if f.suffix in TEXTO:
            datos = f.read_bytes()
            gz = gzip.compress(datos, compresslevel=9, mtime=0)
            Path(str(f) + ".gz").write_bytes(gz)
            pesos[rel] = (len(datos), len(gz))
        else:
            n = f.stat().st_size
            pesos[rel] = (n, n)
    falta = [p for p in PRIMERA if p not in pesos]
    if falta:
        raise SystemExit(f"Faltan ficheros de la primera carga: {falta}")
    primera = sum(pesos[p][1] for p in PRIMERA)
    sin_pmtiles = {k: v for k, v in pesos.items() if not k.endswith(".pmtiles")}
    total = sum(v[1] for v in sin_pmtiles.values())
    interactiva = sum(pesos[p][1] for p in INTERACTIVA)
    resumen = {
        "primera_pintura_e_interaccion_kb": round(interactiva / 1024),
        "primera_carga_comprimida_kb": round(primera / 1024),
        "total_comprimido_sin_mapa_base_kb": round(total / 1024),
        "mapa_base_pmtiles_kb": round(pesos.get("data/mapa_base/bizkaia.pmtiles", (0, 0))[1] / 1024),
        "primera_carga": {p: round(pesos[p][1] / 1024, 1) for p in PRIMERA},
    }
    (WEB / "data" / "pesos.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Primera pintura e interacción (comprimida): {resumen['primera_pintura_e_interaccion_kb']} KB")
    print(f"Primera carga completa con el mapa vivo de la portada (comprimida): {resumen['primera_carga_comprimida_kb']} KB")
    print(f"Total (comprimido, sin el PMTiles): {resumen['total_comprimido_sin_mapa_base_kb']} KB; "
          f"PMTiles: {resumen['mapa_base_pmtiles_kb']} KB (por rangos: solo se baja lo que se ve)")
    for p, kb in sorted(resumen["primera_carga"].items(), key=lambda x: -x[1])[:8]:
        print(f"  {p}: {kb} KB")


if __name__ == "__main__":
    main()
