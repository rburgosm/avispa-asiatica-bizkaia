"""Impacto socioeconómico de la avispa asiática en Bizkaia: cruces de los nidos con otros
conjuntos de Open Data Bizkaia (ODB).

Uso:
    python -I scripts/avispa_impacto.py <raiz_bizkaia> <padron_ine.json> [salida.txt]

<raiz_bizkaia> es la carpeta con un subdirectorio por conjunto descargado:
  avispa_asiatica/nidos.csv, explotaciones-ganaderas/, declaracion-superficies/,
  parcelas-registro-viticola/, speis/, playas/, areas-esparcimiento/,
  encomiendas-gestion/, subvenciones-otorgadas/, contratos-menores/, contratos-no-menores/,
  convenios/, plan-anual-contratacion*/, liquidacion-presupuestos/,
  memoria-anual-hacienda-foral-irpf/, parcelario-catastral/{municipios,parcelas_colmenares}.geojson
  (estos dos, del servicio REST del parcelario catastral; ver descargar_parcelas_colmenares.py),
  informacion-geografica-playas/playas.geojson.
Escribe un resumen compacto (por defecto outputs/avispa_impacto.txt).
"""
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explorar_avispa import cargar as cargar_nidos  # noqa: E402

CRS = "EPSG:25830"
MESES = "ENERO FEBRERO MARZO ABRIL MAYO JUNIO JULIO AGOSTO SEPTIEMBRE OCTUBRE NOVIEMBRE DICIEMBRE".split()
OUT = []


def p(*a):
    OUT.append(" ".join(str(x) for x in a))


