"""Descarga las fuentes externas a Open Data Bizkaia que usan los análisis (y las de lectura documental).

Uso:
    python -I scripts/descargar_externos.py [--raiz data/raw] [--grupos g1 g2 ...] [--forzar] [--lista]

Antes del 08/11/2026 estos ficheros se bajaron a mano; este script los reproduce. Cada fichero se
guarda en <raiz>/<ruta> (si ya existe y no se pide --forzar, no se vuelve a bajar) y se compara con
la huella de la descarga original (SHA-256 del 07-08/11/2026, en REFERENCIA):
- «igual»: mismos bytes.
- «equivalente»: bytes distintos pero mismo contenido (JSON con los mismos datos, la misma
  geometría y atributos fijos en GeoJSON, el mismo texto visible en HTML), según la comprobación
  propia de cada fuente. Necesita la copia original (--original <carpeta>).
- «DISTINTO»: el servidor ya no sirve lo mismo; se explica en la nota de la fuente.
Escribe <raiz>/externos/_descargas_externas.tsv con ruta, URL, bytes, SHA-256 y resultado.

Grupos (por defecto todos menos «euskalmet», que pesa 1,1 GB):
- ine: padrón municipal de Bizkaia, tabla 2905 del INE (API JSON Tempus3). nult=1 (último año,
  lo usan explorar_avispa.py y avispa_estabilizacion.py) y nult=9 (2017-2025, el resto).
- regiones: informes oficiales de Asturias (2018-2025, sin 2020, que no se publicó) y de Araba
  (2012-2024), manual del Gobierno Vasco (2016) y página de gov.uk con los avistamientos del
  Reino Unido. Los leen avispa_comparativa_regiones.py, digitalizar_asturias.py y
  avispa_validacion_estacionalidad.py.
- gbif: facetas por mes y año (2004-2025) del conjunto GBIF 9fd6c3da (MNHN, Francia) y su ficha,
  para avispa_validacion_estacionalidad.py.
- geo_bizkaia: servicio REST de la Diputación (geo.bizkaia.eus): playas (puntos) y municipios
  del catastro simplificados (maxAllowableOffset=20 m), para avispa_impacto.py.
- documentales: normas y noticias de la cronología de políticas (avispa_politicas_hitos.py
  cita sus URL; avispa_politicas_textos.py extrae su texto) y fichas de bizkaia.eus. No entran
  en ningún cálculo. Los servidores de bizkaia.eus (noticias, fichas y la memoria de
  transparencia de gardentasuna.bizkaia.eus) responden a las peticiones automáticas con una
  página antirrobots (comprobado el 08/11/2026): el script lo detecta, no la guarda y lo anota
  como «BLOQUEADO»; esas copias solo se pueden obtener con un navegador.
- euskalmet: lecturas de las estaciones meteorológicas 2018-2025 (un zip por año) y su
  inventario, para clima_euskalmet_mensual.py.
"""
import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"}

INE = "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/2905?nult={n}&tip=A"
AST = "https://www.asturias.es/documents/d/guest/informe-actividad-{tipo}-{anio}"
GBIF_MNHN = "9fd6c3da-88f7-4df7-9a3f-3f3f9c703998"
GEO = "https://geo.bizkaia.eus/arcgisserverinspire/rest/services/"
CATASTRO_8 = GEO + "LurraldeAntolamendua_PlanificacionTerritorial/Katastro_Catastro_WFS/MapServer/8/query"
PLAYAS_0 = GEO + "Gizartea_Sociedad/Hondartzak_Playas/MapServer/0/query"
DFB_N = "https://www.bizkaia.eus/es/web/comunicacion/noticias/-/news/detailView/"
BIZKAIA_TEMA = "https://www.bizkaia.eus/es/tema-detalle/-/edukia/dt/"
EUSKALMET = "https://opendata.euskadi.eus/contenidos/ds_meteorologicos/"


def q(base, **p):
    return base + "?" + urllib.parse.urlencode(p)


