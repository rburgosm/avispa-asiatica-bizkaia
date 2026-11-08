"""Prepara los datos compactos de la web (web/data/) a partir de los brutos y de los resultados
de los scripts de análisis. En la web no se escribe ninguna cifra a mano: todas salen de aquí.

Uso:
    python -I scripts/web_preparar_datos.py [nidos.csv] [municipios.geojson] [carpeta_salida]

Por defecto lee data/raw/bizkaia/avispa_asiatica/nidos.csv, data/raw/bizkaia/municipios_catastro/
municipios.geojson (scripts/descargar_municipios_bizkaia.py), el padrón del INE
(data/raw/ine/padron_bizkaia_2905_2017_2025.json) y estas salidas de outputs/, que hay que
generar antes con sus scripts:

- avispa_indicadores_temporada.csv y avispa_dias_tramos.csv (scripts/avispa_indicadores_control.py)
- avispa_comparativa_regiones.csv y avispa_comparativa_meseta.csv (scripts/avispa_comparativa_regiones.py)
- avispa_gasto_anual.csv y avispa_gasto_coste_nido.csv (scripts/avispa_gasto.py)
- avispa_politicas_hitos.csv (scripts/avispa_politicas_hitos.py)
- asturias_avisos_mensual.csv (scripts/digitalizar_asturias.py)

El perfil de los nidos por época, el reparto mensual y las tasas por 1.000 habitantes se
recalculan importando las funciones de scripts/avispa_cifras_guion.py (misma base: temporadas
2019-2025, avisos de abril a diciembre). Se comprueba que coinciden con los CSV de outputs/.

Escribe en web/data/:
- indicadores.json  por temporada (2018-2025; 2018 marcada como registro incompleto): nidos
                    avisados, no eliminables, tramos de días entre aviso y retirada, quién retira,
                    primavera y retirados después del 1 de noviembre; distribución de los días
                    entre aviso y retirada de 2019-2025 (dias_distribucion).
- mensual.json      avisos por mes, de abril a diciembre (2019-2025).
- asturias_mensual.json  reparto mensual de los avisos de Asturias 2023-2025 (abril-diciembre),
                    para dibujarlo sobre el de Bizkaia.
- esquemas.json     perfil de los nidos retirados según la época (paso 2).
- regiones.json     curvas de nidos por 1.000 km² alineadas por años desde la llegada.
- gasto.json        gasto identificable en la retirada de nidos (2017-2025), coste por nido y
                    escenario de 2021-2025 al coste por nido de 2018 (no es un dato).
- cronologia.json   hitos confirmados de la cronología de medidas.
- nidos.json        puntos en columnas planas [lon, lat, temporada, mes], redondeados a
                    3 decimales (~100 m; también evita señalar viviendas concretas).
- municipios.geojson  límites simplificados (WGS84) con la tasa de nidos por 1.000 habitantes.
- municipios_serie.json  serie, tasa, puesto y días de retirada por municipio (buscador).
- descargas/*.csv   datos procesados descargables.
- meta.json y resumen.txt  procedencia, tamaños y cifras de control.

Definiciones: avispa asiática, sin anuladas ni duplicados exactos (limpieza de explorar_avispa.cargar);
temporada = año de alta, salvo altas de enero a marzo, que cuentan en la temporada anterior.
Bilbao tiene un servicio municipal propio y apenas aparece en el registro: «sin datos».
"""
import json
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import avispa_indicadores_control as control  # noqa: E402
from avispa_avisos_poblacion import padron  # noqa: E402
from avispa_cifras_guion import TEMPORADAS, base, perfil_epoca, reparto_mensual, tasas_tamano  # noqa: E402
from avispa_llegamos_tarde import preparar  # noqa: E402
from explorar_avispa import sin_tildes  # noqa: E402

OUT = RAIZ / "outputs"
DECIMALES = 3
SIMPLIFICAR_M = 40  # tolerancia de simplificación de los límites, en metros
CRS = "EPSG:25830"
INCOMPLETAS = [2018]  # primer año del registro: empieza en abril, 16 % sin coordenadas, alturas a 0
SIN_DATOS = ["BILBAO"]  # servicio municipal propio
REGIONES = ["Bizkaia", "Asturias", "Gipuzkoa", "Araba"]  # las del guion (paso 10)
CORTE_REGISTRO = "2023-01-01"  # cambio del campo «usuario» (avispa_politicas_hitos.csv)
ESTADOS_HITO = ("confirmado", "confirmado_secundaria")  # se excluye «no_confirmado»
CLASES_TASA = 5


