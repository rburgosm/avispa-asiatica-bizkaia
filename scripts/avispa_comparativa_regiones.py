"""Comparativa de la curva anual de nidos de Vespa velutina de Bizkaia con otras regiones.

Pregunta: ¿la curva de Bizkaia (llegada, subida y meseta) se parece a la de regiones con
otras políticas, lo que apuntaría a que manda la biología, o se aparta de ellas?

Uso:
    python -I scripts/avispa_comparativa_regiones.py data/raw/externos outputs

Entradas (descargadas antes):
- data/raw/externos/asturias/informe_AAAA.pdf: informes anuales del Principado (cifras
  extraídas aquí con expresiones regulares).
- data/raw/externos/araba/araba_2012_2024.pdf: informe de la DFA (se comprueba que la
  secuencia del gráfico «Evolución del nº de nidos» está en el texto).
- data/raw/externos/politicas_avispa/gv_manual_vespa_velutina_2016.pdf.txt: tabla 2 del
  manual del Gobierno Vasco (Gipuzkoa, Bizkaia y Álava 2012-2015).
- data/raw/externos/uk_govuk/sightings.html: nidos destruidos confirmados en el Reino Unido.
- data/raw/externos/{galicia_xunta,jersey_prensa,cantabria_prensa,portugal_prensa,catalunya}/:
  notas oficiales y prensa (scripts/descargar_comparativa_regiones.py). Para cada cifra se
  guarda la frase literal y se comprueba que está en el fichero descargado.

Salidas: avispa_comparativa_regiones.csv, avispa_comparativa_meseta.csv (densidad media en la
meseta, para la web), avispa_comparativa_regiones.txt y avispa_comparativa_regiones.png
(gráfico de prueba).

No es un análisis causal: las series miden cosas distintas (avisos, nidos detectados,
nidos retirados por un operativo concreto) y el esfuerzo de búsqueda cambia entre regiones.
"""
import html
import re
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

# Superficie en km² (INE / ONS / States of Jersey; redondeada)
SUPERFICIE = {
    "Bizkaia": 2217, "Gipuzkoa": 1980, "Araba": 3037, "Asturias": 10604,
    "Galicia": 29575, "Cantabria": 5321, "Cataluña": 32108, "Jersey": 118,
    "Portugal continental": 89015,
}
# Año de la primera detección (individuo o nido) en cada región
LLEGADA = {
    "Bizkaia": 2012,     # primer ejemplar confirmado (10/04/2012); primeros nidos retirados en 2013
    "Gipuzkoa": 2010,    # Irún, 2010 (manual GV 2016)
    "Araba": 2012,       # 2 nidos en 2012 (DFA)
    "Asturias": 2014,    # San Tirso de Abres (informe 2018)
    "Galicia": 2012,     # primeros ejemplares en 2012 (informe Asturias 2018)
    "Jersey": 2016,      # agosto de 2016 (JEP)
    "Reino Unido": 2016, # primer nido destruido en 2016 (gov.uk)
    "Cataluña": 2012,    # Generalitat, 26/01/2018
    "Cantabria": None,
    "Portugal continental": 2011,
}
URL = {
    "odb": "https://www.opendatabizkaia.eus (conjunto avispa-asiatica)",
    "dfb2015": "https://www.agronewscastillayleon.com/la-diputacion-de-bizkaia-ha-retirado-ya-135-nidos-de-vespa-velutina-entre-mayo-y-junio",
    "dfb2017": "https://www.bizkaia.eus/es/web/comunicacion/noticias (22/02/2018, balance de 2017)",
    "gv2016": "https://www.euskadi.eus/contenidos/documentacion/vespa_velutina/es_def/adjuntos/vespa_velutina.pdf",
    "dfa": "https://web.araba.eus/documents/d/araba/vespa-velutina-araban_2012_2024-web-pdf",
    "ast": "https://www.asturias.es/documents/d/guest/informe-actividad-{tipo}-{anio}",
    "uk": "https://www.gov.uk/government/publications/asian-hornet-uk-sightings",
}


