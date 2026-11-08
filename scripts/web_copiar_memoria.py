"""Copia la memoria técnica en PDF a la web, para enlazarla desde la página de metodología.

Uso (después de scripts/memoria_pdf.py, que genera docs/memoria_tecnica.pdf):
    python -I scripts/web_copiar_memoria.py [origen.pdf] [destino.pdf]

Por defecto copia docs/memoria_tecnica.pdf en web/memoria_tecnica.pdf. Avisa si el PDF es más
antiguo que docs/memoria_tecnica.md (habría que regenerarlo antes con memoria_pdf.py).
"""
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
origen = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs/memoria_tecnica.pdf"
destino = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "web/memoria_tecnica.pdf"

if not origen.exists():
    sys.exit(f"No existe {origen}: genérala antes con scripts/memoria_pdf.py")
md = origen.with_suffix(".md")
if md.exists() and md.stat().st_mtime > origen.stat().st_mtime + 1:
    print(f"Aviso: {md.name} es más reciente que {origen.name}; regenera el PDF con scripts/memoria_pdf.py")
shutil.copy2(origen, destino)
print(f"Copiada {origen.relative_to(RAIZ)} -> {destino.relative_to(RAIZ)} ({destino.stat().st_size:,} bytes)".replace(",", "."))
