"""Estacionalidad de los nidos de avispa asiática: Bizkaia frente a otras regiones.

Uso:
    python -I scripts/avispa_validacion_estacionalidad.py \
        <nidos_bizkaia.csv> <asturias_semanal.csv> <jersey_entries_2025.json> \
        <uk_sightings.html> <mnhn_facetas.jsonl> <araba_mes.csv> <carpeta_salida>

Entradas (todas descargadas; datos no fiables, solo se leen):
- nidos_bizkaia.csv: Open Data Bizkaia, conjunto «avispa asiática» (se carga con explorar_avispa.cargar,
  que corrige el doble UTF-8 y el intercambio día/mes de 2018-2022).
- asturias_semanal.csv: avisos semanales digitalizados de la gráfica del informe 2025 de Asturias
  (scripts/digitalizar_asturias.py). Semanas 10-53: falta enero-febrero.
- jersey_entries_2025.json: Epicollect5 «2025-jersey-asian-hornet-reports» (scripts/descargar_jersey_epicollect.py).
- uk_sightings.html: página de gov.uk «Asian hornet sightings recorded since 2016».
- mnhn_facetas.jsonl: facetas por mes y año del conjunto GBIF 9fd6c3da (MNHN, «colonies viables»), 2004-2025.
- araba_mes.csv: nidos inactivados por mes 2019-2024 (fuente Liztorbeltza), transcritos a mano de las
  gráficas de las págs. 29-34 del informe de la Diputación Foral de Álava «Vespa velutina Araban 2012-2024».

Salidas: avispa_validacion_estacionalidad.csv (proporción mensual por región y serie),
avispa_validacion_estacionalidad.png y avispa_validacion_estacionalidad.txt (resumen compacto).
"""
import html
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))  # carpeta scripts/ (código propio)
from explorar_avispa import cargar  # noqa: E402

MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()
MES_EN = {m: i + 1 for i, m in enumerate("January February March April May June July August September October November December".split())}


def bizkaia(ruta):
    d = cargar(ruta)
    a = d[d.especie.eq("AVISPA ASIÁTICA") & d.estado.ne("ANULADA") & d.anio.between(2018, 2025)]
    alta = a.groupby(a.alta.dt.month).size().reindex(range(1, 13), fill_value=0)
    el = a[a.estado.eq("CERRADA - ELIMINADO") & a.cierre.notna()]
    cierre = el.groupby(el.cierre.dt.month).size().reindex(range(1, 13), fill_value=0)
    return {"Bizkaia 2018-2025 (avisos, fecha de alta)": alta,
            "Bizkaia 2018-2025 (eliminados, fecha de cierre)": cierre}


def asturias(ruta):
    s = pd.read_csv(ruta)
    out = {}
    for anio, g in s.groupby("anio"):
        m = g.groupby("mes").avisos.sum().reindex(range(1, 13))
        out[f"Asturias {anio} (avisos semanales digitalizados, sin ene-feb)"] = m
    tot = s.groupby("mes").avisos.sum().reindex(range(1, 13))
    out["Asturias 2023-2025 (avisos semanales digitalizados, sin ene-feb)"] = tot
    return out


def jersey(ruta):
    e = pd.DataFrame(json.loads(Path(ruta).read_text()))
    e["f"] = pd.to_datetime(e["2_Date_of_reported_s"], dayfirst=True, errors="coerce")
    n = e[e["8_We_are_no_longer_r"].astype(str).str.startswith("Nest") & e.f.dt.year.eq(2025)]
    tipo = n["13_If_a_verified_Asi"].astype(str)
    muerto = n["8_We_are_no_longer_r"].str.startswith("Nest ONLY")
    tabla = pd.DataFrame({
        "nidos": n.groupby(n.f.dt.month).size(),
        "embrionarios_o_primarios": n[tipo.str.contains("Embryo|Primary")].groupby(n.f.dt.month).size(),
        "secundarios": n[tipo.str.contains("Secondary")].groupby(n.f.dt.month).size(),
        "muertos_sin_actividad": n[muerto].groupby(n.f.dt.month).size(),
    }).reindex(range(1, 13)).fillna(0).astype(int)
    return {"Jersey 2025 (nidos en Epicollect, fecha de aviso)": tabla.nidos}, tabla


