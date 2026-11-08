"""Prueba de humo de la web con un navegador sin ventana (Playwright + Chromium).

Uso (con la web servida, p. ej. `python -m http.server 8000 --bind 127.0.0.1` dentro de web/):
    python scripts/web_probar.py <carpeta_capturas> [url_base]

Necesita un entorno con `playwright` (p. ej. ~/Proyectos/econolabs/.venv/bin/python).
Recorre todos los pasos en móvil (390x844, con movimiento reducido) y en escritorio
(1440x900, con animaciones); hace capturas de la portada y de cada paso (los animados, en varios
puntos de su progreso); prueba «Dibuja tu estimación»
(toques en las columnas y botón «Ver los datos reales»), el buscador de municipios (Getxo y
Bilbao), la carga con la red limitada (4G lenta: primera pintura, CLS y capturas del esqueleto)
y la página de metodología. Lista los errores y avisos de consola, las peticiones
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
        pg.wait_for_timeout(1500)
        pg.screenshot(path=str(S / f"{nombre}_00_portada_a.png"))
        pg.wait_for_timeout(9000)  # la portada enciende los nidos año a año
        pg.screenshot(path=str(S / f"{nombre}_00_portada_b.png"))
        pasos = pg.evaluate("window.__historia.contenido.pasos.map(p => p.id)")
        res = []
        # Pasos animados: capturas en varios puntos de su progreso (el progreso del paso mueve el
        # mapa o el gráfico); el resto, a mitad del paso.
        PROGRESOS = {"apertura": [0.1, 0.35, 0.58, 0.72, 0.92], "censo": [0.2, 0.7], "tasas": [0.3, 0.8],
                     "llegada": [0.25, 0.8], "ciclo": [0.2, 0.8], "estimacion-real": [0.25, 0.85],
                     "no-eliminables": [0.3, 0.9], "regiones": [0.2, 0.5, 0.9], "gasto": [0.2, 0.8]}
        for i, pid in enumerate(pasos):
            for k, prog in enumerate(PROGRESOS.get(pid, [0.5])):
                pg.evaluate(f"""(() => {{ const el = document.querySelectorAll('.paso')[{i}];
                  const r = el.getBoundingClientRect();
                  window.scrollBy(0, r.top - innerHeight * 0.75 + r.height * {prog}); }})()""")
                espera = 3500 if (pid in ("apertura", "censo", "tasas") and rm != "reduce") else 1500
                pg.wait_for_timeout(espera)
                if k < len(PROGRESOS.get(pid, [0.5])) - 1:
                    pg.screenshot(path=str(S / f"{nombre}_{i + 1:02d}_{pid}_{int(prog * 100):02d}.png"))
            if pid == "estimacion":
                # Marca tres estimaciones tocando las columnas y hace la captura antes de revelar
                caja = pg.locator("#lienzo-estimacion").bounding_box()
                for fx, fy in [(0.42, 0.55), (0.62, 0.45), (0.85, 0.35)]:
                    # sin salir del lienzo ni tocar la navegación de la derecha
                    px = min(caja["x"] + caja["width"] * fx, vp["width"] - 90)
                    pg.mouse.click(px, caja["y"] + caja["height"] * fy)
                pg.wait_for_timeout(300)
            a = pg.evaluate("[document.querySelector('.paso.activo')?.id, [...document.querySelectorAll('.panel')]"
                            ".filter(p=>!p.hidden).map(p=>p.dataset.grafico).join()]")
            fuera = pg.evaluate(DESBORDES)
            res.append(f"{i}:{pid}:{a[0]}:{a[1]}" + (f" FUERA{fuera}" if fuera else ""))
            pg.screenshot(path=str(S / f"{nombre}_{i + 1:02d}_{pid}_{int(prog * 100):02d}.png"))
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
    # Carga con la red limitada (4G lenta: 150 ms de latencia, 1,6 Mbit/s): primera pintura,
    # saltos de maquetación (CLS) y esqueletos de carga
    pg = b.new_page(viewport={"width": 390, "height": 844})
    cdp = pg.context.new_cdp_session(pg)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 150,
             "downloadThroughput": 1.6e6 / 8, "uploadThroughput": 0.75e6 / 8})
    pg.add_init_script("""window.__cls = 0; new PerformanceObserver((l) => { for (const e of l.getEntries())
      if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: "layout-shift", buffered: true });""")
    pg.goto(U + "index.html?lenta=1", wait_until="commit")
    pg.wait_for_selector(".portada h1", state="visible")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(S / "lenta_portada_1500ms.png"))
    fcp = pg.evaluate("(performance.getEntriesByName('first-contentful-paint')[0] || {}).startTime")
    pg.wait_for_function("window.__historia !== undefined", timeout=90000)
    pg.evaluate("""(() => { const el = document.getElementById('paso-rapidez'); const r = el.getBoundingClientRect();
      window.scrollBy(0, r.top - innerHeight * 0.75 + r.height * 0.4); })()""")
    pg.wait_for_timeout(120)
    pg.screenshot(path=str(S / "lenta_esqueleto.png"))
    pg.wait_for_timeout(4000)
    pg.screenshot(path=str(S / "lenta_cargado.png"))
    pg.evaluate("window.scrollTo(0, 0)")
    pg.wait_for_timeout(1500)
    print(f"red lenta: primera pintura con contenido {fcp:.0f} ms; CLS acumulado {pg.evaluate('window.__cls'):.3f}")
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
