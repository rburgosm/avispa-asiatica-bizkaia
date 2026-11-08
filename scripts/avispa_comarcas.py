"""Avispa asiática en Bizkaia por comarcas (Eustat), temporadas 2019-2025.

Uso:
    python -I scripts/avispa_comarcas.py [nidos.csv] [padron_2017_2025.json] [municipios.geojson] [municipio_comarca.csv] [carpeta_salida]

Por defecto: data/raw/bizkaia/avispa_asiatica/nidos.csv, data/raw/ine/padron_bizkaia_2905_2017_2025.json,
data/raw/bizkaia/municipios_catastro/municipios.geojson, outputs/municipio_comarca.csv (de
scripts/descargar_comarcas.py) y outputs/. Escribe:
- avispa_comarcas.csv: comarca x temporada (incluye «Bizkaia sin Bilbao» como referencia).
- avispa_comarcas_resumen.csv: una fila por comarca, 2019-2025, con comparación frente al resto
  de Bizkaia y tendencia.
- avispa_comarcas.txt: resumen compacto.

Base y limpieza: avispa_indicadores_control.base (que reutiliza avispa_llegamos_tarde.preparar y
explorar_avispa.cargar): asiática, sin anuladas ni duplicados, avisos de abril a diciembre,
días negativos anulados. Periodo 2019-2025 (decisión de CLAUDE.md; 2018 incompleto).
La comarca se asigna por el campo municipio del registro (no por coordenadas).

Bilbao queda fuera de todo el cálculo por comarcas (servicio municipal propio, 3 nidos en el
registro): Gran Bilbao se da sin Bilbao, en nidos, población y superficie.

Indicadores por comarca y temporada:
- nidos; nidos por 1.000 habitantes (padrón INE a 1 de enero del año de la temporada); nidos por
  1.000 km² (superficie del término municipal según el catastro foral, EPSG:25830).
- % avisos en primavera (abril-junio) sobre todos los nidos.
- % retirados después del 01/11: eliminados con fecha de cierre válida cuyo cierre es >= 01/11.
- Días aviso-retirada de los eliminados: mediana y percentil 90; % retirados en <= 7 días.
- % no eliminables sobre todos los nidos.

Comparación con el resto de Bizkaia (sin Bilbao), con la temporada como unidad:
- Tasas: GLM de Poisson con exposición (población o superficie), efectos fijos de temporada y una
  variable «esta comarca», con escala de Pearson (cuasi-Poisson): razón de tasas (RR) e IC 95 %.
- Proporciones: igual con GLM binomial con escala de Pearson (cuasibinomial): razón de odds (OR).
- Días (mediana): diferencia por temporada entre la mediana de la comarca y la del resto; media de
  las 7 diferencias con IC t de Student.
- Con 7 comarcas por indicador se corrige p por comparaciones múltiples (Holm).
Tendencias por comarca, como avispa_indicadores_control y avispa_estabilizacion: nidos con GLM
binomial negativa (alfa fijo 0,05) y proporciones con GLM cuasibinomial (tend_prop). Con 7
temporadas y pocos nidos en algunas comarcas la potencia es baja: un IC que incluye 0 no prueba
estabilidad.
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multitest import multipletests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from avispa_avisos_poblacion import padron  # noqa: E402
from avispa_indicadores_control import base, tend_prop  # noqa: E402
from explorar_avispa import sin_tildes  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
T0, T1 = 2019, 2025
BIZ = "Bizkaia sin Bilbao"
P = lambda x: f"{100 * x:.1f} %"  # noqa: E731
COMARCAS = ["Gran Bilbao", "Plentzia-Mungia", "Gernika-Bermeo", "Markina-Ondarroa",
            "Duranguesado", "Arratia-Nervión", "Encartaciones"]


def q(s: pd.Series, x: float) -> float:
    s = s.dropna()
    return float(s.quantile(x)) if len(s) else np.nan


def indicadores(g: pd.DataFrame) -> dict:
    el = g[g.eliminado]
    return {
        "nidos": len(g),
        "primavera": int(g.primavera.sum()),
        "no_elim": int(g.no_elim.sum()),
        "elim": len(el),
        "elim_con_cierre": int(el.antes_nov.notna().sum()),
        "elim_tras_1nov": int((el.antes_nov == False).sum()),  # noqa: E712
        "elim_con_dias": int(el.dias.notna().sum()),
        "elim_le7": int((el.le7 == True).sum()),  # noqa: E712
        "dias_mediana": q(el.dias, .5), "dias_p90": q(el.dias, .9),
    }


def pcts(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["pct_primavera"] = df.primavera / df.nidos
    df["pct_tras_1nov"] = df.elim_tras_1nov / df.elim_con_cierre
    df["pct_le7"] = df.elim_le7 / df.elim_con_dias
    df["pct_no_elim"] = df.no_elim / df.nidos
    return df


# ---------------------------------------------------------------- comparaciones
def glm_cuasi(df: pd.DataFrame, familia, **kw):
    r = smf.glm("y ~ es + C(temporada)", df, family=familia, **kw).fit(scale="X2")
    if r.scale < 1:
        r = smf.glm("y ~ es + C(temporada)", df, family=familia, **kw).fit()
    lo, hi = np.exp(r.conf_int().loc["es"])
    return np.exp(r.params["es"]), lo, hi, r.pvalues["es"]


def vs_resto(st: pd.DataFrame, c: str) -> dict:
    """Comarca c frente al resto de Bizkaia sin Bilbao, por temporada."""
    a = st[st.comarca == c].set_index("temporada")
    b = st[st.comarca == BIZ].set_index("temporada")
    r = b.drop(columns="comarca").select_dtypes("number") - a.drop(columns="comarca").select_dtypes("number")
    out = {}
    for nombre, expo in (("hab", "poblacion"), ("km2", "superficie_km2")):
        df = pd.concat([pd.DataFrame({"y": a.nidos, "e": a[expo], "es": 1}),
                        pd.DataFrame({"y": r.nidos, "e": r[expo], "es": 0})]).rename_axis("temporada").reset_index()
        out[f"rr_{nombre}"] = glm_cuasi(df, sm.families.Poisson(), offset=np.log(df.e))
    for nombre, k, n in (("primavera", "primavera", "nidos"), ("tras_1nov", "elim_tras_1nov", "elim_con_cierre"),
                         ("le7", "elim_le7", "elim_con_dias"), ("no_elim", "no_elim", "nidos")):
        df = pd.concat([pd.DataFrame({"k": a[k], "n": a[n], "es": 1}),
                        pd.DataFrame({"k": r[k], "n": r[n], "es": 0})]).rename_axis("temporada").reset_index()
        df = df[df.n > 0].assign(y=lambda x: x.k / x.n)
        out[f"or_{nombre}"] = glm_cuasi(df, sm.families.Binomial(), var_weights=df.n.values)
    return out


def dias_vs_resto(d: pd.DataFrame, c: str) -> tuple:
    """Media de las diferencias anuales de mediana de días (comarca - resto) e IC t."""
    el = d[d.eliminado & d.dias.notna()]
    dif = []
    for t, g in el.groupby("temporada"):
        dif.append(g.dias[g.comarca == c].median() - g.dias[g.comarca != c].median())
    dif = np.array(dif, dtype=float)
    dif = dif[~np.isnan(dif)]
    if np.ptp(dif) == 0:  # todas las temporadas con la misma diferencia (p. ej., 0): sin variación
        return dif.mean(), dif.mean(), dif.mean(), float(dif.mean() != 0)
    tt = stats.ttest_1samp(dif, 0)
    ci = tt.confidence_interval()
    return dif.mean(), ci.low, ci.high, tt.pvalue


def tend_nb(s: pd.Series) -> tuple:
    X = sm.add_constant(np.asarray(s.index, dtype=float) - T0)
    m = sm.GLM(s.values.astype(float), X, family=sm.families.NegativeBinomial(alpha=0.05)).fit()
    lo, hi = np.exp(m.conf_int()[1]) - 1
    return np.exp(m.params[1]) - 1, lo, hi, m.pvalues[1]


# ---------------------------------------------------------------- main
def main() -> None:
    a = sys.argv[1:]
    ruta = Path(a[0]) if len(a) > 0 else RAIZ / "data/raw/bizkaia/avispa_asiatica/nidos.csv"
    ruta_pob = Path(a[1]) if len(a) > 1 else RAIZ / "data/raw/ine/padron_bizkaia_2905_2017_2025.json"
    ruta_geo = Path(a[2]) if len(a) > 2 else RAIZ / "data/raw/bizkaia/municipios_catastro/municipios.geojson"
    ruta_mc = Path(a[3]) if len(a) > 3 else RAIZ / "outputs/municipio_comarca.csv"
    salida = Path(a[4]) if len(a) > 4 else RAIZ / "outputs"

    mc = pd.read_csv(ruta_mc, dtype=str)
    mc["clave"] = mc.municipio.map(sin_tildes)
    geo = gpd.read_file(ruta_geo)
    geo["codigo_ine"] = "48" + geo.Codigo_Municipio.astype(int).astype(str).str.zfill(3)
    geo["superficie_km2"] = geo.to_crs(25830).area / 1e6
    mc = mc.merge(geo[["codigo_ine", "superficie_km2"]], on="codigo_ine", how="left", validate="1:1")
    pob = padron(ruta_pob)
    sin_pob = sorted(set(mc.clave) - set(pob.index))

    d, info = base(ruta)
    d = d[d.temporada.between(T0, T1)].copy()
    mapa = mc.set_index("clave")
    sin_asig = sorted(set(d.muni.dropna()) - set(mapa.index))
    d["comarca"] = d.muni.map(mapa.comarca_eustat)
    n_bilbao = int((d.muni == "BILBAO").sum())
    n_total = len(d)
    d = d[d.muni != "BILBAO"]

    # Exposición por comarca (sin Bilbao)
    m2 = mc[mc.clave != "BILBAO"]
    pobc = pob.reindex(m2.clave).fillna(0).groupby(m2.comarca_eustat.values).sum()  # Usansolo 2017-2023: dentro de Galdakao
    supc = m2.groupby("comarca_eustat").superficie_km2.sum()

    filas = []
    for (c, t), g in list(d.groupby(["comarca", "temporada"])) + [((BIZ, t), g) for t, g in d.groupby("temporada")]:
        f = {"comarca": c, "temporada": t, **indicadores(g)}
        f["poblacion"] = pobc.sum()[t] if c == BIZ else pobc.loc[c, t]
        f["superficie_km2"] = supc.sum() if c == BIZ else supc[c]
        filas.append(f)
    st = pd.DataFrame(filas)
    st["nidos_1000hab"] = 1000 * st.nidos / st.poblacion
    st["nidos_1000km2"] = 1000 * st.nidos / st.superficie_km2
    st = pcts(st)
    orden = {c: i for i, c in enumerate(COMARCAS + [BIZ])}
    st = st.sort_values(["comarca", "temporada"], key=lambda s: s.map(orden) if s.name == "comarca" else s)

    # Resumen 2019-2025
    res = []
    for c, g in st.groupby("comarca", sort=False):
        s = g.select_dtypes("number").sum()
        dd = d if c == BIZ else d[d.comarca == c]
        el = dd[dd.eliminado]
        f = {"comarca": c, "municipios": int(len(m2) if c == BIZ else (m2.comarca_eustat == c).sum()),
             "poblacion_2025": int(g.poblacion[g.temporada == T1].iloc[0]), "superficie_km2": round(g.superficie_km2.iloc[0], 1),
             "nidos_2019_2025": int(s.nidos), "nidos_media_anual": s.nidos / g.temporada.nunique(),
             "nidos_1000hab_anual": 1000 * s.nidos / s.poblacion,
             "nidos_1000km2_anual": 1000 * g.nidos.mean() / g.superficie_km2.iloc[0],
             "pct_primavera": s.primavera / s.nidos, "pct_tras_1nov": s.elim_tras_1nov / s.elim_con_cierre,
             "dias_mediana": q(el.dias, .5), "dias_p90": q(el.dias, .9),
             "pct_le7": s.elim_le7 / s.elim_con_dias, "pct_no_elim": s.no_elim / s.nidos}
        tn = tend_nb(g.set_index("temporada").nidos)
        f.update(tend_nidos_pct_anual=tn[0], tend_nidos_lo=tn[1], tend_nidos_hi=tn[2], tend_nidos_p=tn[3])
        for k, n, nom in (("primavera", "nidos", "primavera"), ("no_elim", "nidos", "no_elim"),
                          ("elim_le7", "elim_con_dias", "le7"), ("elim_tras_1nov", "elim_con_cierre", "tras_1nov")):
            tp = tend_prop(g.set_index("temporada")[k], g.set_index("temporada")[n], T0)
            f.update({f"tend_{nom}_or": tp["or_"], f"tend_{nom}_lo": tp["lo"], f"tend_{nom}_hi": tp["hi"],
                      f"tend_{nom}_p": tp["p"]})
        if c != BIZ:
            for k, (e, lo, hi, p) in vs_resto(st, c).items():
                f.update({k: e, f"{k}_lo": lo, f"{k}_hi": hi, f"{k}_p": p})
            e, lo, hi, p = dias_vs_resto(d, c)
            f.update(dif_dias_mediana=e, dif_dias_mediana_lo=lo, dif_dias_mediana_hi=hi, dif_dias_mediana_p=p)
        res.append(f)
    res = pd.DataFrame(res)
    comp = [k for k in res.columns if k.endswith("_p") and (k.startswith(("rr_", "or_", "dif_")))]
    m = res.comarca != BIZ
    for k in comp:
        res.loc[m, k[:-2] + "_p_holm"] = multipletests(res.loc[m, k], method="holm")[1]
    res.loc[m, "tend_nidos_p_holm"] = multipletests(res.loc[m, "tend_nidos_p"], method="holm")[1]
    # ¿Difieren las tendencias entre comarcas? (cuasi-Poisson, interacción comarca x año)
    sc = st[st.comarca != BIZ].assign(anio=lambda x: x.temporada - T0)
    r1 = smf.glm("nidos ~ C(comarca) * anio", sc, family=sm.families.Poisson()).fit()
    r0 = smf.glm("nidos ~ C(comarca) + anio", sc, family=sm.families.Poisson()).fit()
    escala = r1.pearson_chi2 / r1.df_resid
    gl = r0.df_resid - r1.df_resid
    F = (r0.deviance - r1.deviance) / gl / escala
    pF = stats.f.sf(F, gl, r1.df_resid)

    salida.mkdir(parents=True, exist_ok=True)
    st.round(4).to_csv(salida / "avispa_comarcas.csv", index=False)
    res.round(4).to_csv(salida / "avispa_comarcas_resumen.csv", index=False)

    # ---------------------------------------------------------------- texto
    L = ["# Avispa asiática por comarcas de Bizkaia (Eustat), temporadas 2019-2025, avisos abril-diciembre", "",
         "## Base",
         f"  Nidos 2019-2025 (abr-dic, asiática, sin anuladas): {n_total}; Bilbao {n_bilbao} (fuera: servicio municipal"
         f" propio); quedan {len(d)}. Municipios sin comarca: {sin_asig or 'ninguno'}; sin padrón: {sin_pob or 'ninguno'}.",
         "  Correspondencia: Eustat, «Municipios de la C.A. de Euskadi» (113 municipios de Bizkaia, 7 comarcas),"
         " idéntica en pertenencia a la capa municipal de la Diputación (outputs/municipio_comarca.csv).",
         "  Gran Bilbao se da siempre sin Bilbao (población 2025 sin Bilbao: "
         f"{int(pobc.loc['Gran Bilbao', T1]):,}".replace(",", ".") + " hab.). La comarca sale del campo municipio.",
         "", "## Resumen 2019-2025 (nidos/año = media anual; tasas sobre población y superficie sin Bilbao)",
         f"  {'comarca':<19}{'mun':>4}{'nidos/año':>10}{'/1000hab':>9}{'/1000km2':>9}{'prim.':>7}{'>=1/11':>7}"
         f"{'d.med':>6}{'d.p90':>6}{'<=7d':>7}{'noelim':>7}"]
    for r in res.itertuples():
        L.append(f"  {r.comarca:<19}{r.municipios:>4}{r.nidos_media_anual:>10.0f}{r.nidos_1000hab_anual:>9.2f}"
                 f"{r.nidos_1000km2_anual:>9.0f}{100*r.pct_primavera:>6.1f}%{100*r.pct_tras_1nov:>6.1f}%"
                 f"{r.dias_mediana:>6.0f}{r.dias_p90:>6.0f}{100*r.pct_le7:>6.1f}%{100*r.pct_no_elim:>6.1f}%")
    L += ["", "## Nidos por temporada"]
    tab = st.pivot(index="comarca", columns="temporada", values="nidos").reindex(COMARCAS + [BIZ])
    L.append(f"  {'':<19}" + "".join(f"{t:>6}" for t in tab.columns))
    for c, r in tab.iterrows():
        L.append(f"  {c:<19}" + "".join(f"{int(v):>6}" for v in r))
    L += ["", "## Frente al resto de Bizkaia (sin Bilbao), temporada como unidad; IC 95 %; * = p Holm < 0,05",
          "  RR = razón de tasas (cuasi-Poisson con efectos de temporada); OR = razón de odds (cuasibinomial);"
          " días = media de las diferencias anuales de mediana."]
    fmt = lambda e, lo, hi, ph, d=2: f"{e:.{d}f} [{lo:.{d}f}-{hi:.{d}f}]{'*' if ph < .05 else ' '}"  # noqa: E731
    for r in res[m].itertuples():
        g = r._asdict()
        L.append(f"  {r.comarca}: RR hab {fmt(g['rr_hab'], g['rr_hab_lo'], g['rr_hab_hi'], g['rr_hab_p_holm'])};"
                 f" RR km2 {fmt(g['rr_km2'], g['rr_km2_lo'], g['rr_km2_hi'], g['rr_km2_p_holm'])}")
        L.append(f"    OR primavera {fmt(g['or_primavera'], g['or_primavera_lo'], g['or_primavera_hi'], g['or_primavera_p_holm'])};"
                 f" OR >=1/11 {fmt(g['or_tras_1nov'], g['or_tras_1nov_lo'], g['or_tras_1nov_hi'], g['or_tras_1nov_p_holm'])};"
                 f" OR <=7d {fmt(g['or_le7'], g['or_le7_lo'], g['or_le7_hi'], g['or_le7_p_holm'])};"
                 f" OR no elim. {fmt(g['or_no_elim'], g['or_no_elim_lo'], g['or_no_elim_hi'], g['or_no_elim_p_holm'])};"
                 f" días {g['dif_dias_mediana']:+.1f} [{g['dif_dias_mediana_lo']:+.1f} a {g['dif_dias_mediana_hi']:+.1f}]"
                 f"{'*' if g['dif_dias_mediana_p_holm'] < .05 else ''}")
    L += ["", "## Tendencias 2019-2025 por comarca (7 temporadas: potencia baja; IC que incluye 0/1 no prueba estabilidad)",
          "  Nidos: binomial negativa (alfa 0,05), % al año. Proporciones: cuasibinomial, OR por año."]
    for r in res.itertuples():
        g = r._asdict()
        L.append(f"  {r.comarca}: nidos {100*g['tend_nidos_pct_anual']:+.1f} %/año [{100*g['tend_nidos_lo']:+.1f} a"
                 f" {100*g['tend_nidos_hi']:+.1f}], p={g['tend_nidos_p']:.3f}; OR/año primavera {g['tend_primavera_or']:.2f}"
                 f" [{g['tend_primavera_lo']:.2f}-{g['tend_primavera_hi']:.2f}]; no elim. {g['tend_no_elim_or']:.2f}"
                 f" [{g['tend_no_elim_lo']:.2f}-{g['tend_no_elim_hi']:.2f}]; <=7d {g['tend_le7_or']:.2f}"
                 f" [{g['tend_le7_lo']:.2f}-{g['tend_le7_hi']:.2f}]; >=1/11 {g['tend_tras_1nov_or']:.2f}"
                 f" [{g['tend_tras_1nov_lo']:.2f}-{g['tend_tras_1nov_hi']:.2f}]")
    L.append("  Tendencia de nidos con p Holm < 0,05 (7 comarcas): " + (", ".join(
        f"{c} ({ph:.3f})" for c, ph in zip(res.comarca[m], res.tend_nidos_p_holm[m]) if ph < .05) or "ninguna")
        + "; p Holm mínima " + f"{res.tend_nidos_p_holm[m].min():.3f}.")
    L.append(f"  ¿Difieren las tendencias de nidos entre comarcas? Interacción comarca x año (cuasi-Poisson):"
             f" F({gl:.0f},{r1.df_resid:.0f})={F:.2f}, p={pF:.3f} (escala {escala:.1f}).")
    L += ["", "## Limitaciones",
          "  - Son avisos atendidos, no un censo: la tasa depende también de cuánto se busca y se avisa en cada zona.",
          "  - Nidos por 1.000 hab. favorece a las comarcas rurales (poca población, mucho territorio); por km² usa la"
          " superficie total del término (monte incluido). Se dan las dos.",
          "  - La comarca se asigna por el municipio anotado en el registro; no se comprueba con las coordenadas.",
          "  - Comparaciones frente al resto con la temporada como unidad (7 por comarca), 7 comarcas x 7 indicadores:"
          " se aplica Holm dentro de cada indicador, no sobre el total.",
          "  - Días: mediana y p90 de los eliminados; % >= 1/11 sobre eliminados con fecha de cierre válida.",
          "  - Cambio de registro el 01/01/2023 (CLAUDE.md): afecta por igual a todas las comarcas, pero puede"
          " desplazar las tendencias de % no eliminables."]
    (salida / "avispa_comarcas.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\n[{len(L)} líneas]")


if __name__ == "__main__":
    main()
