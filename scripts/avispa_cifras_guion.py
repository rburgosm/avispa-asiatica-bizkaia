"""Cifras del guion recalculadas con el periodo principal (temporadas 2019-2025, avisos de abril a diciembre).

Uso:
    python -I scripts/avispa_cifras_guion.py [nidos.csv] [padron_2017_2025.json] [carpeta_salida]

Reutiliza la limpieza de explorar_avispa.cargar (vía avispa_llegamos_tarde.preparar) y el padrón de
avispa_avisos_poblacion.padron. Escribe outputs/avispa_cifras_guion.txt, outputs/avispa_reparto_mensual.csv,
outputs/avispa_perfil_epoca.csv y outputs/avispa_tasas_tamano.csv.

Las funciones base(), perfil_epoca(), reparto_mensual() y tasas_tamano() devuelven tablas; las usa
también scripts/web_preparar_datos.py para no copiar cifras a mano en la web.

Calcula:
  1. Tamaño y altura de los nidos eliminados según la época de cierre (primavera abr-jun, verano-otoño
     jul-31/10, tardío desde el 01/11).
  2. Reparto mensual de los avisos (abril-diciembre), en conjunto y por temporada.
  3. Nidos por 1.000 habitantes según el tamaño del municipio (padrón del año de cada temporada).
     Bilbao queda fuera: tiene servicio municipal propio y apenas aparece en el registro (3 nidos).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from avispa_llegamos_tarde import preparar  # noqa: E402
from avispa_avisos_poblacion import padron  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
TEMPORADAS = range(2019, 2026)
TAMANOS = ([0, 2000, 5000, 20000, 1e7], ["<2.000", "2.000-5.000", "5.000-20.000", ">20.000"])
EPOCAS = ["primavera (cierre abr-jun)", "verano-otoño (cierre jul-31/10)", "tardío (cierre desde el 01/11)"]


def base(ruta: Path) -> pd.DataFrame:
    """Asiática sin anuladas, temporadas 2019-2025, avisos de abril a diciembre."""
    d = preparar(ruta)
    return d[d.temporada.isin(TEMPORADAS) & d.mes_alta.between(4, 12)].copy()


def perfil_epoca(d: pd.DataFrame) -> pd.DataFrame:
    """Tamaño, altura y ubicación de los nidos eliminados según la época de cierre."""
    e = d[d.eliminado & d.cierre.notna()].copy()
    e["altura_v"] = e.altura.where((e.altura > 0) & (e.altura <= 60))
    e["diam_v"] = e.diam.where((e.diam > 0) & (e.diam < 250))
    mc = e.cierre.dt.month
    e["epoca"] = np.select([mc.between(4, 6), (mc >= 11) | (mc <= 3)], [EPOCAS[0], EPOCAS[2]], EPOCAS[1])
    filas = []
    for ep, g in e.groupby("epoca"):
        filas.append(dict(epoca=ep, n=len(g), diam_mediana_cm=g.diam_v.median(), diam_validos=int(g.diam_v.notna().sum()),
                          altura_mediana_m=g.altura_v.median(), altura_validos=int(g.altura_v.notna().sum()),
                          pct_arbol=g.ubic.astype(str).str.contains("ARBOL|ÁRBOL", case=False).mean()))
    return pd.DataFrame(filas).set_index("epoca").reindex(EPOCAS)


def reparto_mensual(d: pd.DataFrame) -> pd.DataFrame:
    """Avisos por temporada y mes (abril-diciembre) y su proporción dentro de la temporada."""
    tab = d.groupby(["temporada", "mes_alta"]).size().unstack(fill_value=0)
    pct = tab.div(tab.sum(axis=1), axis=0)
    out = pct.reset_index().melt(id_vars="temporada", var_name="mes", value_name="proporcion")
    out = out.merge(tab.reset_index().melt(id_vars="temporada", var_name="mes", value_name="avisos"))
    return out.sort_values(["temporada", "mes"]).reset_index(drop=True)


def tasas_tamano(d: pd.DataFrame, pob: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Nidos por 1.000 habitantes según el tamaño del municipio (padrón de 2025), sin Bilbao.
    Devuelve una fila por tamaño con la tasa de cada temporada y la media 2019-2025, y la lista de
    municipios del registro que no cruzan con el padrón."""
    nm = d.groupby(["muni", "temporada"]).size().unstack(fill_value=0).reindex(columns=TEMPORADAS, fill_value=0)
    sin_cruzar = sorted(set(d.muni.unique()) - set(pob.index))
    nm = nm.reindex(pob.index, fill_value=0)
    pob, nm = pob.drop(index="BILBAO"), nm.drop(index="BILBAO")
    tam = pd.cut(pob[2025], TAMANOS[0], labels=TAMANOS[1])
    filas = []
    for k in tam.cat.categories:
        idx = tam[tam == k].index
        f = {"tamano": k, "municipios": len(idx)}
        f.update({str(t): 1000 * nm.loc[idx, t].sum() / pob.loc[idx, t].sum() for t in TEMPORADAS})
        f["media_2019_2025"] = 1000 * nm.loc[idx].sum().sum() / pob.loc[idx, list(TEMPORADAS)].sum().sum()
        filas.append(f)
    return pd.DataFrame(filas).set_index("tamano"), sin_cruzar


