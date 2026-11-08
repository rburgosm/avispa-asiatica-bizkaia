"""Comprueba en el móvil que cada pantalla de scroll cambia algo respecto a la anterior.

Uso (con la web servida):
    python scripts/web_probar_pantallas.py <carpeta_capturas> [url_base] [ancho] [alto]

Baja de pantalla en pantalla (por defecto 390 x 844, con animaciones), espera a que terminen las
transiciones, hace una captura y la compara con la anterior (Pillow: fracción de píxeles que
cambian más de un umbral). Lista los tramos sin cambios visibles, el alto total de la página y
cuántas pantallas ocupa cada parada. Necesita playwright y Pillow (p. ej. ~/Proyectos/econolabs/.venv).
"""
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

S = Path(sys.argv[1])
U = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000/"
W = int(sys.argv[3]) if len(sys.argv) > 3 else 390
H = int(sys.argv[4]) if len(sys.argv) > 4 else 844
UMBRAL_PIXEL, MINIMO = 24, 0.02  # un 2 % de píxeles que cambian = «pasa algo»
S.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    pg.goto(U + "index.html")
    pg.wait_for_function("window.__historia !== undefined", timeout=30000)
    pg.wait_for_timeout(2500)
    alto = pg.evaluate("document.documentElement.scrollHeight")
    paradas = pg.evaluate("""[...document.querySelectorAll('.parada')].map(e => [e.id, e.offsetHeight])""")
    fin = pg.evaluate("document.getElementById('seccion-explorador').getBoundingClientRect().top + scrollY")
    print(f"alto total: {alto} px = {alto / H:.1f} pantallas; historia hasta el buscador: {fin / H:.1f} pantallas")
    for pid, h in paradas:
        print(f"  {pid}: {h / H:.1f} pantallas")
    anterior, quietos, k, y = None, [], 0, 0
    while y < fin:
        pg.evaluate(f"window.scrollTo(0, {y})")
        pg.wait_for_timeout(1300)
        img = Image.open(BytesIO(pg.screenshot())).convert("L").resize((W // 2, H // 2))
        if anterior is not None:
            dif = ImageChops.difference(img, anterior).point(lambda v: 255 if v > UMBRAL_PIXEL else 0)
            frac = sum(dif.histogram()[255:]) / (dif.width * dif.height)
            paso = pg.evaluate("document.querySelector('.paso.activo')?.id || '(portada)'")
            if frac < MINIMO:
                quietos.append((k, y, paso, round(frac, 4)))
                img.save(S / f"quieto_{k:03d}.png")
        anterior, k, y = img, k + 1, y + H
    print(f"pantallas revisadas: {k}; sin cambios visibles: {len(quietos)}")
    for q in quietos:
        print(f"  pantalla {q[0]} (y={q[1]}), paso {q[2]}: {q[3] * 100:.1f} % de píxeles cambian")
    b.close()
