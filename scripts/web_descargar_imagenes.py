"""Descarga de Wikimedia Commons las tres fotografías de la web y genera los WebP.

Uso:
    python -I scripts/web_descargar_imagenes.py

Qué hace:
  1. Para cada fichero de Commons fijado en FOTOS, pide a la API
     (action=query, prop=imageinfo, iiprop=url|extmetadata|size) el autor
     (Artist, limpio de HTML), la licencia (LicenseShortName y LicenseUrl),
     la URL de la página del fichero, la URL del original y su tamaño.
  2. Comprueba que la licencia está en la lista blanca (CC BY, CC BY-SA, CC0
     o dominio público). Si no lo está, el script se detiene con error.
  3. Descarga el original a data/raw/commons/ (carpeta propia para datos
     externos; nada se ejecuta desde ella).
  4. Recorta al encuadre indicado (sin deformar), reescala a 800 y 1600 px de
     ancho (o al ancho del original si es menor) y guarda WebP sin metadatos
     en web/img/<clave>-800.webp y web/img/<clave>-1600.webp. Si un fichero
     supera el peso máximo, baja la calidad en pasos de 4.
  5. Escribe web/img/creditos_imagenes.csv y web/data/imagenes.json (créditos para la web).

Solo usa la biblioteca estándar de Python y Pillow.
"""

from __future__ import annotations

import csv
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw" / "commons"
DIR_IMG = RAIZ / "web" / "img"
API = "https://commons.wikimedia.org/w/api.php"
UA = ("opendata-eus-avispa-asiatica/1.0 (proyecto de periodismo de datos, "
      "Reto Open Data Bizkaia; descarga puntual de 3 fotos con licencia libre)")

# Ficheros elegidos tras revisar las candidatas a mano (fijados; revisión del 08/11/2026,
# recorriendo las categorías «Vespa velutina», «Vespa velutina nests» y
# «Vespa velutina nigrithorax» con sus subcategorías por país).
# encuadre: proporción ancho/alto del recorte; centro_y: posición vertical
# del centro del recorte (0 = arriba, 1 = abajo). Estos WebP (-800/-1600) son
# los genéricos; los recortes que usa la web los hace web_adaptar_imagenes.py.
FOTOS = [
    {
        # Imagen valorada (Valued image) de Commons, identificada como V. velutina
        # nigrithorax (Portugal, 2016): rasgos diagnósticos visibles (tórax negro,
        # banda anaranjada, patas de punta amarilla), nítida y con fondo limpio.
        "clave": "avispa",
        "titulo": "File:Asian hornet (Vespa velutina).jpg",
        "encuadre": 3 / 2,
        "centro_y": 0.5,
        "descripcion_es": ("Avispa asiática (Vespa velutina nigrithorax) posada "
                           "sobre flores blancas de una umbelífera: tórax negro, "
                           "abdomen oscuro con una banda anaranjada y patas con "
                           "el extremo amarillo."),
    },
    {
        # Sustituye a «File:Vespa vélutina.jpg», que mostraba un nido con muchas
        # obreras (ya no era primario). Este es un nido embrionario de pocos
        # centímetros con un único individuo, la reina fundadora, asomado a la
        # abertura inferior: es exactamente la fase primaria. Mismo autor que la
        # anterior. Descartadas: «Vespa-velutina-starting-nest.png» (paleta de
        # colores reducida y 1198 px) y «Nido primario de una vespa velutina.jpg»
        # (nido ya retirado, fotografiado en estudio).
        "clave": "nido_primario",
        "titulo": "File:Vespa velutina nest.JPG",
        "encuadre": 4 / 3,
        "centro_y": 0.5,
        "descripcion_es": ("Nido primario de avispa asiática: una pequeña esfera "
                           "de papel pardo claro, vista por su abertura, con "
                           "una sola avispa, la reina fundadora, asomada a la "
                           "entrada."),
    },
    {
        # Sustituye a «File:Vespa velutina nid.jpg» (ramas por delante, se
        # entendía mal). Nido secundario grande, entero y sin nada delante, en lo
        # alto de un árbol sin hojas, recortado contra el cielo y con el bosque
        # al fondo: se reconoce a primera vista. Descartada «Paula Jorge -
        # vespas.jpg» (muy procesada: sobresaturación y ruido a tamaño real).
        "clave": "nido_secundario",
        "titulo": "File:Nid de frelons asiatiques.JPG",
        "encuadre": 4 / 3,
        "centro_y": 0.5,
        "descripcion_es": ("Nido secundario de avispa asiática, grande y con "
                           "forma de pera, colgado en lo alto de un árbol sin "
                           "hojas, contra el cielo y con un bosque al fondo."),
    },
]

ANCHOS = {800: 150_000, 1600: 350_000}  # ancho -> peso máximo en bytes
CALIDAD = 78
CALIDAD_MIN = 50

LICENCIAS_OK = re.compile(
    r"^(CC BY(-SA)? \d\.\d( [a-z]{2,3})?|CC0( 1\.0)?|Public domain|"
    r"PD|Dominio público)$", re.IGNORECASE)


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for intento in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and intento < 3:
                time.sleep(10 * (intento + 1))
                continue
            raise
    raise RuntimeError("inalcanzable")


def limpiar_html(texto: str) -> str:
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", html.unescape(texto)).strip()


