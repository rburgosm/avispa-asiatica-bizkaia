"""Cifras preliminares de los conjuntos candidatos de Open Data Bizkaia.

Uso: cifras_candidatos.py <raiz_raw_bizkaia> <salida.txt>

Lee cada carpeta data/raw/bizkaia/<slug>/ y escribe un resumen compacto.
Solo exploración: las cifras son orientativas y hay que revisarlas antes de publicar.
"""
import csv
import io
import re
import sys
from pathlib import Path

import pandas as pd

OUT = []


def p(*a):
    OUT.append(" ".join(str(x) for x in a))


def leer(path):
    raw = Path(path).read_bytes()
    try:
        txt = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt = raw.decode("latin-1")
    if "Ã" in txt:
        try:
            txt = txt.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            txt = re.sub(r"Ã[\x80-\xbf]", lambda m: m.group(0).encode("latin-1").decode("utf-8", "replace"), txt)
    try:
        sep = csv.Sniffer().sniff(txt[:20000], delimiters=",;\t").delimiter
    except csv.Error:
        sep = ","
    df = pd.read_csv(io.StringIO(txt), sep=sep, dtype=str, low_memory=False)
    df.columns = [c.split("/")[-1].strip() if "/" in c else c.strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].str.strip().str.replace(r'^="?|"$', "", regex=True)
    return df


def num(s, miles_punto=False):
    s = s.astype(str).str.strip()
    if miles_punto:
        s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def todos(carpeta, patron="*.csv"):
    fs = sorted(Path(carpeta).glob(patron))
    return pd.concat([leer(f).assign(_f=f.stem) for f in fs], ignore_index=True) if fs else None


def fauna(r):
    p("\n### FAUNA (centro de recuperación)")
    df = todos(r / "centro-recuperacion-fauna")
    df["fecha"] = pd.to_datetime(df["FECHA RECEPCION"], errors="coerce")
    df["anio"] = df["EJERCICIO"]
    p("filas por año:", df.groupby("anio").size().to_dict())
    p("rango fechas:", df.fecha.min(), df.fecha.max())
    p("estado ingreso %:", (df["ESTADO INGRESO"].value_counts(normalize=True) * 100).round(1).to_dict())
    p("top 15 especies:", df["ESPECIE_CAS"].value_counts().head(15).to_dict())
    p("causas ingreso:", df["CAUSA INGRESO"].value_counts().head(25).to_dict())
    p("evolución:", df["EVOLUCION"].value_counts(dropna=False).to_dict())
    vivos = df[df["ESTADO INGRESO"].str.contains("VIVO", na=False)]
    p("vivos:", len(vivos), "liberados entre vivos %:", round(100 * vivos["EVOLUCION"].eq("Liberados").mean(), 1))
    p("ingresos por mes (total):", df.fecha.dt.month.value_counts().sort_index().to_dict())
    p("top municipios recogida:", df["MUNICIPIO RECOGIDA"].value_counts().head(10).to_dict())
    for pat in ["Tortuga", "Erizo", "Búho|Lechuza|Cárabo|Mochuelo", "Milano|Busardo|Águila|Halcón|Buitre|Azor|Gavilán", "Murciélago", "Corzo", "Nutria|Visón|Garduña|Tejón|Zorro", "Delfín|Marsopa|Tortuga boba|Alcatraz|Arao|Frailecillo"]:
        m = df["ESPECIE_CAS"].str.contains(pat, case=False, na=False)
        p(f"  {pat}: {m.sum()} | por año {df[m].groupby('anio').size().to_dict()}")
    ca = df["CAUSA INGRESO"].fillna("")
    for pat in ["Atropello", "Electrocuc", "Disparo|Arma", "Envenen|Intoxica", "Colisi", "Petrol|Hidrocarb", "Captura|Control"]:
        m = ca.str.contains(pat, case=False)
        p(f"  causa {pat}: {m.sum()} | top especies {df[m]['ESPECIE_CAS'].value_counts().head(4).to_dict()}")


