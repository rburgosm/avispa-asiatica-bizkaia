"""Reproduce el proyecto de principio a fin: descargas, limpieza y análisis, datos de la web y comprobación.

Uso (desde cualquier carpeta; trabaja en la raíz del proyecto):
    python -I scripts/reproducir.py                  # todo, con descargas (~2,3 GB la primera vez)
    python -I scripts/reproducir.py --sin-descargas  # usa data/raw/ tal como está
    python -I scripts/reproducir.py --lista          # solo enseña los pasos y sus órdenes
    python -I scripts/reproducir.py --desde web_preparar_datos   # retoma desde un paso

Cada paso es un script de Python del directorio scripts/ que se ejecuta con el mismo intérprete
(o el de --python) y la opción -I. Si un paso falla, se detiene y dice cuál.

Fases:
1. descarga: Open Data Bizkaia (descargar_bizkaia.py, que deja el registro de nidos en
   data/raw/bizkaia/avispa_asiatica/nidos.csv), límites municipales y parcelas de colmenares
   (servicio REST de la Diputación), comarcas de Eustat, padrón del INE, informes de otras
   regiones, GBIF, Epicollect5 (Jersey), Euskalmet y páginas de prensa y notas oficiales.
   Los scripts de descarga no vuelven a bajar un fichero que ya existe.
2. analisis: limpieza (explorar_avispa.py, que usan todos los demás) y análisis
   (avispa_*.py, comparativa de regiones, gasto, comarcas, cronología de medidas, clima).
   Escriben en outputs/.
3. web: datos de la web (web_preparar_*.py, web_adaptar_imagenes.py, web_comprimir.py), que
   escriben en web/data/. Con descargas, también se vuelven a bajar el mapa base (con el build
   anotado en web/data/mapa_base/mapa_base.json), las fotos, las librerías y las tipografías.
4. comprobacion: web_comprobar_cifras.py (las cifras redondeadas de los textos cuadran con los
   datos; sale con error si alguna no cuadra).

Requisitos: Python 3.12 con pandas, numpy, geopandas, shapely, pyproj, scipy, statsmodels,
matplotlib, openpyxl y Pillow; pdftotext y pdftoppm (poppler-utils) para leer los PDF.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NIDOS = "data/raw/bizkaia/avispa_asiatica/nidos.csv"
PADRON_1 = "data/raw/ine/padron_bizkaia_2905.json"
PADRON_9 = "data/raw/ine/padron_bizkaia_2905_2017_2025.json"
EXT = "data/raw/externos"

# Conjuntos de Open Data Bizkaia que leen los análisis: (slugs, patrón sobre el nombre del recurso o None).
# Los patrones reproducen la selección de la descarga original (08/11/2026): sin 2014-2016 en los
# conjuntos de contratación, encargos y subvenciones (ni el «acumulado» de contratos no menores), solo
# los gastos de los presupuestos completos y de la liquidación, y solo la memoria del IRPF de 2024.
# Sin ellos se bajan ficheros de más que avispa_gasto.py también leería.
CONJUNTOS_BIZKAIA = [
    (["avispa-asiatica", "intervenciones-speis", "subvenciones", "plan-anual-contratacion",
      "plan-anual-contratacion-basalan", "modificaciones-presupuestos", "ejecucion-presupuestos",
      # impacto socioeconómico (avispa_impacto.py)
      "explotaciones-ganaderas", "declaracion-superficies", "parcelas-registro-viticola", "playas",
      "areas-esparcimiento"], None),
    (["encomiendas-gestion", "contratos-menores", "contratos-no-menores", "convenios", "subvenciones-otorgadas"],
     r"-20(1[7-9]|2[0-9])"),
    (["presupuestos-completos", "liquidacion-presupuestos"], r"gastos-20(1[7-9]|2[0-9])"),
    (["memoria-anual-hacienda-foral-irpf"], r"-2024$"),
]


def build_mapa_base() -> str:
    """Build de Protomaps usado en la versión publicada (los builds antiguos se borran del servidor)."""
    f = RAIZ / "web/data/mapa_base/mapa_base.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))["build"].removesuffix(".pmtiles")
    except (OSError, KeyError, ValueError):
        return ""


def pasos(sin_descargas: bool) -> list[tuple[str, str, list[str]]]:
    """(fase, script, argumentos). Las fases «descarga» y «web_descarga» se saltan con --sin-descargas."""
    P = [
        # 1. Descargas
        *[("descarga", "descargar_bizkaia.py", ["data/raw/bizkaia", *slugs] + ([f"--patron={patron}"] if patron else []))
          for slugs, patron in CONJUNTOS_BIZKAIA],
        ("descarga", "descargar_municipios_bizkaia.py", []),
        ("descarga", "descargar_comarcas.py", []),
        ("descarga", "descargar_parcelas_colmenares.py",
         ["data/raw/bizkaia/explotaciones-ganaderas", "data/raw/bizkaia/parcelario-catastral/parcelas_colmenares.geojson"]),
        ("descarga", "descargar_externos.py", ["--grupos", "ine", "regiones", "gbif", "geo_bizkaia",
                                                "documentales", "euskalmet"]),
        ("descarga", "descargar_comparativa_regiones.py", [EXT]),
        ("descarga", "descargar_jersey_epicollect.py", ["2025", f"{EXT}/jersey_epicollect"]),
        # 2. Limpieza y análisis
        ("analisis", "descargar_comarcas.py", ["--sin-descarga"]),  # outputs/municipio_comarca.csv
        ("analisis", "avispa_politicas_textos.py", [f"{EXT}/politicas_avispa"]),
        ("analisis", "explorar_avispa.py", [NIDOS, PADRON_1]),
        ("analisis", "avispa_llegamos_tarde.py", [NIDOS]),
        ("analisis", "avispa_avisos_poblacion.py", [NIDOS, PADRON_9]),
        ("analisis", "avispa_indicadores_control.py", []),
        ("analisis", "avispa_cifras_guion.py", []),
        ("analisis", "avispa_comarcas.py", []),
        ("analisis", "avispa_estabilizacion.py",
         [NIDOS, PADRON_1, f"{EXT}/gbif", "outputs"] + (["--sin-descarga"] if sin_descargas else [])),
        ("analisis", "avispa_dificultad_bizkaia.py", [NIDOS, "outputs/avispa_dificultad_bizkaia.txt"]),
        ("analisis", "digitalizar_asturias.py",
         [f"{EXT}/asturias/informe_2025.pdf", "outputs/asturias_avisos_semanales_digitalizado.csv"]),
        ("analisis", "avispa_comparativa_regiones.py", [EXT, "outputs"]),
        ("analisis", "avispa_validacion_estacionalidad.py",
         [NIDOS, "outputs/asturias_avisos_semanales_digitalizado.csv", f"{EXT}/jersey_epicollect/entries_2025.json",
          f"{EXT}/uk_govuk/sightings.html", f"{EXT}/mnhn_gbif/facetas_mes_por_anio.jsonl",
          "outputs/avispa_araba_mes_transcrito.csv", "outputs"]),
        ("analisis", "avispa_gasto.py", ["data/raw/bizkaia", "outputs"]),
        ("analisis", "avispa_politicas_hitos.py", []),
        ("analisis", "avispa_impacto.py", ["data/raw/bizkaia", PADRON_1, "outputs/avispa_impacto.txt"]),
        ("analisis", "clima_euskalmet_mensual.py",
         [f"{EXT}/euskalmet", "outputs/clima_euskalmet_mensual.csv", "C002", "C036"]),
        # 3. Web
        ("web", "web_preparar_datos.py", []),
        ("web", "web_preparar_hilo.py", []),
        ("web", "web_preparar_densidad.py", []),
        ("web", "web_preparar_situacion.py", []),
        ("web", "web_preparar_relieve.py", []),
        ("web_descarga", "web_descargar_mapa_base.py", [build_mapa_base()]),
        ("web_descarga", "web_descargar_imagenes.py", []),
        ("web", "web_adaptar_imagenes.py", []),
        ("web", "web_preparar_portada.py", []),
        ("web", "web_preparar_compartir.py", []),  # iconos, og-*.png y metadatos del <head>
        ("web_descarga", "web_descargar_librerias.py", []),
        ("web_descarga", "web_descargar_fuentes.py", []),
        ("web", "web_copiar_memoria.py", []),
        ("web", "web_comprimir.py", []),
        # 4. Comprobación
        ("comprobacion", "web_comprobar_cifras.py", []),
    ]
    if sin_descargas:
        P = [p for p in P if p[0] not in ("descarga", "web_descarga")]
    return P


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sin-descargas", action="store_true",
                    help="no descarga nada: usa data/raw/ y los ficheros de web/ (vendor, mapa base, fotos) existentes")
    ap.add_argument("--python", default=sys.executable, help="intérprete con las librerías (por defecto, este)")
    ap.add_argument("--desde", default=None, help="empieza en este paso (nombre del script, con o sin .py)")
    ap.add_argument("--fases", nargs="+", default=None,
                    choices=["descarga", "analisis", "web", "web_descarga", "comprobacion"],
                    help="solo estas fases (p. ej. --fases descarga para comprobar las descargas)")
    ap.add_argument("--lista", action="store_true", help="solo enseña los pasos")
    a = ap.parse_args()

    P = pasos(a.sin_descargas)
    if a.fases:
        P = [p for p in P if p[0] in a.fases]
    if a.desde:
        nombres = [s for _, s, _ in P]
        desde = a.desde if a.desde.endswith(".py") else a.desde + ".py"
        if desde not in nombres:
            sys.exit(f"No hay ningún paso {desde}. Pasos: {', '.join(nombres)}")
        P = P[nombres.index(desde):]  # si el script sale dos veces, desde la primera
    for i, (fase, script, args) in enumerate(P, 1):
        orden = [a.python, "-I", f"scripts/{script}", *args]
        print(f"[{i}/{len(P)}] {fase:12} {' '.join(orden[2:])}", flush=True)
        if a.lista:
            continue
        t0 = time.monotonic()
        r = subprocess.run(orden, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        dt = time.monotonic() - t0
        salida = r.stdout.strip().splitlines()
        for linea in salida[-3:]:
            print(f"      | {linea[:160]}")
        print(f"      {'ok' if r.returncode == 0 else 'FALLO'} en {dt:.0f} s", flush=True)
        if r.returncode != 0:
            print("\n".join(salida[-40:]))
            sys.exit(f"Ha fallado el paso {script} (código {r.returncode}).")
    if not a.lista:
        print("Reproducción completa.")


if __name__ == "__main__":
    main()
