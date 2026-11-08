"""¿Qué parte de los nidos de avispa asiática se retira cuando las reinas ya han podido salir?

Uso:
    python -I scripts/avispa_llegamos_tarde.py <nidos.csv> [carpeta_salida]

Reutiliza la carga y la corrección de fechas día/mes de 2018-2022 de explorar_avispa.py.
Escribe <salida>/avispa_llegamos_tarde.txt (por defecto, outputs/).

Definiciones:
- Base: avispa asiática, sin anuladas, sin duplicados exactos, años 2018-2025.
  2017 se descarta (108 filas, casi todas pendientes). 2018 empieza en abril.
- Temporada: un nido dado de alta entre enero y marzo pertenece a la temporada del año
  anterior (nido viejo descubierto en invierno). El resto, a la temporada de su año.
- Fecha de retirada: fecha de cierre (si falta o es «9999-12-31», no se usa).
- Tardío: retirado en o después de la fecha de corte de su temporada. Se prueban
  15/10, 01/11 y 01/12, que son los cortes discutidos en la literatura.
- Primavera: alta entre abril y junio (fase de nido primario).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explorar_avispa import cargar  # noqa: E402

CORTES = {"15/10": (10, 15), "01/11": (11, 1), "01/12": (12, 1)}


def preparar(ruta: Path) -> pd.DataFrame:
    d = cargar(ruta)
    n0 = len(d)
    d = d.drop_duplicates(subset=[c for c in d.columns if c not in ("alta_orig",)])
    d = d[d.especie.str.contains("ASI", na=False) & ~d.estado.str.contains("ANULADA", na=False)]
    d = d[d.anio.between(2018, 2025) & d.alta.notna()].copy()
    d["temporada"] = np.where(d.alta.dt.month <= 3, d.alta.dt.year - 1, d.alta.dt.year)
    d = d[d.temporada.between(2018, 2025)]
    d["eliminado"] = d.estado.str.contains("ELIMINADO", na=False)
    d["no_elim"] = d.estado.str.contains("NO ELIMINABLE", na=False)
    d["mes_alta"] = d.alta.dt.month
    d.attrs["n_bruto"] = n0
    return d


def tardio(d: pd.DataFrame, fecha: pd.Series, corte) -> pd.Series:
    m, dia = corte
    limite = pd.to_datetime(dict(year=d.temporada, month=m, day=dia))
    return fecha >= limite


def main() -> None:
    ruta = Path(sys.argv[1])
    salida = Path(sys.argv[2] if len(sys.argv) > 2 else "outputs")
    d = preparar(ruta)
    L = []
    p = lambda x: f"{100 * x:.1f} %"

    L.append(f"Filas brutas: {d.attrs['n_bruto']}; base (asiática, sin anuladas, 2018-2025): {len(d)}")
    L.append(f"Eliminados: {d.eliminado.sum()}; no eliminables: {d.no_elim.sum()}; "
             f"otros estados: {(~d.eliminado & ~d.no_elim).sum()}")
    cierre_ok = d.cierre.notna() & (d.cierre >= d.alta - pd.Timedelta(days=1))
    L.append(f"Con fecha de cierre utilizable: {cierre_ok.sum()} ({p(cierre_ok.mean())})")
    L.append(f"Altas de enero-marzo (nidos viejos de la temporada anterior): {(d.mes_alta <= 3).sum()}")

    # 1. Reparto mensual de altas
    L.append("\n## Altas por mes (toda la serie, % del total)")
    mens = d.mes_alta.value_counts(normalize=True).sort_index()
    L.append("  " + "  ".join(f"{m}:{100*v:.1f}" for m, v in mens.items()))
    L.append(f"Primavera (abr-jun): {p(d.mes_alta.between(4, 6).mean())}; "
             f"verano (jul-sep): {p(d.mes_alta.between(7, 9).mean())}; "
             f"otoño (oct-dic): {p(d.mes_alta.between(10, 12).mean())}; "
             f"invierno (ene-mar): {p(d.mes_alta.between(1, 3).mean())}")

    # 2. Proporción tardía según corte, con la fecha de alta y con la de cierre
    L.append("\n## Proporción de nidos tardíos según la fecha de corte")
    el = d[d.eliminado & cierre_ok].copy()
    ne = d[d.no_elim].copy()
    for nombre, c in CORTES.items():
        d[f"ta_{nombre}"] = tardio(d, d.alta, c)
        el[f"tc_{nombre}"] = tardio(el, el.cierre, c)
        ne[f"ta_{nombre}"] = tardio(ne, ne.alta, c)
        por_anio = el.groupby("temporada")[f"tc_{nombre}"].mean()
        L.append(f"Corte {nombre}: por fecha de alta {p(d[f'ta_{nombre}'].mean())} | eliminados por fecha "
                 f"de cierre {p(el[f'tc_{nombre}'].mean())} (rango anual {p(por_anio.min())}-"
                 f"{p(por_anio.max())}) | no eliminables por alta {p(ne[f'ta_{nombre}'].mean())}")

    L.append("\n## Corte 01/11, eliminados por fecha de cierre, por temporada")
    g = el.groupby("temporada")["tc_01/11"].agg(["size", "sum", "mean"])
    for t, r in g.iterrows():
        L.append(f"  {t}: {int(r['size'])} retirados, {int(r['sum'])} tardíos ({p(r['mean'])})")
    L.append("  (2018 empieza en abril: su proporción puede estar sesgada.)")

    # 3. Qué son los nidos tardíos: ubicación, tamaño y altura
    L.append("\n## Perfil de los nidos según la fase (eliminados, fecha de cierre)")
    el["fase"] = np.select(
        [el.cierre.dt.month.between(4, 6) & (el.temporada == el.cierre.dt.year), el["tc_01/11"]],
        ["primavera", "tardio"], "verano-otono")
    for f, sub in el.groupby("fase"):
        arbol = sub.ubic.str.contains("ARBOL", na=False).mean()
        L.append(f"  {f}: n={len(sub)}, en árbol {p(arbol)}, diámetro mediano {sub.diam.median():.0f} cm, "
                 f"altura mediana {sub.altura.median():.0f} m")

    # 4. Nidos de primavera y su evolución
    L.append("\n## Nidos dados de alta en primavera (abr-jun) por temporada")
    d["es_primavera"] = d.mes_alta.between(4, 6)
    pr = d.groupby("temporada")["es_primavera"].agg(n="size", primavera="sum")
    for t, r in pr.iterrows():
        L.append(f"  {t}: {int(r.primavera)} de {int(r.n)} ({p(r.primavera / r.n)})")
    ratio = (pr.n - pr.primavera) / pr.primavera
    L.append(f"Nidos del resto del año por cada nido de primavera: mediana {ratio.median():.1f} "
             f"(rango {ratio.min():.1f}-{ratio.max():.1f})")

    # 5. Tiempo de espera de los nidos avisados en octubre (¿se cuelan en noviembre?)
    oct_ = d[d.eliminado & cierre_ok & (d.mes_alta == 10)]
    cruza = (oct_.cierre >= pd.to_datetime(dict(year=oct_.temporada, month=11, day=1))).mean()
    L.append(f"\nNidos avisados en octubre y retirados ya en noviembre o después: {p(cruza)} "
             f"(mediana de espera {oct_.dias.median():.0f} días)")

    # 6. No eliminables: cuándo se avisan
    L.append(f"No eliminables: {len(ne)}; avisados desde el 01/11: "
             f"{p(ne['ta_01/11'].mean())}; en árbol: {p(ne.ubic.str.contains('ARBOL', na=False).mean())}")

    # 7. Visibilidad: dónde y de qué tamaño son los nidos que se avisan cada mes
    d["arbol"] = d.ubic.str.contains("ARBOL", na=False)
    L.append("\n## Nidos avisados por mes: % en árbol, diámetro y altura medianos (árbol / casa)")
    for m, g in d.groupby("mes_alta"):
        a, c = g[g.arbol], g[~g.arbol]
        L.append(f"  {m:>2}: n={len(g):>5}, en árbol {p(g.arbol.mean()):>7}, diám. árbol {a.diam.median():.0f} cm / "
                 f"casa {c.diam.median():.0f} cm, altura árbol {a.altura.median():.0f} m / casa {c.altura.median():.0f} m")
    a = d[d.arbol]
    L.append(f"Nidos en árbol avisados en oct-nov: {p(a.mes_alta.between(10, 11).mean())}")
    grande = a[a.diam >= 40]
    L.append(f"Nidos en árbol de 40 cm o más: {len(grande)}; avisados oct-dic {p(grande.mes_alta.between(10, 12).mean())}, "
             f"nov-dic {p(grande.mes_alta.between(11, 12).mean())}")

    salida.mkdir(parents=True, exist_ok=True)
    (salida / "avispa_llegamos_tarde.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
