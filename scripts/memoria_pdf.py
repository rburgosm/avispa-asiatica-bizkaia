"""Genera docs/memoria_tecnica.pdf a partir de docs/memoria_tecnica.md, con la identidad visual de la web.

Uso:
    .venv/bin/python -I scripts/memoria_pdf.py [entrada.md] [salida.pdf]

Herramientas libres: Python-Markdown (BSD) pasa el markdown a HTML y WeasyPrint (BSD) lo maqueta
en PDF; la imagen de portada se compone con Pillow (dependencia de WeasyPrint). Entorno propio:
    python3 -m venv .venv && .venv/bin/pip install markdown weasyprint
(WeasyPrint necesita Pango, que traen las distribuciones Linux habituales.)

Identidad visual, la misma que la web (web/css/estilo.css y docs/paleta_colores.md):
- Tipografías alojadas en web/vendor/fonts (Source Serif 4 para el texto, Source Sans 3 para títulos,
  tablas y notas; licencia OFL). WeasyPrint lee los woff2 directamente.
- Paleta: papel #faf7f0, tinta #1d1a16, tinta suave #5a5248, línea #ddd5c7, naranja #c4600a
  (filetes de las aperturas) y naranja texto #9a4a06 (enlaces y números).
- Portada: el mapa de la portada de la web (web/data/portada.webp: relieve, límites y contorno)
  con la densidad media de nidos (web/data/densidad.geojson) y el nido de Morga
  (web/data/nido_hilo.json), en la misma proyección en kilómetros que js/componentes/mapa_narrativo.js.
  Título y subtítulo de web/content/es.json (bloque «meta»). La imagen se incrusta en el HTML, sin
  ficheros intermedios.
- Índice con números de página (target-counter) a partir de los apartados «## » del markdown.

Lo que hay en el markdown antes del primer apartado («## ») no se imprime: es la cabecera para quien
lee el .md, y en el PDF la sustituye la portada. Los comentarios HTML (<!-- ... -->), que anotan de
dónde sale cada cifra, pasan al HTML pero no se imprimen.
"""
import base64
import html
import io
import json
import math
import re
import sys
from pathlib import Path

import markdown
from PIL import Image, ImageDraw
from weasyprint import HTML

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"
FUENTES = WEB / "vendor" / "fonts"
URL = "https://tresmilnidos.eus"
CONCURSO = "Reto de Periodismo de Datos Open Data Bizkaia 2026"
CATEGORIA = "Categoría: visualización de datos"

# Paleta (web/css/estilo.css)
PAPEL, TINTA, TINTA_SUAVE, LINEA = "#faf7f0", "#1d1a16", "#5a5248", "#ddd5c7"
ACENTO, ACENTO_TEXTO = "#c4600a", "#9a4a06"
RAMPA = ["#f6cf86", "#eba545", "#cf7414", "#9c4f08", "#5a2a05"]
OPACIDAD_MEDIA = 0.82  # capa «media» de la densidad en mapa_narrativo.js
# Proyección del mapa vivo y de la portada (mapa_narrativo.js, web_preparar_portada.py)
LON0, LAT0, KM_LON, KM_LAT = -2.9, 43.2, 111.32, 110.57
K = math.cos(math.radians(43.2))

# Imagen de portada: ancho de la página A4 a sangre y alto de la franja del mapa
PORTADA_MM = (210, 165)
PORTADA_PX = 2100  # ancho en píxeles (unos 250 ppp)
KM_ANCHO = 112.0   # kilómetros que caben a lo ancho (Bizkaia mide unos 84 km de oeste a este)


def a_km(lon: float, lat: float) -> tuple[float, float]:
    return (lon - LON0) * K * KM_LON, (lat - LAT0) * KM_LAT


def poligonos(geom: dict):
    """Anillos (exterior y huecos) de un Polygon o MultiPolygon de GeoJSON."""
    if geom["type"] == "Polygon":
        yield geom["coordinates"]
    elif geom["type"] == "MultiPolygon":
        yield from geom["coordinates"]