def escribir(ruta: Path, obj) -> int:
    texto = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    ruta.write_text(texto, encoding="utf-8")
    return len(texto.encode("utf-8"))


def limpio(x, n=6):
    """Número para JSON: None si falta, entero si lo es, redondeado si no."""
    if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x):
        return None
    x = float(x)
    return int(x) if x.is_integer() else round(x, n)


def redondear(geo: dict, n: int) -> dict:
    def r(c):
        return [round(c[0], n), round(c[1], n)] if isinstance(c[0], float) else [r(x) for x in c]
    return {"type": geo["type"], "coordinates": r(geo["coordinates"])}


def nombres_ine(ruta: Path) -> dict:
    """Nombre del municipio con mayúsculas y tildes, tal como lo publica el INE (clave: sin_tildes)."""
    filas = json.loads(ruta.read_text(encoding="utf-8"))
    n = [x["Nombre"].split(". ")[0] for x in filas if ". Total. Total habitantes" in x["Nombre"]]
    return {sin_tildes(x): x for x in n if sin_tildes(x) != "BIZKAIA"}


def indicadores(R: list) -> dict:
    T = pd.read_csv(OUT / "avispa_indicadores_temporada.csv", index_col="temporada")
    D = pd.read_csv(OUT / "avispa_dias_tramos.csv", index_col="temporada")
    tramos = ["mismo_dia", "de_1_a_3_dias", "de_4_a_7_dias", "mas_de_7_dias"]
    # Control: los tramos suman 1 y los tres primeros, el % en <= 7 días del CSV por temporada
    dif = (D[tramos[:3]].sum(axis=1) - T.pct_le7).abs().max()
    R.append(f"Tramos de días: diferencia máxima con pct_le7 = {dif:.4f}")
    t = [int(x) for x in T.index]
    col = lambda s: [limpio(v) for v in s]  # noqa: E731
    return {
        "temporadas": t, "incompletas": INCOMPLETAS, "periodo": [min(TEMPORADAS), max(TEMPORADAS)],
        "corte_registro": CORTE_REGISTRO,
        "nidos": col(T.nidos), "eliminados": col(T.eliminados), "no_eliminables": col(T.no_eliminables),
        "pct_no_eliminables": col(T.pct_no_eliminables), "pct_le7": col(T.pct_le7),
        "dias_mediana": col(T.dias_mediana), "pct_basalan": col(T.pct_basalan),
        "pct_primavera": col(T.pct_primavera),
        "pct_elim_despues_1nov": col(1 - T.pct_elim_antes_1nov),
        "tramos": {"claves": tramos, "n": col(D.n.reindex(t)),
                   "valores": [col(D.loc[x, tramos]) for x in t]},
        # Avisos de abril a diciembre de asiática y de avispa común (control de las ganas de avisar)
        "avisos_asiatica": col(T.avisos_asiatica_abr_dic), "avisos_comun": col(T.avisos_comun_abr_dic),
        "tendencia": tendencia(T.nidos),
    }


def tendencia(nidos: pd.Series) -> dict:
    """Tendencia log-lineal de los nidos avisados 2019-2025 (MCO de log(nidos) sobre la temporada,
    statsmodels) con el intervalo de confianza del 95 % de la recta ajustada, en nidos."""
    import statsmodels.api as sm
    y = nidos.loc[list(TEMPORADAS)].astype(float)
    X = sm.add_constant(np.array(y.index, dtype=float) - TEMPORADAS[0])
    m = sm.OLS(np.log(y.values), X).fit()
    pr = m.get_prediction(X).summary_frame(alpha=0.05)
    lo, hi = m.conf_int(alpha=0.05)[1]
    return {"temporadas": [int(x) for x in y.index], "ajuste": [round(float(np.exp(v)), 1) for v in pr["mean"]],
            "inferior": [round(float(np.exp(v)), 1) for v in pr["mean_ci_lower"]],
            "superior": [round(float(np.exp(v)), 1) for v in pr["mean_ci_upper"]],
            "crecimiento_anual": round(float(np.exp(m.params[1]) - 1), 4),
            "crecimiento_ic95": [round(float(np.exp(lo) - 1), 4), round(float(np.exp(hi) - 1), 4)],
            "p": round(float(m.pvalues[1]), 4), "metodo": "MCO de log(nidos) ~ temporada, 2019-2025; IC 95 % de la recta"}


