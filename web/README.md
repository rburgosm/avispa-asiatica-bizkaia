# Web: «Tres mil nidos al año»

Scrollytelling por paradas (mapa a pantalla completa y gráficos fijos con tarjetas por encima) para el Reto de Periodismo de Datos de Open Data Bizkaia 2026, categoría de visualización: qué consigue Bizkaia retirando nidos de avispa asiática, y qué no. Los textos son los del guion aprobado (`docs/guion.md`), copiados tal cual en `content/es.json`. **En la web no hay ninguna cifra escrita a mano**: los gráficos, las etiquetas, las notas y los textos alternativos salen de `data/*.json`, que genera un script.

## Servir la web

```bash
cd web
python3 -m http.server 8000 --bind 127.0.0.1
# abrir http://127.0.0.1:8000/  (euskera, cuando exista: ?lang=eu)
```

No hay paso de compilación. Hace falta servirla por HTTP (abierta como fichero no puede leer los JSON). El mapa de detalle lee `data/mapa_base/bizkaia.pmtiles` con peticiones de rango (HTTP Range), como cualquier alojamiento estático normal; `python -m http.server` no las admite y entonces la web baja el fichero entero (26 MB) una vez, solo al llegar a ese paso (`js/componentes/fondo_mapa.js`).

## Compartir: favicon, imágenes y metadatos (`scripts/web_preparar_compartir.py`)

Un solo script genera en la raíz de `web/` el favicon (`favicon.svg`, con su versión para modo oscuro por `prefers-color-scheme`; `favicon.ico` de 16, 32 y 48 px), `apple-touch-icon.png` (180 px), `icon-192.png`, `icon-512.png`, `site.webmanifest` y las imágenes para compartir `og-image.png` y `og-metodologia.png` (1200×630, menos de 300 KB). El motivo de los iconos es el marcador del nido hilo del mapa; las imágenes llevan el mapa de densidad media de la portada (`data/portada.webp` + `data/densidad.geojson`) y el título, el subtítulo y la autoría de `content/es.json` (`meta`).

También reescribe el bloque de metadatos del `<head>` de `index.html` y `metodologia.html`, entre `<!-- compartir:auto -->` y `<!-- /compartir:auto -->` (no se edita a mano): título, descripción, autor, iconos, `theme-color` (claro y oscuro), Open Graph, Twitter/X (`summary_large_image`) y JSON-LD (`NewsArticle` en la portada, `TechArticle` en la metodología).

**Dominio.** La dirección pública es una sola constante, el argumento `--url-base`:

```bash
$PY -I scripts/web_preparar_compartir.py                                   # sin dominio (por defecto)
$PY -I scripts/web_preparar_compartir.py --url-base https://ejemplo.org/nidos/   # al desplegar
$PY -I scripts/web_comprimir.py                                            # después, para regenerar los .gz
```

