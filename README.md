# Tres mil nidos al año

Qué consigue Bizkaia retirando nidos de avispa asiática, y qué no. Pieza de visualización de datos para el Reto de Periodismo de Datos de Open Data Bizkaia 2026.

Autor: Roberto Burgos.

## Contenido
- `web/`: la pieza (web estática: D3, Scrollama y MapLibre). Se sirve con `cd web && python3 -m http.server 8000`. Detalle en `web/README.md`.
- `scripts/`: todo el proceso en Python, de la descarga de los datos a la preparación de la web.
- `outputs/`: resultados de los análisis (resúmenes y CSV) que usa la web.

## Reproducir de principio a fin
Requisitos: Python 3.12 con pandas, numpy, geopandas, shapely, pyproj, scipy, statsmodels, matplotlib, openpyxl y Pillow; `pdftotext` y `pdftoppm` (poppler-utils) para leer los PDF.

Una sola orden, desde la raíz del proyecto:

```
python -I scripts/reproducir.py                  # todo, con descargas
python -I scripts/reproducir.py --sin-descargas  # reutiliza data/raw/ y los ficheros ya bajados de web/
python -I scripts/reproducir.py --lista          # enseña los pasos y las órdenes exactas
python -I scripts/reproducir.py --desde avispa_gasto   # retoma desde un paso
python -I scripts/reproducir.py --fases descarga       # solo una o varias fases
```

Orden real de los pasos (cada uno es un script de `scripts/`):

1. **Descargas** (a `data/raw/`, que no se sube al repositorio; ~2,3 GB). Los scripts no vuelven a bajar un fichero que ya existe, salvo Epicollect5 y las parcelas de colmenares, que se piden siempre. Con la API del GBIF también conecta `avispa_estabilizacion.py` (con `--sin-descargas` resume el JSON ya guardado).
   - `descargar_bizkaia.py`: 20 conjuntos de Open Data Bizkaia, con los mismos filtros por nombre de recurso que la descarga original (detalle en `scripts/reproducir.py`). El registro de nidos queda en `data/raw/bizkaia/avispa_asiatica/nidos.csv` y las intervenciones del SPEIS en `data/raw/bizkaia/speis/`, que es donde los leen los análisis.
   - `descargar_municipios_bizkaia.py`, `descargar_comarcas.py`, `descargar_parcelas_colmenares.py`: límites municipales y parcelas (servicio REST de la Diputación) y comarcas de Eustat.
   - `descargar_externos.py`: padrón del INE (tabla 2905), informes de Asturias y Araba, manual del Gobierno Vasco, avistamientos del Reino Unido (gov.uk), GBIF (MNHN), playas y municipios simplificados (geo.bizkaia.eus), normas y noticias de la cronología, y lecturas de Euskalmet. Compara cada fichero con la huella SHA-256 de la descarga original y anota el resultado en `data/raw/externos/_descargas_externas.tsv`.
   - `descargar_comparativa_regiones.py` (prensa y notas oficiales de otras regiones) y `descargar_jersey_epicollect.py` (Jersey 2025).
2. **Limpieza y análisis** (a `outputs/`): `descargar_comarcas.py --sin-descarga` (tabla municipio-comarca), `avispa_politicas_textos.py`, `explorar_avispa.py` (limpieza común), `avispa_llegamos_tarde.py`, `avispa_avisos_poblacion.py`, `avispa_indicadores_control.py`, `avispa_cifras_guion.py`, `avispa_comarcas.py`, `avispa_estabilizacion.py`, `avispa_dificultad_bizkaia.py`, `digitalizar_asturias.py`, `avispa_comparativa_regiones.py`, `avispa_validacion_estacionalidad.py`, `avispa_gasto.py`, `avispa_politicas_hitos.py` (cronología), `avispa_impacto.py` y `clima_euskalmet_mensual.py`.
3. **Datos de la web** (a `web/data/` y `web/img/`): `web_preparar_datos.py`, `web_preparar_hilo.py`, `web_preparar_densidad.py`, `web_preparar_situacion.py`, `web_preparar_relieve.py`, [`web_descargar_mapa_base.py` con el build anotado en `web/data/mapa_base/mapa_base.json`], [`web_descargar_imagenes.py`], `web_adaptar_imagenes.py`, `web_preparar_portada.py`, [`web_descargar_librerias.py`, `web_descargar_fuentes.py`] y `web_comprimir.py`. Los pasos entre corchetes descargan y se saltan con `--sin-descargas`.
4. **Comprobación**: `web_comprobar_cifras.py` (las cifras redondeadas de los textos cuadran con los datos).

Tiempo aproximado (portátil, conexión doméstica): descargas, unos 21 minutos la primera vez (15 de ellos, Open Data Bizkaia; 3, las lecturas de Euskalmet); análisis, web y comprobación, unos 3 minutos y medio (prueba del 08/11/2026 en una copia limpia: 26 pasos; el más lento, `avispa_gasto.py`, con 2,5 minutos, porque lee ~800 MB de contratos y presupuestos).

Lo que no sale de un script (y por qué):
- `outputs/avispa_araba_mes_transcrito.csv`, `avispa_validacion_fenologia.csv` y `avispa_validacion_costes.csv`: transcripciones manuales de gráficas y tablas de informes (fuentes en `docs/avispa_validacion_externa.md`). Entran como datos de partida.
- `web/content/es.json`: los textos de la pieza.
- Las fuentes de bizkaia.eus (noticias de la Diputación, fichas temáticas y la memoria de transparencia de 2021) responden a las peticiones automáticas con una página antirrobots: `descargar_externos.py` lo detecta y no las guarda. Son lectura documental de la cronología; ninguna cifra calculada depende de ellas.
- Exploración previa, fuera del proceso de la pieza: `outputs/catalogo_*.json`, `outputs/perfiles/`, `outputs/speis_resumen.txt`, `outputs/cifras_candidatos.txt` y los artículos científicos de `data/raw/externos/` que no lee ningún script (se citan en la metodología).

Los ficheros que cambian con el tiempo en el servidor están anotados en `descargar_externos.py`: el padrón del INE (con el de 2026 cambia la ventana de años), la página de gov.uk (se actualiza con cada avistamiento), los conjuntos de Open Data Bizkaia que se siguen publicando (contratos, presupuestos, el propio registro de nidos) y el build del mapa base de Protomaps (los antiguos se borran). Para comprobar que se parte del mismo registro de nidos: SHA-256 `2da62168e1f298013b2590ecd025b1c45341fa70915638cc094d5fcaba4fc6d4` (descarga del 08/11/2026).

La metodología completa (conjuntos usados, decisiones y limitaciones) está en `web/metodologia.html`.

## Licencias
- Código: MIT.
- Textos, gráficos y datos procesados: CC BY 4.0.
- Datos de origen: Open Data Bizkaia y las demás fuentes citadas en la metodología, con sus propias licencias.
- Librerías incluidas en `web/vendor/`: D3 (ISC), Scrollama (MIT), MapLibre GL JS (BSD-3-Clause); tipografías Source Serif 4 y Source Sans 3 (SIL Open Font License).
