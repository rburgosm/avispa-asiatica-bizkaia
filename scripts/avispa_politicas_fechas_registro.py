"""Fechas de referencia del registro de nidos para la cronología de políticas.

Solo fecha hitos (primer y último registro, primera aparición de cada agente de cierre
y de cada usuario que da el aviso). No calcula indicadores (los hace otro script).
Uso: python -I scripts/avispa_politicas_fechas_registro.py data/raw/bizkaia/avispa_asiatica/nidos.csv
"""
import sys

import pandas as pd

d = pd.read_csv(sys.argv[1])
alta = pd.to_datetime(d["ALTA_DATA/FECHA ALTA"], errors="coerce")
print("Primer alta:", alta.min(), "| último alta:", alta.max())
print("Altas por año y mes del primer año:")
print(alta[alta.dt.year == alta.dt.year.min()].dt.to_period("M").value_counts().sort_index().to_string())
for col in ["ITXIERAKO AGENTEA_CAS/AGENTE CIERRE_CAS", "ERABILTZAILEA_CAS/USUARIO_CAS"]:
    print(f"\n{col}: primera y última alta, n")
    v = d[col].fillna("(vacío)").str.strip()
    # «AYUNTAMIENTO <nombre>» (2018-2022) frente a «AYUNTAMIENTO» genérico (desde 2023)
    v = v.where(~v.str.match(r"AYUNTAMIENTO .+"), "AYUNTAMIENTO <nombre del municipio>")
    g = pd.DataFrame({"v": v, "alta": alta}).groupby("v")["alta"]
    print(pd.concat([g.min(), g.max(), g.size()], axis=1, keys=["primera", "ultima", "n"]).to_string())
pb = d[d["ITXIERAKO AGENTEA_CAS/AGENTE CIERRE_CAS"].astype(str).str.contains("PAINT", na=False)]
print("\nFilas con agente PAINT BALL:")
print(pb[["URTEA/AÑO", "ALTA_DATA/FECHA ALTA", "UDALERRIA/MUNICIPIO", "ALTUERA/ALTURA",
          "EGOERA_CAS/ESTADO_CAS"]].to_string())
