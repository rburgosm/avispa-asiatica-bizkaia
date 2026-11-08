"""Genera docs/memoria_tecnica.pdf a partir de docs/memoria_tecnica.md.

Uso:
    .venv/bin/python -I scripts/memoria_pdf.py [entrada.md] [salida.pdf]

Herramientas libres: Python-Markdown (licencia BSD) para pasar el markdown a HTML y WeasyPrint
(licencia BSD) para maquetar el HTML en PDF. Se instalan en el entorno propio del proyecto:
    python3 -m venv .venv && .venv/bin/pip install markdown weasyprint
(WeasyPrint necesita Pango, que traen las distribuciones Linux habituales.)

Los comentarios HTML del markdown (<!-- ... -->), que anotan de dónde sale cada cifra, pasan al
HTML pero no se imprimen. La tipografía es la de la web (Source Serif 4 y Source Sans 3, OFL),
leída de web/vendor/fonts/ si existe; si no, se usa la serif del sistema.
"""
import sys
from pathlib import Path

import markdown
from weasyprint import HTML

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "web" / "vendor" / "fonts"


def css() -> str:
    caras = []
    for familia, fichero, peso, estilo in [
        ("Source Serif 4", "source-serif-4-latin-400-normal.woff2", 400, "normal"),
        ("Source Serif 4", "source-serif-4-latin-400-italic.woff2", 400, "italic"),
        ("Source Serif 4", "source-serif-4-latin-600-normal.woff2", 600, "normal"),
        ("Source Sans 3", "source-sans-3-latin-400-normal.woff2", 400, "normal"),
        ("Source Sans 3", "source-sans-3-latin-600-normal.woff2", 600, "normal"),
    ]:
        f = FUENTES / fichero
        if f.exists():
            caras.append(f"@font-face {{ font-family: '{familia}'; src: url('{f.as_uri()}'); "
                         f"font-weight: {peso}; font-style: {estilo}; }}")
    return "\n".join(caras) + """
@page { size: A4; margin: 20mm 19mm 20mm 19mm;
        @bottom-center { content: counter(page) " / " counter(pages);
                         font: 8pt 'Source Sans 3', sans-serif; color: #666; }
        @bottom-left { content: "Tres mil nidos al año · Memoria técnica";
                       font: 8pt 'Source Sans 3', sans-serif; color: #666; } }
html { font-family: 'Source Serif 4', serif; font-size: 9.8pt; line-height: 1.38; color: #1a1a1a; }
h1 { font-family: 'Source Sans 3', sans-serif; font-size: 21pt; margin: 0 0 2pt; font-weight: 600; }
h1 + p strong { font-size: 12pt; font-weight: 400; font-style: italic; }
h2 { font-family: 'Source Sans 3', sans-serif; font-size: 12.5pt; font-weight: 600;
     margin: 13pt 0 4pt; padding-bottom: 2pt; border-bottom: 0.6pt solid #b8860b;
     break-after: avoid; }
p { margin: 0 0 5pt; text-align: left; hyphens: auto; }
ul { margin: 0 0 6pt; padding-left: 13pt; }
li { margin-bottom: 2.5pt; }
a { color: #6b4e00; text-decoration: none; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8pt; }
pre { background: #f5f2ea; padding: 6pt 8pt; font-size: 7.2pt; line-height: 1.3;
      white-space: pre-wrap; word-break: break-all; break-inside: auto; }
pre code { font-size: 7.2pt; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt; font-family: 'Source Sans 3', sans-serif;
        font-size: 8.3pt; line-height: 1.28; }
th { text-align: left; font-weight: 600; border-bottom: 0.8pt solid #333; padding: 3pt 4pt; }
td { vertical-align: top; border-bottom: 0.4pt solid #ddd; padding: 2.5pt 4pt; }
tr { break-inside: avoid; }
"""


def main() -> None:
    entrada = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "memoria_tecnica.md"
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else entrada.with_suffix(".pdf")
    cuerpo = markdown.markdown(entrada.read_text(encoding="utf-8"),
                               extensions=["tables", "fenced_code", "sane_lists"])
    html = (f"<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            f"<title>Tres mil nidos al año. Memoria técnica</title>"
            f"<meta name='author' content='Roberto Burgos'><style>{css()}</style></head>"
            f"<body>{cuerpo}</body></html>")
    doc = HTML(string=html, base_url=str(RAIZ)).render()
    doc.write_pdf(salida)
    print(f"{salida} ({len(doc.pages)} páginas, {salida.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
