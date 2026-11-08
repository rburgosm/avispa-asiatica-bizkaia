"""Capturas de la web publicada (https://tresmilnidos.eus) para docs/proyecto_tresmilnidos.pdf.

Uso (Playwright para Python, libre, Apache 2.0; con Chromium instalado: `playwright install chromium`):
    python -I scripts/proyecto_capturas.py [carpeta_salida] [nombre ...]   (nombres: rehacer solo esas)

Recorre la pieza con la rueda del ratón (como una persona, para que se disparen los pasos del
scrollytelling), coloca cada paso por encima de la línea de disparo y espera a que acaben las
animaciones antes de capturar. Escritorio 1440x900.
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "capturas_proyecto"
URL = "https://tresmilnidos.eus/"

# (nombre, selector, fracción de la ventana donde queda la parte de arriba del elemento, espera en s)
CAPTURAS = [
    ("01_portada", None, None, 5),
    ("02_mapa_contador", "#paso-apertura-5 .tarjeta", 0.62, 7),
    ("03_parada", "#parada-respuesta", 0.0, 3),
    ("04_estimacion", "#paso-estimacion-real .tarjeta", 0.12, 5),
    ("05_rapidez", "#paso-rapidez .tarjeta", 0.12, 5),
    ("06_calendario", "#paso-primavera .tarjeta", 0.12, 5),
    ("07_comarcas", "#paso-comarca-habitante .tarjeta", 0.55, 7),
    ("08_buscador", "#seccion-explorador", -0.08, 4),
]


def ir_a(pagina, selector: str, fraccion: float) -> None:
    """Baja con la rueda en tramos cortos hasta dejar el elemento a la altura indicada."""
    for _ in range(400):
        top = pagina.eval_on_selector(selector, "e => e.getBoundingClientRect().top")
        objetivo = 900 * fraccion
        d = top - objetivo
        if abs(d) < 4:
            break
        pagina.mouse.wheel(0, max(-300, min(300, d)))
        time.sleep(0.06)


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pagina = nav.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        pagina.goto(URL, wait_until="networkidle")
        pagina.mouse.move(720, 450)
        solo = set(sys.argv[2:])
        for nombre, selector, fraccion, espera in CAPTURAS:
            if solo and nombre not in solo and not any(n > nombre for n in solo):
                continue
            if selector:
                ir_a(pagina, selector, fraccion)
            if solo and nombre not in solo:
                continue
            time.sleep(espera)
            pagina.screenshot(path=str(SALIDA / f"{nombre}.png"))
            print("captura", nombre)
        nav.close()


if __name__ == "__main__":
    main()