def ganado(r):
    p("\n### GANADERÍA")
    d = r / "explotaciones-ganaderas"
    ex = todos(d, "explotaciones-ganaderas-*.csv")
    ex["censo"] = num(ex["CENSO"])
    t = ex.pivot_table(index="ESPECIE", columns="EJERCICIO", values="censo", aggfunc="sum").fillna(0)
    t = t.sort_values(t.columns[-1], ascending=False)
    p("censo por especie y año (top 12):\n" + t.head(12).astype(int).to_string())
    p("explotaciones por año:", ex.groupby("EJERCICIO").size().to_dict())
    e25 = ex[ex.EJERCICIO == "2025"]
    p("2025 top municipios por nº explotaciones:", e25["MUNICIPIO"].value_counts().head(8).to_dict())
    mv = todos(d, "movimientos-ganado-*.csv")
    mv["n"] = num(mv["NUMERO_ANIMALES"])
    p("movimientos (guías) por año:", mv.groupby("EJERCICIO").size().to_dict(), "animales:", mv.groupby("EJERCICIO").n.sum().to_dict())
    m25 = mv[mv.EJERCICIO == "2025"].copy()
    p("2025 trashumancia S: guías", (m25.TRASHUMANCIA == "S").sum(), "animales", m25.loc[m25.TRASHUMANCIA == "S", "n"].sum())
    tr = m25[m25.TRASHUMANCIA == "S"]
    tr_mes = pd.to_datetime(tr.FECHA_SALIDA).dt.month.value_counts().sort_index()
    p("  trashumancia por mes (guías):", tr_mes.to_dict())
    p("  trashumancia especies (animales):", tr.groupby("ESPECIE").n.sum().sort_values(ascending=False).to_dict())
    p("  trashumancia origen top:", tr["MUNICIPIO_ORIGEN"].value_counts().head(6).to_dict())
    p("  trashumancia destino top:", tr["MUNICIPIO_DESTINO"].value_counts(dropna=False).head(6).to_dict())
    p("2025 destino (comunidad) animales:", m25.groupby("LUGAR_DESTINO").n.sum().sort_values(ascending=False).head(10).to_dict())
    p("2025 origen (comunidad) animales:", m25.groupby("LUGAR_ORIGEN").n.sum().sort_values(ascending=False).head(10).to_dict())
    p("2025 explotación destino top (animales):", m25.groupby("EXPLOTACION_DESTINO").n.sum().sort_values(ascending=False).head(5).to_dict())
    p("2025 bovinos a Francia/Italia/otros países:", m25[m25.LUGAR_DESTINO.isin(["Francia", "Italia", "Portugal"])].groupby(["LUGAR_DESTINO", "ESPECIE"]).n.sum().to_dict())
    na = todos(d, "nacimientos-ganado-*.csv")
    p("nacimientos por fichero:", na.groupby("_f").size().to_dict())
    p("razas top (todas):", na["RAZA"].value_counts().head(15).to_dict())
    for pat in ["BETIZU", "POTTOKA", "MONCHINA", "TERREÑA", "SASI", "CARRANZANA", "AZPI", "PIRENAICA"]:
        m = na["RAZA"].str.contains(pat, case=False, na=False)
        p(f"  raza {pat}: {m.sum()} nacimientos | por fichero {na[m].groupby('_f').size().to_dict()}")
    na["mes"] = pd.to_datetime(na["FECHA_NACIMIENTO"], errors="coerce").dt.day
    p("  nacimientos con día=1 (fecha aproximada) %:", round(100 * (na.mes == 1).mean(), 1))


