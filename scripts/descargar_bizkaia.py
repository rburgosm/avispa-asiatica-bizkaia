"""Descarga los CSV de uno o varios conjuntos de Open Data Bizkaia.

Uso: descargar_bizkaia.py <carpeta_destino_raiz> <slug> [<slug> ...] [--patron REGEX]

Cada conjunto se guarda en <raiz>/<slug>/<nombre>.csv. Los enlaces se sacan del
HTML de la ficha (https://www.opendatabizkaia.eus/es/catalogo/<slug>).

Excepciones (DESTINOS), para que los ficheros queden donde los leen los análisis:
- avispa-asiatica -> <raiz>/avispa_asiatica/nidos.csv (recurso «datos-nidos-avispa-asiatica»).
- intervenciones-speis -> <raiz>/speis/intervenciones-speis-AAAA.csv.
Con --literal se guarda todo como <raiz>/<slug>/<nombre>.csv, sin excepciones.
Si el fichero ya existe, no se vuelve a bajar (--forzar para bajarlo de nuevo).
"""
import argparse
import re
import time
import urllib.request
from pathlib import Path

BASE = "https://www.opendatabizkaia.eus"
# slug -> (carpeta, {nombre del recurso: nombre del fichero sin .csv})
DESTINOS = {
    "avispa-asiatica": ("avispa_asiatica", {"datos-nidos-avispa-asiatica": "nidos"}),
    "intervenciones-speis": ("speis", {}),
}


def get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (investigacion datos abiertos)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raiz")
    ap.add_argument("slugs", nargs="+")
    ap.add_argument("--patron", default=None, help="regex sobre el nombre del recurso")
    ap.add_argument("--literal", action="store_true", help="sin las excepciones de DESTINOS")
    ap.add_argument("--forzar", action="store_true", help="vuelve a bajar aunque el fichero exista")
    a = ap.parse_args()
    for slug in a.slugs:
        html = get(f"{BASE}/es/catalogo/{slug}").decode("utf-8", "replace")
        enlaces = sorted(set(re.findall(r"/es/dump/([0-9a-f-]+)/([^\"?/]+)\?format=csv", html)))
        carpeta, renombrar = (slug, {}) if a.literal else DESTINOS.get(slug, (slug, {}))
        dest = Path(a.raiz) / carpeta
        dest.mkdir(parents=True, exist_ok=True)
        n = 0
        for rid, nombre in enlaces:
            if a.patron and not re.search(a.patron, nombre):
                continue
            f = dest / f"{renombrar.get(nombre, nombre)}.csv"
            if f.exists() and f.stat().st_size > 0 and not a.forzar:
                continue
            try:
                f.write_bytes(get(f"{BASE}/es/dump/{rid}/{nombre}?format=csv"))
                n += 1
            except Exception as e:  # noqa: BLE001
                print(f"ERROR {slug}/{nombre}: {e}")
            time.sleep(0.3)
        print(f"{slug}: {len(enlaces)} recursos, {n} descargados")


if __name__ == "__main__":
    main()
