"""Favicon, iconos, manifiesto, imágenes para compartir y metadatos del <head> de la web.

Uso (después de web_preparar_portada.py y web_preparar_densidad.py):
    python -I scripts/web_preparar_compartir.py                       # sin dominio: rutas relativas
    python -I scripts/web_preparar_compartir.py --url-base https://ejemplo.org/nidos/

Escribe en web/:
- favicon.svg (con su versión para modo oscuro dentro, por prefers-color-scheme), favicon.ico
  (16, 32 y 48 px), apple-touch-icon.png (180 px), icon-192.png, icon-512.png y site.webmanifest.
  El motivo es el marcador del nido hilo del mapa (js/componentes/mapa_narrativo.js): punto naranja
  con anillo oscuro sobre el papel.
- og-image.png y og-metodologia.png (1200x630): el mapa de densidad media de la portada
  (data/portada.webp, que ya lleva el relieve, los límites y el contorno, más las bandas de
  data/densidad.geojson y el nido hilo de data/nido_hilo.json) con el título, el subtítulo y la firma
  de content/es.json (bloque «meta») en Source Serif 4 y Source Sans 3 (vendor/fonts; los woff2
  se pasan a TrueType en memoria con fontTools).
- El bloque de metadatos del <head> de index.html y metodologia.html, entre los marcadores
  <!-- compartir:auto --> y <!-- /compartir:auto -->: título, descripción, autor, iconos,
  theme-color, Open Graph, Twitter/X y JSON-LD. Sin --url-base, og:image va con ruta relativa y no
  se escriben canonical ni og:url (necesitan la dirección absoluta). Con --url-base, todo absoluto.

Pillow, fontTools (con brotli), matplotlib y geopandas.
"""
import argparse
import html
import io
import json
import struct
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"
# Paleta (css/estilo.css y docs/paleta_colores.md, modo oscuro validado)
PAPEL, TINTA, TINTA_SUAVE, ACENTO = "#faf7f0", "#1d1a16", "#5a5248", "#c4600a"
PAPEL_OSC, TINTA_OSC, ACENTO_OSC = "#17140f", "#ece6da", "#d0701c"
RAMPA = ["#f6cf86", "#eba545", "#cf7414", "#9c4f08", "#5a2a05"]
OPACIDAD_MEDIA = 0.82  # capa «media» de la densidad en mapa_narrativo.js
# Proyección del mapa vivo y de la portada (mapa_narrativo.js, web_preparar_portada.py)
LON0, LAT0, KM_LON, KM_LAT = -2.9, 43.2, 111.32, 110.57
K = np.cos(np.radians(43.2))
FECHA = "2026-11"  # noviembre de 2026 (ISO 8601 con precisión de mes)
FUENTE_DATOS = "https://www.opendatabizkaia.eus"
MARCA_INI, MARCA_FIN = "<!-- compartir:auto -->", "<!-- /compartir:auto -->"
DESC_MAX = 155


# ---------- Iconos ----------
# Rejilla de 32 unidades pensada para que se lea a 16 px: anillo de 1,75 px y punto de 6 px de diámetro.
FONDO_RX, ANILLO_R, ANILLO_W, PUNTO_R = 7, 10.5, 3.5, 6.0


def svg_favicon() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <style>
    .fondo {{ fill: {PAPEL}; }} .anillo {{ fill: none; stroke: {TINTA}; }} .punto {{ fill: {ACENTO}; }}
    @media (prefers-color-scheme: dark) {{
      .fondo {{ fill: {PAPEL_OSC}; }} .anillo {{ stroke: {TINTA_OSC}; }} .punto {{ fill: {ACENTO_OSC}; }}
    }}
  </style>
  <rect class="fondo" width="32" height="32" rx="{FONDO_RX}"/>
  <circle class="anillo" cx="16" cy="16" r="{ANILLO_R}" stroke-width="{ANILLO_W}"/>
  <circle class="punto" cx="16" cy="16" r="{PUNTO_R}"/>
