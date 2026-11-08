"""Exploración del conjunto «Avispa asiática en Bizkaia» (Open Data Bizkaia).

Uso:
    python -I scripts/explorar_avispa.py <nidos.csv> <padron_ine.json> [carpeta_salida]

- nidos.csv: descarga del conjunto (separador coma, textos con doble UTF-8).
- padron_ine.json: tabla 2905 del INE (padrón municipal de Bizkaia), de
  https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/2905?nult=1&tip=A
Escribe <salida>/avispa_resumen.txt y <salida>/avispa_mapa_prueba.png (por defecto, outputs/).
"""
import json
import sys
import unicodedata
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy import stats

MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()
# Rectángulo generoso de Bizkaia (WGS84)
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 42.95, 43.47, -3.47, -2.40
ARREGLOS_MUNI = {"ARRANKUDIAGA": "ARRANKUDIAGA-ZOLLO", "IURETA": "IURRETA"}


def arreglar(s: pd.Series) -> pd.Series:
    """Deshace el doble UTF-8 («Ã³»), quita espacios y pasa a mayúsculas."""
    return (s.astype(str).str.encode("latin-1", errors="ignore")
            .str.decode("utf-8", errors="ignore").str.strip().str.upper()
            .replace({"NAN": pd.NA, "": pd.NA}))


def sin_tildes(x: str) -> str:
    x = x.replace("Ñ", "__N__").replace("ñ", "__n__")
    x = "".join(c for c in unicodedata.normalize("NFD", x) if unicodedata.category(c) != "Mn")
    return x.replace("__N__", "Ñ").replace("__n__", "ñ").upper().strip()


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", ".", regex=False), errors="coerce")


def cargar(ruta: Path) -> pd.DataFrame:
    r = pd.read_csv(ruta, dtype=str)
    c = list(r.columns)
    d = pd.DataFrame({
        "anio": pd.to_numeric(r[c[1]]), "num": pd.to_numeric(r[c[2]]),
        "alta": pd.to_datetime(r[c[3]], errors="coerce"),
        "usuario": arreglar(r[c[5]]), "muni": arreglar(r[c[6]]), "dir": r[c[7]],
        "especie": arreglar(r[c[8]]), "ubic": arreglar(r[c[9]]),
        "altura": num(r[c[10]]), "diam": num(r[c[11]]),
        "lat": num(r["latitude GEO"]), "lon": num(r["longitude GEO"]),
        "utm_x": num(r["longitude"]), "utm_y": num(r["latitude"]),
        "estado": arreglar(r[c[17]]), "cierre_txt": r[c[18]], "agente": arreglar(r[c[20]]),
    })
    d["muni"] = d.muni.map(lambda x: x if pd.isna(x) else sin_tildes(x)).replace(ARREGLOS_MUNI)
    d["centinela_9999"] = d.cierre_txt.astype(str).str.startswith("9999")
    d["cierre"] = pd.to_datetime(d.cierre_txt.where(~d.centinela_9999), errors="coerce")
    d["usuario_tipo"] = np.select(
        [d.usuario.str.contains("AYUNTAMIENTO", na=False), d.usuario.eq("BASALAN")],
        ["AYUNTAMIENTO", "BASALAN"], "OTROS")
    return reparar_fechas(d)


def intercambiar(s: pd.Series) -> pd.Series:
    """Fecha con día y mes intercambiados (solo posible si el día es <= 12)."""
    ok = s.dt.day <= 12
    out = pd.to_datetime(dict(year=s.dt.year, month=s.dt.day.where(ok, 1), day=s.dt.month.where(ok, 1)),
                         errors="coerce")
    return out.where(ok & (s.dt.day != s.dt.month))