def imagen_portada() -> str:
    """Mapa de densidad de la portada de la web, a sangre, fundido con el papel por abajo.
    Solo Pillow: la imagen base (portada.webp) ya está en la proyección lineal en km, así que basta
    con recortarla y dibujar encima las bandas de densidad y el contorno. Devuelve un data URI JPEG."""
    datos = WEB / "data"
    por = json.loads((datos / "portada.json").read_text(encoding="utf-8"))
    o, s_, e, n = por["caja_imagen"]
    (rx0, ry0), (rx1, ry1) = a_km(o, s_), a_km(e, n)
    x0, y0, x1, y1 = por["caja_municipios"]
    cx, cy = a_km((x0 + x1) / 2, (y0 + y1) / 2)

    w_mm, h_mm = PORTADA_MM
    ss = 2  # se dibuja al doble y se reduce (bordes suaves)
    w_px = PORTADA_PX
    h_px = round(w_px * h_mm / w_mm)
    W, H = w_px * ss, h_px * ss
    km_alto = KM_ANCHO * h_mm / w_mm
    izq = cx - KM_ANCHO / 2
    aba = cy - km_alto * 0.60  # Bizkaia algo por encima del centro: abajo queda el fundido
    arr = aba + km_alto
    esc = W / KM_ANCHO  # píxeles por km

    def px(lon: float, lat: float) -> tuple[float, float]:
        x, y = a_km(lon, lat)
        return (x - izq) * esc, (arr - y) * esc

    base = Image.open(datos / "portada.webp").convert("RGB")
    bx = base.width / (rx1 - rx0)
    by = base.height / (ry1 - ry0)
    caja = ((izq - rx0) * bx, (ry1 - arr) * by, (izq + KM_ANCHO - rx0) * bx, (ry1 - aba) * by)
    lienzo = base.resize((W, H), Image.Resampling.LANCZOS, box=caja).convert("RGBA")

    dens = json.loads((datos / "densidad.geojson").read_text(encoding="utf-8"))
    for f in dens["features"]:
        if f["properties"]["capa"] != "media":
            continue
        mascara = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(mascara)
        for anillos in poligonos(f["geometry"]):
            d.polygon([px(*c) for c in anillos[0]], fill=255)
            for hueco in anillos[1:]:
                d.polygon([px(*c) for c in hueco], fill=0)
        capa = Image.new("RGBA", (W, H), RAMPA[min(int(f["properties"]["banda"]), 4)])
        capa.putalpha(mascara.point(lambda v: round(v * OPACIDAD_MEDIA)))
        lienzo = Image.alpha_composite(lienzo, capa)

    trazo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(trazo)
    cont = json.loads((datos / "contorno.geojson").read_text(encoding="utf-8"))
    for f in cont.get("features", [cont]):
        for anillos in poligonos(f["geometry"]):
            for anillo in anillos:
                d.line([px(*c) for c in anillo], fill=TINTA + "cc", width=round(2.4 * ss),
                       joint="curve")
    hilo = json.loads((datos / "nido_hilo.json").read_text(encoding="utf-8"))["nido"]
    hx, hy = px(hilo["lon"], hilo["lat"])
    u = W / 1200 * 0.75  # marcador con las proporciones de la imagen para compartir
    r_ext, r_int, r_pto = 14.25 * u, 11.75 * u, 5 * u
    d.ellipse([hx - r_ext, hy - r_ext, hx + r_ext, hy + r_ext], fill=TINTA)
    d.ellipse([hx - r_int, hy - r_int, hx + r_int, hy + r_int], fill=(0, 0, 0, 0))
    lienzo = Image.alpha_composite(lienzo, trazo)
    d = ImageDraw.Draw(lienzo)
    d.ellipse([hx - r_pto - 2 * u, hy - r_pto - 2 * u, hx + r_pto + 2 * u, hy + r_pto + 2 * u], fill=PAPEL)
    d.ellipse([hx - r_pto, hy - r_pto, hx + r_pto, hy + r_pto], fill=ACENTO)
    mapa = lienzo.convert("RGB").resize((w_px, h_px), Image.Resampling.LANCZOS)

    # Fundido con el papel en el último 22 % (como la franja de papel de las aperturas de la web)
    alto_fundido = int(h_px * 0.22)
    columna = Image.new("L", (1, h_px), 0)
    for k in range(alto_fundido):
        s = k / (alto_fundido - 1)
        columna.putpixel((0, h_px - alto_fundido + k), round(255 * s * s * (3 - 2 * s)))
    final = Image.composite(Image.new("RGB", mapa.size, PAPEL), mapa, columna.resize(mapa.size))
    b = io.BytesIO()
    final.save(b, "JPEG", quality=88, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode("ascii")


def css() -> str:
    caras = []
    for familia, fichero, peso, estilo in [
        ("Source Serif 4", "source-serif-4-latin-400-normal.woff2", 400, "normal"),
        ("Source Serif 4", "source-serif-4-latin-400-italic.woff2", 400, "italic"),
        ("Source Serif 4", "source-serif-4-latin-600-normal.woff2", 600, "normal"),
        ("Source Sans 3", "source-sans-3-latin-400-normal.woff2", 400, "normal"),
        ("Source Sans 3", "source-sans-3-latin-600-normal.woff2", 600, "normal"),
        ("Source Sans 3", "source-sans-3-latin-700-normal.woff2", 700, "normal"),
    ]:
        f = FUENTES / fichero
        if f.exists():
            caras.append(f"@font-face {{ font-family: '{familia}'; src: url('{f.as_uri()}'); "
                         f"font-weight: {peso}; font-style: {estilo}; }}")
    sans = "'Source Sans 3', sans-serif"
    return "\n".join(caras) + f"""
:root {{ --papel: {PAPEL}; --tinta: {TINTA}; --tinta-suave: {TINTA_SUAVE}; --linea: {LINEA};
         --acento: {ACENTO}; --acento-texto: {ACENTO_TEXTO}; }}
@page {{ size: A4; margin: 21mm 21mm 20mm 21mm; background: {PAPEL};
  @top-left {{ content: "Tres mil nidos al año"; font: 600 7.6pt {sans}; color: {TINTA};
              vertical-align: bottom; padding-bottom: 3mm; }}
  @top-right {{ content: "Memoria técnica"; font: 400 7.6pt {sans}; color: {TINTA_SUAVE};
               vertical-align: bottom; padding-bottom: 3mm; }}
  @bottom-left {{ content: "tresmilnidos.eus"; font: 400 7.6pt {sans}; color: {ACENTO_TEXTO};
                 vertical-align: top; padding-top: 3mm; }}
  @bottom-right {{ content: counter(page); font: 600 7.6pt {sans}; color: {TINTA};
                  vertical-align: top; padding-top: 3mm; }} }}
@page portada {{ margin: 0; background: {PAPEL};
  @top-left {{ content: none; }} @top-right {{ content: none; }}
  @bottom-left {{ content: none; }} @bottom-right {{ content: none; }} }}

html {{ font-family: 'Source Serif 4', serif; font-size: 9.5pt; line-height: 1.4; color: var(--tinta); }}
body {{ margin: 0; }}

/* Portada */
.portada {{ page: portada; height: 297mm; position: relative; break-after: page; }}
.portada img {{ display: block; width: 210mm; height: {PORTADA_MM[1]}mm; }}
.portada .texto {{ position: absolute; left: 21mm; right: 21mm; top: {PORTADA_MM[1] - 16}mm; }}
.portada .antetitulo {{ font: 600 8.5pt {sans}; letter-spacing: .14em; text-transform: uppercase;
                       color: var(--acento-texto); margin: 0 0 4mm; }}
.portada h1 {{ font: 600 44pt/1.02 'Source Serif 4', serif; letter-spacing: -.012em; margin: 0; }}
.portada .linea {{ width: 18mm; height: 1mm; background: var(--acento); margin: 7mm 0 6mm; }}
.portada .subtitulo {{ font: 400 16pt/1.32 'Source Serif 4', serif; color: var(--tinta); margin: 0;
                      max-width: 150mm; hyphens: none; }}
.portada .datos {{ position: absolute; left: 21mm; right: 21mm; bottom: 22mm; font: 400 9.5pt/1.5 {sans};
                  color: var(--tinta-suave); border-top: 0.6pt solid var(--linea); padding-top: 4mm; }}
.portada .datos p {{ margin: 0; }}
.portada .datos .autor {{ font-weight: 600; color: var(--tinta); font-size: 11pt; margin-bottom: 1mm; }}
.portada .datos a {{ color: var(--acento-texto); font-weight: 600; }}
.portada .pie-mapa {{ position: absolute; right: 21mm; top: {PORTADA_MM[1] - 22}mm; font: 400 7pt {sans};
                     color: var(--tinta-suave); text-align: right; }}

/* Índice */
.indice {{ break-after: avoid; margin: 0 0 6mm; }}
.indice h2 {{ margin-top: 0; }}
.indice ol {{ list-style: none; padding: 0; margin: 0; font: 400 9.5pt/1.25 {sans}; columns: 2; column-gap: 10mm; }}
.indice li {{ margin: 0; padding: 1.2mm 0; break-inside: avoid; border-bottom: 0.4pt solid var(--linea); }}
.indice a {{ color: var(--tinta); text-decoration: none; }}
.indice a .n {{ display: inline-block; width: 8mm; color: var(--acento-texto); font-weight: 600; }}
.indice a::after {{ content: leader(' ') target-counter(attr(href), page); font-weight: 600; }}

/* Títulos: misma jerarquía que las aperturas de la web (filete naranja, número en naranja) */
h2 {{ font: 700 14pt/1.2 {sans}; margin: 7mm 0 3mm; break-after: avoid; color: var(--tinta); }}
h2::before {{ content: ""; display: block; width: 14mm; height: 0.9mm; background: var(--acento);
             margin-bottom: 2.5mm; }}
h2 .n {{ color: var(--acento-texto); margin-right: 2.2mm; font-weight: 600; }}
p {{ margin: 0 0 2.2mm; hyphens: auto; orphans: 3; widows: 3; }}
strong {{ font-weight: 600; }}
ul {{ margin: 0 0 3mm; padding-left: 4.5mm; }}
li {{ margin-bottom: 1.1mm; hyphens: auto; }}
li::marker {{ color: var(--acento); }}
a {{ color: var(--acento-texto); text-decoration: none; hyphens: none; }}
code {{ font-family: 'DejaVu Sans Mono', monospace; font-size: 7.6pt; color: #3d362e; }}
pre {{ background: #f1ece1; border-left: 0.9mm solid var(--linea); padding: 3mm 4mm; margin: 2mm 0 4mm;
      font-size: 7.4pt; line-height: 1.45; white-space: pre-wrap; break-inside: avoid; }}
pre code {{ font-size: 7.4pt; color: var(--tinta); }}
table {{ border-collapse: collapse; width: 100%; margin: 2mm 0 5mm; font: 400 8.2pt/1.28 {sans}; }}
thead th {{ text-align: left; font-weight: 700; border-bottom: 1pt solid var(--tinta); padding: 1.3mm 1.8mm;
           background: #f1ece1; }}
td {{ vertical-align: top; border-bottom: 0.4pt solid var(--linea); padding: 1.1mm 1.8mm; }}
td strong {{ font-weight: 700; }}
tr {{ break-inside: avoid; }}
td a {{ overflow-wrap: anywhere; }}
td code {{ font-size: 7.2pt; }}
"""


def portada(meta: dict) -> str:
    e = html.escape
    return f"""<section class="portada">
<img src="{imagen_portada()}" alt="Mapa de densidad de los nidos de avispa asiática avisados en Bizkaia">
<p class="pie-mapa">Densidad media de nidos avisados por km² y año, 2019-2025.<br>
Datos: Open Data Bizkaia. Relieve: Copernicus GLO-90.</p>
<div class="texto">
<p class="antetitulo">Memoria técnica</p>
<h1>{e(meta['titulo'])}</h1>
<div class="linea"></div>
<p class="subtitulo">{e(meta['subtitulo'])}</p>
</div>
<div class="datos">
<p class="autor">{e(meta['autoria'])}</p>
<p>Memoria técnica · {CONCURSO} · {CATEGORIA}</p>
<p>{e(meta['fecha'])} · <a href="{URL}">{URL}</a></p>
</div>
</section>"""


def numerar_titulos(cuerpo: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Separa el número de los apartados («1. Texto») y devuelve el índice (id, número, texto)."""
    indice = []

    def sub(m: re.Match) -> str:
        ident, num, texto = m.group(1), m.group(2), m.group(3)
        indice.append((ident, num, texto))
        return f'<h2 id="{ident}"><span class="n">{num}</span>{texto}</h2>'

    cuerpo = re.sub(r'<h2 id="([^"]+)">(\d+)\.\s*(.*?)</h2>', sub, cuerpo)
    return cuerpo, indice


def main() -> None:
    entrada = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "memoria_tecnica.md"
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else entrada.with_suffix(".pdf")
    meta = json.loads((WEB / "content" / "es.json").read_text(encoding="utf-8"))["meta"]
    texto = entrada.read_text(encoding="utf-8")
    texto = texto[texto.index("\n## ") + 1:]  # la cabecera del .md la sustituye la portada
    cuerpo = markdown.markdown(texto, extensions=["tables", "fenced_code", "sane_lists", "toc"])
    cuerpo, indice = numerar_titulos(cuerpo)
    # Espacio de no separación entre la cifra y su unidad («16 %», «7 m», «IC 95 %»)
    cuerpo = re.sub(r"(\d) (%|km|m\b|€|euros\b|días\b|nidos\b)", "\\1\u00a0\\2", cuerpo)
    filas = "".join(f'<li><a href="#{i}"><span class="n">{n}</span>{t}</a></li>' for i, n, t in indice)
    html_indice = f'<nav class="indice"><h2>Índice</h2><ol>{filas}</ol></nav>'
    doc_html = (f"<!doctype html><html lang='es'><head><meta charset='utf-8'>"
                f"<title>{html.escape(meta['titulo'])}. Memoria técnica</title>"
                f"<meta name='author' content='{html.escape(meta['autoria'])}'>"
                f"<meta name='description' content='{html.escape(meta['subtitulo'])}'>"
                f"<style>{css()}</style></head>"
                f"<body>{portada(meta)}{html_indice}{cuerpo}</body></html>")
    doc = HTML(string=doc_html, base_url=str(RAIZ)).render()
    doc.write_pdf(salida)
    print(f"{salida} ({len(doc.pages)} páginas, {salida.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
