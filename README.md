# Tres mil nidos al año

Qué consigue Bizkaia retirando nidos de avispa asiática, y qué no. Pieza de visualización de datos para el Reto de Periodismo de Datos de Open Data Bizkaia 2026.

Autor: Roberto Burgos.

## Contenido
- `web/`: la pieza (web estática: D3, Scrollama y MapLibre). Se sirve con `cd web && python3 -m http.server 8000`. Detalle en `web/README.md`.
- `scripts/`: todo el proceso en Python, de la descarga de los datos a la preparación de la web.
- `outputs/`: resultados de los análisis (resúmenes y CSV) que usa la web.

## Reproducir de principio a fin
Requisitos: Python 3.12 con pandas, numpy, geopandas, shapely, scipy, statsmodels, requests y matplotlib.

1. Descarga de los datos: `scripts/descargar_bizkaia.py`, `scripts/descargar_municipios_bizkaia.py`, `scripts/descargar_comparativa_regiones.py` (y el resto de `scripts/descargar_*.py`). Los datos brutos se guardan en `data/raw/`, que no se sube al repositorio.
2. Limpieza y análisis: `scripts/avispa_indicadores_control.py`, `scripts/avispa_cifras_guion.py`, `scripts/avispa_gasto.py`, `scripts/avispa_comparativa_regiones.py`, `scripts/avispa_politicas_hitos.py` y los demás `scripts/avispa_*.py`. Todos reutilizan la limpieza de `scripts/explorar_avispa.py`.
3. Datos de la web: `scripts/web_preparar_datos.py` y, para comprobar que las cifras de los textos cuadran con los datos, `scripts/web_comprobar_cifras.py`.

La metodología completa (conjuntos usados, decisiones y limitaciones) está en `web/metodologia.html`.

## Licencias
- Código: MIT.
- Textos, gráficos y datos procesados: CC BY 4.0.
- Datos de origen: Open Data Bizkaia y las demás fuentes citadas en la metodología, con sus propias licencias.
- Librerías incluidas en `web/vendor/`: D3 (ISC), Scrollama (MIT), MapLibre GL JS (BSD-3-Clause); tipografías Source Serif 4 y Source Sans 3 (SIL Open Font License).
