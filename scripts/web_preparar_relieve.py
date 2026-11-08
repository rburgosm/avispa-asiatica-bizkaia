"""Relieve sombreado (hillshade) de Bizkaia para el fondo de los mapas de la narración.

Uso:
    python -I scripts/web_preparar_relieve.py [carpeta_web_data]

Fuente: Copernicus DEM GLO-90 (modelo digital de superficie de 90 m; © DLR e.V. 2010-2014 y
© Airbus Defence and Space GmbH 2014-2018, distribuido por el programa Copernicus de la UE y la
ESA con licencia de uso libre con atribución), teselas de 1° x 1° del registro público en AWS
(https://copernicus-dem-90m.s3.amazonaws.com). Se descargan a data/raw/copernicus_dem/.

Proceso (numpy y Pillow): mosaico de las cuatro teselas que cubren el recorte, sombreado con la
fórmula clásica (luz del noroeste, azimut 315°, altura 45°; pendientes con numpy.gradient y el
paso de la rejilla pasado a metros), exageración vertical moderada y color con la paleta: la tierra
en el tono del papel oscurecida suavemente por la sombra y el mar transparente (el SVG pone el
color del mar). Se recorta a la caja de la vista de la narración y se guarda en WebP.

La rejilla está en grados (EPSG:4326). La web dibuja los mapas de la narración con una proyección
cilíndrica equidistante con el paralelo de 43,2° como estándar (x = λ·cos 43,2°, y = φ): con ella
la imagen encaja como un rectángulo sin reproyectar. Salida: web/data/relieve.webp y relieve.json
(caja en grados, tamaño, fuente).
"""
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
URL = ("https://copernicus-dem-90m.s3.amazonaws.com/Copernicus_DSM_COG_30_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
       "Copernicus_DSM_COG_30_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif")
TESELAS = [(42, 5), (42, 4), (42, 3), (42, 2), (43, 5), (43, 4), (43, 3), (43, 2)]  # (latitud sur, longitud oeste) de cada tesela 1°x1°
CAJA = (-4.70, 42.45, -1.40, 43.85)  # oeste, sur, este, norte: Bizkaia con mucho margen (pantallas anchas y móviles)
AZIMUT, ALTURA, EXAGERACION = 315, 45, 2.0
TIERRA = (245, 241, 232)      # --mapa-tierra
SOMBRA = (120, 108, 92)       # tono cálido de la sombra (tinta suave aclarada)
INTENSIDAD = 0.42             # cuánto oscurece la sombra como máximo
ANCHO_MAX = 2200


def tesela(lat: int, lon: int, carpeta: Path) -> np.ndarray:
    destino = carpeta / f"N{lat}_W{lon:03d}.tif"
    if not destino.exists():
        req = urllib.request.Request(URL.format(ns="N", lat=lat, ew="W", lon=lon), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            destino.write_bytes(r.read())
    a = np.array(Image.open(destino), dtype=np.float32)
    if a.shape != (1200, 1200):
        raise SystemExit(f"Tamaño inesperado de la tesela {destino.name}: {a.shape}")
    return a


def main() -> None:
    web = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "web/data"
    carpeta = RAIZ / "data/raw/copernicus_dem"
    carpeta.mkdir(parents=True, exist_ok=True)
    # Mosaico: 4 x 2 teselas, de -5° a -1° de longitud y de 42° a 44° de latitud (fila 0 = norte)
    norte = np.hstack([tesela(43, w, carpeta) for w in (5, 4, 3, 2)])
    sur = np.hstack([tesela(42, w, carpeta) for w in (5, 4, 3, 2)])
    z = np.vstack([norte, sur])
    paso = 1 / 1200  # grados por celda (GLO-90 a esta latitud: 3" x 3")
    lon0, lat1 = -5.0, 44.0
    c0, c1 = int((CAJA[0] - lon0) / paso), int((CAJA[2] - lon0) / paso)
    f0, f1 = int((lat1 - CAJA[3]) / paso), int((lat1 - CAJA[1]) / paso)
    z = z[f0:f1, c0:c1]
    mar = z <= 0.5
    lat_media = np.radians((CAJA[1] + CAJA[3]) / 2)
    dx = paso * 111_320 * np.cos(lat_media)
    dy = paso * 110_574
    gy, gx = np.gradient(z * EXAGERACION, dy, dx)
    pendiente = np.arctan(np.hypot(gx, gy))
    aspecto = np.arctan2(-gx, gy)  # filas hacia el sur: gy positivo = baja hacia el norte
    az, alt = np.radians(360 - AZIMUT + 90), np.radians(ALTURA)
    sombra = np.sin(alt) * np.cos(pendiente) + np.cos(alt) * np.sin(pendiente) * np.cos(az - aspecto)
    sombra = np.clip(sombra, 0, 1)
    plano = np.sin(alt)  # valor de un terreno llano: no se oscurece
    osc = np.clip((plano - sombra) / plano, 0, 1) * INTENSIDAD  # solo las laderas en sombra
    luz = np.clip((sombra - plano) / (1 - plano), 0, 1) * 0.25  # laderas al sol, algo más claras
    rgb = np.zeros(z.shape + (4,), dtype=np.float32)
    for k in range(3):
        base = TIERRA[k] * (1 - osc) + SOMBRA[k] * osc
        rgb[..., k] = base + (255 - base) * luz
    rgb[..., 3] = np.where(mar, 0, 255)
    img = Image.fromarray(rgb.clip(0, 255).astype(np.uint8), "RGBA")
    if img.width > ANCHO_MAX:
        img = img.resize((ANCHO_MAX, round(img.height * ANCHO_MAX / img.width)), Image.LANCZOS)
    img.save(web / "relieve.webp", "WEBP", quality=60, method=6)
    meta = {"caja": CAJA, "ancho": img.width, "alto": img.height, "fuente": "Copernicus DEM GLO-90 (© DLR e.V., © Airbus Defence and Space GmbH; programa Copernicus de la UE y la ESA)",
            "sombreado": {"azimut": AZIMUT, "altura": ALTURA, "exageracion": EXAGERACION}}
    (web / "relieve.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"relieve.webp: {img.width}x{img.height}, {(web / 'relieve.webp').stat().st_size / 1024:.0f} KB; "
          f"cotas {z.min():.0f}-{z.max():.0f} m")


if __name__ == "__main__":
    main()
