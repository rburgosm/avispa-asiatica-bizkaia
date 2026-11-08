"""Imagen estática y ligera del mapa de la portada (web/data/portada.webp), para la primera pintura.

Uso (después de web_preparar_relieve.py):
    python -I scripts/web_preparar_portada.py [carpeta_web_data]

Se ve al instante, antes de que carguen los datos y D3; después el mapa vivo aparece encima con
un fundido. Para que el relevo no se note, la imagen es el mismo mapa a sangre que pinta
js/componentes/mapa_narrativo.js en su primer fotograma: la misma proyección en kilómetros
(x = (λ + 2,9)·cos 43,2°·111,32; y = −(φ − 43,2)·110,57), la misma extensión (la caja entera del
relieve sombreado), el relieve, los límites municipales y el contorno (los nidos y la densidad se
encienden después, ya en el mapa vivo).

La imagen se coloca con CSS (bloque «mapa (ronda 2)» de web/css/estilo.css) con la misma
cuenta que la cámara de la portada: la caja de los municipios encajada en la pantalla con sus
márgenes. Este script escribe esas constantes en el CSS y en el CSS crítico en línea de index.html
(entre los marcadores portada:auto) y en portada.json. Matplotlib y Pillow.
"""
import io
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
K = np.cos(np.radians(43.2))
MAR, TINTA, TINTA_SUAVE = "#dfe5e8", "#1d1a16", "#5a5248"
ANCHO_PX = 2000
LON0, LAT0, KM_LON, KM_LAT = -2.9, 43.2, 111.32, 110.57  # js/componentes/mapa_narrativo.js
MARCA_INI, MARCA_FIN = "/* portada:auto */", "/* /portada:auto */"


def main() -> None:
    web = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "web/data"
    m = gpd.read_file(web / "municipios.geojson")
    rel = json.loads((web / "relieve.json").read_text(encoding="utf-8"))
    cont = gpd.read_file(web / "contorno.geojson")

    def km(g):  # misma proyección que mapa_narrativo.js (y hacia arriba; la pantalla la invierte)
        return g.set_crs("EPSG:4326", allow_override=True).affine_transform(
            [K * KM_LON, 0, 0, KM_LAT, -LON0 * K * KM_LON, -LAT0 * KM_LAT])

    o, s_, e, n = rel["caja"]
    rx0, rx1 = (o - LON0) * K * KM_LON, (e - LON0) * K * KM_LON
    ry0, ry1 = (s_ - LAT0) * KM_LAT, (n - LAT0) * KM_LAT
    alto_px = round(ANCHO_PX * (ry1 - ry0) / (rx1 - rx0))
    fig = plt.figure(figsize=(ANCHO_PX / 100, alto_px / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(MAR)
    ax.axis("off")
    ax.imshow(np.asarray(Image.open(web / "relieve.webp").convert("RGBA")), extent=[rx0, rx1, ry0, ry1],
              interpolation="bilinear", zorder=0, aspect="auto")
    # Grosores del mapa vivo (0,6 y 1,3 px) a la escala típica de escritorio (imagen ampliada ~1,3 veces)
    km(m.boundary).plot(ax=ax, color=TINTA_SUAVE, linewidth=0.35, alpha=0.4, zorder=2)
    km(cont.boundary).plot(ax=ax, color=TINTA, linewidth=0.75, alpha=0.75, zorder=3)
    ax.set_xlim(rx0, rx1)  # geopandas e imshow cambian los límites y la proporción: se fijan al final
    ax.set_ylim(ry0, ry1)
    ax.set_aspect("auto")
    ax.set_position([0, 0, 1, 1])
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor=MAR)
    plt.close(fig)
    img = Image.open(buf).convert("RGB")
    img.save(web / "portada.webp", "WEBP", quality=72, method=6)

    # Constantes de colocación (km): caja de los municipios y su centro respecto a la esquina
    # superior izquierda de la imagen (la del relieve)
    x0, y0, x1, y1 = m.total_bounds
    mx0, mx1 = (x0 - LON0) * K * KM_LON, (x1 - LON0) * K * KM_LON
    my0, my1 = -(y1 - LAT0) * KM_LAT, -(y0 - LAT0) * KM_LAT  # en pantalla (y hacia abajo)
    top = -ry1
    c = {"w": mx1 - mx0, "h": my1 - my0, "a": (mx0 + mx1) / 2 - rx0, "b": (my0 + my1) / 2 - top,
         "rw": rx1 - rx0, "rh": ry1 - ry0}
    c = {k: round(float(v), 3) for k, v in c.items()}
    (web / "portada.json").write_text(json.dumps({"caja_municipios": [round(float(v), 5) for v in (x0, y0, x1, y1)],
                                                  "caja_imagen": rel["caja"], "km": c,
                                                  "ancho": img.width, "alto": img.height}), encoding="utf-8")
    # Las constantes van en la hoja de estilos y en el CSS crítico en línea de index.html (bloque
    # .portada-mapa), los dos entre los marcadores portada:auto
    linea = " ".join(f"--pm-{k}: {v};" for k, v in c.items())
    for f, sep in ((web.parent / "css/estilo.css", "\n  "), (web.parent / "index.html", " ")):
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8")
        a, b = t.find(MARCA_INI), t.find(MARCA_FIN)
        if a >= 0 and b > a:
            nuevo = t[:a + len(MARCA_INI)] + f"{sep}{linea}{sep}" + t[b:]
            if nuevo != t:
                f.write_text(nuevo, encoding="utf-8")
                print(f"{f.name}: constantes de la portada actualizadas")
        else:
            print(f"AVISO: {f.name} no tiene los marcadores portada:auto")
    print(f"portada.webp: {img.width}x{img.height}, {(web / 'portada.webp').stat().st_size / 1024:.0f} KB; {c}")


if __name__ == "__main__":
    main()