def dias_distribucion(ruta_nidos: Path, R: list) -> dict:
    """Nidos retirados de 2019-2025 según los días entre aviso y retirada (0, 1, …, 7 y más de 7),
    con las definiciones de avispa_indicadores_control.py (su función base: avisos de abril a
    diciembre, días negativos descartados; nidos «CERRADA - ELIMINADO» con días válidos)."""
    d, _ = control.base(ruta_nidos)
    e = d[d.eliminado & d.dias.notna() & d.temporada.isin(TEMPORADAS)]
    n = e.dias.clip(upper=8).astype(int).value_counts().reindex(range(9), fill_value=0)
    # Control: mismo total y mismos tramos que avispa_dias_tramos.csv (2019-2025)
    D = pd.read_csv(OUT / "avispa_dias_tramos.csv", index_col="temporada").loc[list(TEMPORADAS)]
    tramos = [n[0], n[1:4].sum(), n[4:8].sum(), n[8]]
    csv = [(D[c] * D.n).sum() for c in ["mismo_dia", "de_1_a_3_dias", "de_4_a_7_dias", "mas_de_7_dias"]]
    ok = int(D.n.sum()) == len(e) and np.allclose(tramos, csv, atol=1)
    acum = n.cumsum() / n.sum()
    R.append(f"Días hasta la retirada 2019-2025: n={len(e)}, {n.tolist()}; acumulado <=2 días {acum[2]:.4f}, "
             f"<=7 días {acum[7]:.4f}, mediana {e.dias.median():.0f}; igual que avispa_dias_tramos.csv: {ok}")
    if not ok:
        raise SystemExit("La distribución de días no cuadra con avispa_dias_tramos.csv")
    return {"dias": list(range(8)), "mas_de": 7, "n": [int(v) for v in n], "total": int(len(e)),
            "periodo": [min(TEMPORADAS), max(TEMPORADAS)], "mediana": limpio(e.dias.median()),
            "definicion": "Nidos retirados (CERRADA - ELIMINADO) de las temporadas 2019-2025, avisados de abril "
                          "a diciembre, con días válidos (>= 0) entre el aviso y el cierre; el último valor de n "
                          "son los de más de 7 días."}


def asturias_mensual(R: list) -> dict:
    """Reparto mensual de los avisos de Asturias 2023-2025 (gráfica digitalizada del informe de
    2025, scripts/digitalizar_asturias.py) sobre abril-diciembre, la misma ventana de Bizkaia."""
    a = pd.read_csv(OUT / "asturias_avisos_mensual.csv", dtype={"anio": str})
    a = a[a.mes.between(4, 12)]
    tot = a[a.anio.eq("2023-2025")].set_index("mes")
    anios = sorted(x for x in a.anio.unique() if x != "2023-2025")
    R.append("Asturias 2023-2025, reparto abr-dic: " + ", ".join(f"{m} {v:.3f}" for m, v in tot.proporcion_abr_dic.items())
             + f"; primavera {tot.proporcion_abr_dic.loc[4:6].sum():.3f}")
    return {
        "region": "Asturias", "periodo": [int(anios[0]), int(anios[-1])], "meses": [int(m) for m in tot.index],
        "proporcion": [limpio(v) for v in tot.proporcion_abr_dic],
        "avisos": [limpio(v, 0) for v in tot.avisos],
        "por_anio": {x: [limpio(v) for v in a[a.anio.eq(x)].sort_values("mes").proporcion_abr_dic] for x in anios},
        "primavera": limpio(tot.proporcion_abr_dic.loc[4:6].sum()),
        "fuente": "Principado de Asturias, informe de actividad de 2025 sobre la avispa asiática, gráfica «Flujo de "
                  "recepción de avisos» (avisos por semana, 2023-2025), digitalizada con scripts/digitalizar_asturias.py",
        "comparacion": "Avisos de nidos de Asturias en 2023-2025 frente a los de Bizkaia en 2019-2025: porcentaje de "
                       "los avisos de abril a diciembre que llega en cada mes (suma de los años). La gráfica de Asturias "
                       "empieza en marzo (semana 10): no hay enero ni febrero y marzo, incompleto, queda fuera. Los "
                       "avisos de cada semana se reparten entre sus 7 días antes de sumarlos por mes. Error de la digitalización: unos ±15 avisos por semana. "
                       "Solo se compara la forma del calendario, no el número de nidos.",
    }