Sin `--url-base`, `og:image`, `twitter:image` y la imagen del JSON-LD van con ruta relativa y no se escriben `canonical` ni `og:url` (exigen una dirección absoluta). Facebook, LinkedIn y X necesitan la imagen con URL absoluta: **antes de publicar hay que volver a ejecutar el script con el dominio definitivo**. La fecha del JSON-LD es `2026-11` (constante `FECHA` del script).

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
$PY -I scripts/web_preparar_hilo.py                       # nido hilo y ventana del censo -> nido_hilo.json, censo_ilustracion.json
$PY -I scripts/web_preparar_densidad.py                   # isobandas de densidad, contorno, comarcas y cabeceras -> densidad.geojson, contorno.geojson, lugares.geojson
$PY -I scripts/web_preparar_situacion.py                  # mapa de situación (Natural Earth) -> situacion.geojson
$PY -I scripts/web_preparar_relieve.py                    # relieve sombreado (Copernicus DEM GLO-90) -> relieve.webp, relieve.json
$PY -I scripts/web_descargar_mapa_base.py                 # recorte de Protomaps con la CLI pmtiles -> data/mapa_base/ (bizkaia.pmtiles, glifos, mapa_base.json)
$PY -I scripts/web_descargar_imagenes.py                  # fotos de Wikimedia Commons (CC BY-SA) -> img/, data/imagenes.json
$PY -I scripts/web_adaptar_imagenes.py                    # recorte 4:5 y 16:9 con punto focal y color común -> img/*-alto-*.webp, *-ancho-*.webp
$PY -I scripts/web_preparar_portada.py                    # imagen estática del mapa de la portada (primera pintura) -> portada.webp
$PY -I scripts/web_preparar_compartir.py                 # favicon, iconos, manifiesto, og-image.png, og-metodologia.png y metadatos del <head> (--url-base al desplegar)
$PY -I scripts/web_comprobar_cifras.py                    # las cifras redondeadas del texto cuadran con web/data/
$PY -I scripts/web_descargar_librerias.py                 # D3, Scrollama, MapLibre, pmtiles y @protomaps/basemaps -> web/vendor/
$PY -I scripts/web_descargar_fuentes.py                   # Source Serif 4 y Source Sans 3 (OFL) -> web/vendor/fonts/
$PY -I scripts/web_comprimir.py                           # versiones .gz (gzip_static) y pesos -> data/pesos.json
~/Proyectos/econolabs/.venv/bin/python scripts/web_probar.py <carpeta_capturas> http://127.0.0.1:8000/
~/Proyectos/econolabs/.venv/bin/python scripts/web_probar_pantallas.py <carpeta_capturas>   # en el móvil, ¿cambia algo en cada pantalla?
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
| `data/nidos.json` | puntos `[lon, lat, temporada, mes]` 2018-2025, abril-diciembre, 3 decimales (~100 m); el mes mueve la animación de la apertura | 0 |
| `data/municipios.geojson` | 113 municipios simplificados con la tasa por 1.000 habitantes, cortes de la leyenda, tasas por tamaño y Bilbao «sin datos» | 12 |
| `data/municipios_serie.json` | por municipio: nidos por temporada, tasa, puesto, días de retirada | 13 (buscador) |
| `data/apertura.json` | avisos por temporada y mes (todos, con y sin coordenadas: el contador), municipios con avisos por temporada, el primero de cada temporada y los que más avisos tienen en 2019-2025 | apertura |
| `data/comarcas.geojson` | 7 comarcas de Eustat sin Bilbao: nidos por km² y año, por 1.000 habitantes, % retirado después del 1/11 (outputs/avispa_comarcas_resumen.csv) | comarcas |
| `data/densidad.geojson` | isobandas de nidos avisados por km² y año (cortes 0,5 / 1 / 2 / 3,5 / 5,5), una capa por temporada 2019-2025 y la media; sin Bilbao | mapa |
| `data/contorno.geojson`, `data/lugares.geojson` | contorno de Bizkaia; comarcas de Eustat (polo de inaccesibilidad) y cabeceras | mapa |
| `data/relieve.webp`, `data/relieve.json` | relieve sombreado (Copernicus DEM GLO-90) en grados, con su caja | mapa |
| `data/situacion.geojson` | península y Bizkaia (Natural Earth 1:50 m) | mapa |
| `data/nido_hilo.json` | nido real de 2025 que acompaña la historia, con el criterio de elección | mapa, 2, 6 |
| `data/censo_ilustracion.json` | ventana de Morga: nidos avisados en 2025 y 4 «nidos fantasma» por aviso (ilustración) | censo |
| `data/mapa_base/` | `bizkaia.pmtiles` (25,9 MB, z0-12), glifos Noto Sans y `mapa_base.json` (build, versión, fecha, SHA-256) | censo |
| `data/imagenes.json`, `img/` | fotos adaptadas y sus créditos (autor, licencia, enlace, parámetros de la adaptación); `img/creditos_imagenes.csv` | 1, 2 |
| `data/descargas/*.csv` | datos procesados descargables | – |
| `vendor/` | D3 7.9.0, Scrollama 3.2.0, MapLibre GL JS 4.7.1, pmtiles 4.4.1, @protomaps/basemaps 5.7.2 y `fonts/` (con licencias y SHA-256) | – |

