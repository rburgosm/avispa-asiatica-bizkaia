# Web: «Tres mil nidos al año»

Scrollytelling (gráfico fijo y pasos de texto) para el Reto de Periodismo de Datos de Open Data Bizkaia 2026, categoría de visualización: qué consigue Bizkaia retirando nidos de avispa asiática, y qué no. Los textos son los del guion aprobado (`docs/guion.md`), copiados tal cual en `content/es.json`. **En la web no hay ninguna cifra escrita a mano**: los gráficos, las etiquetas, las notas y los textos alternativos salen de `data/*.json`, que genera un script.

## Servir la web

```bash
cd web
python3 -m http.server 8000 --bind 127.0.0.1
# abrir http://127.0.0.1:8000/  (euskera, cuando exista: ?lang=eu)
```

No hay paso de compilación. Hace falta servirla por HTTP (abierta como fichero no puede leer los JSON).

## Regenerar todo, en orden

Desde la raíz del proyecto, con `PY=~/Proyectos/observatorio-patinetes/.venv/bin/python`:

```bash
$PY -I scripts/descargar_municipios_bizkaia.py            # límites -> data/raw/bizkaia/municipios_catastro/
$PY -I scripts/avispa_indicadores_control.py              # -> outputs/avispa_indicadores_temporada.csv, avispa_dias_tramos.csv
$PY -I scripts/avispa_cifras_guion.py                     # -> outputs/avispa_reparto_mensual.csv, _perfil_epoca.csv, _tasas_tamano.csv
$PY -I scripts/avispa_comparativa_regiones.py data/raw/externos outputs   # -> _comparativa_regiones.csv, _meseta.csv
$PY -I scripts/avispa_gasto.py                            # -> outputs/avispa_gasto_anual.csv, _gasto_coste_nido.csv (unos 2 min)
$PY -I scripts/avispa_politicas_hitos.py                  # -> outputs/avispa_politicas_hitos.csv
$PY -I scripts/web_preparar_datos.py                      # todo lo anterior -> web/data/
$PY -I scripts/web_comprobar_cifras.py                    # las cifras redondeadas del texto cuadran con web/data/
$PY -I scripts/web_descargar_librerias.py                 # D3, Scrollama y MapLibre -> web/vendor/
$PY -I scripts/web_descargar_fuentes.py                   # Source Serif 4 y Source Sans 3 (OFL) -> web/vendor/fonts/
~/Proyectos/econolabs/.venv/bin/python scripts/web_probar.py <carpeta_capturas> http://127.0.0.1:8000/
```

`web_preparar_datos.py` no copia cifras: lee los CSV de `outputs/` y, para el perfil por época, el reparto mensual y las tasas por habitante, importa las funciones de `scripts/avispa_cifras_guion.py`. Comprueba que lo recalculado coincide con los CSV y deja las cifras de control en `data/resumen.txt`.

| Fichero | Contenido | Paso |
|---|---|---|
| `data/indicadores.json` | por temporada 2018-2025 (abril-diciembre; 2018 marcada como incompleta): nidos, no eliminables, tramos de días hasta la retirada, % de Basalan, primavera, retirados después del 1 de noviembre | 3, 5, 6, 7, 9 |
| `data/mensual.json` | avisos por mes de abril a diciembre, 2019-2025, y reparto por estaciones | 8, 9 |
| `data/esquemas.json` | tamaño, altura y % en árbol de los nidos retirados según la época | 2 |
| `data/regiones.json` | nidos por 1.000 km² por años desde la llegada (Bizkaia, Asturias, Gipuzkoa, Araba) y media en la meseta | 10 |
| `data/gasto.json` | gasto de retirada con línea propia (2017-2019), 2020 mezclado, 2021-2025 sin desglose, encargo a Basalan y coste por nido | 11 |
| `data/cronologia.json` | hitos de la cronología con estado «confirmado» o «confirmado_secundaria» (se excluyen los no confirmados) | 1, 3 |
| `data/nidos.json` | puntos `[lon, lat, temporada, mes]` 2018-2025, abril-diciembre, 3 decimales (~100 m) | 0 |
| `data/municipios.geojson` | 113 municipios simplificados con la tasa por 1.000 habitantes, cortes de la leyenda, tasas por tamaño y Bilbao «sin datos» | 12 |
| `data/municipios_serie.json` | por municipio: nidos por temporada, tasa, puesto, días de retirada | 13 (buscador) |
| `data/descargas/*.csv` | datos procesados descargables | – |
| `vendor/` | D3 7.9.0, Scrollama 3.2.0, MapLibre GL JS 4.7.1 y `fonts/` (con licencias y SHA-256) | – |