def mensual(d: pd.DataFrame, R: list) -> dict:
    m = reparto_mensual(d)
    csv = pd.read_csv(OUT / "avispa_reparto_mensual.csv")
    igual = np.array_equal(m.avisos.to_numpy(), csv.avisos.to_numpy())
    R.append(f"Reparto mensual recalculado igual que outputs/avispa_reparto_mensual.csv: {igual}")
    tab = m.pivot(index="temporada", columns="mes", values="avisos")
    total = tab.sum() / tab.values.sum()
    meses = [int(x) for x in tab.columns]
    return {
        "meses": meses, "temporadas": {str(t): [int(v) for v in tab.loc[t]] for t in tab.index},
        "proporcion_total": [limpio(total[mm]) for mm in meses],
        "estaciones": {"primavera": limpio(total.loc[4:6].sum()), "verano": limpio(total.loc[7:9].sum()),
                       "otono": limpio(total.loc[10:12].sum())},
        "primavera_por_temporada": {str(t): limpio(tab.loc[t, 4:6].sum() / tab.loc[t].sum()) for t in tab.index},
    }


def esquemas(d: pd.DataFrame) -> dict:
    pe = perfil_epoca(d)
    claves = {"primavera (cierre abr-jun)": "primavera", "verano-otoño (cierre jul-31/10)": "verano_otono",
              "tardío (cierre desde el 01/11)": "tardio"}
    return {"perfil": [{"epoca": claves[ep], "n": int(r.n), "diam_cm": limpio(r.diam_mediana_cm),
                        "altura_m": limpio(r.altura_mediana_m), "pct_arbol": limpio(r.pct_arbol)}
                       for ep, r in pe.iterrows()]}


def regiones() -> dict:
    c = pd.read_csv(OUT / "avispa_comparativa_regiones.csv")
    c = c[c.region.isin(REGIONES) & c.anios_desde_llegada.notna()].sort_values(["region", "anio"])
    ms = pd.read_csv(OUT / "avispa_comparativa_meseta.csv").set_index("region")
    series = []
    for r in REGIONES:
        s = c[c.region == r]
        series.append({
            "region": r, "llegada": int(s.anio.iloc[0] - s.anios_desde_llegada.iloc[0]),
            "que_mide": s.que_mide.iloc[-1], "fuente": s.fuente_url.iloc[-1],
            "puntos": [{"anio": int(x.anio), "a": int(x.anios_desde_llegada), "nidos": int(x.nidos),
                        "densidad": limpio(x.nidos_por_1000km2, 1),
                        "incompleto": bool(r == "Bizkaia" and x.anio in INCOMPLETAS)} for x in s.itertuples()],
            "meseta": ({"desde": int(ms.at[r, "desde"]), "hasta": int(ms.at[r, "hasta"]),
                        "densidad": limpio(ms.at[r, "nidos_por_1000km2_media"], 1)} if r in ms.index else None),
        })
    return {"series": series}