def txakoli(r):
    p("\n### REGISTRO VITÍCOLA")
    df = todos(r / "parcelas-registro-viticola")
    sv = [c for c in df.columns if "SUPERFICIE VIT" in c.upper()][0]
    df["m2"] = num(df[sv])
    g = df.groupby("EJERCICIO").agg(parcelas=("m2", "size"), ha=("m2", lambda x: round(x.sum() / 1e4, 1)))
    p(g.to_string())
    p("estado parcela por año:\n" + pd.crosstab(df["ESTADO PARCELA"], df.EJERCICIO).to_string())
    d25 = df[df.EJERCICIO == "2025"]
    p("2025 ha por municipio top 12:", (d25.groupby("MUNICIPIO").m2.sum() / 1e4).round(1).sort_values(ascending=False).head(12).to_dict())
    p("2025 municipios con viña:", d25.MUNICIPIO.nunique(), "| parcelas con 0 m2:", (d25.m2 == 0).sum())
    p("2025 ha por variedad 1:", (d25.groupby("VARIEDAD 1").m2.sum() / 1e4).round(1).sort_values(ascending=False).to_dict())
    p("tamaño parcela m2 (2025, >0): mediana", d25.m2[d25.m2 > 0].median(), "p90", d25.m2[d25.m2 > 0].quantile(.9))
    a = df[df.EJERCICIO == "2021"].groupby("MUNICIPIO").m2.sum()
    b = d25.groupby("MUNICIPIO").m2.sum()
    dd = ((b.reindex(a.index.union(b.index)).fillna(0) - a.reindex(a.index.union(b.index)).fillna(0)) / 1e4).round(2).sort_values()
    p("cambio ha 2021-2025 por municipio (peores/mejores):", dd.head(5).to_dict(), dd.tail(5).to_dict())


def superficies(r):
    p("\n### DECLARACIÓN DE SUPERFICIES")
    df = todos(r / "declaracion-superficies")
    df["ha"] = num(df["SUPERFICIE DECLARADA (HA)"]) if "SUPERFICIE DECLARADA (HA)" in df else num(df[df.columns[-2]])
    t = df.pivot_table(index="TIPO CULTIVO", columns="EJERCICIO", values="ha", aggfunc="sum").fillna(0)
    t = t.sort_values(t.columns[-1], ascending=False)
    p("total ha por año:", t.sum().round(0).to_dict())
    p("top 15 cultivos ha:\n" + t.head(15).round(1).to_string())
    t["dif%"] = (100 * (t[t.columns[-1]] / t[t.columns[0]] - 1)).round(0)
    p("mayores cambios (cultivos >20 ha en 2025):\n" + t[t[t.columns[-2]] > 20].sort_values("dif%").iloc[[0, 1, 2, 3, -4, -3, -2, -1]].round(1).to_string())
    for pat in ["KIWI", "ARANDANO|ARÁNDANO", "VIÑ", "MANZAN", "PIMIENT", "INVERNADERO", "EUCALIP", "PINO"]:
        m = df["TIPO CULTIVO"].str.contains(pat, case=False, na=False)
        p(f"  {pat}: ", df[m].groupby("EJERCICIO").ha.sum().round(1).to_dict(), df[m]["TIPO CULTIVO"].unique()[:4])