def reparar_fechas(d: pd.DataFrame, anios=range(2018, 2023)) -> pd.DataFrame:
    """En 2018-2022 las fechas con día <= 12 vienen con día y mes intercambiados.

    Alta: el nº de actuación es correlativo dentro del año, así que se interpola la fecha
    esperada a partir de las fechas no ambiguas (día > 12) y se elige, entre la original y la
    intercambiada, la más cercana. Cierre: se intercambia con la misma regla y se comprueba
    después cuántos cierres siguen siendo anteriores al alta.
    """
    d = d.copy()
    d["alta_orig"], d["alta_corr"], d["cierre_corr"] = d.alta, False, False
    for y in anios:
        m = d.anio.eq(y) & d.alta.notna()
        s = d[m].sort_values("num")
        amb = s.alta.dt.day <= 12
        esperado = np.interp(s.num, s.num[~amb], s.alta[~amb].astype("int64"))
        alt = intercambiar(s.alta)
        mejor = amb & alt.notna() & ((alt.astype("int64") - esperado).abs() < (s.alta.astype("int64") - esperado).abs())
        d.loc[mejor[mejor].index, "alta"] = alt[mejor]
        d.loc[mejor[mejor].index, "alta_corr"] = True
        c = d.loc[m, "cierre"]
        altc = intercambiar(c)
        cambia = altc.notna()
        d.loc[cambia[cambia].index, "cierre"] = altc[cambia]
        d.loc[cambia[cambia].index, "cierre_corr"] = True
    d["dias"] = (d.cierre - d.alta).dt.days
    return d


def poblacion(ruta: Path) -> pd.Series:
    j = json.loads(ruta.read_text(encoding="utf-8"))
    filas = {}
    for x in j:
        if ". Total. Total habitantes" in x["Nombre"]:
            nombre = sin_tildes(x["Nombre"].split(". ")[0])
            if nombre != "BIZKAIA":  # total provincial
                filas[nombre] = x["Data"][0]["Valor"]
            anio = x["Data"][0]["Anyo"]
    s = pd.Series(filas, name="pob")
    s.attrs["anio"] = anio
    return s


def pct(s, qs=(0.25, 0.5, 0.75, 0.9)):
    q = s.quantile(list(qs))
    return " / ".join(f"{v:.0f}" for v in q.values)


