# Tres mil nidos al año

**Qué consigue Bizkaia retirando nidos de avispa asiática, y qué no**

Memoria técnica (base 6). Reto de Periodismo de Datos de Open Data Bizkaia 2026, categoría a) Visualización de datos. Autor: Roberto Burgos. Noviembre de 2026. Web: <https://tresmilnidos.eus>.

<!-- En el PDF, la portada y el índice los compone scripts/memoria_pdf.py (título y subtítulo de web/content/es.json, bloque «meta»); lo que hay antes del primer apartado no se imprime. -->

<!-- Todas las cifras de esta memoria salen de outputs/ o de web/data/. Cada una lleva al lado un comentario con su origen. Las cifras redondeadas del texto de la web se comprueban con scripts/web_comprobar_cifras.py (36 de 36 cuadran el 08/11/2026). -->

## 1. Qué es la pieza y por qué es de visualización

«Tres mil nidos al año» es una web estática de una sola página que se recorre con el scroll. El eje son **los mapas y los gráficos interactivos**: un mapa a pantalla completa con los 21.121 nidos avisados en 2018-2025 que tienen coordenadas<!-- web/data/resumen.txt: «en el mapa 21121» (2018-2025, abril-diciembre) -->, que se anima por temporadas y meses, una superficie de densidad, mapas de comarcas y municipios, y gráficos que cambian de serie en cada paso (días hasta la retirada, nidos no eliminables, reparto mensual, curvas de otras regiones y gasto). El lector también interactúa: dibuja su estimación de los nidos de cada año antes de ver los datos reales y busca su municipio para ver su ficha (serie, tasa, puesto y días de retirada).