def gasto() -> dict:
    A = pd.read_csv(OUT / "avispa_gasto_anual.csv", index_col="anio").loc[2017:2025]
    K = pd.read_csv(OUT / "avispa_gasto_coste_nido.csv")
    lin = K[K.tipo.eq("retirada_nidos_basalan") & K.eur_nido.notna()]
    anios = []
    for a, r in A.iterrows():
        mixta = pd.notna(r.retirada_nidos_basalan_mixta_eur) and r.retirada_nidos_basalan_mixta_eur > 0
        propia = pd.notna(r.retirada_nidos_basalan_eur) and r.retirada_nidos_basalan_eur > 0
        estado = "mezclado" if mixta else "importe" if propia else "sin_desglose"
        anios.append({"anio": int(a), "estado": estado,
                      "retirada_eur": limpio(r.retirada_nidos_basalan_eur, 2) if estado == "importe" else None,
                      "mixta_eur": limpio(r.retirada_nidos_basalan_mixta_eur, 2) if mixta else None,
                      "encargo_eur": limpio(r.encargo_basalan_patrimonio_natural_eur, 2),
                      "detalle": r.detalle_retirada_en_encomiendas})
    tot18 = K[K.tipo.eq("total_2018")]
    # Coste por nido: solo 2018 (tres líneas con meses claros). En 2019 el texto de las líneas viene
    # cortado («…ASIATICA SE»), el resultado depende de a qué meses se asignen (37 o 79-98 €/nido) y
    # no se muestra; queda en avispa_gasto.txt, apartado 3 a).
    coste = {}
    if len(tot18):
        coste["2018"] = {"min": limpio(tot18.eur_nido.iloc[0], 1), "max": limpio(tot18.eur_nido.iloc[0], 1),
                         "nota": "las tres líneas juntas"}
    # Escenario (no es un dato): nidos de Basalan de cada temporada al coste por nido de 2018 (las tres
    # líneas juntas), frente al encargo anual; mismo cálculo que el apartado 3c de avispa_gasto.txt.
    esc = {}
    if len(tot18):
        eur18 = float(tot18.eur.iloc[0]) / float(tot18.nidos_basalan.iloc[0])
        sd = [a["anio"] for a in anios if a["estado"] == "sin_desglose"]
        filas = {y: {"nidos_basalan": int(A.at[y, "nidos_temporada_basalan"]),
                     "eur": limpio(A.at[y, "nidos_temporada_basalan"] * eur18, 0),
                     "pct_encargo": limpio(A.at[y, "nidos_temporada_basalan"] * eur18
                                           / A.at[y, "encargo_basalan_patrimonio_natural_eur"], 4)} for y in sd}
        esc = {"eur_nido": limpio(eur18, 2), "anios": {str(y): f for y, f in filas.items()},
               "nota": "Escenario, no dato: nidos retirados por Basalan en cada temporada por el coste por nido de "
                       "2018 (las tres líneas juntas), a precios de 2018, frente al encargo anual de Patrimonio Natural."}
    return {"anios": anios, "coste_nido": coste, "escenario_2018": esc}


def cronologia() -> dict:
    h = pd.read_csv(OUT / "avispa_politicas_hitos.csv", dtype=str)
    h = h[h.estado.isin(ESTADOS_HITO)]
    return {"estados": list(ESTADOS_HITO), "hitos": [
        {"id": f"h{i:02d}", "fecha": r.fecha, "precision": r.precision_fecha, "titulo": r.medida,
         "ambito": r.ambito, "tipo": r.tipo, "estado": r.estado, "url": r.fuente_url}
        for i, r in enumerate(h.itertuples(), 1)]}