def main() -> None:
    ruta, ruta_pob = Path(sys.argv[1]), Path(sys.argv[2])
    salida = Path(sys.argv[3] if len(sys.argv) > 3 else "outputs")
    salida.mkdir(exist_ok=True)
    d = cargar(ruta)
    pob = poblacion(ruta_pob)
    out, K = [], {}
    p = out.append

    # ---------------- Calidad ----------------
    p("=== 1. CALIDAD DEL DATO ===")
    p(f"Filas: {len(d)}; por año: {d.groupby('anio').size().to_dict()}")
    p(f"Especie: {d.especie.value_counts(dropna=False).to_dict()}")
    p(f"Estado: {d.estado.value_counts(dropna=False).to_dict()}")
    p(f"Agente de cierre: {d.agente.value_counts(dropna=False).to_dict()}")
    p(f"Quién avisa (agrupado): {d.usuario_tipo.value_counts().to_dict()}")
    cols = ["anio", "alta", "muni", "dir", "especie", "ubic", "altura", "diam", "lat", "lon", "estado", "cierre"]
    p(f"Filas duplicadas exactas (sin _id ni nº actuación): {d.duplicated(cols).sum()}")
    p(f"Nº actuación repetido dentro del año: {d.duplicated(['anio', 'num']).sum()}")
    dup_coord = d.dropna(subset=["lat"]).duplicated(["alta", "lat", "lon"]).sum()
    p(f"Misma fecha de alta y mismas coordenadas: {dup_coord}")
    rep = d.dropna(subset=["lat"]).groupby(["lat", "lon"]).size()
    p(f"Puntos con >=10 nidos en coordenada idéntica (centroides o puntos por defecto): "
      f"{(rep >= 10).sum()} puntos, {rep[rep >= 10].sum()} filas")
    p(f"Coordenadas nulas: {d.lat.isna().sum()} ({d.lat.isna().mean():.1%}); por año: "
      f"{d[d.lat.isna()].groupby('anio').size().to_dict()}")
    fuera = d.lat.notna() & ~(d.lat.between(LAT_MIN, LAT_MAX) & d.lon.between(LON_MIN, LON_MAX))
    p(f"Coordenadas fuera del rectángulo de Bizkaia: {fuera.sum()}")
    # Coherencia GEO frente a UTM (ETRS89 / UTM 30N)
    tr = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True)
    x, y = tr.transform(d.lon.values, d.lat.values)
    d["x"], d["y"] = x, y
    dist = np.hypot(d.x - d.utm_x, d.y - d.utm_y)
    p(f"Distancia GEO vs UTM: mediana {np.nanmedian(dist):.0f} m; >1 km: {(dist > 1000).sum()} filas")
    # Lejos del resto de nidos de su municipio
    med = d.groupby("muni")[["x", "y"]].transform("median")
    dmuni = np.hypot(d.x - med.x, d.y - med.y) / 1000
    p(f"Nidos a >15 km de la mediana de su municipio (posible municipio o coordenada errónea): "
      f"{(dmuni > 15).sum()}")
    d["geo_ok"] = d.lat.notna() & ~fuera & (dmuni <= 15)
    p(f"Fecha cierre '9999-12-31' (centinela): {d.centinela_9999.sum()}; cierre nulo: "
      f"{d.cierre_txt.isna().sum()}; estados de las centinela: "
      f"{d[d.centinela_9999].estado.value_counts().to_dict()}")
    p(f"FECHAS 2018-2022 CON DÍA Y MES INTERCAMBIADOS (día <= 12): altas corregidas {d.alta_corr.sum()}, "
      f"cierres corregidos {d.cierre_corr.sum()}. Prueba: correlación de Spearman nº actuación-fecha alta "
      f"antes/después por año: " + ", ".join(
          f"{y}: {d[d.anio == y].num.corr(d[d.anio == y].alta_orig.astype('int64'), method='spearman'):.2f}"
          f"->{d[d.anio == y].num.corr(d[d.anio == y].alta.astype('int64'), method='spearman'):.3f}"
          for y in range(2018, 2026)))
    p(f"Tras corregir, cierre anterior al alta: {(d.dias < 0).sum()}; mismo día: {(d.dias == 0).sum()}; "
      f">365 días: {(d.dias > 365).sum()}")
    p(f"Año de la columna distinto del año de la fecha de alta: {(d.anio != d.alta.dt.year).sum()}")
    p(f"Altura: =0 {(d.altura == 0).sum()}, >=100 m {(d.altura >= 100).sum()}, =255 {(d.altura == 255).sum()}; "
      f"diámetro: =0 {(d.diam == 0).sum()}, >=150 cm {(d.diam >= 150).sum()}, =255 {(d.diam == 255).sum()}")
    p(f"2017: {(d.anio == 2017).sum()} filas; por mes {d[d.anio == 2017].alta.dt.month.value_counts().sort_index().to_dict()}; "
      f"estados {d[d.anio == 2017].estado.value_counts().to_dict()}")
    m25 = d[d.anio == 2025].alta.dt.month.value_counts().sort_index()
    p(f"2025 por mes de alta: {m25.to_dict()}; última alta {d.alta.max().date()}; último cierre {d.cierre.max().date()}")
    p(f"Pendientes de grupo por año: {d[d.estado.eq('PENDIENTE DE GRUPO')].groupby('anio').size().to_dict()}")

    # ---------------- Serie ----------------
    a = d[d.especie.eq("AVISPA ASIÁTICA") & ~d.estado.eq("ANULADA") & d.anio.between(2018, 2025)].copy()
    a["mes"] = a.alta.dt.month
    p("\n=== 2. SERIE DE NIDOS DE AVISPA ASIÁTICA (sin anuladas, 2018-2025) ===")
    serie = a.groupby("anio").size()
    K["serie"] = serie
    p(f"Por año: {serie.to_dict()}")
    otros = d[~d.especie.eq("AVISPA ASIÁTICA") & d.anio.between(2018, 2025)].groupby(["anio", "especie"]).size().unstack(fill_value=0)
    p("Otras especies por año:\n" + otros.to_string())
    piv = a.pivot_table(index="anio", columns="mes", values="num", aggfunc="count").fillna(0).astype(int)
    piv.columns = [MESES[m - 1] for m in piv.columns]
    p("Por año y mes:\n" + piv.to_string())
    est = a.mes.value_counts(normalize=True).sort_index()
    p("Peso de cada mes (2018-2025): " + ", ".join(f"{MESES[m-1]} {v:.1%}" for m, v in est.items()))
    pico = a.groupby("anio").mes.agg(lambda s: s.value_counts().idxmax())
    p(f"Mes pico por año: {pico.map(lambda m: MESES[m-1]).to_dict()}")
    sem = a.groupby("anio").alta.agg(lambda s: s.dt.day_of_year.median())
    p(f"Día del año mediano del aviso: {sem.round(0).astype(int).to_dict()}")
    K["primavera"] = a[a.mes.between(3, 6)].groupby("anio").size()
    p(f"Nidos marzo-junio (nidos primarios probables) por año: {K['primavera'].to_dict()}")
    p(f"Nidos sep-dic por año: {a[a.mes >= 9].groupby('anio').size().to_dict()}")
    dm = a[a.diam > 0].groupby("mes").diam.median()
    p("Diámetro mediano (cm) por mes: " + ", ".join(f"{MESES[m-1]} {v:.0f}" for m, v in dm.items()))

    # ---------------- Municipios ----------------
    p("\n=== 3. MUNICIPIOS (asiática 2018-2025) ===")
    mu = a.groupby("muni").size().rename("nidos").to_frame()
    mu = mu.join(pob, how="left")
    sin_pob = mu[mu.pob.isna()].index.tolist()
    p(f"Población: INE, padrón a 1/1/{pob.attrs['anio']} ({len(pob)} municipios). "
      f"Sin cruzar: {sin_pob}")
    mu["por_1000_hab_anual"] = mu.nidos / 8 / mu.pob * 1000
    p(f"Municipios con algún nido: {len(mu)} de {len(pob)}; sin ninguno: "
      f"{sorted(set(pob.index) - set(mu.index))}")
    p("Top 15 en total:\n" + mu.sort_values("nidos", ascending=False).head(15).round(2).to_string())
    p("Top 15 por 1.000 hab. y año (media 2018-2025, municipios >=500 hab.):\n" +
      mu[mu.pob >= 500].sort_values("por_1000_hab_anual", ascending=False).head(15).round(2).to_string())
    big = mu.sort_values("pob", ascending=False).head(8)
    p("Los 8 más poblados (Bilbao tiene servicio propio: no comparable):\n" + big.round(2).to_string())
    K["mu"] = mu
    top10 = mu.nidos.sort_values(ascending=False)
    p(f"Concentración: el 10 % de municipios con más nidos acumula "
      f"{top10.head(int(round(len(top10) * .1))).sum() / top10.sum():.1%}")
    p(f"Quién avisa por año (asiática):\n"
      f"{a.groupby(['anio', 'usuario_tipo']).size().unstack(fill_value=0).to_string()}")

    # ---------------- Tiempo de respuesta ----------------
    p("\n=== 4. TIEMPO DE RESPUESTA (días cierre - alta; asiática, cerradas, 0-365 d) ===")
    t = a[a.estado.str.startswith("CERRADA", na=False) & a.dias.between(0, 365)]
    p(f"Filas válidas: {len(t)} de {len(a)}")
    g = t.groupby("anio").dias
    tab = pd.DataFrame({"n": g.size(), "p25": g.quantile(.25), "mediana": g.median(),
                        "p75": g.quantile(.75), "p90": g.quantile(.9),
                        "<=3d": g.apply(lambda s: (s <= 3).mean()), ">14d": g.apply(lambda s: (s > 14).mean())})
    p(tab.round(2).to_string())
    K["resp"] = tab
    tau = stats.kendalltau(tab.index, tab.mediana)
    p(f"Tendencia de la mediana anual (Kendall): tau={tau.statistic:.2f}, p={tau.pvalue:.3f}")
    p("Por agente de cierre (p25/med/p75/p90; n):")
    for ag, s in t.groupby("agente").dias:
        p(f"  {ag}: {pct(s)}; n={len(s)}")
    p("Por agente y año (mediana):\n" + t.pivot_table(index="anio", columns="agente", values="dias",
                                                      aggfunc="median").to_string())
    p("Agente por año (%):\n" + (pd.crosstab(a.anio, a.agente, normalize="index") * 100).round(1).to_string())
    p("Por estado eliminado/no eliminable (mediana): " +
      str(t.groupby("estado").dias.median().to_dict()))
    p("Por mes de alta (mediana): " + ", ".join(f"{MESES[m-1]} {v:.0f}" for m, v in t.groupby("mes").dias.median().items()))
    gm = t.groupby("muni").dias
    tm = pd.DataFrame({"n": gm.size(), "mediana": gm.median(), "p90": gm.quantile(.9)})
    tm = tm[tm.n >= 150].sort_values("mediana")
    p(f"Municipios (n>=150) más rápidos:\n{tm.head(8).to_string()}\nMás lentos:\n{tm.tail(8).to_string()}")
    K["tm"] = tm

    # ---------------- Altura y diámetro ----------------
    p("\n=== 5. ALTURA Y DIÁMETRO (asiática) ===")
    h = a[(a.altura > 0) & (a.altura < 100)]
    dd = a[(a.diam > 0) & (a.diam < 150)]
    p(f"Altura (m) p25/med/p75/p90: {pct(h.altura)}; máximo válido {h.altura.max():.0f}")
    p(f"Diámetro (cm) p25/med/p75/p90: {pct(dd.diam)}")
    for u in ("ARBOLADO", "CONSTRUCCIÓN"):
        p(f"  {u}: altura {pct(h[h.ubic == u].altura)}; diámetro {pct(dd[dd.ubic == u].diam)}")
    ub = pd.crosstab(a.anio, a.ubic, normalize="index") * 100
    p("Ubicación por año (%):\n" + ub.round(1).to_string())
    K["arbol"] = ub.get("ARBOLADO")
    p("Altura mediana por año y ubicación:\n" +
      h.pivot_table(index="anio", columns="ubic", values="altura", aggfunc="median").to_string())
    p("Diámetro mediano por año y ubicación:\n" +
      dd.pivot_table(index="anio", columns="ubic", values="diam", aggfunc="median").to_string())
    ne = a.estado.eq("CERRADA - NO ELIMINABLE")
    p(f"No eliminables: {ne.mean():.1%}; por ubicación: {a.groupby('ubic').estado.apply(lambda s: (s == 'CERRADA - NO ELIMINABLE').mean()).round(3).to_dict()}")
    p(f"No eliminables por año (%): {(a.groupby('anio').estado.apply(lambda s: (s == 'CERRADA - NO ELIMINABLE').mean()) * 100).round(1).to_dict()}")
    p(f"Altura mediana eliminados vs no eliminables: "
      f"{h.groupby(h.estado.eq('CERRADA - NO ELIMINABLE')).altura.median().to_dict()}")
    p(f"Nidos a >=20 m: {(h.altura >= 20).sum()} ({(h.altura >= 20).mean():.1%}); "
      f"cierre por bomberos según altura >=20 m: {h[h.altura >= 20].agente.value_counts(normalize=True).round(2).to_dict()}")
    hp = a.pivot_table(index="mes", columns="ubic", values="num", aggfunc="count").fillna(0)
    p("Ubicación por mes (nidos):\n" + hp.astype(int).T.to_string())

    # ---------------- Geografía ----------------
    p("\n=== 6. AVANCE GEOGRÁFICO (asiática, coordenadas válidas) ===")
    gg = a[a.geo_ok].copy()
    p(f"Nidos con coordenada válida: {len(gg)} de {len(a)}")
    gg["celda"] = (gg.x // 1000).astype(int).astype(str) + "_" + (gg.y // 1000).astype(int).astype(str)
    cen = gg.groupby("anio")[["x", "y"]].mean()
    cen_med = gg.groupby("anio")[["x", "y"]].median()
    paso = np.hypot(cen.x.diff(), cen.y.diff()) / 1000
    desde18 = np.hypot(cen.x - cen.x.iloc[0], cen.y - cen.y.iloc[0]) / 1000
    lonlat = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True).transform(cen.x.values, cen.y.values)
    p("Centroide anual (media):\n" + pd.DataFrame({
        "lon": np.round(lonlat[0], 4), "lat": np.round(lonlat[1], 4),
        "km_desde_año_anterior": paso.round(1).values, "km_desde_2018": desde18.round(1).values,
        "dx_km_vs_2018(+E)": ((cen.x - cen.x.iloc[0]) / 1000).round(1).values,
        "dy_km_vs_2018(+N)": ((cen.y - cen.y.iloc[0]) / 1000).round(1).values}, index=cen.index).to_string())
    disp = gg.groupby("anio").apply(lambda s: np.sqrt(((s.x - s.x.mean()) ** 2 + (s.y - s.y.mean()) ** 2).mean()) / 1000)
    p(f"Dispersión (distancia típica al centroide, km): {disp.round(1).to_dict()}")
    celdas = gg.groupby("anio").celda.nunique()
    vistas, nuevas, persist = set(), {}, {}
    prev = set()
    for y_ in sorted(gg.anio.unique()):
        cs = set(gg[gg.anio == y_].celda)
        nuevas[y_] = len(cs - vistas)
        persist[y_] = len(cs & prev) / len(prev) if prev else np.nan
        vistas |= cs
        prev = cs
    p(f"Celdas de 1 km con nidos por año: {celdas.to_dict()}")
    p(f"Celdas nunca vistas antes: {nuevas}")
    p(f"Celdas acumuladas: {len(vistas)} (Bizkaia ~2.217 km²)")
    p(f"Persistencia (de las celdas del año anterior, % con nidos este año): "
      f"{ {k: round(v * 100, 1) for k, v in persist.items() if not np.isnan(v)} }")
    dens = gg.groupby(["anio", "celda"]).size()
    conc = dens.groupby("anio").apply(lambda s: s.sort_values(ascending=False).head(max(1, int(len(s) * .1))).sum() / s.sum())
    p(f"Nidos por celda ocupada: {(gg.groupby('anio').size() / celdas).round(2).to_dict()}")
    p(f"% de nidos en el 10 % de celdas más densas: {(conc * 100).round(1).to_dict()}")
    K["celdas"], K["nuevas"] = celdas, nuevas
    primero = a.groupby("muni").anio.min()
    p(f"Municipios por año de primera aparición: {primero.value_counts().sort_index().to_dict()}")
    p(f"Aparecen después de 2018: { {y_: sorted(primero[primero == y_].index) for y_ in range(2019, 2026) if (primero == y_).any()} }")
    nmu = a.groupby("anio").muni.nunique()
    p(f"Municipios con nidos por año: {nmu.to_dict()}")
    # Tendencia por zona: comarcas aproximadas mediante cuadrantes UTM
    gg["zona"] = np.where(gg.x < 500000, "Oeste (Encartaciones/Margen izq.)",
                          np.where(gg.y > 4795000, "Costa/Uribe-Busturia-Lea", "Interior (Durango/Arratia)"))
    p("Nidos por zona aproximada y año:\n" + gg.pivot_table(index="zona", columns="anio", values="num",
                                                           aggfunc="count").to_string())
    # Municipios con mayor crecimiento 2018-19 vs 2024-25
    ini = a[a.anio.isin([2018, 2019])].groupby("muni").size()
    fin = a[a.anio.isin([2024, 2025])].groupby("muni").size()
    cm = pd.DataFrame({"2018_19": ini, "2024_25": fin}).fillna(0)
    cm["dif"] = cm["2024_25"] - cm["2018_19"]
    p("Mayor aumento 2018-19 -> 2024-25:\n" + cm.sort_values("dif").tail(8).astype(int).to_string())
    p("Mayor descenso:\n" + cm.sort_values("dif").head(8).astype(int).to_string())
    K["cm"] = cm

    # ---------------- Mapa de prueba ----------------
    anios = list(range(2018, 2026))
    fig, axs = plt.subplots(2, 4, figsize=(16, 8), sharex=True, sharey=True)
    fondo = gg[["x", "y"]]
    for ax, y_ in zip(axs.flat, anios):
        s = gg[gg.anio == y_]
        ax.scatter(fondo.x, fondo.y, s=0.3, c="#dddddd", lw=0)
        ax.scatter(s.x, s.y, s=1.5, c="#c0392b", lw=0, alpha=.6)
        ax.plot(cen.loc[y_, "x"], cen.loc[y_, "y"], "k+", ms=10)
        ax.set_title(f"{y_}: {len(s)} nidos, {celdas[y_]} km² con nidos", fontsize=9)
        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Nidos de avispa asiática en Bizkaia por año (prueba; gris = todos los años; + = centroide)")
    fig.tight_layout()
    fig.savefig(salida / "avispa_mapa_prueba.png", dpi=110)

    # ---------------- Hallazgos (cifras para redactarlos) ----------------
    p("\n=== 7. DIEZ HALLAZGOS (cifra + limitación) ===")
    sinb = mu.drop(index="BILBAO", errors="ignore")
    rural = sinb[sinb.pob < 2000]
    urb = sinb[sinb.pob >= 20000]
    tasa = lambda m: m.nidos.sum() / 8 / m.pob.sum() * 1000
    pv = a[a.mes.between(5, 8)].ubic.value_counts(normalize=True)
    ot = a[a.mes >= 9].ubic.value_counts(normalize=True)
    bomb0 = (t[t.agente == "BOMBEROS"].dias == 0).mean()
    h18 = h[h.anio == 2018].groupby("ubic").altura.median()
    hall = [
        f"1. Récord del periodo en 2025: {serie[2025]} nidos de asiática, +{serie[2025] / serie[2019] - 1:.0%} sobre el "
        f"mínimo de 2019 ({serie[2019]}) y cuarto año seguido al alza desde 2021 ({serie[2021]}). 2018 ({serie[2018]}) "
        "fue mayor aún. LIMITACIÓN: son avisos atendidos, no nidos existentes; dependen de que vecinos y ayuntamientos avisen.",
        f"2. No se expande: ya en 2018 había nidos en {nmu[2018]} municipios (de 113 con padrón y servicio foral) y solo 3 "
        f"aparecen después (Lanestosa, Bilbao, Usansolo: este último por segregarse de Galdakao). El centroide se mueve "
        f"<3 km en 8 años. Está asentada: es endémica, no un frente que avanza. LIMITACIÓN: la serie empieza cuando la plaga ya había llegado (2010-2014 aprox.).",
        f"3. Saturación del territorio: celdas de 1 km con nidos 2018-2025 {celdas.min()}-{celdas.max()}; las celdas nunca "
        f"vistas caen de {nuevas[2019]} (2019) a {nuevas[2025]} (2025); acumuladas {len(vistas)} km² (≈{len(vistas) / 2217:.0%} de Bizkaia). "
        f"En 2025, máximo de celdas ocupadas ({celdas[2025]}). LIMITACIÓN: la detección depende de que haya gente que vea el nido (bosque deshabitado infrarrepresentado).",
        f"4. Es un problema rural: municipios <2.000 hab. {tasa(rural):.1f} nidos por 1.000 hab. y año frente a "
        f"{tasa(urb):.2f} en los de >=20.000 (sin Bilbao); Galdames {mu.loc['GALDAMES', 'por_1000_hab_anual']:.0f}, Meñaka "
        f"{mu.loc['MEÑAKA', 'por_1000_hab_anual']:.0f}. LIMITACIÓN: la tasa por habitante premia lo rural por definición; por km² el orden cambiaría (no se ha calculado: falta superficie municipal).",
        f"5. Bilbao, agujero negro: {int(mu.loc['BILBAO', 'nidos'])} nidos en 8 años para 351.000 habitantes. No es que no haya "
        "avispas: tiene servicio propio y sus avisos no están en este conjunto. LIMITACIÓN: imprescindible decirlo en cualquier mapa.",
        f"6. En casa en verano, en el árbol en otoño: de mayo a agosto el {pv.get('CONSTRUCCIÓN', 0):.0%} de los nidos está en "
        f"construcciones; de septiembre a diciembre el {ot.get('ARBOLADO', 0):.0%} en árboles. Encaja con el ciclo de nido "
        f"primario (pequeño, bajo, en aleros) y secundario (grande, en copa); diámetro mediano de {dm.min():.0f} cm en primavera a {dm.max():.0f} cm en noviembre-diciembre. "
        "LIMITACIÓN: en otoño los árboles se deshojan y los nidos se ven más (sesgo de detección).",
        f"7. El pico es tardío: agosto-octubre concentran el {est.loc[[8, 9, 10]].sum():.0%} de los avisos y el día mediano del aviso es "
        f"~{int(sem.median())} (principios de septiembre); en 2022, 2023 y 2025 el mes pico fue octubre. Hipótesis a verificar con expertos: parte de los nidos se retira cuando ya ha podido soltar reinas. "
        "LIMITACIÓN: la fecha es la del aviso, no la de formación del nido.",
        f"8. Respuesta rápida y estable: mediana de {tab.mediana.median():.0f} días todos los años, p90 de "
        f"{tab.p90.min():.0f}-{tab.p90.max():.0f} días; sin tendencia (Kendall p={tau.pvalue:.2f}). Los bomberos cierran el "
        f"{bomb0:.0%} de sus casos el mismo día. LIMITACIÓN: en 2018-2022 hubo que corregir fechas con día y mes intercambiados; sin corregir salían medianas de 30-90 días falsas.",
        f"9. Los primarios de primavera no crecen: nidos de marzo-junio {K['primavera'].to_dict()}, mientras que los de "
        f"sep-dic suben a {a[a.mes >= 9].groupby('anio').size()[2025]} en 2025. Los avisos de primavera no anticipan los de otoño "
        "(hipótesis a contrastar con expertos: nidos primarios poco detectados, o que no predicen el otoño). LIMITACIÓN: no hay datos de trampeo en el conjunto; no permite evaluar ninguna política.",
        f"10. Cambios locales grandes: Galdakao pasa de {int(cm.loc['GALDAKAO', '2018_19'])} (2018-19) a "
        f"{int(cm.loc['GALDAKAO', '2024_25'])} (2024-25) nidos; Muskiz de {int(cm.loc['MUSKIZ', '2018_19'])} a "
        f"{int(cm.loc['MUSKIZ', '2024_25'])}. Ver si es plaga o cambio en quién avisa. LIMITACIÓN: Usansolo (segregado de Galdakao) solo explica 18 nidos.",
    ]
    out.extend(hall)
    p("\nOTRAS ANOMALÍAS: 2018 tiene la altura invertida respecto a otros años "
      f"(mediana árbol {h18.get('ARBOLADO', np.nan):.0f} m, construcción {h18.get('CONSTRUCCIÓN', np.nan):.0f} m; resto de años 8-10 m y 3-4 m), "
      "no usar 2018 en altura/diámetro por ubicación. 2024: solo 39 % en árbol (49-53 % el resto), posible cambio de criterio. "
      "2017 son 108 filas casi todas 'pendiente de grupo': descartar.")
    (salida / "avispa_resumen.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"OK: {salida / 'avispa_resumen.txt'} ({len(out)} líneas)")


if __name__ == "__main__":
    main()