def residuos(r):
    p("\n### RESIDUOS URBANOS")
    df = todos(r / "residuos-urbanos")
    cols = ["RECOGIDA_EN_MASA", "PAPEL-CARTON", "VIDRIO", "VOLUMINOSOS", "ENVASES", "REUTILIZACION", "BIORRESIDUO", "EH_TOTALA"]
    for c in cols:
        df[c] = num(df[c], miles_punto=True)
    p("años:", sorted(df.EJERCICIO.unique()), "municipios/año:", df.groupby("EJERCICIO").size().to_dict())
    p("nombres municipio raros:", [m for m in df["UDALERRIA"].unique() if not re.match(r"^[A-ZÑÁÉÍÓÚÜ\-\s/\.()']+$", str(m))][:10])
    tot = df.groupby("EJERCICIO")[cols].sum()
    tot["%selectiva"] = (100 * (1 - tot.RECOGIDA_EN_MASA / tot.EH_TOTALA)).round(1)
    p("totales (unidad sin documentar, prob. kg):\n" + (tot / 1e6).round(1).to_string())
    last = df[df.EJERCICIO == df.EJERCICIO.max()].copy()
    last["sel%"] = 100 * (1 - last.RECOGIDA_EN_MASA / last.EH_TOTALA)
    last["bio%"] = 100 * last.BIORRESIDUO / last.EH_TOTALA
    p("último año: % selectiva top/bottom:", last.set_index("UDALERRIA")["sel%"].round(0).sort_values().head(5).to_dict(), last.set_index("UDALERRIA")["sel%"].round(0).sort_values().tail(5).to_dict())
    p("último año: biorresiduo 0 en", (last.BIORRESIDUO.fillna(0) == 0).sum(), "municipios; bio% top:", last.set_index("UDALERRIA")["bio%"].round(0).sort_values().tail(5).to_dict())
    p("comprobación suma: |total - suma fracciones|/total mediana:", round(((last[cols[:-1]].sum(axis=1) - last.EH_TOTALA).abs() / last.EH_TOTALA).median(), 3))


def playas(r):
    p("\n### PLAYAS")
    d = r / "playas"
    a = leer(d / "asistencias-socorristas.csv")
    tipos = [c for c in a.columns if c not in ("_id", "CODIGO_INE_MUNICIPIO", "MUNICIPIO", "EJERCICIO", "MES", "PLAYA") and not c.startswith("UDAL")]
    for c in tipos:
        a[c] = num(a[c])
    p("años:", sorted(a.EJERCICIO.unique()), "playas:", a.PLAYA.nunique())
    t = a.groupby("EJERCICIO")[tipos].sum()
    p("asistencias por año y tipo:\n" + t.astype(int).T.to_string())
    s = a[tipos].sum().sort_values(ascending=False)
    p("total por tipo:", s.astype(int).to_dict())
    p("sabirón por playa top:", a.groupby("PLAYA")["PICADURA_SABIRON"].sum().sort_values(ascending=False).head(6).to_dict() if "PICADURA_SABIRON" in a else "")
    p("medusa por año:", a.groupby("EJERCICIO")["PICADURA_MEDUSA"].sum().to_dict() if "PICADURA_MEDUSA" in a else "")
    u = leer(d / "asistencia-personas-usuarias.csv")
    dias = [c for c in u.columns if c.isdigit()]
    for c in dias:
        u[c] = num(u[c])
    u["tot"] = u[dias].sum(axis=1)
    p("asistencia (personas usuarias?) total por año:", u.groupby("EJERCICIO").tot.sum().round(0).to_dict())
    p("top playas:", u.groupby("PLAYA").tot.sum().sort_values(ascending=False).head(6).round(0).to_dict())
    e = leer(d / "estado-playas.csv")
    p("estado-playas: filas por año", e.groupby("EJERCICIO").size().to_dict())
    k = e.drop(columns=["_id", "EJERCICIO", "FECHA"]).astype(str).agg("|".join, axis=1)
    e["k"] = k
    e["md"] = e.FECHA.str[5:10]
    piv = e.pivot_table(index=["PLAYA", "md"], columns="EJERCICIO", values="k", aggfunc="first")
    if piv.shape[1] >= 2:
        c = piv.columns
        p("  estado-playas: % filas idénticas entre años", c[0], c[1], round(100 * (piv[c[0]] == piv[c[1]]).mean(), 1), "|", c[1], c[2] if len(c) > 2 else "", round(100 * (piv[c[1]] == piv[c[-1]]).mean(), 1))
    p("  estado-playas meses presentes:", sorted(e.FECHA.str[5:7].unique()))