# ------------------------------------------------------------------ comprobaciones de contenido
def json_igual(a: bytes, b: bytes) -> bool:
    return json.loads(a) == json.loads(b)


def geojson_fijo(campos_variables=()):
    """Mismas geometrías y atributos, salvo los campos que cambian solos (p. ej. el tiempo en directo)."""
    def comparar(a: bytes, b: bytes) -> bool:
        fa, fb = json.loads(a)["features"], json.loads(b)["features"]
        if len(fa) != len(fb):
            return False
        for x, y in zip(fa, fb):
            px = {k: v for k, v in x["properties"].items() if k not in campos_variables}
            py = {k: v for k, v in y["properties"].items() if k not in campos_variables}
            if x["geometry"] != y["geometry"] or px != py:
                return False
        return True
    return comparar


def texto_html(b: bytes) -> str:
    t = b.decode("utf-8", "replace")
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", t, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def html_texto_igual(a: bytes, b: bytes) -> bool:
    return texto_html(a) == texto_html(b)


def jsonl_igual(a: bytes, b: bytes) -> bool:
    la = [json.loads(x) for x in a.decode().splitlines() if x.strip()]
    lb = [json.loads(x) for x in b.decode().splitlines() if x.strip()]
    return la == lb


# ------------------------------------------------------------------ catálogo de fuentes
# (grupo, ruta relativa a la raíz, url o función que devuelve bytes, sha256 de referencia,
#  comprobación de contenido equivalente o None, nota)
def gbif_facetas() -> bytes:
    lineas = []
    for anio in range(2004, 2026):
        url = q("https://api.gbif.org/v1/occurrence/search", datasetKey=GBIF_MNHN, year=anio,
                limit=0, facet="month", facetLimit=12)
        lineas.append(get(url).decode("utf-8").strip())
        time.sleep(0.2)
    return ("\n".join(lineas) + "\n").encode("utf-8")