def main() -> None:
    a = sys.argv[1:]
    ruta_nidos = Path(a[0]) if len(a) > 0 else RAIZ / "data/raw/bizkaia/avispa_asiatica/nidos.csv"
    ruta_muni = Path(a[1]) if len(a) > 1 else RAIZ / "data/raw/bizkaia/municipios_catastro/municipios.geojson"
    salida = Path(a[2]) if len(a) > 2 else RAIZ / "web/data"
    ruta_pob = RAIZ / "data/raw/ine/padron_bizkaia_2905_2017_2025.json"
    salida.mkdir(parents=True, exist_ok=True)
    R, tam = [], {}
    for viejo in ("temporadas.json", "mensual.json"):  # temporadas.json lo sustituye indicadores.json
        (salida / viejo).unlink(missing_ok=True)

    todo = preparar(ruta_nidos)  # 2018-2025, todos los meses
    todo = todo[todo.mes_alta.between(4, 12)].copy()  # ventana común abril-diciembre
    d = base(ruta_nidos)  # 2019-2025, abril-diciembre
    R.append(f"Avisos abril-diciembre: 2018-2025 {len(todo)}; periodo principal 2019-2025 {len(d)}")

    ind = indicadores(R)
    suma = sum(n for t, n in zip(ind["temporadas"], ind["nidos"]) if t in TEMPORADAS)
    R.append(f"Nidos 2019-2025 en avispa_indicadores_temporada.csv: {suma} (base recalculada: {len(d)})")
    ind["total_periodo"] = suma
    ind["dias_distribucion"] = dias_distribucion(ruta_nidos, R)
    tam["indicadores.json"] = escribir(salida / "indicadores.json", ind)
    tam["mensual.json"] = escribir(salida / "mensual.json", mensual(d, R))
    tam["asturias_mensual.json"] = escribir(salida / "asturias_mensual.json", asturias_mensual(R))
    tam["esquemas.json"] = escribir(salida / "esquemas.json", esquemas(d))
    tam["regiones.json"] = escribir(salida / "regiones.json", regiones())
    tam["gasto.json"] = escribir(salida / "gasto.json", gasto())
    cr = cronologia()
    tam["cronologia.json"] = escribir(salida / "cronologia.json", cr)
    R.append(f"Hitos en cronologia.json (estado {', '.join(ESTADOS_HITO)}): {len(cr['hitos'])}")

    # --- Población y tasas por municipio (2019-2025, abril-diciembre; columna de municipio del registro) ---
    pob = padron(ruta_pob)
    ine = nombres_ine(ruta_pob)
    tt, sin_cruzar = tasas_tamano(d, pob)
    R.append(f"Tasas por tamaño (media 2019-2025): {tt.media_2019_2025.round(1).to_dict()}; sin cruzar: {sin_cruzar}")
    T = list(TEMPORADAS)
    nm = d.groupby(["muni", "temporada"]).size().unstack(fill_value=0).reindex(index=pob.index, columns=T, fill_value=0)
    tasa = 1000 * nm.sum(axis=1) / pob[T].sum(axis=1)
    tasa[SIN_DATOS] = np.nan
    puesto = tasa.rank(ascending=False, method="min")
    dias = d[d.eliminado & d.dias.ge(0)].groupby("muni").dias.median()
    serie_t = sorted(int(x) for x in todo.temporada.unique())
    st = todo.groupby(["muni", "temporada"]).size().unstack(fill_value=0).reindex(
        index=pob.index, columns=serie_t, fill_value=0)

    # --- Municipios y puntos ---
    m = gpd.read_file(ruta_muni).to_crs(CRS)
    m["nombre"] = m["Descripcion"].str.strip()
    m["cod"] = m["Codigo_Municipio"].astype(int)
    m = m.dissolve(by=["cod", "nombre"], as_index=False)[["cod", "nombre", "geometry"]]
    m["clave"] = m.nombre.map(sin_tildes)
    areas = (m.set_index("cod").geometry.area / 1e6).to_dict()

    validas = tasa.dropna()
    cortes = [round(float(x), 1) for x in validas.quantile(np.linspace(0, 1, CLASES_TASA + 1)[1:-1])]
    R.append(f"Cortes de la tasa por 1.000 habitantes (quintiles de {len(validas)} municipios): {cortes}")

    p = todo.dropna(subset=["lat", "lon"])
    pg = gpd.GeoDataFrame(p[["temporada", "mes_alta"]], geometry=gpd.points_from_xy(p.lon, p.lat),
                          crs="EPSG:4326").to_crs(CRS)
    j = gpd.sjoin_nearest(pg, m[["cod", "geometry"]], how="left", max_distance=200)
    j = j[~j.index.duplicated()]
    dentro = j.cod.notna()
    R.append(f"Puntos 2018-2025 abr-dic: sin coordenadas {len(todo) - len(p)}; fuera de Bizkaia (>200 m): "
             f"{(~dentro).sum()}; en el mapa {dentro.sum()}")
    j = j[dentro]

    mw = m.copy()
    mw["geometry"] = mw.geometry.simplify(SIMPLIFICAR_M, preserve_topology=True)
    mw = mw.to_crs("EPSG:4326")
    feats = []
    for _, r in mw.iterrows():
        k = r.clave
        props = {"cod": int(r.cod), "nombre": ine.get(k, r.nombre), "km2": round(areas[r.cod], 2),
                 "sin_datos": k in SIN_DATOS, "tasa": limpio(tasa.get(k), 4),
                 "pob": int(pob.at[k, 2025])}
        geo = json.loads(gpd.GeoSeries([r.geometry]).to_json(drop_id=True))["features"][0]["geometry"]
        feats.append({"type": "Feature", "properties": props, "geometry": redondear(geo, 5)})
    tam["municipios.geojson"] = escribir(salida / "municipios.geojson", {
        "type": "FeatureCollection", "cortes_tasa": cortes, "periodo": [T[0], T[-1]],
        "tasas_tamano": [{"tamano": k, "municipios": int(r.municipios), "media": limpio(r.media_2019_2025, 4)}
                         for k, r in tt.iterrows()],
        "features": feats})

    w = j.to_crs("EPSG:4326")
    plano = np.column_stack([w.geometry.x.round(DECIMALES), w.geometry.y.round(DECIMALES),
                             w.temporada.astype(int), w.mes_alta.astype(int)])
    plano = plano[np.lexsort((plano[:, 3], plano[:, 2]))]
    nj = {"campos": ["lon", "lat", "temporada", "mes"], "decimales": DECIMALES,
          "datos": [x for fila in plano.tolist() for x in (round(fila[0], DECIMALES), round(fila[1], DECIMALES),
                                                           int(fila[2]), int(fila[3]))]}
    tam["nidos.json"] = escribir(salida / "nidos.json", nj)
    R.append("Puntos con coordenadas por temporada: " + str(pd.Series(plano[:, 2].astype(int)).value_counts()
                                                            .sort_index().to_dict()))

    # --- Buscador por municipio: serie, tasas anuales, tendencia y comarca ---
    nombre = {k: ine.get(k, n) for k, n in zip(m.clave, m.nombre)}
    cc = pd.read_csv(OUT / "municipio_comarca.csv")
    cod_comarca = dict(zip(cc.codigo_ine - 48000, cc.comarca_eustat))
    comarca = {k: cod_comarca.get(int(c)) for k, c in zip(m.clave, m.cod)}

    def ajuste(v):
        """Recta de MCO (numpy.polyfit) de la tasa anual sobre la temporada: valores en 2019 y 2025."""
        a, b = np.polyfit(np.array(T, dtype=float), np.array(v, dtype=float), 1)
        return [limpio(a * T[0] + b, 3), limpio(a * T[-1] + b, 3)]
    tasa_anual = 1000 * nm[T] / pob[T]
    tasa_anual.loc[tasa_anual.index.isin(SIN_DATOS)] = np.nan
    sinb = [k for k in pob.index if k not in SIN_DATOS]
    biz_anual = (1000 * nm.loc[sinb, T].sum() / pob.loc[sinb, T].sum())
    com_anual = {}
    for c0 in sorted(set(v for v in comarca.values() if v)):
        ks = [k for k in sinb if comarca.get(k) == c0]
        com_anual[c0] = [limpio(v, 3) for v in 1000 * nm.loc[ks, T].sum() / pob.loc[ks, T].sum()]
    munis = []
    for k in pob.index:
        sd = k in SIN_DATOS
        munis.append({"nombre": nombre[k], "sin_datos": sd, "pob": int(pob.at[k, 2025]),
                      "nidos": [int(v) for v in st.loc[k]],
                      "tasa": None if sd else limpio(tasa[k], 4),
                      "puesto": None if sd else int(puesto[k]),
                      "dias_mediana": None if sd or k not in dias.index else limpio(dias[k], 1),
                      "comarca": comarca.get(k),
                      "tasa_anual": None if sd else [limpio(v, 3) for v in tasa_anual.loc[k, T]],
                      "tendencia": None if sd else ajuste(tasa_anual.loc[k, T])})
    munis.sort(key=lambda x: x["nombre"])
    tam["municipios_serie.json"] = escribir(salida / "municipios_serie.json", {
        "temporadas": serie_t, "incompletas": INCOMPLETAS, "periodo": [T[0], T[-1]], "temporadas_tasa": T,
        "bizkaia_tasa_anual": [limpio(v, 3) for v in biz_anual], "bizkaia_tendencia": ajuste(biz_anual),
        "comarcas_tasa_anual": com_anual,
        "con_puesto": int(validas.size), "municipios": munis})

    # --- Apertura: avisos por temporada y mes (todos, con y sin coordenadas), municipios con avisos
    #     y municipios con más avisos ---
    nombre_de = lambda k: nombre.get(k, str(k).title())  # noqa: E731
    am = d.groupby(["temporada", "mes_alta"]).size().unstack(fill_value=0).reindex(index=T, columns=range(4, 13), fill_value=0)
    pm = d.groupby(["temporada", "muni"]).size().reset_index(name="n")
    primero = pm.sort_values(["temporada", "n"], ascending=[True, False]).groupby("temporada").head(1)
    tot = d.groupby("muni").size().sort_values(ascending=False)
    ap = {"temporadas": T, "meses": list(range(4, 13)),
          "avisos": [int(v) for v in am.sum(axis=1)], "avisos_mes": [[int(v) for v in fila] for fila in am.values],
          "municipios_con_avisos": [int(v) for v in d.groupby("temporada").muni.nunique().reindex(T)],
          "municipios_total": int(len(m)),
          "primero_por_temporada": [{"temporada": int(r.temporada), "municipio": nombre_de(r.muni), "n": int(r.n)}
                                    for r in primero.itertuples()],
          "mas_avisos_periodo": [{"municipio": nombre_de(k), "n": int(v)} for k, v in tot.head(5).items()]}
    tam["apertura.json"] = escribir(salida / "apertura.json", ap)
    R.append(f"Apertura: avisos {ap['avisos']}; municipios con avisos {ap['municipios_con_avisos']}; "
             f"más avisos {ap['mas_avisos_periodo'][:3]}")

    # --- Descargas CSV (datos procesados) ---
    dd = salida / "descargas"
    dd.mkdir(exist_ok=True)
    for f in dd.glob("*.csv"):
        f.unlink()
    pd.DataFrame({"temporada": ind["temporadas"], "nidos_avisados_abr_dic": ind["nidos"],
                  "eliminados": ind["eliminados"], "no_eliminables": ind["no_eliminables"],
                  "pct_no_eliminables": ind["pct_no_eliminables"], "pct_retirados_en_7_dias": ind["pct_le7"],
                  "pct_avisos_primavera": ind["pct_primavera"],
                  "pct_retirados_despues_1_nov": ind["pct_elim_despues_1nov"],
                  "registro_incompleto": [t in INCOMPLETAS for t in ind["temporadas"]]}).to_csv(
        dd / "indicadores_por_temporada.csv", index=False)
    reparto_mensual(d).to_csv(dd / "avisos_por_temporada_y_mes_abr_dic.csv", index=False)
    pd.DataFrame([{"municipio": x["nombre"], "poblacion_2025": x["pob"],
                   **{f"nidos_{t}": v for t, v in zip(serie_t, x["nidos"])},
                   "nidos_por_1000_hab_2019_2025": x["tasa"], "puesto": x["puesto"],
                   "dias_mediana_retirada_2019_2025": x["dias_mediana"], "sin_datos": x["sin_datos"]}
                  for x in munis]).to_csv(dd / "municipios.csv", index=False)
    pd.DataFrame(plano, columns=["lon", "lat", "temporada", "mes"]).astype(
        {"temporada": int, "mes": int}).to_csv(dd / "nidos_coordenadas_redondeadas.csv", index=False)
    for f in sorted(dd.glob("*.csv")):
        tam[f"descargas/{f.name}"] = f.stat().st_size

    meta = {"generado": date.today().isoformat(), "fuente_nidos": "Open Data Bizkaia, «Avispa asiática en Bizkaia»",
            "fuente_limites": "Catastro foral de Bizkaia (capa Municipios)", "fuente_poblacion": "INE, padrón continuo",
            "puntos": int(len(plano)), "sin_coordenadas": int(len(todo) - len(p)), "ficheros_bytes": tam}
    escribir(salida / "meta.json", meta)
    R.append("Tamaño: " + ", ".join(f"{k} {v / 1024:.0f} KB" for k, v in tam.items()))
    (salida / "resumen.txt").write_text("\n".join(R) + "\n", encoding="utf-8")
    print("\n".join(R))


if __name__ == "__main__":
    main()
