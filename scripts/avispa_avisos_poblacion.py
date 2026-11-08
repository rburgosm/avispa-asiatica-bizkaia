"""¿La estabilidad de los nidos se explica por la población o por las ganas de avisar?

Uso:
    python -I scripts/avispa_avisos_poblacion.py <nidos.csv> <padron_2017_2025.json> [carpeta_salida]

- padron_2017_2025.json: tabla 2905 del INE con varios años,
  https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/2905?nult=9&tip=A
Escribe <salida>/avispa_avisos_poblacion.txt (por defecto, outputs/).

Comprobaciones:
1. Población por municipio 2018-2025 y su relación con la variación de nidos de asiática
   (correlación de Spearman entre la variación de población y la de nidos, 2019-2020 frente a
   2024-2025, para no depender de un solo año).
2. Control de esfuerzo de aviso: los avisos de otras especies del mismo conjunto (avispa común,
   abeja) pasan por el mismo canal; si las ganas de avisar cambiaran, deberían moverse con los
   de asiática.
3. Quién avisa (ayuntamiento u otros) por temporada.
4. Nidos por 1.000 habitantes por tamaño de municipio y temporada.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explorar_avispa import cargar, sin_tildes  # noqa: E402


def padron(ruta: Path) -> pd.DataFrame:
    filas = {}
    for x in json.loads(ruta.read_text(encoding="utf-8")):
        if ". Total. Total habitantes" in x["Nombre"]:
            nombre = sin_tildes(x["Nombre"].split(". ")[0])
            if nombre != "BIZKAIA":
                filas[nombre] = {v["Anyo"]: v["Valor"] for v in x["Data"]}
    return pd.DataFrame(filas).T.sort_index(axis=1)


def main() -> None:
    ruta, ruta_pob = Path(sys.argv[1]), Path(sys.argv[2])
    salida = Path(sys.argv[3] if len(sys.argv) > 3 else "outputs")
    p = lambda x: f"{100 * x:.1f} %"
    L = []

    d = cargar(ruta)
    d = d.drop_duplicates(subset=[c for c in d.columns if c != "alta_orig"])
    d = d[~d.estado.str.contains("ANULADA", na=False) & d.alta.notna()].copy()
    d["temporada"] = np.where(d.alta.dt.month <= 3, d.alta.dt.year - 1, d.alta.dt.year)
    d = d[d.temporada.between(2018, 2025)]
    d["sp"] = np.select([d.especie.str.contains("ASI", na=False), d.especie.str.contains("COM", na=False),
                         d.especie.str.contains("ABEJA", na=False)], ["asiatica", "comun", "abeja"], "otra")
    asi = d[d.sp == "asiatica"]

    # 1. Población
    pob = padron(ruta_pob)
    tot = pob.sum()
    L.append("## Población de Bizkaia (INE, 1 de enero; suma de municipios)")
    L.append("  " + "  ".join(f"{a}: {int(v):,}".replace(",", ".") for a, v in tot.items() if a >= 2018))
    var = pob[2025] / pob[2018] - 1
    L.append(f"  Variación 2018-2025 por municipio: mediana {p(var.median())}; "
             f"pierden población {int((var < 0).sum())} de {len(var)}; "
             f"pierden más del 5 %: {int((var < -0.05).sum())}")
    tam = pd.cut(pob[2025], [0, 2000, 5000, 20000, 1e7], labels=["<2.000", "2.000-5.000", "5.000-20.000", ">20.000"])
    L.append("  Variación por tamaño: " + ", ".join(f"{k} {p(v)}" for k, v in
             (pob.groupby(tam, observed=True)[2025].sum() / pob.groupby(tam, observed=True)[2018].sum() - 1).items()))

    nm = asi.groupby(["muni", "temporada"]).size().unstack(fill_value=0)
    comun = nm.index.intersection(pob.index)
    L.append(f"  Municipios cruzados con el padrón: {len(comun)} de {len(nm)}"
             f" (sin cruzar: {sorted(set(nm.index) - set(pob.index))[:8]})")
    nm, pb = nm.loc[comun], pob.loc[comun]
    dn = np.log1p(nm[[2024, 2025]].sum(axis=1)) - np.log1p(nm[[2019, 2020]].sum(axis=1))
    dp = np.log(pb[[2024, 2025]].sum(axis=1)) - np.log(pb[[2019, 2020]].sum(axis=1))
    r = stats.spearmanr(dp, dn)
    L.append(f"  Variación de nidos frente a variación de población (2019-20 → 2024-25): "
             f"Spearman rho = {r.statistic:.2f}, p = {r.pvalue:.2f}")
    tasa = nm.div(pb[[c for c in nm.columns]].values, axis=None) * 1000 if False else None  # noqa: F841
    L.append("  Nidos por 1.000 hab. por tamaño de municipio:")
    for k in tam.cat.categories:
        ms = tam[tam == k].index.intersection(comun)
        fila = (nm.loc[ms].sum() / pb.loc[ms, nm.columns].sum() * 1000)
        L.append(f"    {k:>13}: " + "  ".join(f"{t}: {v:.1f}" for t, v in fila.items()))

    # 2. Control con otras especies
    L.append("\n## Avisos por especie y temporada (mismo canal de aviso)")
    sp = d.groupby(["temporada", "sp"]).size().unstack(fill_value=0)
    L.append(sp.to_string())
    base = sp.loc[2019]
    L.append("  Índice 2019 = 100: " + " | ".join(
        f"{c}: " + " ".join(f"{int(round(100 * v / base[c]))}" for v in sp[c]) for c in ("asiatica", "comun", "abeja")))
    for c in ("comun", "abeja"):
        r = stats.spearmanr(sp.loc[2019:, "asiatica"], sp.loc[2019:, c])
        L.append(f"  Spearman asiática frente a {c} (2019-2025): {r.statistic:.2f} (p = {r.pvalue:.2f}; solo 7 años)")

    # 3. Quién avisa
    L.append("\n## Quién avisa los nidos de asiática (% por temporada)")
    q = pd.crosstab(asi.temporada, asi.usuario, normalize="index").mul(100).round(1)
    q = q.loc[:, q.max() >= 2]
    L.append(q.to_string())
    L.append("  Agente que cierra (% por temporada):")
    L.append(pd.crosstab(asi.temporada, asi.agente, normalize="index").mul(100).round(1).loc[:, lambda t: t.max() >= 2].to_string())

    salida.mkdir(parents=True, exist_ok=True)
    (salida / "avispa_avisos_poblacion.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