def texto(ruta):
    ruta = Path(ruta)
    if ruta.suffix == ".pdf":
        t = subprocess.run(["pdftotext", str(ruta), "-"], capture_output=True, text=True).stdout
    else:
        t = ruta.read_text(encoding="utf-8", errors="replace")
        t = re.sub(r"<script.*?</script>", " ", t, flags=re.S)
        t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def num(s):
    return int(s.replace(".", "").replace(" ", ""))


# ---------------------------------------------------------------- series oficiales en local
def asturias(base):
    """Nidos de V. velutina por año en Asturias, extraídos de los informes oficiales."""
    filas = []
    d = Path(base) / "asturias"
    for anio in range(2018, 2026):
        f = d / f"informe_{anio}.pdf"
        if not f.exists():
            continue
        t = texto(f)
        tipo = "velutina" if anio <= 2023 else "avispa"
        url = URL["ast"].format(tipo=tipo, anio=anio)
        m = re.search(r"han sido generados un total de ([\d.]+) expedientes de nidos, de los cuales "
                      r"([\d.]+) han resultado ser nidos de Vespa velutina, encontrándose activos ([\d.]+)", t)
        if m:
            filas.append(("Asturias", anio, num(m.group(2)), "nidos de V. velutina detectados (activos e inactivos)",
                          url, "oficial", f"expedientes {m.group(1)}; activos {m.group(3)}"))
            if anio == 2021:
                # «se reduce el número de nidos detectados en 144» y «(-1,56 %)»: 2020 = 9.073 + 144
                m2 = re.search(r"se reduce el número de nidos detectados en (\d+)", t)
                if m2 and "(-1,56 %)" in t:
                    n20 = num(m.group(2)) + int(m2.group(1))
                    filas.append(("Asturias", 2020, n20, "nidos de V. velutina detectados (activos e inactivos)",
                                  url, "oficial (derivado)",
                                  f"no hay informe de 2020 en local: 9.073 + 144 (informe 2021); cuadra con -1,56 % ({144 / n20:.2%})"))
            continue
        m = re.search(r"verificados un total de ([\d.]+) avisos, de los cuales han resultado ser nidos activos de Vespa velutina ([\d.]+)", t)
        if m:
            nota = "solo del 1 de agosto al 31 de diciembre (inicio del operativo)" if anio == 2018 else "del 1 de abril al 31 de diciembre"
            filas.append(("Asturias", anio, num(m.group(2)), "nidos activos verificados (sin inactivos)",
                          url, "oficial", f"avisos verificados {m.group(1)}; {nota}"))
            if anio == 2018 and "aproximadamente 500 nidos" in t:
                filas.append(("Asturias", 2017, 500, "nidos detectados (aproximado)", url, "oficial",
                              "«En 2017 han sido ya detectados en Asturias aproximadamente 500 nidos» (informe 2018)"))
    return filas


def araba(base):
    t = texto(Path(base) / "araba" / "araba_2012_2024.pdf")
    grafico = [2, 6, 24, 164, 426, 268, 663, 350, 392, 391, 498, 316, 439]
    # Comprueba que los valores del gráfico aparecen en el texto del PDF
    faltan = [v for v in grafico if not re.search(rf"\b{v}\b", t)]
    assert not faltan, f"Araba: valores no encontrados {faltan}"
    filas = []
    diapositiva = {2019: 350, 2020: 480, 2021: 352, 2022: 498, 2023: 316, 2024: 439}
    for anio, n in zip(range(2012, 2025), grafico):
        nota = "gráfico «Evolución del nº de nidos» (pág. 27)"
        if anio == 2018:
            nota += "; diapositiva: 178 primarios + 485 secundarios"
        if anio in diapositiva and diapositiva[anio] != n:
            nota += f"; DISCREPANCIA: la diapositiva del año dice {diapositiva[anio]}"
        filas.append(("Araba", anio, n, "nidos detectados y/o eliminados", URL["dfa"], "oficial", nota))
    return filas