def reino_unido(ruta):
    t = html.unescape(Path(ruta).read_text(encoding="utf8"))
    t = re.sub(r"\\u003c", "<", t)
    t = re.sub(r"<[^>]+>", "\n", t)
    lineas = [l.strip() for l in t.split("\n") if l.strip()]
    # El cuerpo visible empieza en la primera cabecera «Confirmed sightings in 2025» tras el índice
    ini = [i for i, l in enumerate(lineas) if l.startswith("Confirmed sightings in 2025")][1]
    anio, filas = None, []
    for l in lineas[ini:]:
        m = re.match(r"^(?:Confirmed sightings in (20\d\d)|(20\d\d): confirmed sightings)", l)
        if m:
            anio = int(m.group(1) or m.group(2))
            continue
        m = re.search(r":\s*(\d{1,2})\s+([A-Z][a-z]+)\s*[–-]\s*(?:\(.*?\)\s*)?(\d+\s+)?nests?\s+destroyed", l, re.I)
        if m and anio and m.group(2) in MES_EN:
            filas.append((anio, MES_EN[m.group(2)], int(m.group(3) or 1)))
    df = pd.DataFrame(filas, columns=["anio", "mes", "nidos"])
    out = {}
    sub = df[df.anio.between(2023, 2025)]
    out["Reino Unido 2023-2025 (nidos destruidos confirmados, gov.uk)"] = sub.groupby("mes").nidos.sum().reindex(range(1, 13), fill_value=0)
    return out, df.groupby("anio").nidos.sum()


def mnhn_por_anio(ruta, anio0=2004):
    """Una línea por año, de 2004 en adelante (orden en que se descargaron)."""
    filas = []
    for i, l in enumerate(x for x in Path(ruta).read_text().splitlines() if x.strip()):
        d = json.loads(l)
        for c in (d["facets"][0]["counts"] if d.get("facets") else []):
            filas.append((anio0 + i, int(c["name"]), c["count"]))
    df = pd.DataFrame(filas, columns=["anio", "mes", "n"])
    sub = df[df.anio.between(2015, 2018)]
    return {"Francia 2015-2018 (MNHN/INPN en GBIF, colonias viables; no son retiradas)":
            sub.groupby("mes").n.sum().reindex(range(1, 13), fill_value=0)}


def araba(ruta):
    a = pd.read_csv(ruta)
    return {"Álava 2019-2024 (nidos inactivados, Liztorbeltza; transcrito de gráficas)":
            a.groupby("mes").nidos.sum().reindex(range(1, 13), fill_value=0)}


def indicadores(s):
    p = s / s.sum()
    return {
        "n": int(s.sum()),
        "mes_pico": MESES[int(p.idxmax()) - 1],
        "pct_mar_jun": 100 * p.loc[3:6].sum(),
        "pct_jul": 100 * p.loc[7],
        "pct_ago_oct": 100 * p.loc[8:10].sum(),
        "pct_oct": 100 * p.loc[10],
        "pct_nov_dic": 100 * p.loc[11:12].sum(),
        "pct_nov_feb": 100 * (p.loc[11:12].sum() + p.loc[1:2].sum()),
    }