def saip(r):
    p("\n### SAIP")
    df = leer(r / "saip" / "saip-dfb.csv")
    df["dias"] = num(df["DIAS_HASTA_RESOLVER"])
    p("por año:", df.groupby("AÑO").size().to_dict())
    p("finalización %:", (df["TIPO_FINALIZACION_CAS"].value_counts(normalize=True) * 100).round(1).to_dict())
    p("días hasta resolver: mediana", df.dias.median(), "p90", df.dias.quantile(.9), "| en plazo:", df["RESUELTA_EN_PLAZO_CAS"].value_counts().to_dict())
    p("tema:", df["TEMA_PRINCIPAL_CAS"].value_counts().head(8).to_dict())
    p("subtema:", df["SUBTEMA_CAS"].value_counts().head(8).to_dict())
    p("persona:", df["PERSONA_CAS"].value_counts().to_dict(), "| reclamación:", df.filter(like="RECLAMACION").iloc[:, -1].value_counts().head(4).to_dict())
    p("denegadas/inadmitidas por departamento:", df[df["TIPO_FINALIZACION_CAS"].isin(["Denegada", "Inadmitida"])]["DEPARTAMENTO_EU"].value_counts().head(5).to_dict())
    p("ejemplos resumen:", df["RESUMEN_SOLICITUD"].sample(8, random_state=1).str[:90].tolist())


def bizkaibus(r):
    p("\n### BIZKAIBUS expediciones 2025 (112 municipios)")
    d = r / "bizkaibus-expediciones"
    fs = list(d.glob("*/*.csv"))
    p("ficheros:", len(fs), "carpetas:", len({f.parent for f in fs}))
    if not fs:
        return
    rows = []
    for f in fs:
        x = leer(f)
        x["tipo"] = "plan" if "planificadas" in f.name else "real"
        rows.append(x)
    df = pd.concat(rows, ignore_index=True)
    df["tot"] = num(df["TOTAL EXPEDICIONES"])
    # Las realizadas son acumuladas por extracción (abr, jul, oct, feb): quedarse con la última.
    ext = df["FECHA EXTRACCION"].str[:10]
    df = df[(df.tipo == "plan") | (ext == ext[df.tipo == "real"].max())].copy()
    g = df.pivot_table(index="MUNICIPIO", columns="tipo", values="tot", aggfunc="sum").fillna(0)
    g["ratio"] = (g.real / g.plan).round(3)
    p("municipios:", len(g), "| suma plan", int(g.plan.sum()), "real", int(g.real.sum()))
    p("ratio real/plan: describe", g.ratio.describe().round(3).to_dict())
    p("ratio más bajo:", g.sort_values("ratio").head(8)[["plan", "real", "ratio"]].to_dict("index"))
    p("ratio más alto:", g.sort_values("ratio").tail(5)[["plan", "real", "ratio"]].to_dict("index"))
    p("menos expediciones planificadas/año:", g.sort_values("plan").head(8).plan.to_dict())
    p("fechas extracción real:", df.loc[df.tipo == "real", "FECHA EXTRACCION"].str[:10].value_counts().to_dict() if "FECHA EXTRACCION" in df else df.columns.tolist())
    li = df[df.tipo == "plan"].drop_duplicates(["CODIGO LINEA", "TEMPORADA", "TIPO DIA", "NUMERO DIAS"])
    li2 = df[df.tipo == "real"].drop_duplicates(["CODIGO LINEA", "TEMPORADA", "TIPO DIA", "NUMERO DIAS"])
    lp = li.groupby("CODIGO LINEA").tot.sum()
    lr = li2.groupby("CODIGO LINEA").tot.sum()
    lx = pd.concat([lp.rename("plan"), lr.rename("real")], axis=1).fillna(0)
    lx["ratio"] = (lx.real / lx.plan).round(3)
    p("por línea (deduplicado): líneas", len(lx), "plan", int(lx.plan.sum()), "real", int(lx.real.sum()))
    p("líneas ratio bajo:", lx[lx.plan > 500].sort_values("ratio").head(6).to_dict("index"))