def gv_tabla2(base):
    t = (Path(base) / "politicas_avispa" / "gv_manual_vespa_velutina_2016.pdf.txt").read_text()
    t = re.sub(r"\s+", " ", t)
    filas = []
    m = re.search(r"Gipuzkoa 1140 278\* 882 1440", t)
    assert m, "tabla 2 del manual GV no encontrada"
    for anio, n in zip(range(2012, 2016), [1140, 278, 882, 1440]):
        filas.append(("Gipuzkoa", anio, n, "nidos retirados", URL["gv2016"], "oficial",
                      "manual GV 2016, tabla 2" + ("; 2013 «año de climatología adversa»" if anio == 2013 else "")))
    assert "Bizkaia - 14 127 2180" in t
    for anio, n in zip(range(2013, 2016), [14, 127, 2180]):
        filas.append(("Bizkaia", anio, n, "nidos retirados", URL["gv2016"], "oficial", "manual GV 2016, tabla 2"))
    return filas


def reino_unido(base):
    t = html.unescape((Path(base) / "uk_govuk" / "sightings.html").read_text(encoding="utf8"))
    t = re.sub(r"\\u003c", "<", t)
    t = re.sub(r"<[^>]+>", "\n", t)
    lineas = [l.strip() for l in t.split("\n") if l.strip()]
    ini = [i for i, l in enumerate(lineas) if l.startswith("Confirmed sightings in 2025")][1]
    anio, cuenta = None, {}
    meses = "January February March April May June July August September October November December".split()
    for l in lineas[ini:]:
        m = re.match(r"^(?:Confirmed sightings in (20\d\d)|(20\d\d): confirmed sightings)", l)
        if m:
            anio = int(m.group(1) or m.group(2))
            continue
        m = re.search(r":\s*(\d{1,2})\s+([A-Z][a-z]+)\s*[–-]\s*(?:\(.*?\)\s*)?(\d+\s+)?nests?\s+destroyed", l, re.I)
        if m and anio and m.group(2) in meses:
            cuenta[anio] = cuenta.get(anio, 0) + int(m.group(3) or 1)
    return [("Reino Unido", a, n, "nidos destruidos confirmados (búsqueda activa)", URL["uk"], "oficial",
             "recuento propio de la página; APHA da 72 en 2023" if a == 2023 else "recuento propio de la página")
            for a, n in sorted(cuenta.items())]


