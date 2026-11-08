"""Copia las tipografías de la web (Source Serif 4 y Source Sans 3) a web/vendor/fonts/.

Uso:
    python -I scripts/web_descargar_fuentes.py

Las dos familias son de Adobe con licencia SIL Open Font License 1.1 (OFL), que permite
alojarlas y redistribuirlas junto a la web si se acompaña la licencia. Se descargan los
ficheros woff2 del subconjunto «latin» (incluye las letras del castellano y del euskera)
de los paquetes de npm de Fontsource, con versión fija, desde jsDelivr. Así la web no
llama a Google Fonts ni a ningún otro servidor al abrirse.

Escribe en web/vendor/fonts/: los .woff2, LICENCIA-source-serif-4.txt,
LICENCIA-source-sans-3.txt y VERSIONES.txt (origen y SHA-256 de cada fichero).
"""
import hashlib
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CDN = "https://cdn.jsdelivr.net/npm/"
VERSION = "5.2.5"  # misma versión para las dos familias
FAMILIAS = {
    # paquete: [(peso, estilo), ...]
    "source-serif-4": [(400, "normal"), (400, "italic"), (600, "normal")],
    "source-sans-3": [(400, "normal"), (600, "normal"), (700, "normal")],
}


def bajar(ruta: str) -> bytes:
    req = urllib.request.Request(CDN + ruta, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> None:
    destino = RAIZ / "web" / "vendor" / "fonts"
    destino.mkdir(parents=True, exist_ok=True)
    lineas = []
    for familia, variantes in FAMILIAS.items():
        paquete = f"@fontsource/{familia}@{VERSION}"
        ficheros = {f"LICENCIA-{familia}.txt": f"{paquete}/LICENSE"}
        for peso, estilo in variantes:
            nombre = f"{familia}-latin-{peso}-{estilo}.woff2"
            ficheros[nombre] = f"{paquete}/files/{nombre}"
        for nombre, ruta in ficheros.items():
            datos = bajar(ruta)
            (destino / nombre).write_bytes(datos)
            lineas.append(f"{nombre}\t{ruta}\t{hashlib.sha256(datos).hexdigest()}")
            print(f"{nombre}: {len(datos) / 1024:.0f} KB")
    (destino / "VERSIONES.txt").write_text("fichero\torigen (npm)\tsha256\n" + "\n".join(lineas) + "\n",
                                          encoding="utf-8")


if __name__ == "__main__":
    main()
