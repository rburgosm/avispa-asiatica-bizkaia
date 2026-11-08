"""Resumen compacto de las intervenciones del SPEIS (bomberos de la Diputación Foral de Bizkaia).

Fuente: https://www.opendatabizkaia.eus/es/catalogo/intervenciones-speis (tres ficheros CSV:
2021, 2022 y «2023-2026»). Se descargan con:
    curl -s "https://www.opendatabizkaia.eus/es/dump/<id>/<nombre>?format=csv"
(los id están en la página del conjunto).

Uso: .venv/bin/python -I scripts/explorar_speis.py data/raw/bizkaia/speis
Escribe outputs/speis_resumen.txt.
"""
import sys
from pathlib import Path

import pandas as pd


def arreglar(s: pd.Series) -> pd.Series:
    """Deshace el doble UTF-8 (mojibake «Ã³») que traen los textos del portal."""
    return (s.astype(str).str.encode("latin-1", errors="ignore")
            .str.decode("utf-8", errors="ignore").str.strip().str.upper())


def cargar(carpeta: Path) -> pd.DataFrame:
    partes = []
    for f in sorted(carpeta.glob("intervenciones-speis-*.csv")):
        d = pd.read_csv(f)
        c = d.columns
        if "TIPO SINIESTRO" in c[6]:  # esquema antiguo (2021 y 2022)
            m = dict(anio=c[1], mes=c[4], franja=c[5], tipo=c[6], muni=c[10], estado=c[12],
                     heridos=c[14], muertos=c[15])
        else:  # esquema nuevo (2023 en adelante), con coordenadas
            m = dict(anio=c[1], mes=c[3], franja=c[4], tipo=c[5], muni=c[8], estado=c[10],
                     heridos=c[12], muertos=c[13])
        p = pd.DataFrame({k: d[v] for k, v in m.items()})
        for k in ("tipo", "muni", "estado", "franja"):
            p[k] = arreglar(p[k])
        p["lat"] = d["latitude"] if "latitude" in c else pd.NA
        p["fichero"] = f.name
        partes.append(p)
    return pd.concat(partes, ignore_index=True)


def main() -> None:
    carpeta = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/bizkaia/speis")
    d = cargar(carpeta)
    out = []
    out.append(f"Filas por año: {d.groupby('anio').size().to_dict()}")
    out.append(f"Tipos distintos por año: {d.groupby('anio').tipo.nunique().to_dict()}")
    out.append(f"Con coordenadas por año: {d.groupby('anio').lat.apply(lambda s: round(s.notna().mean(), 2)).to_dict()}")
    out.append(f"Simulaciones informáticas por año: {d[d.tipo.str.contains('SIMUL')].groupby('anio').size().to_dict()}")
    out.append(f"Accidentes de tráfico por año: {d[d.tipo.str.contains('ACCIDENTE')].groupby('anio').size().to_dict()}")
    out.append("Top 10 tipos 2023-2025:")
    out.append(d[d.anio >= 2023].tipo.value_counts().head(10).to_string())
    av = d[d.tipo.str.contains("ABEJA|AVISP")]
    out.append("Avispas y abejas por año y mes:")
    out.append(av.pivot_table(index="anio", columns="mes", values="tipo", aggfunc="count")
               .fillna(0).astype(int).to_string())
    out.append(f"Top municipios avispas 2023-2025: {av[av.anio >= 2023].muni.value_counts().head(10).to_dict()}")
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/speis_resumen.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
