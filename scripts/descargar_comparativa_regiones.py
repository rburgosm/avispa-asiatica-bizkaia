"""Descarga las páginas web (notas oficiales y prensa) que sostienen las cifras de nidos
por año de otras regiones usadas en scripts/avispa_comparativa_regiones.py.

Uso: python -I scripts/descargar_comparativa_regiones.py data/raw/externos

Cada página se guarda en data/raw/externos/<carpeta>/<nombre>.html. Si una web bloquea la
descarga (403/429), se anota en <carpeta>/_fallos.txt y la cifra queda marcada en el análisis
como «no verificable en local».
"""
import sys
from pathlib import Path

import urllib.error
import urllib.request

FUENTES = {
    "galicia_xunta": {
        "nota_2020_16700": "https://www.xunta.gal/es/hemeroteca/-/nova/115920/xunta-retiro-este-ano-mas-16-700-nidos-vespa-velutina-marco-del-plan-llevado",
        "nota_2021_14600": "https://www.xunta.gal/hemeroteca/-/nova/139094/xunta-retirou-este-ano-mais-14-600-ninos-vespa-velutina-marco-plan-posto-marcha",
        "nota_2022_22200": "https://www.xunta.gal/notas-de-prensa/-/nova/76402/xunta-retirou-ano-pasado-mais-22-200-ninos-vespa-velutina-marco-plan-acordado",
        "nota_2025_131000": "https://www.xunta.gal/notas-de-prensa/-/nova/018491/plan-centralizado-xunta-acordado-cos-concellos-permitiu-retirada-mais-131-000",
        "eldebate_2026_24500": "https://www.eldebate.com/espana/galicia/20260425/xunta-destina-17-millones-euros-campana-retirada-nidos-velutina_409825.html",
    },
    "jersey_prensa": {
        "islandfm_2026": "https://www.islandfm.com/news/jersey/asian-hornet-queens-and-nests-this-year-double-2025s-numbers/",
        "bbc_2025_694": "https://www.bbc.co.uk/news/articles/cgr147vewneo",
        "itv_2022_record": "https://itv.com/news/channel/2022-09-27/record-number-of-asian-hornet-nests-found-in-jersey",
        "islandfm_record_year": "https://islandfm.com/news/jersey/a-record-year-for-asian-hornets-already",
        "jep_2023_08_23": "https://jerseyeveningpost.com/news/2023/08/23/number-of-asian-hornet-nests-found-in-jersey-passes-last-years-record/",
        "bailiwick_2023_338": "https://www.bailiwickexpress.com/news/first-hornets-nest-year/",
        "jep_2024_01_03": "https://www.jerseyeveningpost.com/news/2024/01/03/surprise-as-first-ever-active-hornet-nest-in-january-is-found/",
        "islandfm_spike": "https://www.islandfm.com/news/jersey/spike-in-discovery-of-asian-hornet-nests",
        "jep_2022_record_numbers": "https://jerseyeveningpost.com/?p=1215878",
    },
    "cantabria_prensa": {
        "agronews_coordinacion": "https://www.agronewscastillayleon.com/el-gobierno-de-cantabria-y-los-ayuntamientos-apuestan-por-la-maxima-coordinacion-en-la-lucha-contra",
        "agronews_stop_velutina": "https://www.agronewscastillayleon.com/el-gobierno-de-cantabria-expone-stop-velutina-las-medidas-que-esta-tomando-para-frenar-la-presencia",
    },
    "portugal_prensa": {
        "cmjornal_2025_175mil": "https://www.cmjornal.pt/sociedade/detalhe/destruidos-175-mil-ninhos-de-vespa-asiatica",
    },
    "catalunya": {
        "govern_2018_01_26": "https://govern.cat/govern/docs/2018/01/26/14/10/def4d8be-2533-4c52-90c4-8e6dc83b9a2e.pdf",
    },
}

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"}


def main(base):
    for carpeta, urls in FUENTES.items():
        d = Path(base) / carpeta
        d.mkdir(parents=True, exist_ok=True)
        fallos = []
        for nombre, url in urls.items():
            ext = ".pdf" if url.lower().endswith(".pdf") else ".html"
            destino = d / f"{nombre}{ext}"
            if destino.exists() and destino.stat().st_size > 2000:
                continue
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                    contenido = r.read()
                destino.write_bytes(contenido)
                print("ok", destino, len(contenido))
            except urllib.error.HTTPError as e:
                fallos.append(f"{e.code}\t{url}")
            except (urllib.error.URLError, TimeoutError) as e:
                fallos.append(f"error {type(e).__name__}\t{url}")
        (d / "_fallos.txt").write_text("\n".join(fallos) + ("\n" if fallos else ""))
        for f in fallos:
            print("FALLO", carpeta, f)


if __name__ == "__main__":
    main(sys.argv[1])
