"""Mapa base propio de la web: recorte de Bizkaia del mapa base de Protomaps (PMTiles).

Uso:
    python -I scripts/web_descargar_mapa_base.py [fecha_build] [zoom_maximo]

Pasos (todo con herramientas oficiales y abiertas de Protomaps):
1. Descarga la CLI oficial `pmtiles` (go-pmtiles, versión fijada) de su página de versiones en
   GitHub y comprueba su SHA-256.
2. Elige un build diario público de https://build.protomaps.com (por defecto el más reciente de
   https://build-metadata.protomaps.dev/builds.json; los builds antiguos se borran, por eso se
   guarda cuál se usó) y ejecuta `pmtiles extract <build> --bbox=... --maxzoom=...`, que solo
   descarga por HTTP los trozos del fichero que caen dentro del recorte.
3. Descarga los glifos de las etiquetas (Noto Sans, licencia OFL) del repositorio oficial
   protomaps/basemaps-assets, fijado a un commit, solo para los rangos de caracteres latinos.

Salida en web/data/mapa_base/:
    bizkaia.pmtiles           teselas vectoriales del recorte (esquema de Protomaps)
    fuentes/<fuente>/<rango>.pbf  glifos para MapLibre, con OFL.txt
    mapa_base.json            build, versión del esquema, fecha, recorte, zoom máximo, tamaño y SHA-256

Los datos del mapa son de OpenStreetMap (ODbL) y otras fuentes abiertas recopiladas por
Protomaps; la atribución se muestra en el mapa.
"""
import hashlib
import json
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "web" / "data" / "mapa_base"
HERRAMIENTAS = RAIZ / "data" / "raw" / "herramientas"  # ignorado por git

PMTILES_VERSION = "1.31.2"
PMTILES_TAR = f"go-pmtiles_{PMTILES_VERSION}_Linux_x86_64.tar.gz"
PMTILES_URL = f"https://github.com/protomaps/go-pmtiles/releases/download/v{PMTILES_VERSION}/{PMTILES_TAR}"
# Alternativa si la descarga directa falla (GitHub da 504 a veces): el mismo fichero por la API
PMTILES_API = "https://api.github.com/repos/protomaps/go-pmtiles/releases/assets/486313332"
PMTILES_SHA256 = "3ed7dbf4ec2e6dfe5e25b6f70d1ffc932729f93c86db353bf514dd71010a312f"  # API de GitHub (digest)

BUILDS = "https://build-metadata.protomaps.dev/builds.json"
BUILD_URL = "https://build.protomaps.com/{key}"

# Bizkaia con margen: Cantábrico al norte, Cantabria al oeste, Gipuzkoa al este y Araba y
# Burgos al sur. Es ancho a propósito: en un móvil en vertical, Bizkaia entera deja ver
# mucho más norte y sur que su propia caja.
BBOX = (-4.00, 42.60, -2.00, 43.90)  # oeste, sur, este, norte
ZOOM_MAXIMO = 12  # con 13 pesa unos 49 MB; MapLibre amplía (overzoom) las teselas de z12

ASSETS_COMMIT = "028c18f713baecad011301ff7a69acc39bcc2ae7"  # protomaps/basemaps-assets, 31/10/2025
ASSETS = f"https://raw.githubusercontent.com/protomaps/basemaps-assets/{ASSETS_COMMIT}/fonts/"
FUENTES = ["Noto Sans Regular", "Noto Sans Medium", "Noto Sans Italic"]
# Latín básico y suplemento, Latín extendido A y B, diacríticos, Latín adicional y puntuación
RANGOS = ["0-255", "256-511", "512-767", "768-1023", "7680-7935", "8192-8447"]


def bajar(url: str, intentos: int = 6, cabeceras: dict | None = None) -> bytes:
    for k in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", **(cabeceras or {})})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # GitHub devuelve 504 de vez en cuando
            if k == intentos - 1:
                raise
            print(f"  reintento {k + 1} ({e})")
            time.sleep(5 * (k + 1))
    raise RuntimeError(url)


def cli_pmtiles() -> Path:
    exe = HERRAMIENTAS / f"pmtiles-{PMTILES_VERSION}" / "pmtiles"
    if exe.exists():
        return exe
    try:
        datos = bajar(PMTILES_URL, intentos=2)
    except Exception:
        datos = bajar(PMTILES_API, cabeceras={"Accept": "application/octet-stream"})
    if hashlib.sha256(datos).hexdigest() != PMTILES_SHA256:
        raise SystemExit("El SHA-256 de la CLI pmtiles no coincide")
    exe.parent.mkdir(parents=True, exist_ok=True)
    tar = exe.parent / PMTILES_TAR
    tar.write_bytes(datos)
    with tarfile.open(tar) as t:
        t.extract("pmtiles", exe.parent, filter="data")
    exe.chmod(0o755)
    return exe


def main() -> None:
    a = sys.argv[1:]
    builds = json.loads(bajar(BUILDS))
    if a and a[0]:
        build = next(b for b in builds if b["key"] == f"{a[0]}.pmtiles")
    else:
        build = max(builds, key=lambda b: b["key"])
    zmax = int(a[1]) if len(a) > 1 else ZOOM_MAXIMO
    SALIDA.mkdir(parents=True, exist_ok=True)
    exe = cli_pmtiles()
    destino = SALIDA / "bizkaia.pmtiles"
    url = BUILD_URL.format(key=build["key"])
    bbox = ",".join(str(x) for x in BBOX)
    print(f"pmtiles extract {url} --bbox={bbox} --maxzoom={zmax}")
    subprocess.run([str(exe), "extract", url, str(destino), f"--bbox={bbox}", f"--maxzoom={zmax}"], check=True)
    datos = destino.read_bytes()
    print(f"bizkaia.pmtiles: {len(datos) / 1e6:.1f} MB")

    n = 0
    for f in FUENTES:
        carpeta = SALIDA / "fuentes" / f
        carpeta.mkdir(parents=True, exist_ok=True)
        for r in RANGOS:
            (carpeta / f"{r}.pbf").write_bytes(bajar(ASSETS + urllib.parse.quote(f) + f"/{r}.pbf"))
            n += 1
    (SALIDA / "fuentes" / "OFL.txt").write_bytes(bajar(ASSETS + "OFL.txt"))
    print(f"glifos: {n} ficheros")

    (SALIDA / "mapa_base.json").write_text(json.dumps({
        "descargado": date.today().isoformat(),
        "build": build["key"], "build_subido": build["uploaded"], "version_esquema": build["version"],
        "origen": url, "cli": f"go-pmtiles {PMTILES_VERSION}", "bbox": BBOX, "zoom_maximo": zmax,
        "bytes": len(datos), "sha256": hashlib.sha256(datos).hexdigest(),
        "glifos": {"origen": f"protomaps/basemaps-assets@{ASSETS_COMMIT}", "fuentes": FUENTES, "rangos": RANGOS},
        "atribucion": "Protomaps © OpenStreetMap",
    }, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
