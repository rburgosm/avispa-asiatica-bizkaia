"""Extrae texto de las fuentes descargadas para la cronología de políticas de avispa asiática.

Uso: python -I scripts/avispa_politicas_textos.py data/raw/externos/politicas_avispa [patron_regex]
Para cada HTML o PDF de la carpeta escribe <fichero>.txt (texto plano) y, si se da un
patrón, imprime los fragmentos que lo contienen (máximo 8 por fichero).
"""
import html
import re
import subprocess
import sys
from pathlib import Path


def texto_html(ruta: Path) -> str:
    t = ruta.read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def texto_pdf(ruta: Path) -> str:
    # pdftotext (poppler, software libre) conserva el orden de lectura
    salida = subprocess.run(["pdftotext", "-layout", str(ruta), "-"],
                            capture_output=True, text=True, check=True).stdout
    return re.sub(r"[ \t]+", " ", salida)


def main() -> None:
    carpeta = Path(sys.argv[1])
    patron = re.compile(sys.argv[2], re.I) if len(sys.argv) > 2 else None
    for ruta in sorted(carpeta.iterdir()):
        if ruta.suffix.lower() not in {".html", ".pdf"}:
            continue
        t = texto_pdf(ruta) if ruta.suffix.lower() == ".pdf" else texto_html(ruta)
        ruta.with_suffix(ruta.suffix + ".txt").write_text(t, encoding="utf-8")
        if patron:
            plano = re.sub(r"\s+", " ", t)
            trozos = [plano[max(0, m.start() - 220): m.end() + 220]
                      for m in patron.finditer(plano)][:8]
            print(f"== {ruta.name} ({len(trozos)} fragmentos)")
            for tr in trozos:
                print("  -", tr)


if __name__ == "__main__":
    main()