def main() -> None:
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data/raw/bizkaia/avispa_asiatica/nidos.csv"
    ruta_pob = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "data/raw/ine/padron_bizkaia_2905_2017_2025.json"
    salida = Path(sys.argv[3]) if len(sys.argv) > 3 else RAIZ / "outputs"
    L = []

    d = base(ruta)
    L.append(f"Base: asiática sin anuladas, temporadas 2019-2025, avisos de abril a diciembre: {len(d)} nidos")
    L.append("  por temporada: " + "  ".join(f"{t}: {n}" for t, n in d.groupby("temporada").size().items()))

    # 1. Perfil por época de cierre (eliminados)
    pe = perfil_epoca(d)
    L.append("\n## 1. Nidos eliminados según la época de cierre (2019-2025)")
    for ep, r in pe.sort_index().iterrows():
        L.append(f"  {ep}: n={r.n:.0f}; diámetro mediano {r.diam_mediana_cm:.0f} cm (válidos {r.diam_validos:.0f}); "
                 f"altura mediana {r.altura_mediana_m:.0f} m (válidos {r.altura_validos:.0f}); "
                 f"% en árbol {100 * r.pct_arbol:.1f} %")
    pe.round(4).to_csv(salida / "avispa_perfil_epoca.csv")

    # 2. Reparto mensual
    out = reparto_mensual(d)
    tab = out.pivot(index="temporada", columns="mes", values="avisos")
    pct = out.pivot(index="temporada", columns="mes", values="proporcion")
    total = tab.sum() / tab.values.sum()
    L.append("\n## 2. Reparto mensual de los avisos, abril-diciembre (2019-2025, en conjunto)")
    L.append("  " + "  ".join(f"{m}: {100 * v:.1f} %" for m, v in total.items()))
    L.append(f"  Primavera (abr-jun): {100 * total.loc[4:6].sum():.1f} %; verano (jul-sep): "
             f"{100 * total.loc[7:9].sum():.1f} %; otoño (oct-dic): {100 * total.loc[10:12].sum():.1f} %")
    L.append("  Primavera por temporada: " + "  ".join(
        f"{t}: {100 * pct.loc[t, 4:6].sum():.1f} %" for t in pct.index))
    out.to_csv(salida / "avispa_reparto_mensual.csv", index=False)

    # 3. Nidos por 1.000 habitantes según tamaño de municipio (sin Bilbao)
    tt, sin_cruzar = tasas_tamano(d, padron(ruta_pob))
    L.append("\n## 3. Nidos por 1.000 habitantes según tamaño de municipio (padrón de 2025 para el tamaño; "
             "padrón de cada año para la tasa; sin Bilbao)")
    L.append(f"  Municipios sin cruzar con el padrón: {sin_cruzar}")
    for k, r in tt.iterrows():
        L.append(f"  {k:>13} ({r.municipios:.0f} municipios): " + "  ".join(f"{t}: {r[str(t)]:.1f}" for t in TEMPORADAS)
                 + f"  | media 2019-2025: {r.media_2019_2025:.1f}")
    tt.round(2).to_csv(salida / "avispa_tasas_tamano.csv")

    (salida / "avispa_cifras_guion.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