## Estructura

```
index.html            escenario del mapa (fijo), portada, paradas (las crea js/app.js), explorador, cierre y pie
metodologia.html      lee su texto de content/es.json (metodologia, creditos, descargas) y los créditos de cartografía y fotos
content/es.json       TODO el texto: pasos del guion, paradas (pregunta, entradilla, pasos), campo «hilo» por paso, interfaz
css/estilo.css        estilos, paleta y escala tipográfica (--t-*: escritorio / móvil) en variables CSS; móvil primero
js/app.js             arranque: paradas, paneles, navegación, barra de lectura y Scrollama (pasos y su progreso)
js/util.js            formatos (es-ES), tamano() de la escala tipográfica, rayado, etiquetas, tablas
js/componentes/
  mapa.js             mapas de la historia: fases por paso (capa, cámara, anotación), contador, leyenda, situación
  mapa_narrativo.js   D3: relieve, isobandas por temporada, tasas, límites, rótulos, puntos en canvas, cámara con interpolateZoom
  mapa_detalle.js     MapLibre + Protomaps: zoom real a Morga con los nidos avisados y los «fantasmas» (censo)
  fondo_mapa.js       estilo del mapa base (sabor de @protomaps/basemaps con la paleta) y lectura del PMTiles
  contador.js         año en grande, nidos acumulados interpolados y barra de tiempo 2019-2025
  anotaciones.js      etiquetas con flecha curva sobre los mapas, que evitan la cabecera y la tarjeta
  esquema.js          D3 sobre fotos: línea del tiempo (paso 1), ciclo del nido (paso 2), circuito del aviso (paso 3)
  estimacion.js       D3: «Dibuja tu estimación» y revelado temporada a temporada con el scroll
  tramos.js           D3: días entre aviso y retirada (con el nido hilo)
  linea.js            D3: no eliminables, dibujada con el scroll
  mensual.js          D3: calendario de avisos (primavera / desde el 1 de noviembre)
  regiones.js         D3: Bizkaia en tinta y las demás regiones que se suman en color con el scroll
  gasto.js            D3: gasto 2017-2025, año a año con el scroll
  explorador.js       D3: buscador «Tu municipio»
```

## Paradas y pasos

`content/es.json` → `paradas`: `{ id, pregunta, entradilla, ficha, paso_siguiente, pasos: [ids] }` (guion v2: `docs/guion_v2_propuesta.md`). `ficha`: cifra clave de la ficha lateral (escritorio ancho); `paso_siguiente`: frase de paso al final de la parada. Cada paso puede llevar `titular` (antetítulo del primer paso de cada tema). Cada parada empieza con su pregunta (rótulo grande); su gráfico se queda fijo mientras pasan sus tarjetas. Cada paso:

```json
{ "id": "rapidez", "grafico": "tramos", "titulo": "Título del gráfico", "estado": {}, "texto": ["Texto del guion."],
  "nota": "Advertencia visible (opcional)", "alt": "Descripción", "hilo": "" }
```

- Los pasos son altos (`estado.alto` en svh; por defecto 150, o 220 si la parada tiene un solo paso) y su tarjeta se queda fija mientras dura: el progreso del paso (Scrollama) mueve el gráfico (`progreso(p)` en cada componente).
- Mapas: `estado.modo` = `puntos` | `censo` | `tasa` | `comarcas`, con `fases: [{ hasta, camara, capa, tiempo, anios: [desde, hasta], marcarHilo, fijo, anotacion, resaltar, fantasmas, medida }]`. Cámaras: `bizkaia`, `maximo`, `bilbao`, `censo`, `morga`, `mungia`. `medida` (comarcas): `km2` | `hab` | `tarde`.
- `hilo`: texto del nido hilo para ese paso (lo escribe el coordinador). Vacío = marcador apagado. Se usa en la apertura (aparece al llegar a septiembre de 2025), el censo, el ciclo (anillo a 7 m con 50 cm) y la rapidez (2025, tramo de 1-3 días).