El texto acompaña: tarjetas breves, de unas 40 palabras de media, que dicen qué mirar en cada gráfico. El detalle del método y las limitaciones va a una página de metodología aparte (<https://tresmilnidos.eus/metodologia.html>). Por eso la presentamos a la categoría de visualización y no a la de investigación.

La historia se organiza en **seis paradas**. Cada una tiene un gráfico o un mapa fijo, se abre con una pregunta y enlaza con la siguiente con una frase de paso:

| Parada | Pregunta | Qué se ve |
|---|---|---|
| 1. Mapa | «Un nido, y otros 18.000» | El nido de Morga, los avisos que se encienden temporada a temporada, la llegada de la especie, el año de un nido, el circuito del aviso y los nidos sin avisar |
| 2. Serie por temporada | «¿Funciona la respuesta?» | Estimación del lector, nidos reales, días hasta la retirada y nidos no eliminables |
| 3. Calendario | «¿Cuándo se actúa?» | Reparto mensual de los avisos, primavera y retirados después del 1 de noviembre |
| 4. Comarcas | «¿Pasa igual en toda Bizkaia?» | Nidos por km² y por 1.000 habitantes en las 7 comarcas de Eustat, tasas por tamaño de municipio y retirada tardía por comarca |
| 5. Regiones | «¿Es Bizkaia distinta?» | Nidos por 1.000 km² de Bizkaia y otras regiones y lo que se ha probado fuera |
| 6. Gasto | «¿Cuánto cuesta?» | Gasto identificable por año, coste por nido y encargo anual a Basalan |

Cierra con «Lo que sabemos y lo que no» y con el buscador de municipios, que da también su comarca.

**El nido de Morga.** Un nido real del registro acompaña la historia: se avisó el 15/09/2025 en Morga, en un árbol a 7 m de altura, y Basalan lo retiró dos días después.<!-- web/data/nido_hilo.json: fecha_aviso 2025-09-15, fecha_retirada 2025-09-17, dias 2, altura_m 7.0, retira Basalan --> No se ha elegido a mano: `web_preparar_hilo.py` lo selecciona con un criterio fijo (nido de 2025 avisado en verano, en arbolado, retirado por Basalan, con altura, diámetro y días de retirada en torno a las medianas de 2025, en un municipio con una tasa igual o mayor que la mediana municipal, y un desempate explícito). Cumplían todos los criterios 2 nidos.<!-- web/data/nido_hilo.json: criterio y candidatos 2 --> Se publican el municipio, las fechas, la altura y el diámetro, y las coordenadas redondeadas a unos 100 m; nunca la dirección.

**Los nidos sin avisar.** En el paso «Un aviso no es un censo», el mapa dibuja 4 nidos sin avisar por cada nido avisado alrededor de Morga, a 150-900 m de cada uno.<!-- web/data/censo_ilustracion.json: por_nido 4, distancia_m [150, 900], semilla 2025 --> Es una ilustración de la proporción de Lagoa y otros (2025) en un pinar de Vigo: al menos cinco nidos reales por cada aviso, el avisado incluido. Los nidos se colocan al azar con una semilla fija; no son ubicaciones reales, y el propio mapa lo dice.

## 2. Pregunta y objetivo

**Pregunta:** ¿qué consigue el sistema público de retirada de nidos de avispa asiática de Bizkaia y qué no consigue?

La pieza responde, con datos abiertos, a seis preguntas concretas: cuántos nidos se avisan y dónde, cuánto se tarda en retirarlos, cuántos no se pueden retirar, en qué época del año llegan los avisos, cuánto cuesta y si Bizkaia se aparta de otras regiones. No atribuye causas: el protocolo actual (ayuntamiento, aplicación foral y Basalan) es de julio de 2016 y no cambia en el periodo analizado.

**Objetivo:** que cualquier persona entienda en pocos minutos lo que el registro abierto permite afirmar y lo que no, con cada cifra comprobable y los datos procesados descargables.

## 3. Conjuntos de Open Data Bizkaia utilizados

Se han usado **15 conjuntos** de Open Data Bizkaia. La lista sale de los scripts que los descargan y leen (`descargar_bizkaia.py`, `descargar_municipios_bizkaia.py`, `avispa_gasto.py` y los `avispa_*.py`).

| Conjunto | Enlace | Para qué se usa |
|---|---|---|
| Avispa asiática en Bizkaia | [avispa-asiatica](https://www.opendatabizkaia.eus/es/catalogo/avispa-asiatica) | **Conjunto principal.** Registro de avisos de nidos 2017-2025 (24.954 filas). Base de todos los mapas y gráficos salvo el de regiones y el de gasto |
| Parcelario catastral de Bizkaia | [parcelario-catastral](https://www.opendatabizkaia.eus/es/catalogo/parcelario-catastral) | Límites de los 113 municipios (capa «Municipios» del servicio del catastro foral); superficie de comarcas y municipios |
| Encomiendas de gestión | [encomiendas-gestion](https://www.opendatabizkaia.eus/es/catalogo/encomiendas-gestion) | Líneas de gasto de retirada de nidos (2017-2020) y encargo anual a Basalan del Servicio de Patrimonio Natural (gráfico de gasto y coste por nido) |
| Contratos menores | [contratos-menores](https://www.opendatabizkaia.eus/es/catalogo/contratos-menores) | Gasto relacionado: material de retirada (2017) y trajes de protección del SPEIS |
| Contratos no menores | [contratos-no-menores](https://www.opendatabizkaia.eus/es/catalogo/contratos-no-menores) | Búsqueda de gasto relacionado (vestuario del SPEIS) |
| Convenios | [convenios](https://www.opendatabizkaia.eus/es/catalogo/convenios) | Búsqueda de gasto relacionado (sin resultados de trampeo ni de retirada) |
| Subvenciones otorgadas | [subvenciones-otorgadas](https://www.opendatabizkaia.eus/es/catalogo/subvenciones-otorgadas) | Ayudas a la apicultura (contexto del gasto; no se suman al control) |
| Subvenciones | [subvenciones](https://www.opendatabizkaia.eus/es/catalogo/subvenciones) | Contraste de las ayudas concedidas con las obligaciones reconocidas |
| Plan Anual de Contratación de la Diputación Foral | [plan-anual-contratacion](https://www.opendatabizkaia.eus/es/catalogo/plan-anual-contratacion) | Búsqueda de gasto relacionado |
| Plan Anual de Contratación de Basalan | [plan-anual-contratacion-basalan](https://www.opendatabizkaia.eus/es/catalogo/plan-anual-contratacion-basalan) | Búsqueda de compras de Basalan (2024-2025; no nombra la avispa) |
| Presupuestos completos | [presupuestos-completos](https://www.opendatabizkaia.eus/es/catalogo/presupuestos-completos) | Comprobación: no hay partida propia de avispa asiática |
| Liquidación del presupuesto | [liquidacion-presupuestos](https://www.opendatabizkaia.eus/es/catalogo/liquidacion-presupuestos) | Comprobación: el encargo a Basalan figura en el programa 172103 Patrimonio Natural |
| Modificaciones presupuestarias | [modificaciones-presupuestos](https://www.opendatabizkaia.eus/es/catalogo/modificaciones-presupuestos) | Comprobación: no hay partida propia de avispa asiática |
| Informes periódicos de ejecución de presupuestos | [ejecucion-presupuestos](https://www.opendatabizkaia.eus/es/catalogo/ejecucion-presupuestos) | Comprobación del encargo a Basalan en 2025-2026 |
| Intervenciones del SPEIS | [intervenciones-speis](https://www.opendatabizkaia.eus/es/catalogo/intervenciones-speis) | Salidas de los bomberos forales por abejas y avispas, 2023-2025 (contexto de los medios; no se muestra en la pieza) |

<!-- 24.954 filas: outputs/avispa_resumen.txt («Filas: 24954»). 113 municipios: data/raw/bizkaia/municipios_catastro/FUENTE.txt. Programa 172103: outputs/avispa_gasto.txt, apartado 2. Basalan 2024-2025: outputs/avispa_gasto.txt, apartado 6. -->

Se exploraron también, y se descartaron para la pieza, `explotaciones-ganaderas`, `declaracion-superficies`, `playas`, `areas-esparcimiento` y `memoria-anual-hacienda-foral-irpf` (cruces de impacto socioeconómico en `scripts/avispa_impacto.py`).

## 4. Fuentes complementarias

Complementan el conjunto principal; ninguna lo sustituye.

| Fuente | Para qué |
|---|---|
| [INE, padrón continuo por municipio (tabla 2905)](https://www.ine.es/jaxiT3/Tabla.htm?t=2905), 2017-2025 | Habitantes de cada municipio para las tasas por 1.000 habitantes |
| [Eustat, clasificación de municipios](https://www.eustat.eus/estadisticas/tema_200162/opt_1/id_60/clasificaciones.html) y [de comarcas](https://www.eustat.eus/estadisticas/tema_200162/opt_1/id_51/clasificaciones.html) | Correspondencia oficial municipio-comarca (7 comarcas de Bizkaia) |
| [Copernicus DEM GLO-90](https://copernicus-dem-90m.s3.amazonaws.com) (DLR y Airbus, programa Copernicus) | Relieve sombreado de fondo de los mapas |
| [Protomaps](https://build.protomaps.com), con datos de © colaboradores de OpenStreetMap (ODbL) | Mapa base propio del paso de detalle, recortado a Bizkaia y alojado en la web |
| [Natural Earth](https://github.com/nvkelso/natural-earth-vector) 1:50 m (dominio público) | Mapa de situación |
| [Principado de Asturias, informes anuales sobre la avispa asiática](https://www.asturias.es/documents/d/guest/informe-actividad-avispa-2025) (2018-2025) | Serie de nidos de Asturias, reparto mensual de sus avisos y criterio del 1 de noviembre |
| [Diputación Foral de Álava, «Vespa velutina Araban 2012-2024»](https://web.araba.eus/documents/d/araba/vespa-velutina-araban_2012_2024-web-pdf) | Serie de nidos de Araba |
| [Gobierno Vasco, manual de gestión de la avispa asiática (2016)](https://www.euskadi.eus/contenidos/documentacion/vespa_velutina/es_def/adjuntos/vespa_velutina.pdf) | Nidos retirados en Gipuzkoa y en Bizkaia antes del registro abierto |
| Notas de prensa de la Xunta de Galicia (2020-2025) | Nidos retirados en Galicia: solo en el análisis comparativo, no en la pieza |
| [Reglamento de Ejecución (UE) 2016/1141](https://eur-lex.europa.eu/eli/reg_impl/2016/1141/oj) | Entrada de la especie en la lista de invasoras de la Unión |
| [Lagoa y otros (2025), *Ecosistemas*](https://doi.org/10.7818/ecos.2987) | Al menos cinco nidos reales por cada nido avisado (pinar de Vigo) |
| [Pérez-de-Heredia y otros (2017), *J. Hymenoptera Research*](https://doi.org/10.3897/jhr.60.13505) | Futuras reinas en los nidos de Bizkaia y Gipuzkoa desde mediados de octubre |
| [Rome y otros (2015)](https://doi.org/10.1111/jen.12210); [Diéguez-Antón y otros (2022)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9597825/); [Requier y otros (2019)](https://doi.org/10.1007/s10340-018-1063-0) | Ciclo de la colonia, ubicación de los nidos y depredación de abejas |
| [Keeling y otros (2017)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5524706/); [Leza y otros (2021)](https://doi.org/10.1002/ps.6264); [Noord-Brabant (2024)](https://open.brabant.nl/public/download/4ee09c55-298d-4481-a062-5c587585ecbe/46_20240603%20Beleidsevaluatie%20V1.0_geanonimiseerd.pdf); [Defra (2024)](https://deframedia.blog.gov.uk/2024/06/04/new-evidence-asian-hornets-overwintering-in-uk/) | Qué se ha probado fuera: erradicación, retirada de nidos primarios y reinas de nidos de noviembre |
| [Muséum national d'Histoire naturelle](https://frelonasiatique.mnhn.fr/home) (Haxaire y otros, 2006) | Primera detección en Francia (2004) |
| Wikimedia Commons: fotografías de Charles J. Sharp (CC BY-SA 4.0), Francis Ithurburu y Père Igor (CC BY-SA 3.0) | Imágenes de la avispa y de los nidos |

<!-- Fuentes: web/content/es.json (creditos.otras_fuentes) y docstrings de scripts/descargar_comarcas.py, web_preparar_relieve.py, web_descargar_mapa_base.py, web_preparar_situacion.py, avispa_comparativa_regiones.py; créditos de fotos en web/data/imagenes.json. -->

## 5. Proceso por fases

Todo el proceso está en scripts de Python, en `scripts/`. Ninguna cifra de la web se escribe a mano: los gráficos, las etiquetas, las notas y los textos alternativos se leen de `web/data/*.json`, que genera un script.

**Fase 1. Obtención.** `descargar_bizkaia.py` lee la ficha de cada conjunto y descarga sus CSV (`/es/dump/<id>/<nombre>?format=csv`); el registro de nidos queda además en `data/raw/bizkaia/avispa_asiatica/nidos.csv`, que es la ruta que leen los análisis. `descargar_municipios_bizkaia.py` baja los límites municipales del servicio REST del catastro foral (EPSG:25830). `descargar_comarcas.py` baja las clasificaciones de Eustat y las contrasta con la capa municipal de la Diputación. `descargar_externos.py` baja las fuentes de fuera de Open Data Bizkaia (padrón del INE, informes de Asturias y Araba, GBIF, Euskalmet y documentos de la cronología), no vuelve a bajar lo que ya existe y compara cada fichero con la huella SHA-256 de la descarga original. `descargar_comparativa_regiones.py` guarda las notas oficiales y de prensa de otras regiones. Decisión: guardar los datos brutos tal cual (`data/raw/`) y no corregirlos nunca en origen.

**Fase 2. Limpieza** (`explorar_avispa.py`, reutilizada por `avispa_llegamos_tarde.py` y por todos los análisis):

- Se deshace la doble codificación UTF-8 de los textos («Ã³» → «ó»).
- **Fechas con el día y el mes intercambiados en 2018-2022**: se corrigen 5.073 fechas de alta y 5.037 de cierre. Prueba: la correlación de Spearman entre el número correlativo de la actuación y la fecha de alta pasa de 0,54-0,59 a 0,999-1,000 en cada año; en 2023-2025, sin corrección, ya es 1,00.<!-- outputs/avispa_resumen.txt, línea «FECHAS 2018-2022 CON DÍA Y MES INTERCAMBIADOS» -->
- Fecha de cierre de relleno «9999-12-31» (161 filas): se trata como vacía.<!-- outputs/avispa_resumen.txt -->
- Se quitan las 42 filas duplicadas exactas y los avisos anulados; solo se usa la especie «avispa asiática». Quedan 22.551 avisos en 2018-2025.<!-- outputs/avispa_resumen.txt (42 duplicadas) y outputs/avispa_indicadores_control.txt («Base y limpieza»: 22551) -->
- Se anulan los 7 intervalos aviso-retirada negativos (errores de fecha) y se marcan como no válidas las alturas de 0 m o de más de 60 m.<!-- outputs/avispa_indicadores_control.txt, «Base y limpieza» -->

**Fase 3. Validación.** Antes de analizar se comprobó que las decisiones de limpieza no crean artefactos:

- El hueco de avisos de enero y febrero de 2019 ya está en el registro publicado; no lo crea la corrección de fechas (apartado 11 de `avispa_indicadores_control.txt`).
- El cambio del campo «usuario» el 1 de enero de 2023 no altera el reparto de quién avisa, pero coincide con un escalón en los nidos no eliminables.
- La estacionalidad de Bizkaia se contrastó con la de Asturias, Araba, Jersey, Reino Unido y Francia (`avispa_validacion_estacionalidad.py`).

**Fase 4. Análisis.**

- `avispa_indicadores_control.py`: indicadores por temporada (días hasta la retirada, no eliminables, quién retira, primavera, retirados después del 1 de noviembre) y sus tendencias.
- `avispa_cifras_guion.py`: perfil de los nidos según la época, reparto mensual y tasas por 1.000 habitantes según el tamaño del municipio.
- `avispa_comarcas.py`: comparación de cada comarca con el resto de Bizkaia.
- `avispa_estabilizacion.py`: nidos por temporada, ocupación por cuadrículas de 1 km² y estabilidad por municipio.
- `digitalizar_asturias.py` y `avispa_comparativa_regiones.py`: series de las regiones, densidad por 1.000 km² y tendencia en la meseta.
- `avispa_gasto.py`: búsqueda del gasto relacionado en 12 conjuntos económicos, con una expresión regular en castellano y euskera. Los 853 candidatos se clasifican con reglas explícitas, cada una con su motivo (90 incluidos), y se calcula el coste por nido.<!-- outputs/avispa_gasto.txt, primera línea -->
- `avispa_politicas_hitos.py`: cronología de medidas, cada una con su fuente y su estado de verificación.

**Fase 5. Preparación de la web.**

- `web_preparar_datos.py` lee los resultados anteriores y genera los JSON de la web y los CSV descargables. Las coordenadas se redondean a 3 decimales (unos 100 m), para no señalar viviendas concretas.
- `web_preparar_densidad.py` calcula la superficie de densidad: estimación por núcleos sobre una rejilla de 250 m, con núcleo gaussiano de 1.500 m (`scipy.ndimage`), en bandas con los mismos cortes para todas las capas.<!-- scripts/web_preparar_densidad.py: CELDA_M = 250, NUCLEO_M = 1500 -->
- `web_preparar_hilo.py` elige el nido de Morga y coloca los nidos de la ilustración. `web_preparar_relieve.py`, `web_preparar_situacion.py`, `web_descargar_mapa_base.py`, `web_preparar_portada.py` y `web_preparar_compartir.py` preparan el relieve, el mapa de situación, el mapa base, la imagen de portada y las imágenes y metadatos para compartir.
- `web_descargar_librerias.py` y `web_descargar_fuentes.py` copian las librerías y las tipografías a la propia web, con versión fija y huella SHA-256. La web funciona sin CDN, sin claves de API y sin llamadas a terceros.

**Fase 6. Comprobación de cifras.**

- `web_preparar_datos.py` recalcula las tablas de la web y comprueba que coinciden con los CSV de los análisis (`web/data/resumen.txt`).
- `web_comprobar_cifras.py` comprueba cada cifra redondeada de los textos («más de 18.000», «entre el 16 % y el 24 %») contra los JSON. El 8 de noviembre de 2026 cuadraban las 36.<!-- salida de scripts/web_comprobar_cifras.py: «36 de 36 cifras del texto cuadran con los datos» -->
- `web_probar.py` (Playwright) recorre la web en el móvil y en el escritorio y registra errores de consola, peticiones fallidas y textos que se salen de los gráficos.

## 6. Métodos estadísticos y decisiones

- **Periodo 2019-2025.** 2018 es el primer año del registro y está incompleto: empieza en abril, tiene un 16 % de avisos sin coordenadas y la altura no se anotaba (figura como 0). Se muestra rayado en gris y queda fuera de las tendencias y de las medias. **Análisis de sensibilidad:** cada tendencia se repite con 2018. La de los nidos no eliminables es significativa en 2019-2025 (razón de probabilidades por año 0,901; IC 95 %: 0,841-0,965) y deja de serlo con 2018 (0,948; IC 95 %: 0,888-1,012).<!-- outputs/avispa_indicadores_control.txt, apartado 2 -->
- **Abril-diciembre.** Hasta 2022 los registros anuales no siguen el año natural: el de 2019 termina el 04/02/2020 y el de 2020 empieza el 13/02/2020. Además, no hay avisos en enero y febrero de 2019. Por eso los avisos de enero a marzo no son comparables entre años y se apartan (416 en 2018-2025). Base del periodo principal: 18.098 avisos.<!-- outputs/avispa_indicadores_control.txt, apartados «Base y limpieza» y 11; 18098 en web/data/resumen.txt -->
- **Bilbao** tiene un servicio municipal propio de retirada de nidos: aparece con 3 avisos en 2019-2025. En los mapas y en el buscador figura como «sin datos (servicio municipal propio)», nunca como cero, y queda fuera de las tasas, de los puestos y de la comarca del Gran Bilbao.<!-- outputs/avispa_comarcas.txt, «Base» -->
- **Comarcas de Eustat** (7), asignadas por el municipio del aviso con la clasificación oficial de Eustat, idéntica en pertenencia a la capa municipal de la Diputación. Cada comarca se compara con el resto de Bizkaia (sin Bilbao) mediante modelos cuasi-Poisson (razón de tasas) y cuasibinomiales (razón de probabilidades) con efectos de temporada, corrigiendo los valores p por comparaciones múltiples con el método de Holm. Gran Bilbao (sin Bilbao) tiene 2,7 veces más nidos por km² que el resto, pero por habitante el orden se invierte: 9,1 nidos al año por 1.000 habitantes en Arratia-Nervión y 1,6 en Gran Bilbao. Después del 1 de noviembre se retira el 30 % de los nidos en Markina-Ondarroa y el 27 % en Encartaciones, frente al 20 % del conjunto.<!-- outputs/avispa_comarcas.txt: RR km2 Gran Bilbao 2.68; /1000hab 9.12 y 1.63; >=1/11 30.1 %, 27.0 %, Bizkaia sin Bilbao 20.4 % -->
- **Tasas por 1.000 habitantes:** avisos de 2019-2025 divididos entre la suma de los habitantes de cada año (padrón del INE). El tamaño del municipio se fija con el padrón de 2025.
- **Proporciones** (no eliminables, retirados en 7 días o menos, primavera, después del 1 de noviembre): modelo lineal generalizado cuasibinomial con la temporada como unidad, por la sobredispersión entre años. Se da la razón de probabilidades por año con su IC 95 %; algunos modelos se ajustan además por el mes del aviso.
- **Tendencia de los nidos, dos modelos que difieren.** Con una regresión log-lineal (mínimos cuadrados de log(nidos) sobre la temporada, avisos de abril a diciembre) los nidos suben un 7,0 % al año (IC 95 %: 2,3 %-12,0 %).<!-- web/data/indicadores.json: tendencia.crecimiento_anual 0.0701, crecimiento_ic95 [0.0226, 0.1197], p 0.0122 --> Con una binomial negativa (todos los avisos de la temporada) suben un 6,9 % al año, pero con un intervalo del −1,6 % al 16,1 %, que no es concluyente.<!-- outputs/avispa_estabilizacion.txt: «Tendencia desde 2019 (binomial negativa): +6.9 % al año (IC 95 %: -1.6 % a +16.1 %; p = 0.117)» --> La estimación central es casi la misma; lo que cambia es la dispersión. La log-lineal la estima con los siete puntos (5 grados de libertad). La binomial negativa la fija de antemano (α = 0,05, equivalente a una variación de en torno al 22 % entre años)<!-- scripts/avispa_estabilizacion.py, línea 118: NegativeBinomial(alpha=0.05); sqrt(0.05) ≈ 0.22 -->, más de lo que se observa (coeficiente de variación del 16 %).<!-- outputs/avispa_estabilizacion.txt: «Coeficiente de variación 2019-2025: 0.16» --> Con siete temporadas, ninguna de las dos es mejor que la otra, y la pieza da las dos. Entre 2019 y 2025 los avisos de avispa asiática crecen un 62 % y los de avispa común, un 117 %.<!-- web/data/indicadores.json: avisos_asiatica 1990 -> 3222; avisos_comun 127 -> 276 --> Además, la subida puede deberse en parte a que se avisa más: el peso de la avispa asiática frente a la avispa común en los avisos baja (razón de probabilidades por año 0,940; IC 95 %: 0,905-0,975).<!-- outputs/avispa_indicadores_control.txt, apartado 7 -->
- **Días hasta la retirada:** fecha de cierre menos fecha de aviso, en días enteros, porque las fechas no traen hora. En 2019-2025 la mediana es de 2 días y el 92 % se retira en 7 días o menos (16.562 nidos).<!-- web/data/resumen.txt: «n=16562 ... <=7 días 0.9225, mediana 2» -->
- **Nido tardío:** nido retirado a partir del 1 de noviembre, el criterio de Asturias para un nido que ha podido soltar reinas. Son entre el 16 % y el 24 % según el año.<!-- web/data/indicadores.json: pct_elim_despues_1nov 2019-2025 = 0,156-0,237 --> Se dice siempre «ha podido», nunca «ha soltado».
- **Coste por nido:** solo se puede calcular con las líneas de la encomienda que nombran meses (2018-2019), divididas entre los nidos que Basalan cerró en esos meses: de 68 a 98 euros por nido.<!-- outputs/avispa_gasto.txt, apartado 3 a) --> El escenario de 2021-2025 al coste de 2018 se presenta como escenario, no como dato.
- **Regiones:** cada serie se divide entre la superficie de la región y se alinea por los años desde la primera detección. En la meseta, Bizkaia (2019-2025) tiene una media de 1.191 nidos por 1.000 km² y Asturias (2021-2025), 1.021.<!-- outputs/avispa_comparativa_regiones.txt, «Densidad media en la meseta» -->

## 7. Herramientas (todas libres)

| Uso | Herramienta y versión |
|---|---|
| Lenguaje | Python 3.12.3 |
| Datos y estadística | pandas 3.1.0, NumPy 2.5.4, SciPy 1.18.1, statsmodels 0.15.0 |
| Geometría | GeoPandas 1.2.0, Shapely 2.2.0, pyproj 3.8.0 |
| Imágenes y figuras de control | Matplotlib 3.11.2, Pillow 13.0.0, fontTools 4.68.0 |
| Texto de los PDF de otras regiones | pdftotext (Poppler 24.02.0) |
| Mapa base | go-pmtiles 1.31.2 (CLI), build de Protomaps del 07/11/2026 |
| Web | D3 7.9.0, Scrollama 3.2.0, MapLibre GL JS 4.7.1, PMTiles 4.4.1, @protomaps/basemaps 5.7.2 |
| Tipografías | Source Serif 4 y Source Sans 3 (Fontsource 5.2.5, SIL Open Font License) |
| Pruebas de la web | Playwright con Chromium |
| Esta memoria | Python-Markdown 3.11.3, WeasyPrint 70.0 y Pillow 13.0.0 para la portada (`scripts/memoria_pdf.py`) |

<!-- Versiones: entorno ~/Proyectos/observatorio-patinetes/.venv (importlib, 08/11/2026); web/vendor/VERSIONES.txt; web/vendor/fonts/VERSIONES.txt; web/data/mapa_base/mapa_base.json; .venv del proyecto para markdown y weasyprint. -->

## 8. Limitaciones del dato

- **Son avisos, no un censo.** Dependen de que alguien vea el nido y avise. En un pinar de Vigo había al menos cinco nidos reales por cada nido avisado.
- **Solo hay siete temporadas comparables** (2019-2025). Las tendencias tienen poca potencia, y un p > 0,05 no demuestra que no haya cambio.
- **Ruptura de registro el 1 de enero de 2023.** Ese día el campo «usuario» pasa de «AYUNTAMIENTO \<municipio\>» a un «AYUNTAMIENTO» genérico. La bajada de los nidos no eliminables (del 9,5 % en 2019-2022 al 6,2 % en 2023-2025) es un escalón justo en esa fecha, así que no se puede presentar como una mejora.<!-- outputs/avispa_indicadores_control.txt, apartado 10 -->
- **Fechas corregidas.** En 2018-2022 la corrección del día y el mes se apoya en el número correlativo de la actuación. Sin ella, las medianas de espera salían de 30 a 90 días, que son falsas.
- **Gasto:** desde 2021 la retirada va sin desglose dentro de un encargo anual a Basalan de 2,1 a 2,7 millones de euros, cuyo contenido además cambia entre años.<!-- outputs/avispa_gasto.txt, apartado 2: 2.100.000-2.737.000 € en 2021-2025 --> Desde 2019, los contratos menores no traen el objeto del contrato. El coste por nido de 2017-2019 es una estimación: hay meses sin línea propia y las líneas de 2019 vienen cortadas a 60 caracteres.
- **Regiones:** las series miden cosas distintas (avisos, nidos detectados, nidos retirados) y el esfuerzo de búsqueda cambia entre regiones. Solo sirven para comparar órdenes de magnitud.
- **Tamaño y altura de los nidos:** los anota quien avisa o quien acude; no consta si se miden o se estiman, y se redondean.
- **Mapa:** las coordenadas se redondean a unos 100 m y faltan 965 avisos sin coordenadas, casi todos de 2018 y 2019. Sí cuentan en las series, en las tasas y en el buscador.<!-- web/data/resumen.txt: «sin coordenadas 965» -->
- **No hay datos de 2026.** El conjunto «Avispa asiática en Bizkaia» figura en el portal como actualizado el 29/07/2026, pero los avisos acaban el 30/12/2025 y los cierres el 15/01/2026 (la descarga del 08/11/2026 es idéntica, byte a byte, a la del 07/11/2026). La pieza no dice nada de la temporada de 2026.
- **Bilbao** no está en el registro foral, y el registro no informa del método de retirada (pértiga, biocida, plataforma) ni del coste de cada actuación.

## 9. Despliegue

La pieza está publicada en **<https://tresmilnidos.eus>** como web estática: HTML, CSS, JavaScript y ficheros de datos (`web/`), sin servidor de aplicaciones ni base de datos. Las librerías, las tipografías y el mapa base van alojados en la propia web, con versión fija, así que no hay CDN, claves de API ni llamadas a terceros. Los ficheros de texto se sirven también comprimidos (`web_comprimir.py`), y `web_preparar_compartir.py --url-base https://tresmilnidos.eus/` escribe los metadatos para compartir con la dirección absoluta. Esta memoria se descarga desde la página de metodología (`web/memoria_tecnica.pdf`).

## 10. Reproducibilidad

- **Repositorio:** <https://github.com/rburgosm/avispa-asiatica-bizkaia> (público antes de la presentación). Contiene la web, los scripts y los resultados de los análisis (`outputs/`). Código con licencia MIT; textos, gráficos y datos procesados con CC BY 4.0. Los datos brutos (`data/raw/`) no se suben: se regeneran con los scripts de descarga.
- **Datos procesados descargables** desde la propia web (`web/data/descargas/`): avisos por temporada y mes, indicadores por temporada, ficha por municipio y nidos con coordenadas redondeadas.
- **Huella del conjunto principal:** la descarga del 08/11/2026 del recurso «Datos de nidos de avispa asiática» (6.631.908 bytes) tiene el SHA-256 `2da62168e1f298013b2590ecd025b1c45341fa70915638cc094d5fcaba4fc6d4`. Sirve para comprobar que se parte del mismo fichero.

**Regenerarlo todo.** `scripts/reproducir.py` ejecuta los 42 pasos en orden, en cuatro fases (descarga, análisis, web y comprobación), con el mismo intérprete y la opción `-I`; si un paso falla, se detiene y dice cuál. Requisitos: Python 3.12 con las librerías del apartado 7 (más openpyxl) y `pdftotext` y `pdftoppm` (poppler-utils).

```
python -I scripts/reproducir.py                  # todo, con descargas (unos 2,3 GB la primera vez)
python -I scripts/reproducir.py --sin-descargas  # usa data/raw/ tal como está
python -I scripts/reproducir.py --lista          # solo enseña los pasos y sus órdenes
.venv/bin/python -I scripts/memoria_pdf.py       # esta memoria en PDF
python -I scripts/web_copiar_memoria.py          # copia el PDF a la web
```

La página de metodología de la web (`web/metodologia.html`) recoge las mismas definiciones, decisiones y limitaciones para el público general.