# ---------------------------------------------------------------- notas y prensa descargadas
NOTAS = [
    # region, año, nidos, qué mide, fichero, frase que debe estar en el fichero, url, oficial_o_prensa, nota
    ("Bizkaia", 2015, 2114, "nidos retirados (bomberos 1.754 y Basalan 360)", None, None, URL["dfb2015"],
     "prensa (cita a la DFB)", "el manual GV da 2.180 para el mismo año"),
    ("Bizkaia", 2017, 2231, "nidos retirados (Basalan 1.949, bomberos 267, ayuntamientos 15)", None, None,
     URL["dfb2017"], "oficial", "docs/avispa_politicas_cronologia.md"),
    ("Galicia", 2020, 16700, "nidos retirados por Seaga (plan Xunta-concellos)", "galicia_xunta/nota_2020_16700.html",
     "más de 16.700 nidos", "https://www.xunta.gal/es/hemeroteca/-/nova/115920/", "oficial (nota de prensa)",
     "de enero a mediados de diciembre; primer año del plan, sin todos los concellos"),
    ("Galicia", 2021, 14651, "nidos retirados por Seaga (plan Xunta-concellos)", "galicia_xunta/nota_2021_14600.html",
     "eliminou un total de 14.651 niños", "https://www.xunta.gal/hemeroteca/-/nova/139094/", "oficial (nota de prensa)",
     "hasta el 29/12/2021; 300 concellos adheridos (96 %)"),
    ("Galicia", 2022, 22223, "nidos retirados por Seaga (plan Xunta-concellos)", "galicia_xunta/nota_2022_22200.html",
     "con 10.352, seguida dos 6.899", "https://www.xunta.gal/notas-de-prensa/-/nova/76402/", "oficial (nota de prensa)",
     "suma de provincias 10.352 + 6.899 + 2.918 + 2.054; 306 concellos (98 %)"),
    ("Galicia", 2025, 24500, "nidos retirados por Seaga (plan Xunta-concellos)", "galicia_xunta/eldebate_2026_24500.html",
     "retirada de más de 24.500 nidos", "https://www.eldebate.com/espana/galicia/20260425/xunta-destina-17-millones-euros-campana-retirada-nidos-velutina_409825.html",
     "prensa (cita a la Xunta)", "«más de»; 2023 y 2024 no encontrados (acumulado oficial 2020-nov. 2025: más de 131.000)"),
    ("Jersey", 2019, 83, "nidos encontrados (voluntarios y gobierno)", "jersey_prensa/islandfm_spike.html",
     "38 in 2020 and 83 in 2019", "https://www.islandfm.com/news/jersey/spike-in-discovery-of-asian-hornet-nests", "prensa", ""),
    ("Jersey", 2020, 38, "nidos encontrados (voluntarios y gobierno)", "jersey_prensa/islandfm_spike.html",
     "38 in 2020", "https://www.islandfm.com/news/jersey/spike-in-discovery-of-asian-hornet-nests", "prensa", ""),
    ("Jersey", 2021, 63, "nidos encontrados (voluntarios y gobierno)", "jersey_prensa/islandfm_spike.html",
     "63 nests were found in the entirety of 2021", "https://www.islandfm.com/news/jersey/spike-in-discovery-of-asian-hornet-nests", "prensa", ""),
    ("Jersey", 2022, 174, "nidos encontrados (voluntarios y gobierno)", "jersey_prensa/bailiwick_2023_338.html",
     "174 nests found during 2022", "https://www.bailiwickexpress.com/news/first-hornets-nest-year/", "prensa", ""),
    ("Jersey", 2023, 338, "nidos encontrados (voluntarios y gobierno)", "jersey_prensa/bailiwick_2023_338.html",
     "now totals 338", "https://www.bailiwickexpress.com/news/first-hornets-nest-year/", "prensa", "la BBC (02/01/2024) da 335"),
    ("Jersey", 2024, 259, "nidos encontrados (voluntarios y gobierno)", "jersey_prensa/bbc_2025_694.html",
     "compared to 259 in 2024", "https://www.bbc.co.uk/news/articles/cgr147vewneo", "prensa", ""),
    ("Jersey", 2025, 694, "nidos encontrados (voluntarios y gobierno)", "jersey_prensa/bbc_2025_694.html",
     "there were 694 nests recorded in 2025", "https://www.bbc.co.uk/news/articles/cgr147vewneo", "prensa", ""),
    ("Cantabria", 2017, 2342, "nidos retirados o destruidos (enero-noviembre)", "cantabria_prensa/agronews_stop_velutina.html",
     "se han retirado o destruido 2.342 nidos", "https://www.agronewscastillayleon.com/el-gobierno-de-cantabria-expone-stop-velutina-las-medidas-que-esta-tomando-para-frenar-la-presencia",
     "prensa (cita al Gobierno de Cantabria)", "cifra suelta; parcial (hasta noviembre)"),
    ("Cataluña", 2016, 116, "nidos detectados", "catalunya/govern_2018_01_26.pdf", "enfront dels 116 localitzats en 2016",
     "https://govern.cat/govern/docs/2018/01/26/14/10/def4d8be-2533-4c52-90c4-8e6dc83b9a2e.pdf", "oficial (nota de prensa)",
     "cifra suelta; la nota dice «más del 68 %» de crecimiento, pero 370/116 es ×3,2"),
    ("Cataluña", 2017, 370, "nidos detectados", "catalunya/govern_2018_01_26.pdf", "arribant als 370 detectats",
     "https://govern.cat/govern/docs/2018/01/26/14/10/def4d8be-2533-4c52-90c4-8e6dc83b9a2e.pdf", "oficial (nota de prensa)", "cifra suelta"),
    ("Portugal continental", 2021, 31666, "nidos destruidos (ICNF, máximo de 2015-2024)", "portugal_prensa/cmjornal_2025_175mil.html",
     "2021 foi o ano com mais ninhos destruídos (31666)", "https://www.cmjornal.pt/sociedade/detalhe/destruidos-175-mil-ninhos-de-vespa-asiatica",
     "prensa (datos del ICNF)", "cifra suelta; 174.256 en 2015-2024"),
]


def notas(base):
    filas = []
    for reg, anio, n, que, fich, frase, url, ofi, nota in NOTAS:
        if fich:
            ok = frase in texto(Path(base) / fich)
            nota = (nota + "; " if nota else "") + ("frase verificada en " + fich if ok else "FRASE NO ENCONTRADA en " + fich)
            assert ok, (reg, anio, fich)
        filas.append((reg, anio, n, que, url, ofi, nota))
    return filas