def main():
    r_biz, r_ast, r_jer, r_uk, r_mnhn, r_ara, salida = sys.argv[1:8]
    salida = Path(salida)
    series = {}
    series.update(bizkaia(Path(r_biz)))
    series.update(asturias(r_ast))
    s_jer, tabla_jer = jersey(r_jer)
    series.update(s_jer)
    s_uk, uk_anual = reino_unido(r_uk)
    series.update(s_uk)
    series.update(mnhn_por_anio(r_mnhn))
    series.update(araba(r_ara))

    filas = []
    for nombre, s in series.items():
        s = s.fillna(0)
        p = s / s.sum()
        fila = {"serie": nombre, **indicadores(s)}
        fila.update({f"pct_{m}": round(100 * p.loc[i + 1], 1) for i, m in enumerate(MESES)})
        filas.append(fila)
    tab = pd.DataFrame(filas)
    tab.round(1).to_csv(salida / "avispa_validacion_estacionalidad.csv", index=False)

    # Resumen
    out = ["=== ESTACIONALIDAD DE NIDOS: BIZKAIA FRENTE A OTRAS REGIONES ==="]
    cols = ["serie", "n", "mes_pico", "pct_mar_jun", "pct_ago_oct", "pct_oct", "pct_nov_dic", "pct_nov_feb"]
    out.append(tab[cols].round(1).to_string(index=False))
    out.append("\nJersey 2025 por mes (Epicollect; muertos = «Nest ONLY report, dead nest, no live insects»):")
    tj = tabla_jer.copy()
    tj["pct_muertos"] = (100 * tj.muertos_sin_actividad / tj.nidos.replace(0, np.nan)).round(0)
    tj.index = [MESES[i - 1] for i in tj.index]
    out.append(tj.to_string())
    out.append(f"\nReino Unido, nidos destruidos confirmados por año (parseo de gov.uk): {uk_anual.to_dict()}")
    (salida / "avispa_validacion_estacionalidad.txt").write_text("\n".join(out) + "\n", encoding="utf8")
    print("\n".join(out))

    # Gráfico: pequeños múltiplos, Bizkaia (gris de fondo) frente a cada región
    plot = [
        ("Asturias 2023-2025 (avisos semanales digitalizados, sin ene-feb)", "Asturias 2023-2025\navisos de nidos (sin ene-feb)"),
        ("Álava 2019-2024 (nidos inactivados, Liztorbeltza; transcrito de gráficas)", "Álava 2019-2024\nnidos inactivados (servicio Liztorbeltza)"),
        ("Jersey 2025 (nidos en Epicollect, fecha de aviso)", "Jersey 2025\nnidos avisados (n=384)"),
        ("Reino Unido 2023-2025 (nidos destruidos confirmados, gov.uk)", "Reino Unido 2023-2025\nnidos destruidos (búsqueda activa)"),
        ("Francia 2015-2018 (MNHN/INPN en GBIF, colonias viables; no son retiradas)", "Francia 2015-2018 (MNHN)\nregistros de colonias"),
    ]
    biz = series["Bizkaia 2018-2025 (avisos, fecha de alta)"]
    biz = 100 * biz / biz.sum()
    fig, axs = plt.subplots(2, 3, figsize=(13, 7.5), sharey=True)
    x = np.arange(1, 13)
    for ax, (k, titulo) in zip(axs.flat, plot):
        s = series[k].fillna(0)
        p = 100 * s / s.sum()
        ax.bar(x, biz.values, color="#c8c8c8", width=0.8, label="Bizkaia 2018-2025 (avisos)")
        ax.plot(x, p.values, color="#1f5fa8", marker="o", lw=2, ms=4, label="Región")
        ax.set_title(titulo, fontsize=10, loc="left")
        ax.set_xticks(x, [m[0].upper() for m in MESES])
        ax.axvspan(10.5, 12.5, color="#f2d0c4", alpha=0.35, lw=0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e6e6", lw=0.6)
        ax.set_axisbelow(True)
    # Sexto panel: proporción de nidos sin actividad en Jersey por mes
    ax = axs[1, 2]
    pm = 100 * tabla_jer.muertos_sin_actividad / tabla_jer.nidos.replace(0, np.nan)
    ax.bar(x, pm.fillna(0).values, color="#b5543c", width=0.7)
    for xi, (v, n) in enumerate(zip(pm.values, tabla_jer.nidos.values), start=1):
        if n:
            ax.text(xi, (0 if np.isnan(v) else v) + 1, f"n={n}", ha="center", fontsize=6, color="#555")
    ax.set_title("Jersey 2025: % de nidos avisados\nya muertos (sin avispas)", fontsize=10, loc="left")
    ax.set_xticks(x, [m[0].upper() for m in MESES])
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e6e6", lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelleft=True)
    axs[0, 0].set_ylabel("% de los nidos del año")
    axs[1, 0].set_ylabel("% de los nidos del año")
    axs[0, 0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle("Avispa asiática: reparto mensual de nidos. Barras grises: Bizkaia. Sombreado: noviembre-diciembre",
                 fontsize=11, x=0.01, ha="left")
    fig.text(0.01, 0.005, "Fuentes: Open Data Bizkaia; informe 2025 de Asturias (gráfica digitalizada, ±15 avisos/semana); "
             "DFA (Álava, transcrito); Epicollect5 Jersey; gov.uk (APHA/NBU); MNHN vía GBIF. No son series homogéneas: ver docs/avispa_validacion_externa.md",
             fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(salida / "avispa_validacion_estacionalidad.png", dpi=150)


if __name__ == "__main__":
    main()
