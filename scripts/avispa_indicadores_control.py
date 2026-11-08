"""¿Ha mejorado el control de la avispa asiática en Bizkaia? Indicadores de respuesta, 2019-2025.

Periodo principal 2019-2025 (decisión del proyecto, CLAUDE.md): 2018 es el primer año del registro
y está incompleto (empieza en abril, alturas a 0, 16 % sin coordenadas). Cada tendencia se da también
con 2018 como análisis de sensibilidad.

Uso:
    python -I scripts/avispa_indicadores_control.py [nidos.csv] [padron_2017_2025.json] [carpeta_salida]

Por defecto: data/raw/bizkaia/avispa_asiatica/nidos.csv, data/raw/ine/padron_bizkaia_2905_2017_2025.json
y outputs/. Escribe:
- avispa_indicadores_control.txt: resumen con tendencias e IC 95 %.
- avispa_indicadores_temporada.csv: una fila por temporada (para gráficos).
- avispa_indicadores_mes.csv: una fila por temporada y mes de aviso.
- avispa_dias_tramos.csv: reparto de los días entre aviso y retirada por temporada (mismo día,
  1-3, 4-7 y más de 7 días), para el gráfico de barras apiladas de la web.

Limpieza: se reutiliza tal cual la de explorar_avispa.py (textos, centinela 9999-12-31, fechas
2018-2022 con día y mes intercambiados) y la base de avispa_llegamos_tarde.preparar (asiática, sin
anuladas, sin duplicados exactos, temporadas 2018-2025, enero-marzo a la temporada anterior).

Decisiones propias de este script (documentadas también en la salida):
- Ventana común: solo avisos de abril a diciembre del año de la temporada. 2018 empieza en abril
  y la temporada 2025 no tiene aún los avisos de enero-marzo de 2026; así las ocho temporadas
  cubren el mismo calendario. Los avisos de enero-marzo (nidos viejos) se cuentan aparte.
- Días aviso-cierre = fecha de cierre - fecha de alta (días enteros, sin hora). Se anulan los
  negativos (errores de fecha) y los cierres que faltan o son centinela.
- Altura: 0 m (solo aparece en 2018-2019, como relleno) y > 60 m se tratan como no válidos.
  Diámetro: 0 y >= 250 cm (255 es el máximo de un byte: valor de relleno) no válidos.
- Tendencias: con solo siete temporadas (ocho con 2018), la unidad de análisis es la temporada.
  * Proporciones: GLM binomial sobre los recuentos por temporada con escala estimada por chi2 de
    Pearson (cuasibinomial; si sale < 1 se fija en 1), para que el IC refleje la variación entre
    temporadas y no solo el tamaño de muestra. Se da la razón de odds por año.
  * Medianas y percentiles: regresión lineal (MCO) del valor de cada temporada sobre el año.
    Como contraste, regresión cuantílica a nivel de nido (QuantReg); su IC trata los nidos como
    independientes y es demasiado estrecho.
  * Ajuste por mes: GLM cuasibinomial por (temporada, mes) con el mes como factor, para separar
    el cambio de calendario del cambio de eficacia.
- Comprobaciones del registro: (a) el 01/01/2023 el campo «usuario» pasa de «AYUNTAMIENTO <municipio>»
  a «AYUNTAMIENTO» (docs/avispa_politicas_cronologia.md); se mira si crea saltos en 2023 comparando
  con un modelo de tendencia más escalón. (b) Hueco de avisos en enero-febrero de 2019: se mira el
  número de actuación correlativo y las fechas originales, antes y después de la corrección día/mes.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from avispa_avisos_poblacion import padron  # noqa: E402
from avispa_llegamos_tarde import preparar  # noqa: E402
from explorar_avispa import cargar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
TAMANOS = ([0, 2000, 5000, 20000, 1e7], ["<2.000", "2.000-5.000", "5.000-20.000", ">20.000"])
P = lambda x: f"{100 * x:.1f} %"  # noqa: E731


# ---------------------------------------------------------------- tendencias
def tend_prop(k: pd.Series, n: pd.Series, desde: int = 2018) -> dict:
    """GLM binomial (cuasi) de k/n por temporada sobre el año. Devuelve OR/año, IC y ajustados."""
    k, n = k.astype(float), n.astype(float)
    m = (n.index >= desde) & (n > 0)
    k, n = k[m], n[m]
    X = sm.add_constant(np.asarray(n.index, dtype=float) - 2018)
    # proporción + var_weights = n: con la endógena de dos columnas statsmodels 0.15 estima mal
    # la escala X2 (sale ~0,01); así coincide con chi2 de Pearson / gl residuales.
    y, w = (k / n).values, n.values
    fam = sm.families.Binomial()
    r = sm.GLM(y, X, family=fam, var_weights=w).fit(scale="X2")
    if r.scale < 1:
        r = sm.GLM(y, X, family=fam, var_weights=w).fit()
    lo, hi = np.exp(r.conf_int()[1])
    ajust = r.predict(X[[0, -1]])
    return dict(or_=np.exp(r.params[1]), lo=lo, hi=hi, p=r.pvalues[1], escala=r.scale,
                f0=ajust[0], f1=ajust[1], a0=int(n.index[0]), a1=int(n.index[-1]))


ETIQ = {2019: "", 2018: "[sensib.] "}


def txt_prop(nombre: str, k: pd.Series, n: pd.Series) -> list[str]:
    out = []
    for desde in (2019, 2018):
        t = tend_prop(k, n, desde)
        out.append(f"  {ETIQ[desde]}{nombre} ({t['a0']}-{t['a1']}): OR/año {t['or_']:.3f} [IC95 {t['lo']:.3f}-{t['hi']:.3f}],"
                   f" p={t['p']:.3f}; ajustado {P(t['f0'])} -> {P(t['f1'])} (escala {t['escala']:.1f})")
    return out


def tend_nivel(s: pd.Series, desde: int = 2018) -> dict:
    s = s[s.index >= desde].dropna()
    X = sm.add_constant(np.asarray(s.index, dtype=float) - 2018)
    r = sm.OLS(s.values, X).fit()
    lo, hi = r.conf_int()[1]
    return dict(b=r.params[1], lo=lo, hi=hi, p=r.pvalues[1], a0=int(s.index[0]), a1=int(s.index[-1]))


def txt_nivel(nombre: str, s: pd.Series, ud: str) -> list[str]:
    out = []
    for desde in (2019, 2018):
        t = tend_nivel(s, desde)
        out.append(f"  {ETIQ[desde]}{nombre} ({t['a0']}-{t['a1']}): {t['b']:+.2f} {ud}/año [IC95 {t['lo']:+.2f} a {t['hi']:+.2f}],"
                   f" p={t['p']:.3f}")
    return out


def txt_quantreg(nombre: str, df: pd.DataFrame, col: str, q: float, ud: str) -> str:
    g = df.loc[df.temporada >= 2019, [col, "temporada"]].dropna().astype(float)
    r = smf.quantreg(f"{col} ~ I(temporada - 2018)", g).fit(q=q)
    b, (lo, hi) = r.params.iloc[1], r.conf_int().iloc[1]
    return (f"  {nombre}, regresión cuantílica q={q} a nivel de nido (2019-2025): {b:+.2f} {ud}/año [IC95 {lo:+.2f} a {hi:+.2f}]"
            f" (IC demasiado estrecho: trata los nidos como independientes)")


def txt_ajuste_mes(nombre: str, df: pd.DataFrame, col: str, desde: int = 2019) -> str:
    """Tendencia anual de una proporción ajustando por mes de aviso (recuentos temporada x mes)."""
    g = df[df.temporada >= desde].dropna(subset=[col]).assign(**{col: lambda x: x[col].astype(float)})
    g = g.groupby(["temporada", "mes_alta"])[col].agg(k="sum", n="size").reset_index()
    g = g[g.n > 0]
    g["prop"] = g.k / g.n
    g["anio"] = g.temporada - 2018
    f = "prop ~ anio + C(mes_alta)"
    kw = dict(family=sm.families.Binomial(), var_weights=g.n.values)
    r = smf.glm(f, g, **kw).fit(scale="X2")
    if r.scale < 1:
        r = smf.glm(f, g, **kw).fit()
    lo, hi = np.exp(r.conf_int().loc["anio"])
    return (f"  {ETIQ[desde]}{nombre}, ajustado por mes de aviso ({desde}-2025): OR/año {np.exp(r.params['anio']):.3f} "
            f"[IC95 {lo:.3f}-{hi:.3f}], p={r.pvalues['anio']:.3f} (escala {r.scale:.1f})")


def txt_escalon(nombre: str, k: pd.Series, n: pd.Series, corte: int = 2023, desde: int = 2019) -> str:
    """Tendencia lineal más escalón en `corte` (GLM cuasibinomial por temporada)."""
    k, n = k.astype(float), n.astype(float)
    m = (n.index >= desde) & (n > 0)
    k, n = k[m], n[m]
    t = np.asarray(n.index, dtype=float)
    X = np.column_stack([np.ones_like(t), t - 2018, (t >= corte).astype(float)])
    kw = dict(family=sm.families.Binomial(), var_weights=n.values)
    r = sm.GLM((k / n).values, X, **kw).fit(scale="X2")
    if r.scale < 1:
        r = sm.GLM((k / n).values, X, **kw).fit()
    lo, hi = np.exp(r.conf_int()[2])
    pre, post = n.index < corte, n.index >= corte
    return (f"  {nombre}: {desde}-{corte - 1} {P(k[pre].sum() / n[pre].sum())} -> {corte}-2025"
            f" {P(k[post].sum() / n[post].sum())}; escalón en {corte} (con tendencia):"
            f" OR {np.exp(r.params[2]):.2f} [IC95 {lo:.2f}-{hi:.2f}], p={r.pvalues[2]:.3f}")


# ---------------------------------------------------------------- datos
def base(ruta: Path) -> tuple[pd.DataFrame, dict]:
    d = preparar(ruta)
    info = {"n_preparar": len(d)}
    info["ene_mar"] = int((d.mes_alta <= 3).sum())
    d = d[d.mes_alta >= 4].copy()  # ventana común abril-diciembre
    info["neg"] = int((d.dias < 0).sum())
    info["neg_detalle"] = d.loc[d.dias < 0, "dias"].astype(int).tolist()
    info["gt90"] = int((d.dias > 90).sum())
    d.loc[d.dias < 0, "dias"] = np.nan
    info["alt_inval"] = int(((d.altura == 0) | (d.altura > 60)).sum())
    info["alt0_por_t"] = d[d.altura == 0].groupby("temporada").size().to_dict()
    d.loc[(d.altura == 0) | (d.altura > 60), "altura"] = np.nan
    info["diam_inval"] = int(((d.diam == 0) | (d.diam >= 250)).sum())
    d.loc[(d.diam == 0) | (d.diam >= 250), "diam"] = np.nan
    d["pendiente"] = d.estado.str.contains("PENDIENTE", na=False)
    d["cerrado"] = d.eliminado | d.no_elim
    d["le3"] = (d.dias <= 3).where(d.dias.notna())
    d["le7"] = (d.dias <= 7).where(d.dias.notna())
    d["primavera"] = d.mes_alta.between(4, 6)
    corte = pd.to_datetime(dict(year=d.temporada, month=11, day=1))
    d["antes_nov"] = (d.cierre < corte).where(d.cierre.notna() & d.dias.notna())
    d["alto15"] = (d.altura >= 15).where(d.altura.notna())
    d["peq10"] = (d.diam <= 10).where(d.diam.notna())
    return d, info


def comun_asiatica(ruta: Path) -> pd.DataFrame:
    """Avisos de asiática y de avispa común por temporada, misma limpieza y ventana abr-dic."""
    d = cargar(ruta)
    d = d.drop_duplicates(subset=[c for c in d.columns if c != "alta_orig"])
    d = d[~d.estado.str.contains("ANULADA", na=False) & d.alta.notna() & d.alta.dt.month.ge(4)]
    d = d[d.anio.between(2018, 2025) & d.alta.dt.year.between(2018, 2025)]
    sp = np.select([d.especie.str.contains("ASI", na=False), d.especie.str.contains("COM", na=False)],
                   ["asiatica", "comun"], "otra")
    return pd.crosstab(d.alta.dt.year.rename("temporada"), sp)[["asiatica", "comun"]]


def q(s: pd.Series, x: float) -> float:
    s = s.dropna()
    return float(s.quantile(x)) if len(s) else np.nan


def resumen(g: pd.DataFrame) -> pd.Series:
    el = g[g.eliminado]
    ne = g[g.no_elim]
    cer = g[g.cerrado]
    agt = cer.agente.value_counts()
    return pd.Series({
        "nidos": len(g),
        "eliminados": len(el), "no_eliminables": len(ne), "pendientes": int(g.pendiente.sum()),
        "pct_no_eliminables": ne.shape[0] / len(g), "pct_pendientes": g.pendiente.mean(),
        "n_dias_elim": int(el.dias.notna().sum()),
        "dias_mediana": q(el.dias, .5), "dias_p75": q(el.dias, .75), "dias_p90": q(el.dias, .9),
        "pct_le3": el.le3.mean(), "pct_le7": el.le7.mean(),
        "dias_mediana_todos_cerrados": q(cer.dias, .5), "dias_p90_todos_cerrados": q(cer.dias, .9),
        "dias_mediana_basalan": q(el.dias[el.agente == "BASALAN"], .5),
        "dias_p90_basalan": q(el.dias[el.agente == "BASALAN"], .9),
        "dias_mediana_bomberos": q(el.dias[el.agente == "BOMBEROS"], .5),
        "dias_p90_bomberos": q(el.dias[el.agente == "BOMBEROS"], .9),
        "pct_basalan": agt.get("BASALAN", 0) / len(cer), "pct_bomberos": agt.get("BOMBEROS", 0) / len(cer),
        "pct_ayuntamiento": agt.get("AYUNTAMIENTO", 0) / len(cer),
        "altura_mediana_elim": q(el.altura, .5), "altura_mediana_no_elim": q(ne.altura, .5),
        "pct_alto15_elim": el.alto15.mean(), "pct_alto15_no_elim": ne.alto15.mean(),
        "pct_elim_entre_alto15": el.alto15.sum() / (el.alto15.sum() + ne.alto15.sum()),
        "pct_primavera": g.primavera.mean(),
        "pct_elim_antes_1nov": el.antes_nov.mean(),
        "diam_mediana_elim": q(el.diam, .5), "pct_diam_le10_elim": el.peq10.mean(),
        "diam_mediana_elim_jul_dic": q(el.diam[el.mes_alta >= 7], .5),
    })


def registro(d: pd.DataFrame, ruta: Path) -> list[str]:
    """Comprobaciones del registro: cambio de «usuario» en 2023 y hueco de enero-febrero de 2019."""
    L = ["", "## 10. Cambio del campo «usuario» el 01/01/2023: ¿saltos falsos?"]
    u = pd.crosstab(d.temporada, d.usuario_tipo, normalize="index")
    L.append("  Quién da el aviso (% ayuntamiento / Basalan / otros: bomberos, administrador): " + "  ".join(
        f"{t}: {100*r.get('AYUNTAMIENTO', 0):.1f}/{100*r.get('BASALAN', 0):.1f}/{100*r.get('OTROS', 0):.1f}"
        for t, r in u.iterrows()))
    L.append("  El reparto por tipo de usuario no cambia en 2023: solo se pierde el nombre del municipio en"
             " «AYUNTAMIENTO <municipio>» (el municipio sigue en su columna).")
    n = d.groupby("temporada").size()
    cer = d[d.cerrado]
    nc = cer.groupby("temporada").size()
    cuenta = lambda df, col, v: df.groupby("temporada")[col].apply(lambda s: (s == v).sum())  # noqa: E731
    L.append(txt_escalon("% no eliminables", d.groupby("temporada").no_elim.sum(), n))
    L.append(txt_escalon("% cerrados por bomberos", cuenta(cer, "agente", "BOMBEROS"), nc))
    L.append(txt_escalon("% cerrados por ayuntamiento", cuenta(cer, "agente", "AYUNTAMIENTO"), nc))
    L.append(txt_escalon("% avisos dados por Basalan", cuenta(d, "usuario_tipo", "BASALAN"), n))
    el = d[d.eliminado]
    L.append(txt_escalon("% eliminados en <= 3 días", el.groupby("temporada").le3.sum(),
                         el.groupby("temporada").le3.count()))
    g = d[d.temporada >= 2019].assign(post=lambda x: np.where(x.temporada >= 2023, "2023-25", "2019-22"))
    ne = g.groupby(["usuario_tipo", "post"]).no_elim.agg(["mean", "size"])
    L.append("  % no eliminables según quién avisa: " + "; ".join(
        f"{u_} {pe} {P(r['mean'])} (n={int(r['size'])})" for (u_, pe), r in ne.iterrows()))
    nea = g[g.no_elim].groupby(["temporada", "agente"]).size().unstack(fill_value=0)
    L.append("  No eliminables por agente que cierra (Basalan / bomberos): " + "  ".join(
        f"{t}: {int(r.get('BASALAN', 0))}/{int(r.get('BOMBEROS', 0))}" for t, r in nea.iterrows()))
    ot = g[g.usuario_tipo == "OTROS"]
    L.append("  Avisos de usuario «otros» (sobre todo BOMBEROS) cerrados por bomberos: " + "; ".join(
        f"{pe} {P((s.agente == 'BOMBEROS').mean())} (n={len(s)})" for pe, s in ot.groupby("post")))
    pend = g[g.pendiente].groupby("temporada").size().reindex(range(2019, 2026), fill_value=0)
    L.append("  Pendientes 2019-2025: " + str(pend.to_dict()) + ".")
    vac = g.groupby("temporada").agg(coord=("lat", lambda s: s.isna().mean()), ubic=("ubic", lambda s: s.isna().mean()))
    L.append("  Campos vacíos (% coordenadas / % ubicación): " + "  ".join(
        f"{t}: {100*r.coord:.1f}/{100*r.ubic:.1f}" for t, r in vac.iterrows()))

    # Hueco de enero-febrero de 2019
    r = cargar(ruta)
    L += ["", "## 11. Avisos de enero-marzo de 2019 (temporada 2018): ¿hueco real o efecto de la corrección?"]
    for a in range(2018, 2026):
        z = r[r.anio == a].sort_values("num")
        L.append(f"  Registro {a}: nº 1 el {z.alta.iloc[0]:%d/%m/%Y}, última fecha {z.alta.max():%d/%m/%Y};"
                 f" filas con fecha original en ene-mar: {int(z.alta_orig.dt.month.le(3).sum())},"
                 f" tras corregir (ene-mar de {a}): {int((z.alta.dt.month.le(3) & z.alta.dt.year.eq(a)).sum())}")
    z = r[r.anio == 2019].sort_values("num")
    L.append("  Registro 2019, actuaciones 1-5 (original -> corregida): " + "; ".join(
        f"{int(x.num)}: {x.alta_orig:%Y-%m-%d} -> {x.alta:%Y-%m-%d}" for x in z.head(5).itertuples()))
    amb = z[z.alta_orig.dt.year.eq(2019) & z.alta_orig.dt.month.le(2)]
    L.append(f"  Filas del registro 2019 con fecha original en ene-feb de 2019: {len(amb)}; con día <= 12:"
             f" {int((amb.alta_orig.dt.day <= 12).sum())}; nº de actuación entre {int(amb.num.min())} y"
             f" {int(amb.num.max())} (las fechas de esos números no ambiguas caen de abril a diciembre).")
    L.append("  Conclusión: el registro 2018 acaba el 30/12/2018 y el 2019 empieza con el nº 1 el 11/03/2019"
             " (el nº 5, 13/03/2019, no es ambiguo). Las fechas originales de ene-feb de 2019 son día/mes"
             " intercambiados de abril-diciembre, según su nº correlativo. El hueco de enero-febrero de 2019 está"
             " en el registro publicado, no lo crea la corrección. No afecta a este script, que solo usa avisos"
             " de abril a diciembre. Hasta 2022 los registros no siguen el año natural (el de 2020 empieza el"
             " 13/02/2020 y el de 2019 acaba el 04/02/2020), así que los avisos de invierno son incomparables"
             " entre años: en la web, mejor no sumar ene-mar del año siguiente a la temporada.")
    return L


# ---------------------------------------------------------------- main
def main() -> None:
    a = sys.argv[1:]
    ruta = Path(a[0]) if len(a) > 0 else RAIZ / "data/raw/bizkaia/avispa_asiatica/nidos.csv"
    ruta_pob = Path(a[1]) if len(a) > 1 else RAIZ / "data/raw/ine/padron_bizkaia_2905_2017_2025.json"
    salida = Path(a[2]) if len(a) > 2 else RAIZ / "outputs"
    salida.mkdir(parents=True, exist_ok=True)

    d, info = base(ruta)
    L = ["# ¿Ha mejorado el control de la avispa asiática en Bizkaia? Indicadores de respuesta, 2018-2025",
         "",
         "## Base y limpieza",
         f"  Nidos de asiática sin anuladas, temporadas 2018-2025 (preparar): {info['n_preparar']}.",
         f"  Ventana común abril-diciembre: se apartan {info['ene_mar']} avisos de enero-marzo (nidos viejos);"
         f" quedan {len(d)}.",
         f"  Días aviso-cierre negativos: {info['neg']} ({info['neg_detalle']}), anulados (todos en 2018-2020,"
         " años con fechas día/mes corregidas). Más de 90 días: "
         f"{info['gt90']}, se conservan (los percentiles no dependen de ellos).",
         f"  Altura no válida (0 m o > 60 m): {info['alt_inval']}; los 0 m son de 2018-2019 "
         f"({info['alt0_por_t']}), relleno. Diámetro no válido (0 o >= 250 cm): {info['diam_inval']}.",
         "  Días en números enteros (las fechas no traen hora): «<= 3 días» incluye el mismo día.",
         "  PERIODO PRINCIPAL 2019-2025 (7 temporadas). 2018 (primer año del registro, incompleto: empieza en"
         " abril, alturas a 0, 16 % sin coordenadas) solo como sensibilidad, marcada «[sensib.]».",
         "  Las tendencias usan la temporada como unidad: poca potencia, y un p > 0,05 no demuestra que no"
         " haya cambio.",
         "  Proporciones: GLM cuasibinomial por temporada (escala = chi2 de Pearson / gl). Los modelos"
         " ajustados por mes usan celdas temporada x mes; su IC puede ser algo optimista porque las celdas"
         " de una misma temporada no son independientes.",
         ]

    T = d.groupby("temporada").apply(resumen, include_groups=False)
    ca = comun_asiatica(ruta)
    T["avisos_asiatica_abr_dic"] = ca.asiatica
    T["avisos_comun_abr_dic"] = ca.comun
    T["ratio_asiatica_comun"] = ca.asiatica / ca.comun
    if not (T.nidos == T.avisos_asiatica_abr_dic).all():
        L.append("  Aviso: el recuento de asiática del control con avispa común no coincide con la base"
                 " (la base usa además la regla de temporada y la reparación de fechas): "
                 + str((T.avisos_asiatica_abr_dic - T.nidos).to_dict()))
    n = T.nidos
    el = d[d.eliminado]

    # 1. Tiempo de respuesta
    L += ["", "## 1. Días entre aviso y cierre (nidos eliminados con fecha válida)",
          "  temp   n  mediana  p75  p90   <=3d    <=7d  | todos cerrados: mediana p90"]
    for t, r in T.iterrows():
        L.append(f"  {t} {int(r.n_dias_elim):>5} {r.dias_mediana:>6.0f} {r.dias_p75:>5.0f} {r.dias_p90:>4.0f}"
                 f" {P(r.pct_le3):>7} {P(r.pct_le7):>7} | {r.dias_mediana_todos_cerrados:>4.0f} {r.dias_p90_todos_cerrados:>4.0f}")
    k3 = el.groupby("temporada").le3.sum()
    k7 = el.groupby("temporada").le7.sum()
    nd = el.groupby("temporada").le3.count()
    L += txt_prop("% cerrados en <= 3 días", k3, nd)
    L += txt_prop("% cerrados en <= 7 días", k7, nd)
    L.append(txt_ajuste_mes("% <= 3 días", el, "le3"))
    L.append(txt_ajuste_mes("% <= 3 días", el, "le3", 2018))
    L.append(txt_ajuste_mes("% <= 7 días", el, "le7"))
    L.append(txt_ajuste_mes("% <= 7 días", el, "le7", 2018))
    L += txt_nivel("Mediana de días", T.dias_mediana, "días")
    L += txt_nivel("p75 de días", T.dias_p75, "días")
    L += txt_nivel("p90 de días", T.dias_p90, "días")
    L.append(txt_quantreg("Mediana de días", el, "dias", .5, "días"))
    L.append(txt_quantreg("p90 de días", el, "dias", .9, "días"))
    T19 = T[T.index >= 2019]
    rho = np.corrcoef(T19.nidos, T19.dias_p90)[0, 1]
    L.append(f"  Carga y espera: correlación (Pearson, 2019-2025) entre nidos y p90 de días: {rho:.2f}.")
    # por agente
    L.append("  Por agente (eliminados): mediana / p90 de días")
    for t, r in T.iterrows():
        L.append(f"    {t}: Basalan {r.dias_mediana_basalan:.0f} / {r.dias_p90_basalan:.0f};"
                 f" bomberos {r.dias_mediana_bomberos:.0f} / {r.dias_p90_bomberos:.0f}")
    b = el[el.agente == "BASALAN"]
    L += txt_prop("Basalan, % <= 7 días", b.groupby("temporada").le7.sum(), b.groupby("temporada").le7.count())

    # 2. Estado final
    L += ["", "## 2. Nidos no eliminables y pendientes (sobre todos los avisos abr-dic)"]
    L.append("  " + "  ".join(f"{t}: {P(r.pct_no_eliminables)} / {P(r.pct_pendientes)}" for t, r in T.iterrows())
             + "   (no elim. / pend.)")
    L += txt_prop("% no eliminables", T.no_eliminables, n)
    for desde in (2019, 2018):
        L.append(txt_ajuste_mes("% no eliminables", d.assign(ne=lambda x: x.no_elim.astype(float)), "ne", desde))
    L.append(f"  Pendientes: {int(T.pendientes.sum())} en total; por temporada {T.pendientes.astype(int).to_dict()}."
             " Son registros antiguos sin cerrar (no se ha comprobado su motivo), no colas actuales:"
             " no sirven como indicador de mejora.")

    # 3. Altura
    L += ["", "## 3. Altura: ¿se retiran ahora nidos más altos?",
          "  temp  alt.med elim / no elim   %>=15 m elim / no elim   % eliminados entre los >=15 m"]
    for t, r in T.iterrows():
        L.append(f"  {t}  {r.altura_mediana_elim:>5.0f} / {r.altura_mediana_no_elim:<5.0f}"
                 f"        {P(r.pct_alto15_elim):>7} / {P(r.pct_alto15_no_elim):<7}"
                 f"        {P(r.pct_elim_entre_alto15)}")
    al = d[d.alto15.eq(True) & d.cerrado]
    L += txt_prop("% eliminados entre nidos >= 15 m", al.groupby("temporada").eliminado.sum(),
                  al.groupby("temporada").size())
    L += txt_prop("% >= 15 m entre eliminados", el.groupby("temporada").alto15.sum(),
                  el.groupby("temporada").alto15.count())
    L.append("  Ojo: la altura la anota quien avisa o quien acude; no se sabe si es medida o estimada.")

    # 4. Agente
    L += ["", "## 4. Quién cierra (nidos cerrados): Basalan / bomberos / ayuntamiento"]
    L.append("  " + "  ".join(f"{t}: {100*r.pct_basalan:.1f}/{100*r.pct_bomberos:.1f}/{100*r.pct_ayuntamiento:.1f}"
                              for t, r in T.iterrows()))
    cer = d[d.cerrado]
    nc = cer.groupby("temporada").size()
    L += txt_prop("% cerrados por bomberos", cer.groupby("temporada").agente.apply(lambda s: (s == "BOMBEROS").sum()), nc)
    L.append(f"  Bomberos frente a Basalan: altura mediana de lo que cierran {cer[cer.agente == 'BOMBEROS'].altura.median():.0f}"
             f" m frente a {cer[cer.agente == 'BASALAN'].altura.median():.0f} m;"
             f" % no eliminable {P(cer[cer.agente == 'BOMBEROS'].no_elim.mean())} frente a"
             f" {P(cer[cer.agente == 'BASALAN'].no_elim.mean())}.")
    L.append("  El conjunto no tiene columna de método de retirada (pértiga, biocida, plataforma...).")

    # 5. Calendario
    L += ["", "## 5. Calendario: avisos en primavera (abr-jun) y eliminados antes del 01/11"]
    L.append("  " + "  ".join(f"{t}: {P(r.pct_primavera)} / {P(r.pct_elim_antes_1nov)}" for t, r in T.iterrows()))
    L += txt_prop("% avisos en primavera", d.groupby("temporada").primavera.sum(), n)
    L += txt_prop("% eliminados antes del 01/11", el.groupby("temporada").antes_nov.sum(),
                  el.groupby("temporada").antes_nov.count())
    L.append("  «Antes del 01/11» depende sobre todo de cuándo se avisa (calendario de la población y de"
             " la detección), no solo de la rapidez de la respuesta.")
    oct_ = el[el.mes_alta == 10]
    L += txt_prop("Avisados en octubre y eliminados antes del 01/11", oct_.groupby("temporada").antes_nov.sum(),
                  oct_.groupby("temporada").antes_nov.count())

    # 6. Diámetro
    L += ["", "## 6. Diámetro de los nidos eliminados (cm)"]
    L.append("  mediana (todos | avisados jul-dic) y % <= 10 cm: " + "  ".join(
        f"{t}: {r.diam_mediana_elim:.0f}|{r.diam_mediana_elim_jul_dic:.0f} {P(r.pct_diam_le10_elim)}"
        for t, r in T.iterrows()))
    L += txt_nivel("Mediana de diámetro", T.diam_mediana_elim, "cm")
    L.append(txt_quantreg("Mediana de diámetro", el, "diam", .5, "cm"))
    L += txt_prop("% eliminados <= 10 cm", el.groupby("temporada").peq10.sum(), el.groupby("temporada").peq10.count())
    L.append(txt_ajuste_mes("% <= 10 cm", el, "peq10"))
    L.append(txt_ajuste_mes("% <= 10 cm", el, "peq10", 2018))
    L.append("  No consta si el diámetro se anota al avisar o al retirar; es una estimación redondeada"
             " (picos en 10, 20, 30... y 1 y 5 cm).")

    # 7. Control de esfuerzo de aviso
    L += ["", "## 7. Avisos de asiática por cada aviso de avispa común (abr-dic)"]
    L.append("  " + "  ".join(f"{t}: {int(r.avisos_asiatica_abr_dic)}/{int(r.avisos_comun_abr_dic)}="
                              f"{r.ratio_asiatica_comun:.1f}" for t, r in T.iterrows()))
    L += txt_prop("Peso de la asiática en (asiática + común)", T.avisos_asiatica_abr_dic,
                  T.avisos_asiatica_abr_dic + T.avisos_comun_abr_dic)
    L.append("  La avispa común es nativa y no se gestiona igual: es un control aproximado de las ganas de"
             " avisar, no una medida de población.")

    # 8. Tamaño de municipio
    pob = padron(ruta_pob)
    tam = pd.cut(pob[2025], TAMANOS[0], labels=TAMANOS[1])
    d["tamano"] = d.muni.map(tam)
    d["periodo"] = np.select([d.temporada == 2018, d.temporada <= 2020, d.temporada >= 2023],
                             ["2018", "2019-20", "2023-25"], "2021-22")
    L += ["", "## 8. Por tamaño de municipio (padrón 2025): 2019-20 frente a 2023-25",
          f"  Sin tamaño (municipio no cruzado): {int(d.tamano.isna().sum())}",
          "  tamaño         periodo   nidos  med.días p90  %<=7d   %no elim  diám.med"]
    for (tm, pe), g in d[d.periodo.isin(["2019-20", "2023-25"])].groupby(["tamano", "periodo"], observed=True):
        e = g[g.eliminado]
        L.append(f"  {tm:<13} {pe}  {len(g):>6}  {e.dias.median():>5.0f} {q(e.dias, .9):>5.0f}  {P(e.le7.mean()):>7}"
                 f"  {P(g.no_elim.mean()):>7}  {e.diam.median():>5.0f}")

    # CSV por temporada
    T.index.name = "temporada"
    enteros = ["nidos", "eliminados", "no_eliminables", "pendientes", "n_dias_elim",
               "avisos_asiatica_abr_dic", "avisos_comun_abr_dic"]
    T[enteros] = T[enteros].astype(int)
    T.round(6).to_csv(salida / "avispa_indicadores_temporada.csv")

    # CSV por temporada y mes
    M = (d.groupby(["temporada", "mes_alta"]).apply(
        lambda g: pd.Series({
            "nidos": len(g), "eliminados": int(g.eliminado.sum()), "no_eliminables": int(g.no_elim.sum()),
            "dias_mediana_elim": q(g.dias[g.eliminado], .5), "dias_p90_elim": q(g.dias[g.eliminado], .9),
            "pct_le3_elim": g.le3[g.eliminado].mean(), "pct_le7_elim": g.le7[g.eliminado].mean(),
            "diam_mediana_elim": q(g.diam[g.eliminado], .5),
            "pct_bomberos": (g.agente[g.cerrado] == "BOMBEROS").mean()}), include_groups=False))
    M[["nidos", "eliminados", "no_eliminables"]] = M[["nidos", "eliminados", "no_eliminables"]].astype(int)
    M.round(6).to_csv(salida / "avispa_indicadores_mes.csv")

    # CSV de tramos de días entre aviso y cierre (eliminados con fecha válida), para las barras apiladas
    # de la web. Días enteros: «mismo día» = 0; los tramos suman la columna pct_le7 del CSV por temporada.
    ev = d[d.eliminado & d.dias.notna()]
    tramo = pd.cut(ev.dias, [-0.5, 0.5, 3.5, 7.5, np.inf],
                   labels=["mismo_dia", "de_1_a_3_dias", "de_4_a_7_dias", "mas_de_7_dias"])
    D = pd.crosstab(ev.temporada, tramo, normalize="index").round(6)
    D.insert(0, "n", ev.groupby("temporada").size())
    D.columns.name = None
    D.to_csv(salida / "avispa_dias_tramos.csv")
    # lectura rápida mensual
    L += ["", "## 9. Por mes de aviso (todas las temporadas): mediana / p90 de días, % <= 7 días (eliminados)"]
    for m, g in el.groupby("mes_alta"):
        L.append(f"  mes {m:>2}: n={len(g):>5}  {g.dias.median():.0f} / {q(g.dias, .9):.0f}  {P(g.le7.mean())}")

    L += registro(d, ruta)
    L += ["", "Archivos: avispa_indicadores_temporada.csv (una fila por temporada) y"
          " avispa_indicadores_mes.csv (temporada x mes de aviso); avispa_dias_tramos.csv (tramos de días)."]
    (salida / "avispa_indicadores_control.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