## Estructura

```
index.html            página única; los paneles de los gráficos los crea js/app.js
metodologia.html      lee su texto de content/es.json (metodologia, creditos, descargas)
content/es.json       TODO el texto: pasos del guion, títulos de los gráficos, notas, interfaz, metodología
css/estilo.css        estilos y paleta (variables CSS de docs/paleta_colores.md); móvil primero
js/app.js             arranque: lee contenido y datos, crea los paneles, pinta los pasos y conecta Scrollama
js/util.js            formatos (es-ES), rayado de datos incompletos, separación y ajuste de etiquetas, tablas
js/componentes/
  mapa.js             MapLibre: nidos que aparecen temporada a temporada (paso 0) y tasa por municipio (paso 12)
  esquema.js          D3: línea del tiempo, año de un nido, circuito del aviso, «un aviso no es un censo» (pasos 1-4)
  estimacion.js       D3: «Dibuja tu estimación» (paso 5)
  tramos.js           D3: barras apiladas de días entre aviso y retirada (paso 6)
  linea.js            D3: no eliminables con la marca del cambio de registro (paso 7)
  mensual.js          D3: calendario de avisos con la primavera o la zona desde el 1 de noviembre (pasos 8 y 9)
  regiones.js         D3: curvas de las regiones en escala logarítmica (paso 10)
  gasto.js            D3: gasto 2017-2025 con 2020 mezclado y 2021-2025 sin desglose (paso 11)
  explorador.js       D3: buscador «Tu municipio» (paso 13)
```

## Pasos

Cada paso de `content/es.json`:

```json
{ "id": "rapidez", "grafico": "tramos", "titulo": "Título del gráfico",
  "estado": {}, "texto": ["Texto del guion."], "nota": "Advertencia visible bajo el gráfico (opcional)",
  "alt": "Descripción del gráfico; el componente añade un resumen de los datos." }
```

Estados: `mapa` `{modo: "puntos", temporadas, meses}` o `{modo: "tasa"}`; `esquema` `{vista: "llegada" | "ciclo" | "circuito" | "censo", ...}`; `estimacion` `{revelar}`; `mensual` `{resaltar: "primavera" | "noviembre"}`. El paso de la estimación lleva `boton` («Ver los datos reales»).

En el móvil el gráfico ocupa el 58 % superior de la pantalla y los textos se leen debajo (pasan por debajo del gráfico); en escritorio, texto a la izquierda y gráfico a la derecha. Alturas en `svh`.

## Decisiones visibles

- Periodo 2019-2025 y avisos de abril a diciembre; 2018, rayado en gris con «registro incompleto».
- Bilbao, rayado y «sin datos (servicio municipal propio)» en el mapa y en el buscador; fuera de las tasas y los puestos.
- Como mucho tres colores de serie por gráfico (naranja = avispa, azul = acción pública, gris = contexto), etiquetas directas, halo del color del fondo en las etiquetas.
- La avispa del paso 1 es un icono esquemático, «sin escala»: el guion pedía un dibujo a escala junto a una abeja, pero no hay medidas con fuente para dibujarlo; se sustituye por la línea del tiempo de la cronología.

## Accesibilidad

Contraste AA, controles nativos, texto alternativo por paso (con un resumen generado de los datos) anunciado con `aria-live`, tabla con los datos de cada gráfico («Ver los datos del gráfico»), estimación con teclado (flechas), sin animaciones con `prefers-reduced-motion`, gestos cooperativos en el mapa.

## Pendiente

- Autoría y fecha definitivas (`meta`), y enlace al repositorio de código (ahora «Código» lleva a la lista de scripts de la metodología).
- Traducción al euskera (`content/eu.json`).
- Modo oscuro (paleta validada en `docs/paleta_colores.md`, sin aplicar).
- Revisión en un móvil real.