FUENTES = [
    ("ine", "ine/padron_bizkaia_2905.json", INE.format(n=1),
     "a3f55ba265dbd55d011812ac01ebad7ee850c05d5bb472c1e1ccb8810d80590f", json_igual,
     "último año publicado (2025); cambiará cuando el INE publique 2026"),
    ("ine", "ine/padron_bizkaia_2905_2017_2025.json", INE.format(n=9),
     "84b9e4fa007d4297d67689e5742f6732edb54d771807b84c024afdc15035e6ad", json_igual,
     "últimos nueve años (2017-2025); con el padrón de 2026 pasará a 2018-2026"),
    ("regiones", "externos/asturias/informe_2018.pdf", AST.format(tipo="velutina", anio=2018),
     "16a93ba9aa71efc4c447dd7b7d6185098bbc092e43281600bae01af7f4284aa9", None, ""),
    ("regiones", "externos/asturias/informe_2019.pdf", AST.format(tipo="velutina", anio=2019),
     "3919a54630f6ed64d0787247dedce994fa34f1fc56ba99d7c5e8e0068f95f063", None, ""),
    ("regiones", "externos/asturias/informe_2021.pdf", AST.format(tipo="velutina", anio=2021),
     "691a01dfad8638eddea1a3f263ec69ce053ac6435c79214c85761f09486bd38b", None, ""),
    ("regiones", "externos/asturias/informe_2022.pdf", AST.format(tipo="velutina", anio=2022),
     "c6e05635cf005f08c9f00b514cc9fdbe5acfbf7f9894c45d96bd4cd2850980aa", None, ""),
    ("regiones", "externos/asturias/informe_2023.pdf", AST.format(tipo="velutina", anio=2023),
     "852e6e4a392ebd76e21ea21521d3e889fb6a3a5b3221701a6f2aa0061528eb93", None, ""),
    ("regiones", "externos/asturias/informe_2024.pdf", AST.format(tipo="avispa", anio=2024),
     "fe3ad7b7721bd86f775ceb2cf049ae400f0094422f85e13eac782246af6e335b", None, ""),
    ("regiones", "externos/asturias/informe_2025.pdf", AST.format(tipo="avispa", anio=2025),
     "996184ba003142c5fa164a1dcc858dbadf4b1d1fa09f1a789a184429ca34d8e2", None, ""),
    ("regiones", "externos/araba/araba_2012_2024.pdf",
     "https://web.araba.eus/documents/d/araba/vespa-velutina-araban_2012_2024-web-pdf",
     "4b9d9193cd7e96e8f07175bfd2decb4818e0a6eb30005dd4bcd1e9c95e310c81", None, ""),
    ("regiones", "externos/politicas_avispa/gv_manual_vespa_velutina_2016.pdf",
     "https://www.euskadi.eus/contenidos/documentacion/vespa_velutina/es_def/adjuntos/vespa_velutina.pdf",
     "7a0a78801b93128922e6556cb3f57ffb094e648d2e15ee3088e2d1150032a838", None,
     "su texto (.pdf.txt) lo extrae avispa_politicas_textos.py"),
    ("regiones", "externos/uk_govuk/sightings.html",
     "https://www.gov.uk/government/publications/asian-hornet-uk-sightings/asian-hornet-sightings-recorded-since-2016",
     "a4e58fe3d2c58b17110b9a8a11bc874e4baea37eed6234c72cbf517f5076a288", html_texto_igual,
     "página viva: gov.uk la actualiza con cada avistamiento; los años cerrados (2016-2025) no deberían cambiar"),
    ("gbif", "externos/mnhn_gbif/facetas_mes_por_anio.jsonl", gbif_facetas,
     "8517ab5acef69d9eab00e007b66f8857aa706559b2f874a547c284133ebc58eb", jsonl_igual,
     "una línea por año 2004-2025 (respuesta de /occurrence/search con facet=month)"),
    ("gbif", "externos/mnhn_gbif/dataset_9fd6c3da.json", "https://api.gbif.org/v1/dataset/" + GBIF_MNHN,
     "aba1f6d98a7a5395db95657b131e183ac70e63124dd059681ff45492f040838f", None,
     "ficha del conjunto; trae fechas de modificación que cambian con cada actualización (solo informativa)"),
    ("geo_bizkaia", "bizkaia/informacion-geografica-playas/playas.geojson",
     q(PLAYAS_0, where="1=1", outFields="*", returnGeometry="true", outSR=25830, f="geojson"),
     "636b095ac82833c783f0d02cab4570eaf1e90a2a2e6ad8ed98d6f805b3694650",
     geojson_fijo(("TiempoRealMeteorologiaES", "TiempoRealMeteorologiaEU", "TiempoRealVientoES",
                   "TiempoRealVientoEU", "TiempoRealTemperaturaAmbiente", "TiempoRealFecha")),
     "los campos TiempoReal* (tiempo del día) cambian en cada descarga; no se usan"),
    ("geo_bizkaia", "bizkaia/parcelario-catastral/municipios.geojson",
     q(CATASTRO_8, where="1=1", outFields="*", returnGeometry="true", outSR=25830,
       maxAllowableOffset=20, geometryPrecision=0, f="geojson"),
     "ef8cd00759dc3e18f02bc8bad0fe8c82fde0c40a368e73e99f809724d72eb4cd", geojson_fijo(),
     "límites simplificados por el servidor (tolerancia 20 m, coordenadas enteras)"),
    ("documentales", "externos/politicas_avispa/boe_rd630_2013.pdf",
     "https://www.boe.es/boe/dias/2013/08/03/pdfs/BOE-A-2013-8565.pdf",
     "e500b19a28be9aff9428f9ba82b12db2c0ae8e592cbf7f10265a489f8159fa54", None, ""),
    ("documentales", "externos/politicas_avispa/miteco_estrategia_2015.pdf",
     "https://www.miteco.gob.es/content/dam/miteco/es/biodiversidad/publicaciones/estrategias/"
     "estrategia_vespavelutina_tcm30-69976.pdf",
     "b196e2adfa333db027144ecbbc659c26a60534e2be11384f37f057fd04c98783", None, ""),
    ("documentales", "externos/politicas_avispa/eu_reglamento_2016_1141.html",
     "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32016R1141",
     "fc3e73e3006aeae78cb91b99211f43f777b1f7b454bb3bb26b57d50ba926f2e9", html_texto_igual, ""),
    ("documentales", "externos/politicas_avispa/dfb_memoria_transparencia_2021.pdf",
     "https://gardentasuna.bizkaia.eus/documents/1261696/1267395/Memoria+2021_cas.pdf",
     "e5ef411a8036a437c9d5354818fb2a36d353682c923ca88043cb2ed9bb79aaa4", None, ""),
    ("documentales", "externos/politicas_avispa/infoagro_2013_biocidas.html",
     "https://www.infoagro.com/noticias/2013/la_eficacia_de_biocidas_contra_vespa_velutina.asp",
     "04109bd21521772428f2123a6a30c770e5103a6a831e0f55bf0eb261ac6da7b7", html_texto_igual, ""),
] + [
    ("documentales", f"externos/politicas_avispa/dfb_noticia_{n}.html", DFB_N + n, h, html_texto_igual,
     "página con menús y avisos que cambian; se compara el texto visible")
    for n, h in [("18131", "20e26561b720b4d207b7a25446ef6af8599b56b93b6b49042bcd071268da9a62"),
                 ("18164", "0d4e32b9b33f90eef0274818de003a3b91d2ff3aec53719a1d36df8ce5b4433c"),
                 ("18402", "7dc0c982087badb5c865f9e657f40ef4a69fa14708d848fb53e2aee2a60dc5eb")]
] + [
    ("documentales", f"externos/bizkaia_eus/{nombre}.html", BIZKAIA_TEMA + n, h, html_texto_igual,
     "ficha de bizkaia.eus; se compara el texto visible")
    for nombre, n, h in [
        ("protocolo_10069", "10069", "c11ad00a3f5d25a7e75d3982b1528b9fd49dd062eef30623cd89c6893252a86a"),
        ("p_10070", "10070", "0bf37b2db3b23ba2d09cc8342314bbe51ee9069672458b72f4426986e7421151"),
        ("p_10071", "10071", "c44506c6b6bfb48d84fc5176e86a4290aee704ef4871ee1160428531291ba235"),
        ("p_10072", "10072", "3d6c78e5dee6479bbc351a5b921fa9e87c5422bc3af7f2ab4ea7b32afef8b902"),
        ("p_10074", "10074", "c0b5c62ff5cf9daa9af70283a1c39bf6a45b41acbdd6914d2c58d6586234839b"),
        ("p_10075", "10075", "664f16a3fa69089659c576233044535e08667f7f71fbbfa7d77ab60453477049")]
] + [
    ("euskalmet", "externos/euskalmet/estaciones.geojson",
     EUSKALMET + "estaciones_meteorologicas/opendata/estaciones.geojson",
     "bac492b634c1f9fa595f92c8c4c1a7e7747b6294539a9390316ce32c196a395f", json_igual, ""),
] + [
    ("euskalmet", f"externos/euskalmet/{a}.zip", EUSKALMET + f"met_stations_ds_{a}/opendata/{a}.zip", h, None,
     "~140 MB")
    for a, h in [(2018, "16bba9aade26a5ab3f7a64e6da72e9d4ccee2f638178b6978f2753efbf6a3f00"),
                 (2019, "9b589aecc3744c4c72c2b105e6bef95d60bd75d133732f29cf81a785a862344a"),
                 (2020, "1bbf5b011a012115fa3c592615e1e8835d1532716caf84f69b902dc064c31c05"),
                 (2021, "e870d07d910c3409082e1b461762c7f31afb2cf21ac75a3e918031c72d4048de"),
                 (2022, "43c97b373c8064604ff4c505405c8b30bd44d9d709a3c390b518f8dbfcd92248"),
                 (2023, "799f2f28d320be23a50d24194fb89ccac569fc11a4dc69bdebf06de09ef1f22f"),
                 (2024, "0dd2235f2fefb57bc6eebad86ae73a113316e99e427c30f67b7fca71780aa037"),
                 (2025, "cb025813a9014657b1901065f881057ed8dffc7ebbaac116f9bca5238e1766c6")]
]
GRUPOS = list(dict.fromkeys(f[0] for f in FUENTES))
POR_DEFECTO = [g for g in GRUPOS if g != "euskalmet"]


