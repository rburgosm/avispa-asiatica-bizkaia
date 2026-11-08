"""Genera docs/proyecto_tresmilnidos.pdf: el documento que se sube en el campo «Proyecto» de la
solicitud del Reto de Periodismo de Datos Open Data Bizkaia 2026. Presenta la web
https://tresmilnidos.eus (portada con enlace y código QR, cómo verla y capturas comentadas).

Uso:
    .venv/bin/python -I scripts/proyecto_pdf.py [carpeta_capturas] [salida.pdf]

Requisitos: las capturas de scripts/proyecto_capturas.py (docs/capturas_proyecto/*.png) y, en el
.venv de la raíz, markdown, weasyprint y segno (QR, licencia BSD): `.venv/bin/pip install segno`.
Reutiliza la identidad visual y la portada de scripts/memoria_pdf.py. Los pies de las capturas solo
citan cifras que están en los textos de la web (web/content/es.json).
"""
import base64
import html
import io
import json
import sys
from pathlib import Path

import segno
from PIL import Image
from weasyprint import HTML

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memoria_pdf as m  # noqa: E402

RAIZ = m.RAIZ
CAPTURAS = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "capturas_proyecto"
SALIDA = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "docs" / "proyecto_tresmilnidos.pdf"
URL = m.URL
ENLACES = [
    ("La pieza", URL, "La historia completa, con los gráficos interactivos y el buscador por municipio."),
    ("Metodología", URL + "/metodologia.html", "Fuentes, limpieza de los datos, modelos y limitaciones, en lenguaje llano."),
    ("Memoria técnica", URL + "/memoria_tecnica.pdf", "Conjuntos de datos usados, proceso completo y herramientas (base 6 del reto)."),
    ("Código", "https://github.com/rburgosm/avispa-asiatica-bizkaia", "Scripts de Python que reproducen todo, de la descarga de los datos a la web."),
]
# (fichero, título, pie). Cifras: solo las de web/content/es.json.
FIGURAS = [
    ("01_portada", "Portada",
     "La pieza se abre con el mapa de Bizkaia sobre el relieve, el título y la pregunta que responde. Después, "
     "la historia se ordena en seis paradas, cada una con una pregunta, y un índice lateral permite saltar entre ellas."),
    ("02_mapa_contador", "Siete temporadas de avisos sobre el mapa",
     "Al bajar, los nidos aparecen temporada a temporada sobre el mapa, con la mancha de concentración y "
     "un contador de años. El círculo marca el nido de Morga que abre la historia; 2025 cerró con 3.222 avisos, "
     "el máximo desde 2019."),
    ("04_estimacion", "Dibuja tu estimación",
     "Antes de ver los datos, quien lee marca cuántos nidos cree que se avisaron. Después aparece la serie "
     "real con la tendencia y su banda de confianza del 95 %."),
    ("05_rapidez", "La rapidez de la retirada",
     "Cuánto se tarda en retirar un nido desde el aviso: la mitad se retira en dos días o menos, y alrededor "
     "de nueve de cada diez en una semana."),
    ("06_calendario", "El calendario, frente a Asturias",
     "Reparto de los avisos por meses en Bizkaia, comparado con Asturias. Solo uno de cada diez avisos "
     "llega en primavera, cuando los nidos son pequeños y bajos."),
    ("07_comarcas", "El mapa de comarcas",
     "Por habitante, el mapa se invierte: en Arratia-Nervión se avisa de unos 9 nidos al año por cada "
     "1.000 vecinos; en Gran Bilbao, de menos de 2."),
    ("08_buscador", "¿Y en tu municipio?",
     "Al final, un buscador muestra para cada municipio los nidos avisados cada año, la tasa por 1.000 "
     "habitantes, la comparación con su comarca y los días hasta la retirada."),
]


def data_uri(png: Path, ancho: int = 1440) -> str:
    im = Image.open(png).convert("RGB")
    if im.width > ancho:
        im = im.resize((ancho, round(im.height * ancho / im.width)), Image.Resampling.LANCZOS)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=84, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode("ascii")


def qr_svg() -> str:
    qr = segno.make(URL, error="m")
    b = io.BytesIO()
    qr.save(b, kind="svg", scale=10, border=0, dark=m.TINTA, light=None, xmldecl=False, svgns=True)
    return "data:image/svg+xml;base64," + base64.b64encode(b.getvalue()).decode("ascii")