def visitas(r):
    p("\n### VISITAS Y DESCARGAS")
    d = r / "visitas-descargas-diarias"
    for f in sorted(d.glob("*.csv")):
        x = leer(f)
        for c in ["VISITAS", "DESCARGAS WEB", "DESCARGAS API"]:
            x[c] = num(x[c])
        por = x.groupby("CONJUNTO DATOS_CAS")[["VISITAS", "DESCARGAS WEB", "DESCARGAS API"]].sum()
        p(f.stem, "conjuntos", len(por), "| sin ninguna visita en el mes:", (por.VISITAS == 0).sum(), "| totales", por.sum().astype(int).to_dict())
        p("  top visitas:", por.VISITAS.sort_values(ascending=False).head(8).to_dict())
        p("  top desc API:", por["DESCARGAS API"].sort_values(ascending=False).head(5).to_dict())
    w = todos(r / "visitas-descargas", "descargas-semanales-*.csv")
    w["web"] = num(w["DESCARGAS WEB"])
    w["api"] = num(w["DESCARGAS API"])
    p("descargas semanales por año (web, api):", w.groupby("EJERCICIO")[["web", "api"]].sum().astype(int).to_dict("index"))
    v = todos(r / "visitas-descargas", "visitas-semanales-*.csv")
    vc = [c for c in v.columns if "VISIT" in c.upper()][0]
    v["v"] = num(v[vc])
    p("visitas semanales por año:", v.groupby("EJERCICIO").v.sum().astype(int).to_dict())


def energia(r):
    p("\n### ENERGÍA DFB")
    df = leer(r / "datos-energeticos" / "sie-otros.csv")
    ce = [c for c in df.columns if c.startswith("CONSUMO_ELEC") or "ELEKTRIZITATE_KONTSUMOA" in c or ("CONSUMO" in c and "ELEC" in c)]
    allc = list(df.columns)
    p("ejemplo columnas:", allc[19:25], "...", allc[-8:])
    elec = [c for c in allc if re.search(r"ELE", c) and "CONSUMO" in c.upper()]
    cost = [c for c in allc if re.search(r"COSTE|KOSTU", c.upper())]
    for c in elec + cost:
        df[c] = num(df[c])
    df["elec_kwh"] = df[elec].sum(axis=1)
    df["coste"] = df[cost].sum(axis=1) if cost else float("nan")
    p("n cols elec", len(elec), "cost", len(cost))
    p("elec GWh por año:", (df.groupby("EJERCICIO").elec_kwh.sum() / 1e6).round(2).to_dict(), "coste M€:", (df.groupby("EJERCICIO").coste.sum() / 1e6).round(2).to_dict())
    p("elec por tipología 2025 (GWh):", (df[df.EJERCICIO == "2025"].groupby("TIPOLOGIA").elec_kwh.sum() / 1e6).round(2).sort_values(ascending=False).head(8).to_dict())
    p("top elementos 2025:", df[df.EJERCICIO == "2025"].set_index("ELEMENTO").elec_kwh.sort_values(ascending=False).head(6).round(0).to_dict())


def flota(r):
    p("\n### PARQUE MÓVIL")
    df = todos(r / "vehiculos-parque-movil")
    c = [x for x in df.columns if "COMBUSTIBLE" in x.upper()]
    if c:
        p(pd.crosstab(df.EJERCICIO, df[c[0]].fillna("¿?")).to_string())
    p("vehículos por año:", df.groupby("EJERCICIO").size().to_dict())


def main():
    r = Path(sys.argv[1])
    for fn in (fauna, ganado, txakoli, superficies, residuos, playas, saip, bizkaibus, visitas, energia, flota):
        try:
            fn(r)
        except Exception as e:  # noqa: BLE001
            p(f"ERROR en {fn.__name__}: {type(e).__name__}: {e}")
    Path(sys.argv[2]).write_text("\n".join(OUT), encoding="utf-8")


if __name__ == "__main__":
    main()