# ----------------------------------------------------------------- utilidades
def norm(x) -> str:
    """Mayúsculas sin tildes (conserva la Ñ), sin espacios sobrantes."""
    x = str(x).replace("Ñ", "__N__").replace("ñ", "__n__")
    x = "".join(c for c in unicodedata.normalize("NFD", x) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", x.replace("__N__", "Ñ").replace("__n__", "Ñ").upper()).strip()


def leer(path: Path) -> pd.DataFrame:
    t = path.read_bytes().decode("utf-8-sig", errors="replace")
    if "Ã" in t[:300000]:
        t = t.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
    d = pd.read_csv(io.StringIO(t), dtype=str, on_bad_lines="skip")
    d.columns = [c.split("/")[-1].strip() for c in d.columns]
    return d


def num(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip().str.strip('="')
    s = pd.Series(np.where(s.str.contains(",", regex=False),
                           s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False), s),
                  index=s.index)
    return pd.to_numeric(s, errors="coerce")


def cod(s: pd.Series) -> pd.Series:
    """Código INE de municipio como entero de 3 cifras (48001 -> 1, ="022" -> 22)."""
    v = pd.to_numeric(s.astype(str).str.replace(r"[^0-9]", "", regex=True), errors="coerce")
    return (v % 1000).astype("Int64")


def ultimo_por_anio(carpeta: Path, prefijo: str) -> dict:
    """Ficheros trimestrales acumulados: devuelve {año: fichero con el último mes}."""
    orden = {"marzo": 3, "junio": 6, "septiembre": 9, "diciembre": 12}
    res = {}
    for f in carpeta.glob(f"{prefijo}-*.csv"):
        m = re.search(r"(20\d\d)-([a-zA-Z]+)$", f.stem)
        if not m:
            continue
        y, mes = int(m.group(1)), orden.get(m.group(2).lower(), 0)
        if y not in res or mes > res[y][0]:
            res[y] = (mes, f)
    return {y: v[1] for y, v in sorted(res.items())}


def spear(x, y, etiqueta):
    m = pd.notna(x) & pd.notna(y)
    r, pv = stats.spearmanr(x[m], y[m])
    p(f"  Spearman {etiqueta}: rho={r:.2f}, p={pv:.3g}, n={m.sum()}")
    return r, pv


def coefs(res, nombres=None, exp=False):
    t = []
    for k in res.params.index:
        if k == "const":
            continue
        b, pv = res.params[k], res.pvalues[k]
        t.append(f"{k}: {'exp(b)=' + format(np.exp(b), '.3f') if exp else 'b=' + format(b, '.3f')} (p={pv:.3g})")
    return "; ".join(t)


def geom(txt):
    """GeoJSON en texto; algunos «MultiPolygon» del registro vitícola traen un nivel de anidamiento menos."""
    j = json.loads(txt)
    try:
        return shape(j)
    except (TypeError, ValueError):
        if j.get("type") == "MultiPolygon":
            return shape({"type": "Polygon", "coordinates": j["coordinates"]})
        raise


def contar_cerca(puntos: gpd.GeoDataFrame, objetivos: gpd.GeoDataFrame, radio: float) -> pd.Series:
    """Nº de puntos a <= radio metros de cada geometría objetivo (índice de objetivos)."""
    b = objetivos[["geometry"]].copy()
    b["geometry"] = b.geometry.buffer(radio)
    b.index.name = None
    j = gpd.sjoin(puntos[["geometry"]], b, predicate="within", how="inner")
    return j.groupby("index_right").size().reindex(objetivos.index, fill_value=0)


# ----------------------------------------------------------------- carga básica
def municipios(raiz: Path) -> gpd.GeoDataFrame:
    m = gpd.read_file(raiz / "parcelario-catastral" / "municipios.geojson").to_crs(CRS)
    m["cod"] = m.Codigo_Municipio.astype(int)
    m["nombre"] = m.Descripcion.map(norm)
    m = m.dissolve("cod", aggfunc="first").reset_index()
    m["km2"] = m.area / 1e6
    return m[["cod", "nombre", "km2", "geometry"]]


def poblacion(ruta: Path) -> pd.Series:
    j = json.loads(ruta.read_text(encoding="utf-8"))
    return pd.Series({norm(x["Nombre"].split(". ")[0]): x["Data"][0]["Valor"] for x in j
                      if ". Total. Total habitantes" in x["Nombre"]})


def main() -> None:
    raiz, ruta_pob = Path(sys.argv[1]), Path(sys.argv[2])
    salida = Path(sys.argv[3] if len(sys.argv) > 3 else "outputs/avispa_impacto.txt")

    muni = municipios(raiz)
    nom2cod = dict(zip(muni.nombre, muni.cod))
    irpf = leer(raiz / "memoria-anual-hacienda-foral-irpf" / "irpf-av111-2024.csv")
    irpf["cod"] = cod(irpf.CODIGO_INE_MUNICIPIO)
    irpf = irpf.dropna(subset=["cod"])
    for a, b in zip(irpf.MUNICIPIO.map(norm), irpf.cod):  # nombres alternativos
        nom2cod.setdefault(a, int(b))
    alias = {"ARRANKUDIAGA": "ARRANKUDIAGA-ZOLLO", "IURETA": "IURRETA"}
    def a_cod(nombre):
        n = norm(nombre)
        n = alias.get(n, n)
        if n in nom2cod:
            return nom2cod[n]
        for k, v in nom2cod.items():  # nombres bilingües: «KARRANTZA HARANA/VALLE DE CARRANZA»
            if n and (n in k.split("/") or k in n.split("/") or k.startswith(n) or n.startswith(k)):
                return v
        return pd.NA
    pob = poblacion(ruta_pob)
    M = muni.set_index("cod")[["nombre", "km2"]].copy()
    pc = pd.Series({a_cod(k): v for k, v in pob.items()})
    M["pob"] = pc.reindex(M.index)
    M["dens"] = M.pob / M.km2
    irpf = irpf.set_index("cod")
    M["renta_decl"] = (num(irpf.BASE_LIQUIDABLE) / num(irpf.NUMERO_DECLARACIONES)).reindex(M.index)
    BILBAO = nom2cod["BILBAO"]

    p("=== 0. DATOS Y CLAVES ===")
    p(f"Municipios (parcelario catastral): {len(M)}; superficie total {M.km2.sum():.0f} km²; "
      f"sin población cruzada: {M.pob.isna().sum()}; sin renta IRPF: {M.renta_decl.isna().sum()}")

    # ---- nidos
    d = cargar_nidos(raiz / "avispa_asiatica" / "nidos.csv")
    d = d[d.especie.eq("AVISPA ASIÁTICA") & d.estado.ne("ANULADA") & d.anio.between(2018, 2025)].copy()
    d["cod"] = d.muni.map(a_cod).astype("Int64")
    d["mes"] = d.alta.dt.month
    g = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.lon, d.lat), crs="EPSG:4326").to_crs(CRS)
    j = gpd.sjoin(g[["geometry"]], muni[["cod", "geometry"]], predicate="within", how="left")
    j = j[~j.index.duplicated()]
    g["cod_geo"] = j["cod"].astype("Int64")
    g["geo_ok"] = g.lat.notna() & g.cod_geo.notna()
    acuerdo = (g.cod_geo == g.cod)[g.geo_ok].mean()
    p(f"Nidos de asiática 2018-2025 (sin anuladas): {len(g)}; sin municipio cruzado: {g.cod.isna().sum()}; "
      f"con coordenada dentro de Bizkaia: {g.geo_ok.sum()} ({g.geo_ok.mean():.1%}); el punto cae en el "
      f"municipio declarado en el {acuerdo:.1%}")
    G = g[g.geo_ok].copy()  # para cruces espaciales

    def por_muni(mask):
        return g[mask].groupby("cod").size().reindex(M.index, fill_value=0)
    M["nidos_18_25"] = por_muni(g.anio.between(2018, 2025))
    M["nidos_21_25"] = por_muni(g.anio.between(2021, 2025))
    M["otono_21_25"] = por_muni(g.anio.between(2021, 2025) & g.mes.between(9, 11))
    M["nidos_km2_anio"] = M.nidos_18_25 / 8 / M.km2
    M["nidos_1000hab_anio"] = M.nidos_18_25 / 8 / M.pob * 1000
    M["nidos_km2_21_25"] = M.nidos_21_25 / 5 / M.km2
    M["otono_km2"] = M.otono_21_25 / 5 / M.km2
    S = M.drop(index=BILBAO)  # Bilbao tiene servicio propio: fuera de todos los contrastes
    p(f"Densidad de nidos (asiática, media anual 2018-2025): mediana {S.nidos_km2_anio.median():.2f} nidos/km²; "
      f"p90 {S.nidos_km2_anio.quantile(.9):.2f}; máx {S.nidos_km2_anio.max():.2f} ({S.nidos_km2_anio.idxmax() and M.loc[S.nidos_km2_anio.idxmax(), 'nombre']})")
    rr = stats.spearmanr(S.nidos_km2_anio, S.dens)
    p(f"Nidos/km² frente a densidad de población: rho={rr[0]:.2f} (p={rr[1]:.2g}); nidos/1.000 hab frente a "
      f"densidad: rho={stats.spearmanr(S.nidos_1000hab_anio, S.dens)[0]:.2f}. Los avisos siguen a la gente: "
      f"por eso todos los modelos controlan por densidad de población.")
    S = S.assign(log_nkm2=np.log(S.nidos_km2_21_25 + 0.05), log_dens=np.log(S.dens), log_pob=np.log(S.pob))

    # =================================================================== 1. APICULTURA
    p("\n=== 1. APICULTURA (registro de explotaciones ganaderas, especie «Abejas») ===")
    ab = {}
    for y in range(2021, 2026):
        e = leer(raiz / "explotaciones-ganaderas" / f"explotaciones-ganaderas-{y}.csv")
        e = e[e.ESPECIE.str.contains("Abej", na=False)].copy()
        e["cod"] = cod(e.CODIGO)
        e["censo"] = num(e.CENSO)
        e["pol"], e["par"] = num(e.POLIGONO), num(e.PARCELA)
        e["prof"] = e["CAPACIDAD PRODUCTIVA"].eq("Profesional")
        e["auto"] = e.AUTOCONSUMO.eq("S")
        e["trash"] = e["SISTEMA PRODUCTIVO"].eq("Trashumante")
        ab[y] = e
    p("Qué mide: una fila = una explotación apícola registrada (REGA); «CENSO» = nº de colmenas declarado "
      "(la declaración anual se hace en enero-febrero del año siguiente: la «fecha censo» de 2025 cae en 2025-2026). "
      "La columna de capacidad máxima vale 0 en todas: no informa. No hay enjambres ni producción de miel.")
    filas = []
    for y, e in ab.items():
        filas.append(dict(anio=y, explot=len(e), colmenas=int(e.censo.sum()), mediana=e.censo.median(),
                          censo0=int((e.censo == 0).sum()), prof=int(e.prof.sum()), col_prof=int(e.censo[e.prof].sum()),
                          autoconsumo=int(e.auto.sum()), trashum=int(e.trash.sum()), munis=e.cod.nunique(),
                          con_parcela=int(e.par.notna().sum()), p90=e.censo.quantile(.9)))
    t = pd.DataFrame(filas).set_index("anio")
    p(t.to_string())
    e21, e25 = ab[2021], ab[2025]
    for nombre, f in [("<10 colmenas", lambda e: e.censo < 10), ("10-49", lambda e: e.censo.between(10, 49)),
                      ("50-149", lambda e: e.censo.between(50, 149)), (">=150", lambda e: e.censo >= 150)]:
        p(f"  Explotaciones {nombre}: 2021 {f(e21).sum()} ({int(e21.censo[f(e21)].sum())} colmenas) -> "
          f"2025 {f(e25).sum()} ({int(e25.censo[f(e25)].sum())} colmenas)")
    p("Lectura: se pierden explotaciones pequeñas (autoconsumo y <10 colmenas); las colmenas totales se mantienen "
      "(~9.200-9.900) y crecen las grandes. Caída brusca 2023->2024 (-40 explotaciones, -26 de autoconsumo): puede ser "
      "una depuración del registro, no solo abandonos.")

    for y in (2021, 2025):
        M[f"expl_{y}"] = ab[y].groupby("cod").size().reindex(M.index, fill_value=0)
        M[f"colm_{y}"] = ab[y].groupby("cod").censo.sum().reindex(M.index, fill_value=0)
    S = S.join(M[["expl_2021", "expl_2025", "colm_2021", "colm_2025"]])
    A = S[S.expl_2021 > 0].copy()
    A["var_expl"] = (A.expl_2025 - A.expl_2021) / A.expl_2021
    p(f"\n1a. Municipios con colmenares en 2021 (sin Bilbao): {len(A)}. Pierden explotaciones {int((A.expl_2025 < A.expl_2021).sum())}, "
      f"igual {int((A.expl_2025 == A.expl_2021).sum())}, ganan {int((A.expl_2025 > A.expl_2021).sum())}")
    q = pd.qcut(A.nidos_km2_21_25, 4, labels=["Q1 menos nidos", "Q2", "Q3", "Q4 más nidos"])
    tq = A.groupby(q, observed=True).agg(munis=("nombre", "size"), nidos_km2=("nidos_km2_21_25", "median"),
                                         expl_2021=("expl_2021", "sum"), expl_2025=("expl_2025", "sum"),
                                         colm_2021=("colm_2021", "sum"), colm_2025=("colm_2025", "sum"))
    tq["var_expl_%"] = (100 * (tq.expl_2025 / tq.expl_2021 - 1)).round(1)
    tq["var_colm_%"] = (100 * (tq.colm_2025 / tq.colm_2021 - 1)).round(1)
    p("Por cuartil de densidad de nidos 2021-2025 (nidos/km²/año):")
    p(tq.round(2).to_string())
    spear(A.nidos_km2_21_25, A.var_expl, "nidos/km² vs variación relativa de explotaciones 2021-25")
    spear(A.nidos_1000hab_anio, A.var_expl, "nidos/1.000 hab vs variación relativa de explotaciones")
    B = A[A.colm_2021 > 0]
    spear(B.nidos_km2_21_25, (B.colm_2025 - B.colm_2021) / B.colm_2021, "nidos/km² vs variación relativa de colmenas")
    X = sm.add_constant(A[["log_nkm2", "log_dens"]])
    glm = sm.GLM(A.expl_2025, X, family=sm.families.Poisson(), offset=np.log(A.expl_2021)).fit(scale="X2")
    p(f"  Cuasi-Poisson expl_2025 ~ log(nidos/km²) + log(densidad), offset log(expl_2021): {coefs(glm, exp=True)}; "
      f"dispersión {glm.scale:.2f}")
    X = sm.add_constant(A[["log_nkm2", "log_dens", "log_pob"]])
    ols = sm.OLS(np.log((A.expl_2025 + 0.5) / (A.expl_2021 + 0.5)), X).fit(cov_type="HC3")
    p(f"  MCO log((expl25+0,5)/(expl21+0,5)) ~ log nidos/km² + log densidad + log población (HC3): {coefs(ols)}; R²={ols.rsquared:.2f}")
    S["tiene_colm"] = (S.expl_2021 > 0).astype(int)
    spear(S.nidos_km2_21_25, S.expl_2021 / S.km2, "nidos/km² vs colmenares 2021 por km² (todos los municipios)")

    # ---- 1b. colmenar a colmenar
    p("\n1b. Colmenar a colmenar (parcela catastral municipio-polígono-parcela; servicio REST del parcelario):")
    pc = gpd.read_file(raiz / "parcelario-catastral" / "parcelas_colmenares.geojson").to_crs(CRS)
    pc = pc.dissolve(["muni_cod", "pol", "par"]).reset_index()
    pc["geometry"] = pc.geometry.centroid
    pc["key"] = list(zip(pc.muni_cod.astype(int), pc.pol.astype(int), pc.par.astype(int)))
    geo_key = pc.set_index("key").geometry

    def con_geo(e):
        e = e.dropna(subset=["pol", "par"]).copy()
        e["key"] = list(zip(e.cod.astype(int), e.pol.astype(int), e.par.astype(int)))
        e = e[e.key.isin(geo_key.index)]
        return gpd.GeoDataFrame(e, geometry=e.key.map(geo_key).values, crs=CRS)
    c21, c25 = con_geo(e21), con_geo(e25)
    p(f"  Situados: 2021 {len(c21)} de {len(e21)} explotaciones; 2025 {len(c25)} de {len(e25)}. "
      f"(Parcela pedida sin respuesta en el catastro: 15 de 234; se usa el centroide de la parcela.)")
    for y, c in ((2025, c25),):
        for r in (1000, 2000):
            G_y = G[G.anio == 2025]
            n = contar_cerca(G_y, c, r)
            p(f"  Nidos de 2025 a <= {r/1000:.0f} km de cada colmenar de 2025: mediana {n.median():.0f}, p75 {n.quantile(.75):.0f}, "
              f"máx {n.max()}; colmenares con >=1 nido: {(n > 0).mean():.0%}; con >=10: {(n >= 10).mean():.0%}")
            c25[f"n{r}"] = n
    # comparación con puntos al azar del mismo municipio
    rng = np.random.default_rng(1)
    G25 = G[G.anio == 2025]
    dif = []
    for idx, r in c25.iterrows():
        poly = muni.loc[muni.cod == r.cod, "geometry"]
        if poly.empty:
            continue
        poly = poly.iloc[0]
        minx, miny, maxx, maxy = poly.bounds
        pts = []
        while len(pts) < 30:
            xs, ys = rng.uniform(minx, maxx, 200), rng.uniform(miny, maxy, 200)
            cand = gpd.GeoSeries(gpd.points_from_xy(xs, ys), crs=CRS)
            pts += list(cand[cand.within(poly)].values)
        pts = gpd.GeoDataFrame(geometry=pts[:30], crs=CRS)
        dif.append((r.n2000, contar_cerca(G25, pts, 2000).mean()))
    dif = np.array(dif)
    w = stats.wilcoxon(dif[:, 0] - dif[:, 1])
    p(f"  Colmenar frente a 30 puntos al azar de su mismo municipio (nidos 2025 a <=2 km): mediana colmenar "
      f"{np.median(dif[:, 0]):.0f} vs azar {np.median(dif[:, 1]):.1f}; Wilcoxon p={w.pvalue:.3g}, n={len(dif)}")
    # supervivencia 2021 -> 2025 por clave de parcela
    k25 = set(c25.key)
    s21 = c21.drop_duplicates("key").copy()
    s21["baja"] = (~s21.key.isin(k25)).astype(int)
    s21["nidos2km"] = contar_cerca(G[G.anio.between(2021, 2024)], s21, 2000).values / 4
    s21["nidos1km"] = contar_cerca(G[G.anio.between(2021, 2024)], s21, 1000).values / 4
    p(f"  Parcelas con colmenar en 2021 y situadas: {len(s21)}; sin colmenar en esa parcela en 2025: {s21.baja.sum()} ({s21.baja.mean():.0%})")
    mw = stats.mannwhitneyu(s21.nidos2km[s21.baja == 1], s21.nidos2km[s21.baja == 0])
    p(f"  Nidos/año a <=2 km (2021-24): bajas mediana {s21.nidos2km[s21.baja == 1].median():.1f}, siguen "
      f"{s21.nidos2km[s21.baja == 0].median():.1f}; Mann-Whitney p={mw.pvalue:.3g}")
    s21 = s21.join(S[["log_dens"]], on="cod")
    s21["log_nidos2km"] = np.log1p(s21.nidos2km)
    s21["log_censo"] = np.log1p(s21.censo.fillna(0))
    p(f"  Profesionales situados en 2021: {int(s21.prof.sum())}, de ellos sin colmenar en 2025: {int(s21.baja[s21.prof].sum())} "
      f"(separación perfecta: se deja fuera del logit)")
    Xl = sm.add_constant(s21[["log_nidos2km", "log_censo", "log_dens"]].astype(float).assign(auto=s21.auto.astype(float)))
    ok = np.isfinite(Xl).all(axis=1)
    try:
        lg = sm.Logit(s21.baja[ok], Xl[ok]).fit(disp=0)
        p(f"  (n={ok.sum()}; fuera {(~ok).sum()} sin dato de censo o en Bilbao)")
        p(f"  Logit baja ~ log(1+nidos/año 2 km) + log(1+colmenas) + log densidad + autoconsumo: "
          f"{coefs(lg, exp=True)} (exp(b) = odds ratio); pseudo-R²={lg.prsquared:.2f}")
    except Exception as ex:  # noqa: BLE001
        p(f"  Logit no converge: {ex}")
    top = c25.sort_values("n1000", ascending=False).head(8)
    p("  Colmenares 2025 con más nidos a <=1 km (sin titular; el registro no lo publica): " + "; ".join(
        f"{M.loc[r.cod, 'nombre']} ({int(r.censo)} colmenas): {r.n1000} nidos" for _, r in top.iterrows()))

    # =================================================================== 2. AGRICULTURA
    p("\n=== 2. CULTIVOS SENSIBLES (declaración anual de superficies; registro vitícola) ===")
    grupos = [("vina", r"VIÑ|VINA|TXAKOLI|UVA"), ("manzano", r"MANZAN"), ("kiwi", r"KIWI|AKTINIDIA|ACTINIDIA"),
              ("peq_frutos", r"ARANDAN|FRAMBUES|FRUTOS DEL BOSQUE|FRESA|GROSELL"),
              ("otros_frutales", r"FRUTAL|PERAL|CEREZ|CIRUEL|MELOCOT|HIGUER")]
    sup = {}
    for y in range(2021, 2026):
        s = leer(raiz / "declaracion-superficies" / f"declaracion-superficies-{y}.csv")
        s["cod"] = cod(s.CODIGO)
        s["ha"] = num(s[[c for c in s.columns if "SUPERFICIE" in c][0]])
        tc = s["TIPO CULTIVO"].map(norm)
        s["grupo"] = pd.NA
        for gname, pat in grupos:
            s.loc[s.grupo.isna() & tc.str.contains(pat) & ~tc.str.contains("VIVERO"), "grupo"] = gname
        sup[y] = s
    tt = pd.DataFrame({y: s.groupby("grupo").ha.sum() for y, s in sup.items()}).round(1)
    tt.loc["total_sensible"] = tt.sum()
    tt.loc["total_declarado"] = pd.Series({y: s.ha.sum() for y, s in sup.items()}).round(0)
    p("Hectáreas declaradas por grupo (nogal y avellano fuera: la avispa no los daña):")
    p(tt.to_string())
    p("Ojo: en 2023 y sobre todo en 2025 cambia la nomenclatura (variedades SIGPAC). Viña, kiwi y pequeños frutos son "
      "comparables; «otros frutales» cae de 200 a 80 ha y manzano oscila: la variación 2021-25 de la superficie sensible "
      "está contaminada por el cambio de códigos. El viñedo del registro vitícola es la serie limpia.")
    for y in (2021, 2025):
        M[f"sens_{y}"] = sup[y][sup[y].grupo.notna()].groupby("cod").ha.sum().reindex(M.index, fill_value=0)
        M[f"vina_{y}"] = sup[y][sup[y].grupo.eq("vina")].groupby("cod").ha.sum().reindex(M.index, fill_value=0)
    S = S.join(M[["sens_2021", "sens_2025", "vina_2021", "vina_2025"]])
    S["sens_ha_km2"] = (S.sens_2021 + S.sens_2025) / 2 / S.km2
    spear(S.otono_km2, S.sens_ha_km2, "nidos de otoño/km² vs ha sensibles/km² (112 municipios)")
    X = sm.add_constant(pd.DataFrame({"log_sens": np.log(S.sens_ha_km2 + 0.01), "log_dens": S.log_dens}))
    o = sm.OLS(np.log(S.otono_km2 + 0.05), X).fit(cov_type="HC3")
    p(f"  MCO log(nidos otoño/km²) ~ log(ha sensibles/km²) + log densidad: {coefs(o)}; R²={o.rsquared:.2f}")
    C = S[S.sens_2021 >= 1]
    spear(C.otono_km2, (C.sens_2025 - C.sens_2021) / C.sens_2021,
          f"nidos otoño/km² vs variación relativa de ha sensibles 2021-25 (municipios con >=1 ha, n={len(C)})")
    top = S.sort_values("sens_2025", ascending=False).head(10)
    p("  Municipios con más cultivo sensible 2025 (ha; nidos de otoño/km²/año): " + "; ".join(
        f"{r.nombre} {r.sens_2025:.0f} ha, {r.otono_km2:.2f}" for _, r in top.iterrows()))

    # registro vitícola
    vt = {}
    for y in range(2021, 2026):
        v = leer(raiz / "parcelas-registro-viticola" / f"parcelas-registro-viticola-{y}.csv")
        v["cod"] = cod(v.CODIGO)
        v["m2"] = num(v[[c for c in v.columns if "SUPERFICIE VITIC" in c][0]])
        vt[y] = v
    p(f"Registro vitícola, superficie de viñedo (ha): " + ", ".join(f"{y}: {v.m2.sum() / 1e4:.0f}" for y, v in vt.items())
      + f"; municipios con viña 2025: {vt[2025].loc[vt[2025].m2 > 0, 'cod'].nunique()}")
    v = vt[2025]
    v = v[v.geometry.notna() & (v.m2 > 0)].copy()
    vg = gpd.GeoDataFrame(v, geometry=[geom(x) for x in v.geometry], crs="EPSG:4326").to_crs(CRS)
    vg["geometry"] = vg.geometry.centroid
    Gv = G[(G.anio == 2025) & G.mes.between(8, 10)]
    for r in (500, 1000):
        n = contar_cerca(Gv, vg, r)
        vg[f"n{r}"] = n
        p(f"  Parcelas de viñedo 2025 ({len(vg)}, {vg.m2.sum() / 1e4:.0f} ha) con nidos de ago-oct 2025 a <= {r} m: "
          f"{(n > 0).mean():.0%}; mediana {n.median():.0f}; ha de viña con >=3 nidos: {vg.m2[n >= 3].sum() / 1e4:.0f}")
    vm = vg.groupby("cod").agg(ha=("m2", lambda s: s.sum() / 1e4), nidos_1km=("n1000", "mean")).sort_values("ha", ascending=False)
    p("  Municipios txakolineros (ha de viña; media de nidos ago-oct 2025 a <=1 km de cada parcela): " + "; ".join(
        f"{M.loc[c, 'nombre']} {r.ha:.0f} ha, {r.nidos_1km:.1f}" for c, r in vm.head(8).iterrows()))
    for y in (2021, 2025):
        S[f"reg_vina_{y}"] = vt[y].groupby("cod").m2.sum().reindex(S.index, fill_value=0) / 1e4
    Cv = S[S.reg_vina_2021 >= 1]
    spear(Cv.otono_km2, (Cv.reg_vina_2025 - Cv.reg_vina_2021) / Cv.reg_vina_2021,
          f"nidos otoño/km² vs variación relativa del viñedo registrado 2021-25 (n={len(Cv)})")

    # =================================================================== 3. DINERO PÚBLICO
    p("\n=== 3. DINERO PÚBLICO ===")
    pat_av = re.compile(r"VELUTIN|AVISPA|AVISPA|LIZTOR|\bNIDOS?\b|TRAMPE", re.I)
    # encomiendas
    filas = []
    for y, f in ultimo_por_anio(raiz / "encomiendas-gestion", "encomiendas-gestion").items():
        e = leer(f)
        desc = [c for c in e.columns if c.startswith("EXPEDIENTE CONTABLE DESCR")][0]
        adm = [c for c in e.columns if c.startswith("ADMINISTRATIVO DESCR")][0]
        ent = [c for c in e.columns if c == "ENTIDAD"][0]
        e["oblig"] = num(e.OBLIGACION)
        texto = e[desc].fillna("") + " " + e[adm].fillna("")
        av = e[texto.str.contains(pat_av)]
        pn = e[e[ent].str.contains("BASALAN", na=False) & e[adm].str.contains("PATRIMONIO NATURAL|PATRIM. NAT", na=False)]
        filas.append(dict(anio=y, fichero_mes=f.stem.split("-")[-1], lineas_avispa=len(av), eur_avispa=av.oblig.sum(),
                          eur_basalan_total=e.loc[e[ent].str.contains("BASALAN", na=False), "oblig"].sum(),
                          eur_basalan_patrimonio_natural=pn.oblig.sum()))
        for _, r in av.iterrows():
            filas[-1].setdefault("detalle", []).append((r[desc].strip(), r.oblig))
    te = pd.DataFrame(filas).set_index("anio")
    p("Encomiendas/encargos de gestión (obligaciones reconocidas, €; último fichero acumulado de cada año):")
    p(te.drop(columns="detalle", errors="ignore").round(0).to_string())
    for y, r in te.iterrows():
        for dsc, v in (r.get("detalle") if isinstance(r.get("detalle"), list) else []):
            p(f"  {y}: {dsc[:75]} -> {v:,.2f} €")
    p("Las líneas de 2020 de mayo, octubre y noviembre mezclan «trabajos extraordinarios y avispa velutina»: no "
      "permiten aislar el coste de los nidos.")
    p("Desde 2021 la retirada de nidos ya no aparece como línea propia: queda dentro del «encargo anual Basalan - "
      "Servicio de Patrimonio Natural» (2,1-2,7 M€/año, que incluye parques, áreas y otros trabajos).")
    # coste por nido con las líneas que nombran meses
    cb = g[g.agente.eq("BASALAN") & g.cierre.notna()]
    def nidos_basalan(y, meses):
        return int(((cb.cierre.dt.year == y) & cb.cierre.dt.month.isin(meses)).sum())
    casos = [(2018, "MAYO-JUNIO 2018", [5, 6], 22660.52), (2018, "SEPTIEMBRE-OCTUBRE 2018", [9, 10], 82929.04),
             (2018, "NOVIEMBRE 2018", [11], 31297.72), (2019, "JUNIO 2019", [6], 10103.08),
             (2019, "«SE...» 2019 si es solo septiembre", [9], 24283.33),
             (2019, "«SE...» 2019 si es septiembre-octubre", [9, 10], 24283.33),
             (2019, "«NO...» 2019 si es noviembre", [11], 15523.01)]
    p("Coste por nido retirado por Basalan (importe de la línea / nidos cerrados por Basalan esos meses):")
    for y, et, ms, eur in casos:
        n = nidos_basalan(y, ms)
        p(f"  {et}: {eur:,.0f} € / {n} nidos = {eur / n:.0f} €/nido" if n else f"  {et}: sin nidos")
    tot18 = nidos_basalan(2018, [5, 6, 9, 10, 11])
    p(f"  2018 con las tres líneas (may-jun, sep-oct, nov): {136887.28:,.0f} € / {tot18} nidos = {136887.28 / tot18:.0f} €/nido. "
      f"Julio-agosto de 2018 no tiene línea propia ({nidos_basalan(2018, [7, 8])} nidos cerrados por Basalan).")
    # subvenciones otorgadas
    filas = []
    for y, f in ultimo_por_anio(raiz / "subvenciones-otorgadas", "subvenciones-otorgadas").items():
        s = leer(f)
        prog = s["ADMINISTRATIVO DESCRIPCION"].fillna("")
        s["imp"] = num(s.OBLIGACION)
        a = s[prog.str.contains("APICULT", case=False)]
        v = s[prog.str.contains(pat_av)]
        seg = s[s["PERSONA BENEFICIARIA"].str.contains("APICULT|ERLEZAIN|ERLAZ", case=False, na=False) &
                ~prog.str.contains("APICULT", case=False)]
        filas.append(dict(anio=y, mes=f.stem.split("-")[-1], eur_ayudas_apicultura=a.imp.sum(), lineas=len(a),
                          eur_asociaciones=a.imp[a["PERSONA BENEFICIARIA"].str.contains("ASOCIACION|ORGANIZACION|ELKARTE", na=False)].sum(),
                          otras_a_asoc_apic=seg.imp.sum(), lineas_avispa=len(v)))
    ts = pd.DataFrame(filas).set_index("anio")
    ts["eur_por_colmena"] = [ts.loc[y, "eur_ayudas_apicultura"] / ab[y].censo.sum() if y in ab else np.nan for y in ts.index]
    p("Subvenciones otorgadas (programa «Ayudas a la apicultura» y similares; importes acumulados del último fichero del año):")
    p(ts.round(2).to_string())
    p("Ninguna línea de subvenciones otorgadas menciona avispa, velutina, nidos o trampeo (búsqueda en el texto del programa).")
    # contratos
    for carpeta, pref in (("contratos-menores", "contratos-menores"), ("contratos-no-menores", "contratos-no-menores"),
                          ("convenios", "convenios")):
        hits = []
        for y, f in ultimo_por_anio(raiz / carpeta, pref).items():
            c = leer(f)
            txt = c.fillna("").astype(str).agg(" ".join, axis=1)
            imp_col = [x for x in c.columns if x in ("OBLIGACION", "IMPORTE ADJUDICACION", "IMPORTE", "IMPORTE ADJUDICADO")] or \
                      [x for x in c.columns if "IMPORTE" in x or "OBLIGACI" in x]
            for i in c.index[txt.str.contains(pat_av) | txt.str.contains("APICULT|ERLEZAIN", case=False)]:
                cols = [k for k in c.columns if k in ("PERSONA ADJUDICATARIA", "OBJETO_CAS", "EXPEDIENTE CONTABLE DESCR.",
                                                      "ADMINISTRATIVO DESCRIPCION", "OBJETO", "DENOMINACION")]
                hits.append((y, " | ".join(str(c.loc[i, k])[:60] for k in cols),
                             c.loc[i, imp_col[-1]] if imp_col else ""))
        p(f"{carpeta}: {len(hits)} líneas con avispa/velutina/nidos/trampeo/apicultura")
        for h in hits[:12]:
            p(f"  {h[0]}: {h[1][:150]} -> {h[2]}")
    for carpeta in ("plan-anual-contratacion", "plan-anual-contratacion-basalan"):
        n = 0
        for f in sorted((raiz / carpeta).glob("*.csv")):
            n += leer(f).fillna("").astype(str).agg(" ".join, axis=1).str.contains(pat_av).sum()
        p(f"{carpeta}: {n} líneas con avispa/velutina/nidos")
    n = 0
    for f in sorted((raiz / "liquidacion-presupuestos").glob("*gastos*.csv")):
        n += leer(f).fillna("").astype(str).agg(" ".join, axis=1).str.contains(pat_av).sum()
    p(f"liquidacion-presupuestos (gastos 2017-2024): {n} partidas con avispa/velutina en el texto. La retirada se paga "
      f"desde los proyectos de encargo a Basalan (Patrimonio Natural), sin partida propia.")

    # =================================================================== 4. SALUD, OCIO
    p("\n=== 4. SALUD, OCIO Y ACTIVIDAD ===")
    sp = pd.read_csv(raiz / "speis" / "intervenciones-speis-2023-2026.csv", dtype=str)
    c = sp.columns
    sp = pd.DataFrame({"anio": pd.to_numeric(sp[c[1]]), "mes": pd.to_numeric(sp[c[3]], errors="coerce"),
                       "tipo": sp[c[5]].str.encode("latin-1", errors="ignore").str.decode("utf-8", errors="ignore").str.strip().str.upper(),
                       "cod": cod(sp[c[7]]), "x": num(sp["longitude"]), "y": num(sp["latitude"])})
    av = sp[sp.tipo.str.contains("AVISPA|ABEJA", na=False) & sp.anio.between(2023, 2025)].copy()
    p(f"SPEIS «Neutralización de abejas y avispas» 2023-2025: {len(av)} salidas; por año {av.groupby('anio').size().to_dict()}")
    S["speis_av"] = av.groupby("cod").size().reindex(S.index, fill_value=0)
    S["nidos_23_25"] = g[g.anio.between(2023, 2025)].groupby("cod").size().reindex(S.index, fill_value=0)
    S["nidos_bomberos_23_25"] = g[g.anio.between(2023, 2025) & g.agente.eq("BOMBEROS")].groupby("cod").size().reindex(S.index, fill_value=0)
    spear(S.nidos_23_25, S.speis_av, "nidos de asiática vs salidas SPEIS por avispas/abejas, por municipio 2023-25")
    X = sm.add_constant(pd.DataFrame({"log_nidos": np.log1p(S.nidos_23_25), "log_pob": S.log_pob}))
    pr = sm.GLM(S.speis_av, X, family=sm.families.Poisson()).fit(scale="X2")
    p(f"  Cuasi-Poisson salidas SPEIS ~ log(1+nidos) + log(población): {coefs(pr, exp=True)}")
    p(f"  Nidos de asiática cerrados por BOMBEROS en el registro de nidos 2023-25: {int(S.nidos_bomberos_23_25.sum())} "
      f"(frente a {len(av)} salidas SPEIS por avispas/abejas: el SPEIS incluye avispa común, abejas y salidas sin nido retirado)")
    mm = pd.DataFrame({"speis": av.groupby("mes").size(), "nidos": g[g.anio.between(2023, 2025)].groupby("mes").size()}).fillna(0)
    p(f"  Perfil mensual (correlación de Spearman entre meses): rho={stats.spearmanr(mm.speis, mm.nidos)[0]:.2f}; "
      f"SPEIS por mes {mm.speis.astype(int).to_dict()}")
    a2 = av[av.anio.isin([2024, 2025]) & av.x.notna()].copy()
    if len(a2):
        utm = a2.x.abs().median() > 1000
        ga = gpd.GeoDataFrame(a2, geometry=gpd.points_from_xy(a2.x, a2.y), crs=CRS if utm else "EPSG:4326").to_crs(CRS)
        todas = cargar_nidos(raiz / "avispa_asiatica" / "nidos.csv")
        todas = todas[todas.lat.notna() & todas.anio.isin([2024, 2025])]
        gt = gpd.GeoDataFrame(todas, geometry=gpd.points_from_xy(todas.lon, todas.lat), crs="EPSG:4326").to_crs(CRS)
        res = []
        for y in (2024, 2025):
            jj = gpd.sjoin_nearest(ga[ga.anio == y], gt[gt.anio == y][["geometry", "especie"]], distance_col="dist", how="left")
            jj = jj[~jj.index.duplicated()]
            res.append(jj)
        jj = pd.concat(res)
        p(f"  Salidas SPEIS 2024-25 con coordenadas: {len(ga)}; con un nido registrado (cualquier especie) del mismo año "
          f"a <=100 m: {(jj.dist <= 100).mean():.0%}; a <=500 m: {(jj.dist <= 500).mean():.0%}; especie del nido más "
          f"cercano (<=100 m): {jj[jj.dist <= 100].especie.value_counts().to_dict()}")
        p("  (Las coordenadas del SPEIS pueden estar redondeadas o desplazadas: la proximidad es orientativa.)")

    # playas
    so = leer(raiz / "playas" / "asistencias-socorristas.csv")
    us = leer(raiz / "playas" / "asistencia-personas-usuarias.csv")
    for t_ in (so, us):
        t_["anio"], t_["mesn"] = pd.to_numeric(t_.EJERCICIO), pd.to_numeric(t_.MES)
    so["pic"] = pd.to_numeric(so.PICADURA_INSECTOS)
    so["tot"] = so[[x for x in so.columns[6:] if x not in ("anio", "mesn", "pic")]].apply(pd.to_numeric).sum(axis=1)
    us["usuarios"] = us[[str(i) for i in range(1, 32)]].apply(pd.to_numeric, errors="coerce").sum(axis=1)
    py = so.groupby("anio").agg(picaduras=("pic", "sum"), asistencias=("tot", "sum")).join(us.groupby("anio").usuarios.sum())
    py["pic_100k_usuarios"] = (py.picaduras / py.usuarios * 1e5).round(2)
    py["nidos_jun_sep_costeros"] = np.nan
    pg = gpd.read_file(raiz / "informacion-geografica-playas" / "playas.geojson").to_crs(CRS)
    pg["k"] = pg.NombrePlayaES.map(lambda s: re.sub(r"[^A-ZÑ]", "", norm(s)))
    so["k"] = so.PLAYA.map(lambda s: re.sub(r"[^A-ZÑ]", "", norm(re.sub(r"\(.*?\)", "", s))))
    us["k"] = us.PLAYA.map(lambda s: re.sub(r"[^A-ZÑ]", "", norm(re.sub(r"\(.*?\)", "", s))))
    pg = pg.drop_duplicates("k").set_index("k")
    sin = sorted(set(so.k) - set(pg.index))
    panel = so.groupby(["k", "anio"]).pic.sum().to_frame().join(us.groupby(["k", "anio"]).usuarios.sum())
    panel = panel[panel.index.get_level_values(0).isin(pg.index)]
    Gs = G[G.mes.between(6, 9)]
    cnt = {}
    for y in range(2019, 2026):
        n = contar_cerca(Gs[Gs.anio == y], pg, 2000)
        for k_, v_ in n.items():
            cnt[(k_, y)] = v_
    panel["nidos2km"] = [cnt.get(i, np.nan) for i in panel.index]
    panel = panel.dropna()
    for y in py.index:
        if y <= 2025:
            py.loc[y, "nidos_jun_sep_costeros"] = sum(v for (k_, yy), v in cnt.items() if yy == y)
    p(f"Playas (socorristas, jun-sep, {so.PLAYA.nunique()} playas; sin punto geográfico: {sin}):")
    p(py.to_string())
    p("  Ojo: los usuarios contados caen a un tercio desde 2024 (cambio de conteo o de playas aforadas): la tasa por "
      "usuario no es comparable entre 2019-23 y 2024-26.")
    panel["tasa"] = panel.pic / panel.usuarios * 1e5
    spear(panel.nidos2km, panel.tasa, "nidos jun-sep a <=2 km de la playa vs picaduras de insecto por 100.000 usuarios (playa-año 2019-25)")
    dm = panel.groupby(level=0).transform(lambda s: s - s.mean())
    spear(dm.nidos2km, dm.tasa, "lo mismo dentro de cada playa (desviaciones respecto a su media)")
    p("  «Picadura de insectos» no distingue avispa, abeja, tábano ni mosquito; el sabirón (pez) va aparte.")
    yy = py.loc[2019:2025]
    p(f"  Tendencia anual 2019-25: picaduras/100k usuarios vs nidos costeros jun-sep, rho={stats.spearmanr(yy.pic_100k_usuarios, yy.nidos_jun_sep_costeros)[0]:.2f} (n=7)")

    # áreas de esparcimiento
    ar = leer(raiz / "areas-esparcimiento" / "areas-esparcimiento-2021.csv")
    ar["x"], ar["y"] = num(ar.longitude), num(ar.latitude)
    ar = ar.dropna(subset=["x"])
    ga = gpd.GeoDataFrame(ar, geometry=gpd.points_from_xy(ar.x, ar.y), crs=CRS)
    ga["cod"] = cod(ga.CODIGO)
    for r in (500,):
        ga["n500"] = contar_cerca(G, ga, r).values
        ga["n500_basalan_aviso"] = contar_cerca(G[G.usuario_tipo.eq("BASALAN")], ga, r).values
    p(f"Áreas de esparcimiento forales ({len(ga)}): nidos de asiática 2018-25 a <=500 m: mediana {ga.n500.median():.0f}, "
      f"p90 {ga.n500.quantile(.9):.0f}, máx {ga.n500.max()}; áreas con >=1: {(ga.n500 > 0).mean():.0%}")
    share_b = G.usuario_tipo.eq("BASALAN").mean()
    p(f"  Avisos dados por la propia Basalan: {ga.n500_basalan_aviso.sum() / max(ga.n500.sum(), 1):.0%} de los nidos a "
      f"<=500 m de un área, frente al {share_b:.0%} en el total (Basalan mantiene las áreas y avisa de lo que ve).")
    p("  Áreas con más nidos alrededor: " + "; ".join(
        f"{r.AREA.strip().title()} ({str(M.loc[r.cod, 'nombre']).title() if r.cod in M.index else '?'}) {r.n500}"
        for _, r in ga.sort_values("n500", ascending=False).head(8).iterrows()))
    p("Senderos PR: el servicio WFS/REST de ODB solo trae los de Armañón y Urkiola (dos parques); no se cruzan.")

    # =================================================================== 5. PERFIL
    p("\n=== 5. PERFIL DE LOS MUNICIPIOS MÁS AFECTADOS ===")
    S["colm_por_1000hab"] = S.expl_2025 / S.pob * 1000
    q = pd.qcut(S.nidos_km2_anio, 4, labels=["Q1", "Q2", "Q3", "Q4"])
    perf = S.groupby(q, observed=True).agg(
        munis=("nombre", "size"), nidos_km2=("nidos_km2_anio", "median"), nidos_1000hab=("nidos_1000hab_anio", "median"),
        pob_mediana=("pob", "median"), dens_mediana=("dens", "median"), renta_decl=("renta_decl", "median"),
        nidos_total=("nidos_18_25", "sum"), pob_total=("pob", "sum"), con_colmenar=("tiene_colm", "mean"),
        ha_sensibles=("sens_2025", "sum"))
    p("Cuartiles de nidos/km²/año 2018-25 (sin Bilbao; renta = base liquidable media por declaración IRPF 2023, €):")
    p(perf.round(2).to_string())
    q2 = pd.qcut(S.nidos_1000hab_anio, 4, labels=["Q1", "Q2", "Q3", "Q4"])
    perf2 = S.groupby(q2, observed=True).agg(munis=("nombre", "size"), nidos_1000hab=("nidos_1000hab_anio", "median"),
                                             pob_mediana=("pob", "median"), dens_mediana=("dens", "median"),
                                             renta_decl=("renta_decl", "median"), con_colmenar=("tiene_colm", "mean"))
    p("Cuartiles de nidos/1.000 hab./año:")
    p(perf2.round(2).to_string())
    spear(S.nidos_1000hab_anio, S.renta_decl, "nidos/1.000 hab vs renta media declarada")
    spear(S.nidos_1000hab_anio, S.dens, "nidos/1.000 hab vs densidad")
    X = sm.add_constant(pd.DataFrame({"log_dens": S.log_dens, "log_renta": np.log(S.renta_decl)}))
    o = sm.OLS(np.log(S.nidos_1000hab_anio), X).fit(cov_type="HC3")
    p(f"  MCO log(nidos/1.000 hab) ~ log densidad + log renta: {coefs(o)}; R²={o.rsquared:.2f}")
    top = S.sort_values("nidos_km2_anio", ascending=False).head(12)
    p("Top 12 por nidos/km²/año (nidos/km², nidos/1.000 hab, hab., hab/km², renta/decl., colmenares 2021->2025):")
    for _, r in top.iterrows():
        p(f"  {r.nombre}: {r.nidos_km2_anio:.2f}; {r.nidos_1000hab_anio:.1f}; {r.pob:.0f}; {r.dens:.0f}; "
          f"{r.renta_decl:,.0f} €; {int(r.expl_2021)}->{int(r.expl_2025)}")
    top = S[S.pob >= 500].sort_values("nidos_1000hab_anio", ascending=False).head(12)
    p("Top 12 por nidos/1.000 hab./año (>=500 hab.):")
    for _, r in top.iterrows():
        p(f"  {r.nombre}: {r.nidos_1000hab_anio:.1f}; {r.nidos_km2_anio:.2f}/km²; {r.pob:.0f} hab; {r.dens:.0f} hab/km²; "
          f"{r.renta_decl:,.0f} €; colmenares {int(r.expl_2021)}->{int(r.expl_2025)}")
    p("Paro registrado: no está en ODB (Lanbide/SEPE); no se cruza.")

    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n".join(OUT) + "\n", encoding="utf-8")
    print(f"Escrito {salida} ({len(OUT)} líneas)")


if __name__ == "__main__":
    main()