def css() -> str:
    sans = "'Source Sans 3', sans-serif"
    return m.css().replace('content: "Memoria técnica"', 'content: "Proyecto"') + f"""
.portada .texto {{ top: {m.PORTADA_MM[1] - 22}mm; }}
.portada h1 {{ font-size: 40pt; }}
.portada .linea {{ margin: 5mm 0 4.5mm; }}
.portada .subtitulo {{ font-size: 15pt; }}
.portada .acceso {{ position: absolute; left: 21mm; right: 21mm; bottom: 38mm; display: flex;
                   align-items: center; gap: 7mm; }}
.portada .acceso img {{ width: 30mm; height: 30mm; }}
.portada .acceso .url {{ font: 700 25pt/1.1 {sans}; color: var(--acento-texto); text-decoration: none; }}
.portada .acceso .nota {{ font: 400 9.5pt/1.4 {sans}; color: var(--tinta-suave); margin: 1.5mm 0 0; }}
.portada .datos {{ bottom: 16mm; }}
.enlaces {{ list-style: none; padding: 0; margin: 3mm 0 6mm; font: 400 9.5pt/1.35 {sans}; }}
.enlaces li {{ border-bottom: 0.4pt solid var(--linea); padding: 2.2mm 0; margin: 0; }}
.enlaces b {{ display: inline-block; width: 32mm; font-weight: 700; }}
.enlaces a {{ font-weight: 600; }}
.enlaces .d {{ display: block; margin-left: 32mm; color: var(--tinta-suave); }}
figure {{ margin: 0 0 6mm; break-inside: avoid; }}
figure img {{ display: block; width: 100%; border: 0.5pt solid var(--linea); }}
figcaption {{ font: 400 8.6pt/1.38 {sans}; color: var(--tinta-suave); margin-top: 2mm; hyphens: none; }}
figcaption b {{ color: var(--tinta); font-weight: 700; }}
figcaption .n {{ color: var(--acento-texto); font-weight: 700; margin-right: 1.5mm; }}
.salto {{ break-before: page; }}
"""


def portada(meta: dict) -> str:
    e = html.escape
    return f"""<section class="portada">
<img src="{m.imagen_portada()}" alt="Mapa de densidad de los nidos de avispa asiática avisados en Bizkaia">
<div class="texto">
<p class="antetitulo">Proyecto · Visualización de datos</p>
<h1>{e(meta['titulo'])}</h1>
<div class="linea"></div>
<p class="subtitulo">{e(meta['subtitulo'])}</p>
</div>
<div class="acceso">
<img src="{qr_svg()}" alt="Código QR con el enlace a {URL}">
<div><a class="url" href="{URL}">tresmilnidos.eus</a>
<p class="nota">Web interactiva. Se recorre con el scroll, en ordenador o en móvil.</p></div>
</div>
<div class="datos">
<p class="autor">{e(meta['autoria'])}</p>
<p>Proyecto · {m.CONCURSO} · {m.CATEGORIA}</p>
<p>{e(meta['fecha'])} · <a href="{URL}">{URL}</a></p>
</div>
</section>"""


def figura(i: int, fichero: str, titulo: str, pie: str) -> str:
    return (f'<figure><img src="{data_uri(CAPTURAS / (fichero + ".png"))}" alt="{html.escape(titulo)}">'
            f'<figcaption><span class="n">{i}</span><b>{html.escape(titulo)}{"" if titulo[-1] in "?!" else "."}</b> {html.escape(pie)}</figcaption></figure>')


def main() -> None:
    meta = json.loads((m.WEB / "content" / "es.json").read_text(encoding="utf-8"))["meta"]
    filas = "".join(f'<li><b>{t}</b><a href="{u}">{u.replace("https://", "")}</a><span class="d">{d}</span></li>'
                    for t, u, d in ENLACES)
    como = f"""<h2>Cómo ver el proyecto</h2>
<p>El proyecto es una <strong>web interactiva</strong> publicada en <a href="{URL}">{URL}</a>. Es una pieza de
<em>scrollytelling</em>: se lee bajando con el scroll (rueda del ratón, teclado o dedo), y a medida que avanza el
texto los mapas y los gráficos cambian para mostrar lo que se cuenta. Funciona en ordenador y en móvil, en
cualquier navegador actual, sin instalar nada. Cada gráfico tiene su tabla de datos y su descripción para
lectores de pantalla.</p>
<p>La pieza responde a una pregunta: qué consigue Bizkaia retirando cada año miles de nidos de avispa asiática,
y qué no. Se apoya en el registro de nidos de Open Data Bizkaia (2019-2025), cruzado con otras fuentes públicas.</p>
<ul class="enlaces">{filas}</ul>
<p>Este documento resume la web con capturas de la versión publicada (escritorio, 1440×900). No sustituye a la
pieza: las animaciones, la estimación interactiva y el buscador solo se pueden ver en la web.</p>"""
    figs = [figura(i + 1, *f) for i, f in enumerate(FIGURAS)]
    cuerpo = (como + figs[0] + '<div class="salto"></div>' + figs[1] + figs[2]
              + '<div class="salto"></div>' + figs[3] + figs[4]
              + '<div class="salto"></div>' + figs[5] + figs[6])
    doc_html = (f"<!doctype html><html lang='es'><head><meta charset='utf-8'>"
                f"<title>{html.escape(meta['titulo'])}. Proyecto</title>"
                f"<meta name='author' content='{html.escape(meta['autoria'])}'>"
                f"<meta name='description' content='{html.escape(meta['subtitulo'])}'>"
                f"<style>{css()}</style></head><body>{portada(meta)}{cuerpo}</body></html>")
    doc = HTML(string=doc_html, base_url=str(RAIZ)).render()
    doc.write_pdf(SALIDA)
    print(f"{SALIDA} ({len(doc.pages)} páginas, {SALIDA.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