def get(url, timeout=300, intentos=3):
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            if i == intentos - 1 or (isinstance(e, urllib.error.HTTPError) and e.code in (403, 404)):
                raise
            time.sleep(3 * (i + 1))


def bloqueado(ruta: str, datos: bytes) -> bool:
    if ruta.endswith(".pdf") and not datos.startswith(b"%PDF"):
        return True
    return b"Your support ID is" in datos[:20000] and b"Please enable JavaScript" in datos[:20000]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raiz", default=str(RAIZ / "data/raw"))
    ap.add_argument("--grupos", nargs="+", choices=GRUPOS, default=POR_DEFECTO)
    ap.add_argument("--forzar", action="store_true", help="vuelve a bajar aunque el fichero exista")
    ap.add_argument("--lista", action="store_true", help="solo lista las fuentes")
    ap.add_argument("--original", default=None,
                    help="carpeta con la descarga original (p. ej. otra copia de data/raw) para comprobar "
                         "si un fichero con distinto SHA-256 tiene el mismo contenido")
    a = ap.parse_args()
    raiz = Path(a.raiz)
    elegidas = [f for f in FUENTES if f[0] in a.grupos]
    if a.lista:
        for g, ruta, url, *_ in elegidas:
            print(f"{g}\t{ruta}\t{url if isinstance(url, str) else url.__name__ + '()'}")
        return
    filas, distintos, errores, bloqueados = [], 0, 0, 0
    for grupo, ruta, url, ref, equivalente, nota in elegidas:
        destino = raiz / ruta
        origen = url if isinstance(url, str) else f"{url.__name__}() (ver código)"
        if destino.exists() and destino.stat().st_size > 0 and not a.forzar:
            datos, accion = destino.read_bytes(), "ya estaba"
        else:
            try:
                datos = get(url) if isinstance(url, str) else url()
            except Exception as e:  # noqa: BLE001
                print(f"ERROR {ruta}: {e}")
                filas.append((ruta, origen, 0, "", f"ERROR {e}"))
                errores += 1
                continue
            if bloqueado(ruta, datos):
                # Página antirrobots (p. ej. bizkaia.eus a peticiones automáticas): no se guarda
                print(f"{'BLOQUEADO':10} {'el servidor devuelve una página antirrobots; no se guarda':60} {ruta}")
                filas.append((ruta, origen, len(datos), "", "BLOQUEADO (página antirrobots)"))
                bloqueados += 1
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(datos)
            accion = "descargado"
            time.sleep(0.3)
        sha = hashlib.sha256(datos).hexdigest()
        original = Path(a.original) / ruta if a.original else None
        if sha == ref:
            res = "igual"
        elif (equivalente and original and original.exists() and original.resolve() != destino.resolve()
              and hashlib.sha256(original.read_bytes()).hexdigest() == ref
              and equivalente(original.read_bytes(), datos)):
            res = "equivalente"
        else:
            res = "DISTINTO" + (f" ({nota})" if nota else "")
            distintos += 1
        filas.append((ruta, origen, len(datos), sha, res))
        print(f"{accion:10} {res[:60]:60} {ruta}")
    reg = raiz / "externos" / "_descargas_externas.tsv"
    reg.parent.mkdir(parents=True, exist_ok=True)
    with reg.open("w", encoding="utf-8") as f:
        f.write("ruta\turl\tbytes\tsha256\tresultado\n")
        for fila in filas:
            f.write("\t".join(map(str, fila)) + "\n")
    print(f"{len(filas)} ficheros; {distintos} distintos de la referencia; {bloqueados} bloqueados; "
          f"{errores} errores -> {reg}")
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