def metadatos(titulos: list[str]) -> dict[str, dict]:
    params = {
        "action": "query", "titles": "|".join(titulos), "prop": "imageinfo",
        "iiprop": "url|extmetadata|size", "format": "json", "formatversion": "2",
    }
    datos = json.loads(http_get(API + "?" + urllib.parse.urlencode(params)))
    salida = {}
    for pg in datos["query"]["pages"]:
        if "imageinfo" not in pg:
            sys.exit(f"ERROR: no existe en Commons: {pg.get('title')}")
        ii = pg["imageinfo"][0]
        em = ii.get("extmetadata", {})
        val = lambda k: em.get(k, {}).get("value", "")  # noqa: E731
        salida[pg["title"]] = {
            "autor": limpiar_html(val("Artist")),
            "licencia": limpiar_html(val("LicenseShortName")),
            "url_licencia": val("LicenseUrl").strip(),
            "url_pagina": ii["descriptionurl"],
            "url_original": ii["url"].split("?")[0],  # sin parámetros utm_*
            "ancho_original": ii["width"],
            "alto_original": ii["height"],
            "bytes_original": ii["size"],
        }
    # La API puede normalizar el título (p. ej. caracteres Unicode).
    for t in titulos:
        if t not in salida:
            sys.exit(f"ERROR: la API no devolvió el título exacto {t!r}")
    return salida


def recortar(im: Image.Image, proporcion: float, centro_y: float) -> Image.Image:
    w, h = im.size
    if w / h > proporcion:  # demasiado ancha: recorte lateral centrado
        nw = round(h * proporcion)
        x0 = (w - nw) // 2
        return im.crop((x0, 0, x0 + nw, h))
    nh = round(w / proporcion)
    y0 = min(max(round(h * centro_y - nh / 2), 0), h - nh)
    return im.crop((0, y0, w, y0 + nh))


def guardar_webp(im: Image.Image, destino: Path, max_bytes: int) -> tuple[int, int]:
    calidad = CALIDAD
    while True:
        im.save(destino, "WEBP", quality=calidad, method=6)
        peso = destino.stat().st_size
        if peso <= max_bytes or calidad <= CALIDAD_MIN:
            return peso, calidad
        calidad -= 4


def main() -> None:
    DIR_RAW.mkdir(parents=True, exist_ok=True)
    DIR_IMG.mkdir(parents=True, exist_ok=True)
    meta = metadatos([f["titulo"] for f in FOTOS])

    for f in FOTOS:
        m = meta[f["titulo"]]
        if not LICENCIAS_OK.match(m["licencia"]):
            sys.exit(f"ERROR: licencia no admitida para {f['titulo']}: {m['licencia']!r}")
        if not m["autor"]:
            sys.exit(f"ERROR: sin autor en los metadatos de {f['titulo']}")
        if not m["url_licencia"] and not m["licencia"].lower().startswith(("public", "pd", "cc0")):
            sys.exit(f"ERROR: sin URL de licencia para {f['titulo']}")

    filas = []
    for f in FOTOS:
        m = meta[f["titulo"]]
        ext = Path(urllib.parse.urlparse(m["url_original"]).path).suffix.lower()
        original = DIR_RAW / f"{f['clave']}{ext}"
        # Si se cambia la foto de una clave, el original guardado ya no coincide en bytes.
        if not original.exists() or original.stat().st_size != m["bytes_original"]:
            for viejo in DIR_RAW.glob(f"{f['clave']}.*"):
                viejo.unlink()
            original.write_bytes(http_get(m["url_original"]))
            time.sleep(1)
        with Image.open(original) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            if im.size != (m["ancho_original"], m["alto_original"]):
                print(f"Aviso: {original.name} mide {im.size}, la API dice "
                      f"{m['ancho_original']}x{m['alto_original']}")
            rec = recortar(im, f["encuadre"], f["centro_y"])
            for ancho, max_bytes in ANCHOS.items():
                a = min(ancho, rec.width)
                out = rec.resize((a, round(rec.height * a / rec.width)), Image.LANCZOS) \
                    if a != rec.width else rec
                destino = DIR_IMG / f"{f['clave']}-{ancho}.webp"
                peso, q = guardar_webp(out, destino, max_bytes)
                print(f"{destino.relative_to(RAIZ)}: {out.width}x{out.height}, "
                      f"{peso / 1000:.0f} kB, calidad {q}")
        filas.append({
            "clave": f["clave"],
            "fichero_commons": f["titulo"],
            **{k: m[k] for k in ("autor", "licencia", "url_licencia", "url_pagina",
                                 "url_original", "ancho_original", "alto_original")},
            "descripcion_es": f["descripcion_es"],
        })

    csv_path = DIR_IMG / "creditos_imagenes.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(f"{csv_path.relative_to(RAIZ)}: {len(filas)} filas")
    # Lo mismo en JSON para la web (créditos visibles al pie de cada foto y en la metodología)
    import json
    (RAIZ / "web" / "data" / "imagenes.json").write_text(json.dumps(
        {f["clave"]: {k: f[k] for k in ("autor", "licencia", "url_licencia", "url_pagina", "descripcion_es")}
         | {"src": f"img/{f['clave']}-800.webp", "src2x": f"img/{f['clave']}-1600.webp"} for f in filas},
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