</svg>
"""


def icono(lado: int, motivo: float = 1.0, redondeo: bool = True) -> Image.Image:
    """Icono raster dibujado a 8 veces su tamaño y reducido con Lanczos.
    motivo: fracción del lado que ocupa la rejilla de 32 (menos de 1 deja margen de papel)."""
    s = 8
    L = lado * s
    im = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if redondeo:
        d.rounded_rectangle([0, 0, L - 1, L - 1], radius=FONDO_RX / 32 * L, fill=PAPEL)
    else:
        d.rectangle([0, 0, L, L], fill=PAPEL)
    u = L * motivo / 32  # píxeles por unidad de la rejilla
    c = L / 2
    r_ext, r_int = (ANILLO_R + ANILLO_W / 2) * u, (ANILLO_R - ANILLO_W / 2) * u
    d.ellipse([c - r_ext, c - r_ext, c + r_ext, c + r_ext], fill=TINTA)
    d.ellipse([c - r_int, c - r_int, c + r_int, c + r_int], fill=PAPEL)
    d.ellipse([c - PUNTO_R * u, c - PUNTO_R * u, c + PUNTO_R * u, c + PUNTO_R * u], fill=ACENTO)
    return im.resize((lado, lado), Image.Resampling.LANCZOS)


def escribir_ico(ruta: Path, imagenes: list[Image.Image]) -> None:
    """ICO con PNG dentro (un PNG por tamaño); se escribe a mano la cabecera para controlar cada
    tamaño (el guardado de Pillow reescala desde una sola imagen)."""
    datos = []
    for im in imagenes:
        b = io.BytesIO()
        im.save(b, "PNG", optimize=True)
        datos.append(b.getvalue())
    cab = struct.pack("<HHH", 0, 1, len(imagenes))
    desp = 6 + 16 * len(imagenes)
    entradas = b""
    for im, d in zip(imagenes, datos):
        w = im.width if im.width < 256 else 0
        entradas += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(d), desp)
        desp += len(d)
    ruta.write_bytes(cab + entradas + b"".join(datos))


def iconos() -> None:
    (WEB / "favicon.svg").write_text(svg_favicon(), encoding="utf-8")
    escribir_ico(WEB / "favicon.ico", [icono(n) for n in (16, 32, 48)])
    # Apple redondea las esquinas: fondo de papel entero y motivo con margen
    icono(180, motivo=0.72, redondeo=False).convert("RGB").save(WEB / "apple-touch-icon.png", optimize=True)
    # 192 y 512: el motivo cabe en la zona segura de los iconos «maskable» (círculo del 80 %)
    for n in (192, 512):
        icono(n, motivo=0.66, redondeo=False).convert("RGB").save(WEB / f"icon-{n}.png", optimize=True)


def manifiesto(meta: dict) -> None:
    m = {
        "name": meta["titulo"],
        "short_name": "Nidos Bizkaia",
        "description": meta["subtitulo"],
        "lang": "es-ES",
        "start_url": "./index.html",
        "scope": "./",
        "display": "standalone",
        "background_color": PAPEL,
        "theme_color": PAPEL,
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            {"src": "favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }
    (WEB / "site.webmanifest").write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ---------- Imágenes para compartir ----------
OG_W, OG_H = 1200, 630
MAPA_X0 = 470            # el mapa ocupa de aquí al borde derecho
CENTRO_X, ESCALA = 922, 6.0  # centro de la caja de los municipios (px) y píxeles por km


def fuente(nombre: str, tam: int) -> ImageFont.FreeTypeFont:
    f = TTFont(WEB / "vendor/fonts" / nombre)
    f.flavor = None  # woff2 -> TrueType, en memoria
    b = io.BytesIO()
    f.save(b)
    b.seek(0)
    return ImageFont.truetype(b, tam)


def mapa_og(tenue: bool) -> Image.Image:
    """Recorte del mapa de la portada con la densidad media y el nido hilo, a la escala ESCALA."""
    datos = WEB / "data"
    por = json.loads((datos / "portada.json").read_text(encoding="utf-8"))
    o, s_, e, n = por["caja_imagen"]
    rx0, rx1 = (o - LON0) * K * KM_LON, (e - LON0) * K * KM_LON
    ry0, ry1 = (s_ - LAT0) * KM_LAT, (n - LAT0) * KM_LAT
    x0, y0, x1, y1 = por["caja_municipios"]
    cx = ((x0 + x1) / 2 - LON0) * K * KM_LON
    cy = ((y0 + y1) / 2 - LAT0) * KM_LAT
    w_px, h_px = OG_W - MAPA_X0, OG_H
    izq = cx - (CENTRO_X - MAPA_X0) / ESCALA
    der = izq + w_px / ESCALA
    aba, arr = cy - h_px / 2 / ESCALA, cy + h_px / 2 / ESCALA

    def km(g):
        return g.set_crs("EPSG:4326", allow_override=True).affine_transform(
            [K * KM_LON, 0, 0, KM_LAT, -LON0 * K * KM_LON, -LAT0 * KM_LAT])

    dens = gpd.read_file(datos / "densidad.geojson")
    dens = dens[dens["capa"] == "media"]
    cont = gpd.read_file(datos / "contorno.geojson")
    hilo = json.loads((datos / "nido_hilo.json").read_text(encoding="utf-8"))["nido"]
    hx, hy = (hilo["lon"] - LON0) * K * KM_LON, (hilo["lat"] - LAT0) * KM_LAT

    sc = 2  # se dibuja al doble y se reduce
    fig = plt.figure(figsize=(w_px * sc / 100, h_px * sc / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.imshow(np.asarray(Image.open(datos / "portada.webp").convert("RGB")), extent=[rx0, rx1, ry0, ry1],
              interpolation="bilinear", zorder=0, aspect="auto")
    alfa = OPACIDAD_MEDIA * (0.55 if tenue else 1)
    for _, f in dens.iterrows():
        km(gpd.GeoSeries([f.geometry])).plot(ax=ax, color=RAMPA[min(int(f["banda"]), 4)], alpha=alfa,
                                             linewidth=0, zorder=1)
    km(cont.boundary).plot(ax=ax, color=TINTA, linewidth=1.4, alpha=0.8, zorder=2)
    if not tenue:  # marcador del nido hilo, como en el mapa (anillo de 13 px y punto de 5 px)
        ax.scatter([hx], [hy], s=(2 * 13 * sc * 0.75) ** 2, facecolors="none", edgecolors=TINTA,
                   linewidths=2.5 * sc * 0.75, zorder=3)
        ax.scatter([hx], [hy], s=(2 * 5 * sc * 0.75) ** 2, color=ACENTO, edgecolors=PAPEL,
                   linewidths=2 * sc * 0.75, zorder=4)
    ax.set_xlim(izq, der)
    ax.set_ylim(aba, arr)
    ax.set_aspect("auto")
    ax.set_position([0, 0, 1, 1])
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=100)
    plt.close(fig)
    return Image.open(b).convert("RGB").resize((w_px, h_px), Image.Resampling.LANCZOS)


def partir(texto: str, f: ImageFont.FreeTypeFont, ancho: int) -> list[str]:
    """Líneas equilibradas: el mínimo número de líneas que caben en «ancho» y, entre los cortes
    posibles, el de la línea más larga más corta (sin palabras huérfanas)."""
    from itertools import combinations
    p = texto.split()
    for n in range(1, len(p) + 1):
        mejor = None
        for cortes in combinations(range(1, len(p)), n - 1):
            lim = (0, *cortes, len(p))
            li = [" ".join(p[a:b]) for a, b in zip(lim, lim[1:])]
            m = max(f.getlength(x) for x in li)
            if m <= ancho and (mejor is None or m < mejor[0]):
                mejor = (m, li)
        if mejor:
            return mejor[1]
    return p


def imagen_og(ruta: Path, titulo: str, subtitulo: str | None, antetitulo: str | None, firma: str,
              tenue: bool) -> None:
    im = Image.new("RGB", (OG_W, OG_H), PAPEL)
    im.paste(mapa_og(tenue), (MAPA_X0, 0))
    # Fundido del papel sobre el borde izquierdo del mapa
    grad = Image.new("L", (OG_W, OG_H), 0)
    gd = ImageDraw.Draw(grad)
    ancho_f = 200
    for i in range(ancho_f):
        a = round(255 * (1 - (i / ancho_f)) ** 1.6)
        gd.line([(MAPA_X0 + i, 0), (MAPA_X0 + i, OG_H)], fill=a)
    gd.rectangle([0, 0, MAPA_X0, OG_H], fill=255)
    im = Image.composite(Image.new("RGB", (OG_W, OG_H), PAPEL), im, grad)

    d = ImageDraw.Draw(im)
    X, ANCHO = 64, 580
    f_tit = fuente("source-serif-4-latin-600-normal.woff2", 84 if subtitulo else 104)
    f_sub = fuente("source-serif-4-latin-400-normal.woff2", 33)
    f_ante = fuente("source-sans-3-latin-600-normal.woff2", 28)
    f_firma = fuente("source-sans-3-latin-600-normal.woff2", 26)
    bloques = []  # (líneas, fuente, color, interlineado, espacio después)
    if antetitulo:
        bloques.append((partir(antetitulo, f_ante, ANCHO), f_ante, ACENTO, 1.2, 18))
    bloques.append((partir(titulo, f_tit, ANCHO), f_tit, TINTA, 1.0, 38))
    if subtitulo:
        bloques.append((partir(subtitulo, f_sub, ANCHO), f_sub, TINTA, 1.3, 0))
    alto = sum(len(li) * f.size * il + esp for li, f, _, il, esp in bloques)
    y = (OG_H - 70 - alto) / 2  # centrado en vertical sobre la firma
    for li, f, col, il, esp in bloques:
        for linea in li:
            d.text((X, y), linea, font=f, fill=col)
            y += f.size * il
        y += esp
    d.text((X, OG_H - 64), firma, font=f_firma, fill=TINTA_SUAVE, anchor="ls")
    im.save(ruta, "PNG", optimize=True)
    if ruta.stat().st_size > 290 * 1024:  # por si acaso: paleta de 256 colores con difuminado
        im.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(
            ruta, "PNG", optimize=True)
    print(f"{ruta.name}: {OG_W}x{OG_H}, {ruta.stat().st_size / 1024:.0f} KB")


# ---------- Metadatos del <head> ----------
def bloque_head(p: dict, url_base: str | None) -> str:
    e = lambda s: html.escape(s, quote=True)  # noqa: E731
    url = (lambda r: url_base + r) if url_base else (lambda r: r)
    img = url(p["imagen"])
    ld = {
        "@context": "https://schema.org",
        "@type": p["tipo_ld"],
        "headline": p["og_titulo"],
        "description": p["descripcion"],
        "inLanguage": "es-ES",
        "datePublished": FECHA,
        "author": {"@type": "Person", "name": p["autor"]},
        "image": {"@type": "ImageObject", "url": img, "width": OG_W, "height": OG_H},
        "isBasedOn": FUENTE_DATOS,
    }
    if url_base:
        ld["url"] = url(p["ruta"])
        ld["mainEntityOfPage"] = url(p["ruta"])
    if p.get("parte_de"):
        ld["isPartOf"] = {"@type": "NewsArticle", "headline": p["parte_de"],
                          **({"url": url("index.html")} if url_base else {})}
    L = [
        MARCA_INI,
        f"<title>{e(p['titulo'])}</title>",
        f'<meta name="description" content="{e(p["descripcion"])}">',
        f'<meta name="author" content="{e(p["autor"])}">',
        f'<meta name="theme-color" content="{PAPEL}" media="(prefers-color-scheme: light)">',
        f'<meta name="theme-color" content="{PAPEL_OSC}" media="(prefers-color-scheme: dark)">',
        '<link rel="icon" href="favicon.ico" sizes="16x16 32x32 48x48">',
        '<link rel="icon" href="favicon.svg" type="image/svg+xml">',
        '<link rel="apple-touch-icon" href="apple-touch-icon.png">',
        '<link rel="manifest" href="site.webmanifest">',
    ]
    if url_base:
        L.append(f'<link rel="canonical" href="{e(url(p["ruta"]))}">')
    L += [
        '<meta property="og:type" content="article">',
        f'<meta property="og:site_name" content="{e(p["sitio"])}">',
        '<meta property="og:locale" content="es_ES">',
        f'<meta property="og:title" content="{e(p["og_titulo"])}">',
        f'<meta property="og:description" content="{e(p["descripcion"])}">',
    ]
    if url_base:
        L.append(f'<meta property="og:url" content="{e(url(p["ruta"]))}">')
    L += [
        f'<meta property="og:image" content="{e(img)}">',
        '<meta property="og:image:type" content="image/png">',
        f'<meta property="og:image:width" content="{OG_W}">',
        f'<meta property="og:image:height" content="{OG_H}">',
        f'<meta property="og:image:alt" content="{e(p["imagen_alt"])}">',
        f'<meta property="article:author" content="{e(p["autor"])}">',
        f'<meta property="article:published_time" content="{FECHA}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{e(p["og_titulo"])}">',
        f'<meta name="twitter:description" content="{e(p["descripcion"])}">',
        f'<meta name="twitter:image" content="{e(img)}">',
        f'<meta name="twitter:image:alt" content="{e(p["imagen_alt"])}">',
        '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
        + "</script>",
        MARCA_FIN,
    ]
    return "\n  ".join(L)


def escribir_head(fichero: Path, bloque: str) -> None:
    t = fichero.read_text(encoding="utf-8")
    a, b = t.find(MARCA_INI), t.find(MARCA_FIN)
    if a >= 0 and b > a:
        nuevo = t[:a] + bloque + t[b + len(MARCA_FIN):]
    else:
        # Primera vez: el bloque sustituye al <title> y a la descripción que hubiera
        import re
        t2 = re.sub(r"\s*<title>.*?</title>", "", t, count=1, flags=re.S)
        t2 = re.sub(r'\s*<meta name="description"[^>]*>', "", t2, count=1)
        i = t2.find('<meta name="viewport"')
        i = t2.find("\n", i)
        nuevo = t2[:i] + "\n  " + bloque + t2[i:]
    if nuevo != t:
        fichero.write_text(nuevo, encoding="utf-8")
        print(f"{fichero.name}: metadatos actualizados")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url-base", default=None,
                    help="dirección pública de la carpeta web/ (p. ej. https://ejemplo.org/nidos/); "
                         "sin ella, rutas relativas y sin canonical ni og:url")
    a = ap.parse_args()
    url_base = a.url_base
    if url_base and not url_base.endswith("/"):
        url_base += "/"

    meta = json.loads((WEB / "content/es.json").read_text(encoding="utf-8"))["meta"]
    titulo, subtitulo, autor = meta["titulo"], meta["subtitulo"], meta["autoria"]
    firma = f"{autor} · Open Data Bizkaia"

    iconos()
    manifiesto(meta)
    print("iconos: favicon.svg, favicon.ico (16/32/48), apple-touch-icon.png, icon-192.png, icon-512.png, site.webmanifest")
    imagen_og(WEB / "og-image.png", titulo, subtitulo, None, firma, tenue=False)
    imagen_og(WEB / "og-metodologia.png", "Metodología", None, titulo, firma, tenue=True)

    alt_mapa = ("Mapa de Bizkaia con la densidad media de nidos de avispa asiática avisados por km² y año "
                "en 2019-2025, junto al título")
    paginas = [
        {"fichero": "index.html", "ruta": "", "titulo": titulo, "og_titulo": titulo,
         "descripcion": f"{subtitulo}: una evaluación con los datos abiertos de Open Data Bizkaia, de 2019 a 2025.",
         "imagen": "og-image.png", "imagen_alt": f"{alt_mapa} «{titulo}».", "tipo_ld": "NewsArticle"},
        {"fichero": "metodologia.html", "ruta": "metodologia.html", "titulo": f"Metodología · {titulo}",
         "og_titulo": f"Metodología · {titulo}",
         "descripcion": (f"Datos, limpieza, métodos, limitaciones y reproducibilidad de «{titulo}», "
                         "sobre la retirada de nidos de avispa asiática en Bizkaia."),
         "imagen": "og-metodologia.png", "imagen_alt": f"{alt_mapa} «Metodología».", "tipo_ld": "TechArticle",
         "parte_de": titulo},
    ]
    for p in paginas:
        p.update(autor=autor, sitio=titulo)
        if len(p["descripcion"]) > DESC_MAX:
            print(f"AVISO: la descripción de {p['fichero']} tiene {len(p['descripcion'])} caracteres (máximo {DESC_MAX})")
        escribir_head(WEB / p["fichero"], bloque_head(p, url_base))
    print(f"URL base: {url_base or '(ninguna: rutas relativas, sin canonical ni og:url)'}")


if __name__ == "__main__":
    main()
