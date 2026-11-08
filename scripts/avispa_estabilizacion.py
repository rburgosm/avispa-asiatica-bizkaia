"""Reconstrucción de la estabilización de la avispa asiática en Bizkaia (2018-2025).

Uso:
    python -I scripts/avispa_estabilizacion.py <nidos.csv> <padron_ine.json> [carpeta_gbif] [carpeta_salida]

- nidos.csv: conjunto «Avispa asiática en Bizkaia» de Open Data Bizkaia.
- padron_ine.json: tabla 2905 del INE (padrón municipal), para las tasas por habitante.
- carpeta_gbif (opcional): si se indica, descarga ahí los registros de GBIF de Vespa velutina
  en Bizkaia (2010-2017) como contexto de la llegada, y los resume.
Escribe <salida>/avispa_estabilizacion.txt y <salida>/avispa_estabilizacion.png (por defecto, outputs/).

Medidas (todas sobre nidos de avispa asiática, sin anuladas, por temporada):
- Nidos por temporada y su tendencia (regresión binomial negativa con statsmodels; solo ocho
  puntos, así que se da como descripción, no como predicción).
- Ocupación por cuadrículas de 1 km (UTM 30N): celdas con nidos, celdas nuevas (nunca vistas
  antes), colonizadas (vacías el año anterior) y abandonadas (con nidos el año anterior y no en
  este). 2018 y 2019 tienen menos coordenadas (81-82 % frente a 92-96 %): se da también la
  ocupación con la misma proporción de coordenadas en todos los años (submuestreo al 81 %).
- Ocupación por municipios (todos los nidos traen municipio): municipios con nidos y
  persistencia del ranking entre años (correlación de Spearman de nidos por municipio).
- Desplazamiento del centroide anual.
Limitación general: son nidos avisados y retirados, no la población real de avispas.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import urllib.parse
import urllib.request
import statsmodels.api as sm
from pyproj import Transformer
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from avispa_llegamos_tarde import preparar  # noqa: E402
from explorar_avispa import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, poblacion  # noqa: E402

CELDA = 1000  # metros
SEMILLA = 2026
GBIF = "https://api.gbif.org/v1/occurrence/search"


def get_json(url: str, params: dict) -> dict:
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}",
                                 headers={"User-Agent": "opendata-eus-analisis/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def con_celdas(d: pd.DataFrame) -> pd.DataFrame:
    ok = d.lat.between(LAT_MIN, LAT_MAX) & d.lon.between(LON_MIN, LON_MAX)
    g = d[ok].copy()
    x, y = Transformer.from_crs(4326, 25830, always_xy=True).transform(g.lon.values, g.lat.values)
    g["x"], g["y"] = x, y
    g["celda"] = (np.floor(x / CELDA).astype(int)).astype(str) + "_" + (np.floor(y / CELDA).astype(int)).astype(str)
    return g


def dinamica(celdas_por_anio: dict) -> pd.DataFrame:
    filas, vistas, prev = [], set(), None
    for t in sorted(celdas_por_anio):
        c = celdas_por_anio[t]
        fila = {"temporada": t, "ocupadas": len(c), "nuevas": len(c - vistas)}
        if prev is not None:
            fila["colonizadas"] = len(c - prev)
            fila["abandonadas"] = len(prev - c)
            fila["persistencia"] = len(c & prev) / len(prev)
        filas.append(fila)
        vistas |= c
        prev = c
    return pd.DataFrame(filas).set_index("temporada")


def gbif(carpeta: Path) -> list[str]:
    """Descarga los registros de GBIF de Vespa velutina en el rectángulo de Bizkaia, 2010-2017."""
    carpeta.mkdir(parents=True, exist_ok=True)
    clave = get_json("https://api.gbif.org/v1/species/match", {"name": "Vespa velutina"})["usageKey"]
    params = {"taxonKey": clave, "decimalLatitude": f"{LAT_MIN},{LAT_MAX}",
              "decimalLongitude": f"{LON_MIN},{LON_MAX}", "year": "2010,2017", "limit": 300}
    r = get_json(GBIF, params)
    (carpeta / "gbif_vespa_velutina_bizkaia_2010_2017.json").write_text(json.dumps(r), encoding="utf-8")
    regs = pd.DataFrame([{k: o.get(k) for k in ("year", "eventDate", "locality", "municipality",
                                                 "stateProvince", "basisOfRecord", "datasetName")}
                         for o in r["results"]])
    L = [f"GBIF: {r['count']} registros de Vespa velutina en el rectángulo de Bizkaia entre 2010 y 2017"
         f" (descarga: {pd.Timestamp.now():%Y-%m-%d}; clave de taxón {clave})."]
    if len(regs):
        L.append("  Por año: " + ", ".join(f"{int(a)}: {n}" for a, n in regs.year.value_counts().sort_index().items()))
        L.append(f"  Primer registro: {regs.sort_values('eventDate').iloc[0].to_dict()}")
        L.append("  Tipo de registro: " + str(regs.basisOfRecord.value_counts().to_dict()))
        L.append("  Fuentes: " + str(regs.datasetName.value_counts().head(5).to_dict()))
    L.append("  Ojo: el rectángulo incluye bordes de Cantabria, Álava y Gipuzkoa; son registros dispersos,"
             " no un seguimiento sistemático.")
    return L


def main() -> None:
    ruta, ruta_pob = Path(sys.argv[1]), Path(sys.argv[2])
    carpeta_gbif = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    salida = Path(sys.argv[4] if len(sys.argv) > 4 else "outputs")
    d = preparar(ruta)
    L = []
    p = lambda x: f"{100 * x:.1f} %"

    # 1. Nidos por temporada y tendencia
    n = d.groupby("temporada").size()
    L.append("## Nidos por temporada (asiática, sin anuladas)")
    L.append("  " + "  ".join(f"{t}: {v}" for t, v in n.items()))
    L.append("  2018 empieza en abril y tiene menos coordenadas; 2017 se descarta.")
    for desde in (2018, 2019):
        s = n[n.index >= desde]
        X = sm.add_constant(np.arange(len(s)))
        m = sm.GLM(s.values, X, family=sm.families.NegativeBinomial(alpha=0.05)).fit()
        tasa = np.exp(m.params[1]) - 1
        lo, hi = np.exp(m.conf_int()[1]) - 1
        L.append(f"  Tendencia desde {desde} (binomial negativa): {tasa*100:+.1f} % al año "
                 f"(IC 95 %: {lo*100:+.1f} % a {hi*100:+.1f} %; p = {m.pvalues[1]:.3f})")
    L.append(f"  Coeficiente de variación 2019-2025: {n[n.index >= 2019].std() / n[n.index >= 2019].mean():.2f}")

    # 2. Ocupación por cuadrículas de 1 km
    g = con_celdas(d)
    cob = (g.groupby("temporada").size() / n).rename("cobertura")
    L.append("\n## Ocupación por cuadrículas de 1 km² (UTM 30N)")
    L.append("  Nidos con coordenadas válidas: " + "  ".join(f"{t}: {p(v)}" for t, v in cob.items()))
    din = dinamica({t: set(s.celda) for t, s in g.groupby("temporada")})
    rng = np.random.default_rng(SEMILLA)
    frac = cob.min()
    rep = []
    for _ in range(50):  # submuestreo: misma proporción de nidos con coordenadas en todos los años
        sub = {t: set(s.celda.values[rng.random(len(s)) < frac / cob[t]]) for t, s in g.groupby("temporada")}
        rep.append(dinamica(sub))
    eq = pd.concat(rep).groupby(level=0).mean()
    din["ocupadas_igualadas"] = eq.ocupadas.round(0)
    din["nuevas_igualadas"] = eq.nuevas.round(0)
    L.append(din.round(3).to_string())
    total = len(set(g.celda))
    L.append(f"  Celdas con algún nido en 2018-2025: {total} (Bizkaia mide unos 2.217 km²: {p(total / 2217)})")
    L.append(f"  Celdas presentes los 8 años: {sum(1 for c, k in g.groupby('celda').temporada.nunique().items() if k == 8)}")

    # 3. Ocupación por municipios y estabilidad del ranking
    pm = d.groupby(["temporada", "muni"]).size().unstack(fill_value=0)
    L.append("\n## Municipios")
    L.append("  Municipios con nidos: " + "  ".join(f"{t}: {(pm.loc[t] > 0).sum()}" for t in pm.index))
    L.append(f"  Municipios con nidos algún año: {(pm.sum() > 0).sum()}; los 8 años: {((pm > 0).sum() == 8).sum()}")
    rhos = [stats.spearmanr(pm.loc[a], pm.loc[a + 1]).statistic for a in pm.index[:-1]]
    L.append("  Spearman de nidos por municipio entre años consecutivos: " + ", ".join(f"{r:.2f}" for r in rhos))
    r1825 = stats.spearmanr(pm.loc[2018], pm.loc[2025]).statistic
    L.append(f"  Spearman 2018 frente a 2025: {r1825:.2f}")
    pob = poblacion(ruta_pob)
    tasa = (pm.loc[2019:2025].mean() / pob.reindex(pm.columns) * 1000).dropna().sort_values(ascending=False)
    L.append("  Nidos al año por 1.000 hab. (media 2019-2025), 8 primeros: "
             + ", ".join(f"{m} {v:.1f}" for m, v in tasa.head(8).items()))

    # 4. Centroide anual
    cen = g.groupby("temporada")[["x", "y"]].mean()
    desp = np.hypot(cen.x - cen.x.iloc[0], cen.y - cen.y.iloc[0]) / 1000
    L.append("\n## Desplazamiento del centroide respecto a 2018 (km): "
             + "  ".join(f"{t}: {v:.1f}" for t, v in desp.items()))

    # 5. Contexto previo: GBIF
    if carpeta_gbif:
        L.append("\n## Antes de 2018 (contexto, GBIF)")
        try:
            L += gbif(carpeta_gbif)
        except OSError as e:
            L.append(f"  No se pudo descargar GBIF: {e}")

    # Figura
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    n.plot(ax=ax[0], marker="o", color="#b5651d"); ax[0].set_title("Nidos retirados por temporada")
    din[["ocupadas", "ocupadas_igualadas"]].plot(ax=ax[1], marker="o"); ax[1].set_title("Cuadrículas de 1 km² con nidos")
    din[["nuevas", "colonizadas", "abandonadas"]].plot(ax=ax[2], marker="o"); ax[2].set_title("Dinámica de cuadrículas")
    for a in ax:
        a.set_xlabel("")
    fig.tight_layout()
    salida.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida / "avispa_estabilizacion.png", dpi=120)
    (salida / "avispa_estabilizacion.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
