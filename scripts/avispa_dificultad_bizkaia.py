"""Por qué se llega tarde, visto en los nidos de Bizkaia: altura, «no eliminables» y fecha de cierre.

Uso: python -I scripts/avispa_dificultad_bizkaia.py <nidos.csv> <salida.txt>

Usa explorar_avispa.cargar (corrige doble UTF-8 e intercambio día/mes 2018-2022).
Avispa asiática, sin anuladas, 2018-2025. Altura en metros (se descartan 0 y >= 100, y 255 = valor centinela).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explorar_avispa import cargar  # noqa: E402

MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()


def main():
    d = cargar(Path(sys.argv[1]))
    a = d[d.especie.eq("AVISPA ASIÁTICA") & d.estado.ne("ANULADA") & d.anio.between(2018, 2025)].copy()
    a["mes"] = a.alta.dt.month
    a["h"] = a.altura.where(a.altura.gt(0) & a.altura.lt(100))
    out = ["=== DIFICULTAD: ALTURA Y NIDOS NO ELIMINABLES POR MES DE AVISO (asiática 2018-2025) ==="]
    t = a.groupby("mes").agg(
        n=("h", "size"), altura_mediana=("h", "median"),
        pct_ge10m=("h", lambda s: 100 * (s >= 10).mean()),
        pct_ge15m=("h", lambda s: 100 * (s >= 15).mean()),
        pct_no_eliminable=("estado", lambda s: 100 * s.eq("CERRADA - NO ELIMINABLE").mean()),
        pct_bomberos=("agente", lambda s: 100 * s.eq("BOMBEROS").mean()),
        diam_mediano=("diam", "median"))
    t["pct_arbolado"] = a.groupby("mes").ubic.apply(lambda s: 100 * s.eq("ARBOLADO").mean())
    t.index = [MESES[i - 1] for i in t.index]
    out.append(t.round(1).to_string())
    ne = a[a.estado.eq("CERRADA - NO ELIMINABLE")]
    out.append(f"\nNo eliminables: {len(ne)} ({100 * len(ne) / len(a):.1f} %). Altura mediana {ne.h.median():.0f} m "
               f"frente a {a[a.estado.eq('CERRADA - ELIMINADO')].h.median():.0f} m en los eliminados.")
    out.append("No eliminables por año: " + str(ne.groupby("anio").size().to_dict()))
    # Corte por fecha de cierre (solo eliminados con cierre válido)
    el = a[a.estado.eq("CERRADA - ELIMINADO") & a.cierre.notna()].copy()
    out.append("\n=== ELIMINADOS SEGÚN FECHA DE CIERRE Y FECHA DE CORTE (misma temporada; ene-feb se cuentan como tardíos del año anterior) ===")
    filas = []
    for y, g in el.groupby("anio"):
        c = g.cierre
        temporada_sig = (c.dt.year > y)  # cerrados en ene-feb del año siguiente
        fila = {"anio": y, "n": len(g)}
        for corte in ["10-15", "11-01", "12-01"]:
            lim = pd.Timestamp(f"{y}-{corte}")
            fila[f"pct_desde_{corte}"] = 100 * ((c >= lim) | temporada_sig).mean()
        filas.append(fila)
    ft = pd.DataFrame(filas).set_index("anio")
    tot = {"n": ft.n.sum(), **{k: (ft[k] * ft.n).sum() / ft.n.sum() for k in ft.columns if k != "n"}}
    ft.loc["total"] = tot
    out.append(ft.round(1).to_string())
    out.append("Nota: los nidos cerrados en ene-feb del año siguiente cuentan como tardíos; los avisados en ene-feb del "
               "mismo año (restos de la temporada anterior, ~1,4 %) no se reasignan aquí.")
    Path(sys.argv[2]).write_text("\n".join(out) + "\n", encoding="utf8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