def bizkaia_registro():
    # Registro abierto de Open Data Bizkaia (nidos por año natural), cifras del encargo
    n = {2018: 4067, 2019: 2026, 2020: 2632, 2021: 2181, 2022: 2537, 2023: 3016, 2024: 2870, 2025: 3222}
    return [("Bizkaia", a, v, "avisos de nidos en el registro abierto (todos los estados)", URL["odb"], "oficial",
             "2018 incompleto o no homogéneo: no se usa en la meseta" if a == 2018 else "") for a, v in n.items()]


# ---------------------------------------------------------------- análisis
def pct(x):
    return f"{x * 100:+.1f} %".replace(".", ",")


def miles(n):
    return f"{n:,.0f}".replace(",", ".")


def tendencia(df, region, desde, hasta):
    s = df[(df.region == region) & df.anio.between(desde, hasta)].sort_values("anio")
    if len(s) < 4:
        return None
    X = sm.add_constant(s.anio - desde)
    r = sm.OLS(np.log(s.nidos), X).fit()
    b, (lo, hi) = r.params.iloc[1], r.conf_int().iloc[1]
    cv = s.nidos.std(ddof=1) / s.nidos.mean()
    return dict(region=region, periodo=f"{s.anio.min()}-{s.anio.max()}", n=len(s),
                cambio_anual=np.expm1(b), ic_lo=np.expm1(lo), ic_hi=np.expm1(hi), cv=cv,
                media=s.nidos.mean())