En el móvil el gráfico ocupa el 58 % superior y la tarjeta se queda abajo; en los mapas, mapa a pantalla completa con la cabecera (contador y leyenda) arriba. En escritorio, tarjetas a la izquierda y gráfico grande a la derecha; en los mapas, tarjetas alternando lados. Alturas en `svh`.

## Decisiones visibles

- Periodo 2019-2025 y avisos de abril a diciembre; 2018, rayado en gris con «registro incompleto».
- Bilbao, rayado y «sin datos (servicio municipal propio)» en el mapa y en el buscador; fuera de las tasas y los puestos.
- Como mucho tres colores de serie por gráfico (naranja = avispa, azul = acción pública, gris = contexto), etiquetas directas, halo del color del fondo en las etiquetas.
- Pasos 1 y 2 con fotos reales de Wikimedia Commons (CC BY-SA), adaptadas (recortadas y retocadas, misma licencia), con el crédito al pie de cada foto, en el pie de la página y en la metodología.
- Censo: los «nidos fantasma» son una ilustración (4 por aviso, posiciones al azar con semilla fija) y lo dicen en el propio mapa.
- Contador de nidos del mapa: nidos **con coordenadas** (17.729 en 2019-2025; el texto habla de los 18.098 avisos, con los que no tienen coordenadas).

## Rendimiento (medido el 08/11/2026 con `scripts/web_comprimir.py` y `scripts/web_probar.py`)

- **Primera pintura**: la portada (título, subtítulo, firma) y una imagen estática del mapa (`data/portada.webp`, 47 KB, mismo encuadre que el mapa vivo) salen al instante: CSS crítico en línea, la hoja completa sin bloquear, `preload` de las dos variantes de Source Serif 4, `font-display: swap`, `cargador.js` con `defer`. **98 KB comprimidos** hasta que la portada se ve y se puede usar.
- **Mapa vivo de la portada**: D3, Scrollama, módulos del mapa y sus datos llegan después, sin bloquear, y el mapa aparece con un fundido sobre la imagen estática: **598 KB comprimidos** en total (el relieve, 124 KB; los nidos, 85 KB; la densidad, 61 KB). No llega al objetivo de 300 KB: el mapa animado necesita los 21.000 puntos y las bandas.
- **Por paradas**: cada parada importa su módulo (`import()`) y pide sus JSON cuando está a 1,5 pantallas (IntersectionObserver); el explorador, igual; MapLibre, pmtiles y basemaps (229 KB comprimidos) solo cuando se acerca el paso del censo. Mientras tanto, esqueleto con brillo del tamaño del gráfico, «Cargando datos…» a los 2 s y, si falla, mensaje y «Reintentar».
- **Total** comprimido (sin el PMTiles): 3,1 MB; el PMTiles (25 MB) se lee por rangos.
- Red limitada (4G lenta simulada, Playwright): primera pintura con contenido a los 288 ms en el servidor local, CLS acumulado 0,054 (por debajo de 0,1). Capturas `lenta_*.png`.
- Coordenadas: nidos y bandas de densidad con 3 decimales (unos 100 m). Imágenes WebP con `width`/`height`, `loading="lazy"` (salvo la portada) y fondo del color dominante.

## Accesibilidad

Contraste AA, letra mínima de 13 px, controles nativos, texto alternativo por paso (con un resumen generado de los datos) anunciado con `aria-live`, tabla con los datos de cada gráfico («Ver los datos del gráfico»), estimación con teclado (flechas), sin animaciones con `prefers-reduced-motion`, gestos cooperativos en el mapa.

## Pendiente

- Autoría y fecha definitivas (`meta`), y enlace al repositorio de código (ahora «Código» lleva a la lista de scripts de la metodología).
- Traducción al euskera (`content/eu.json`).
- Modo oscuro (paleta validada en `docs/paleta_colores.md`, sin aplicar).
- Ficha lateral con la cifra clave de cada parada, buscador con tendencia del municipio frente a Bizkaia y comarca, banda de incertidumbre (ver `docs/diseno_web.md`).
- Revisión en un móvil real.
