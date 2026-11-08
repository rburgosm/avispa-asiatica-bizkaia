"""Prueba de humo de la web con un navegador sin ventana (Playwright + Chromium).

Uso (con la web servida, p. ej. `python -m http.server 8000 --bind 127.0.0.1` dentro de web/):
    python scripts/web_probar.py <carpeta_capturas> [url_base]

Necesita un entorno con `playwright` (p. ej. ~/Proyectos/econolabs/.venv/bin/python).
Recorre todos los pasos en móvil (390x844, con movimiento reducido) y en escritorio
(1440x900, con animaciones); hace una captura de cada paso; prueba «Dibuja tu estimación»
(toques en las columnas y botón «Ver los datos reales»), el buscador de municipios (Getxo y
Bilbao) y la página de metodología. Lista los errores y avisos de consola, las peticiones
fallidas y los textos de los gráficos que se salen del lienzo.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

S = Path(sys.argv[1])
U = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000/"
S.mkdir(parents=True, exist_ok=True)

# Textos SVG que se salen del lienzo visible (cortes)
DESBORDES = """() => {
  const p = [...document.querySelectorAll('.panel')].find(x => !x.hidden);
  if (!p) return [];
  const l = p.querySelector('.lienzo').getBoundingClientRect();
  return [...p.querySelectorAll('svg text')].filter(t => t.textContent.trim()).map(t => {
    const r = t.getBoundingClientRect();
    return (r.width && (r.left < l.left - 2 || r.right > l.right + 2 || r.top < l.top - 2 || r.bottom > l.bottom + 2))
      ? t.textContent.trim().slice(0, 40) : null;
  }).filter(Boolean);
}"""

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for nombre, vp, rm in [("movil", {"width": 390, "height": 844}, "reduce"),
                           ("escritorio", {"width": 1440, "height": 900}, "no-preference")]:
        pg = b.new_page(viewport=vp, reduced_motion=rm, device_scale_factor=1)
        errores = []
        pg.on("console", lambda m: errores.append(f"{m.type}: {m.text}")
              if m.type in ("error", "warning") and "GL Driver Message" not in m.text else None)  # avisos de SwiftShader
        pg.on("pageerror", lambda e: errores.append(f"pageerror: {e}"))
        pg.on("requestfailed", lambda r: errores.append(f"falló: {r.url}"))
        pg.on("response", lambda r: errores.append(f"{r.status}: {r.url}") if r.status >= 400 else None)
        pg.goto(U + "index.html")
        pg.wait_for_function("window.__historia !== undefined", timeout=20000)
        pg.screenshot(path=str(S / f"{nombre}_00_cabecera.png"))
        pasos = pg.evaluate("window.__historia.contenido.pasos.map(p => p.id)")
        res = []
        for i, pid in enumerate(pasos):
            # Móvil: el texto se lee bajo el gráfico (borde superior de la tarjeta al 62 % de la
            # pantalla); escritorio: tarjeta centrada.
            pg.evaluate(f"""(() => {{ const el = document.querySelectorAll('.paso')[{i}];
              const r = el.getBoundingClientRect();
              const destino = innerWidth < 900 ? innerHeight * 0.62 : (innerHeight - r.height) / 2;
              window.scrollBy(0, r.top - destino); }})()""")
            espera = 5500 if (i == 0 and rm != "reduce") else 1400
            pg.wait_for_timeout(espera)
            if pid == "estimacion":
                # Marca tres estimaciones tocando las columnas y hace la captura antes de revelar
                caja = pg.locator("#lienzo-estimacion svg").bounding_box()
                for fx, fy in [(0.42, 0.55), (0.62, 0.45), (0.9, 0.35)]:
                    pg.mouse.click(caja["x"] + caja["width"] * fx, caja["y"] + caja["height"] * fy)
                pg.wait_for_timeout(300)
            a = pg.evaluate("[document.querySelector('.paso.activo')?.id, [...document.querySelectorAll('.panel')]"
                            ".filter(p=>!p.hidden).map(p=>p.dataset.grafico).join()]")
            fuera = pg.evaluate(DESBORDES)
            res.append(f"{i}:{pid}:{a[0]}:{a[1]}" + (f" FUERA{fuera}" if fuera else ""))
            pg.screenshot(path=str(S / f"{nombre}_{i + 1:02d}_{pid}.png"))
            if pid == "estimacion":  # botón «Ver los datos reales»
                pg.click("#paso-estimacion .boton")
                pg.wait_for_timeout(1500)
                pg.screenshot(path=str(S / f"{nombre}_{i + 1:02d}b_estimacion_revelada.png"))
        print(nombre, "\n  " + "\n  ".join(res))
        # Buscador
        pg.locator(".explorador").scroll_into_view_if_needed()
        for q in ("getxo", "bilbao"):
            pg.fill("#buscar-municipio", q)
            pg.dispatch_event("#buscar-municipio", "change")
            pg.wait_for_timeout(700)
            print(nombre, q, "->", pg.text_content("#resumen-municipio"))
            pg.screenshot(path=str(S / f"{nombre}_buscador_{q}.png"))
        pg.locator("#cierre").scroll_into_view_if_needed()
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(S / f"{nombre}_cierre.png"))
        print(nombre, "errores:", errores or "ninguno")
        pg.close()
    pg = b.new_page(viewport={"width": 390, "height": 844})
    err = []
    pg.on("pageerror", lambda e: err.append(str(e)))
    pg.on("console", lambda m: err.append(m.text) if m.type == "error" else None)
    pg.goto(U + "metodologia.html")
    pg.wait_for_timeout(800)
    print("metodologia:", pg.evaluate("document.querySelectorAll('#metodologia h2').length"), "h2; errores:", err or "ninguno")
    pg.screenshot(path=str(S / "metodologia.png"), full_page=True)
    b.close()