def main(base, salida):
    salida = Path(salida)
    filas = bizkaia_registro() + gv_tabla2(base) + asturias(base) + araba(base) + reino_unido(base) + notas(base)
    df = pd.DataFrame(filas, columns=["region", "anio", "nidos", "que_mide", "fuente_url", "oficial_o_prensa", "nota"])
    # Bizkaia 2015: se queda la cifra de la DFB (2.114) y se anota la del GV
    df = df[~((df.region == "Bizkaia") & (df.anio == 2015) & (df.fuente_url == URL["gv2016"]))]
    df = df.sort_values(["region", "anio"]).reset_index(drop=True)
    df["anios_desde_llegada"] = df.apply(lambda r: r.anio - LLEGADA[r.region] if LLEGADA.get(r.region) else np.nan, axis=1)
    df["nidos_por_1000km2"] = df.apply(lambda r: round(1000 * r.nidos / SUPERFICIE[r.region], 1) if r.region in SUPERFICIE else np.nan, axis=1)
    df.to_csv(salida / "avispa_comparativa_regiones.csv", index=False)

    # Tendencia en la meseta (log-lineal): ¿sube, baja o se mantiene?
    tramos = [("Bizkaia", 2019, 2025), ("Asturias", 2020, 2025), ("Asturias", 2022, 2025), ("Araba", 2019, 2024),
              ("Galicia", 2020, 2025), ("Jersey", 2019, 2025), ("Reino Unido", 2023, 2025)]
    tend = [t for t in (tendencia(df, *x) for x in tramos) if t]

    out = ["Comparativa de nidos anuales de Vespa velutina: Bizkaia frente a otras regiones",
           "(fuentes y limitaciones en docs/avispa_comparativa_regiones.md; NO es una prueba causal)", ""]
    usable = ["Bizkaia", "Gipuzkoa", "Araba", "Asturias", "Galicia", "Jersey", "Reino Unido"]
    out.append("Series por años desde la primera detección (nidos; entre paréntesis, por 1.000 km²):")
    for reg in usable:
        s = df[df.region == reg]
        txt = ", ".join(f"a{int(r.anios_desde_llegada)}={r.nidos:,}".replace(",", ".") +
                        (f" ({r.nidos_por_1000km2:.0f})" if not np.isnan(r.nidos_por_1000km2) else "")
                        for r in s.itertuples())
        out.append(f"- {reg} (llegada {LLEGADA[reg]}; {s.que_mide.iloc[-1]}): {txt}")
    out.append("\nCifras sueltas (no forman serie): " + "; ".join(
        f"{r.region} {r.anio}: {r.nidos:,}".replace(",", ".") for r in df[~df.region.isin(usable)].itertuples()))
    out.append("\nTendencia en la fase de meseta (regresión log-lineal; cambio anual medio e IC 95 %; CV = variación interanual):")
    for t in tend:
        out.append(f"- {t['region']} {t['periodo']} (n={t['n']}): {pct(t['cambio_anual'])} al año "
                   f"[IC 95 %: {pct(t['ic_lo'])}; {pct(t['ic_hi'])}]; CV {t['cv'] * 100:.0f} %; media {miles(t['media'])}")
    biz = df[(df.region == "Bizkaia") & df.anio.between(2019, 2025)]
    ast = df[(df.region == "Asturias") & df.anio.between(2021, 2025)]
    gal = df[(df.region == "Galicia")]
    out.append("\nDensidad media en la meseta (nidos por 1.000 km²): "
               f"Bizkaia 2019-2025 {biz.nidos_por_1000km2.mean():.0f}; Asturias 2021-2025 {ast.nidos_por_1000km2.mean():.0f}; "
               f"Galicia (4 años, solo operativo Seaga) {gal.nidos_por_1000km2.mean():.0f}; "
               f"Gipuzkoa 2015 {df[(df.region == 'Gipuzkoa') & (df.anio == 2015)].nidos_por_1000km2.iloc[0]:.0f}; "
               f"Araba 2019-2024 {df[(df.region == 'Araba') & df.anio.between(2019, 2024)].nidos_por_1000km2.mean():.0f}; "
               f"Jersey 2025 {df[(df.region == 'Jersey') & (df.anio == 2025)].nidos_por_1000km2.iloc[0]:.0f}")
    (salida / "avispa_comparativa_regiones.txt").write_text("\n".join(out) + "\n")
    # Densidad media en la meseta, en CSV (la web lee de aquí las cifras del texto)
    meseta = [("Bizkaia", 2019, 2025), ("Asturias", 2021, 2025), ("Araba", 2019, 2024), ("Gipuzkoa", 2015, 2015)]
    pd.DataFrame([dict(region=r, desde=a, hasta=b, n=int(s.size), nidos_por_1000km2_media=round(s.mean(), 1))
                  for r, a, b in meseta
                  for s in [df[(df.region == r) & df.anio.between(a, b)].nidos_por_1000km2]]).to_csv(
        salida / "avispa_comparativa_meseta.csv", index=False)
    print("\n".join(out))

    # Gráfico de prueba: índice 100 = media de cada serie en sus años con dato desde a3 (meseta),
    # eje x = años desde la primera detección; escala log
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    estilos = {"Bizkaia": ("#c0392b", 2.8), "Gipuzkoa": ("#e67e22", 1.5), "Araba": ("#8e44ad", 1.5),
               "Asturias": ("#2471a3", 2), "Galicia": ("#17a589", 1.5), "Jersey": ("#7f8c8d", 1.5),
               "Reino Unido": ("#34495e", 1.2)}
    for reg, (col, lw) in estilos.items():
        s = df[df.region == reg].sort_values("anio")
        if reg == "Bizkaia":
            s = s[s.anio != 2018]
        axes[0].plot(s.anios_desde_llegada, s.nidos, "o-", color=col, lw=lw, ms=4, label=reg)
        if reg in SUPERFICIE:
            axes[1].plot(s.anios_desde_llegada, s.nidos_por_1000km2, "o-", color=col, lw=lw, ms=4, label=reg)
    for ax, tit in zip(axes, ["Nidos por año (escala log)", "Nidos por 1.000 km² (escala log)"]):
        ax.set_yscale("log")
        ax.set_xlabel("Años desde la primera detección en la región")
        ax.set_title(tit, fontsize=11)
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8, frameon=False)
    fig.suptitle("Vespa velutina: nidos por año alineados por llegada (gráfico de prueba; miden cosas distintas)", fontsize=11)
    fig.text(0.01, 0.01, "Fuentes: ODB, DFB, Gobierno Vasco, DFA, Principado de Asturias, Xunta, gov.uk; Jersey: prensa. "
             "Bizkaia 2018 excluido (registro incompleto).", fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(salida / "avispa_comparativa_regiones.png", dpi=120)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
