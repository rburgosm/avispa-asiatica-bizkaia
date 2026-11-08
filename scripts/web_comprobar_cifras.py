"""Comprueba que las cifras redondeadas de los textos del guion (web/content/es.json) cuadran
con los datos que genera scripts/web_preparar_datos.py (web/data/*.json).

Uso:
    python -I scripts/web_comprobar_cifras.py [carpeta_web]

Los textos se copian tal cual del guion aprobado (docs/guion.md) y llevan cifras redondeadas
(«más de 18.000», «unos 3.200», «entre el 16 % y el 24 %»). Este script no las cambia: calcula
el valor exacto con los JSON y dice si el redondeo del texto es correcto. Si algo no cuadra,
hay que corregir el guion o los datos, no la web a mano. Sale con código 1 si falla alguna.
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
W = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "web"
J = lambda n: json.loads((W / "data" / n).read_text(encoding="utf-8"))  # noqa: E731

ind, men, reg, gas, mun, cro = (J("indicadores.json"), J("mensual.json"), J("regiones.json"), J("gasto.json"),
                                J("municipios.geojson"), J("cronologia.json"))
d0, d1 = ind["periodo"]
per = [i for i, t in enumerate(ind["temporadas"]) if d0 <= t <= d1]
serie = lambda k: [ind[k][i] for i in per]  # noqa: E731
t = dict(zip(ind["temporadas"], ind["nidos"]))
pooled = lambda a, b: (sum(ind["no_eliminables"][i] for i in per if a <= ind["temporadas"][i] <= b)  # noqa: E731
                       / sum(ind["nidos"][i] for i in per if a <= ind["temporadas"][i] <= b))
meseta = {s["region"]: s["meseta"]["densidad"] for s in reg["series"] if s["meseta"]}
coste = [v for c in gas["coste_nido"].values() for v in (c["min"], c["max"])]
encargo = [a["encargo_eur"] for a in gas["anios"] if a["estado"] == "sin_desglose"]
tam = {r["tamano"]: r["media"] for r in mun["tasas_tamano"]}
anios_hitos = {h["fecha"][:4] for h in cro["hitos"]}

C = [
    ("Paso 0", "más de 18.000 nidos", ind["total_periodo"], 18000 < ind["total_periodo"] < 19000),
    ("Paso 1", "2004, 2012 y 2016 en la cronología", sorted(anios_hitos & {"2004", "2012", "2016"}),
     {"2004", "2012", "2016"} <= anios_hitos),
    ("Paso 3", "julio de 2016 (protocolo)", [h["fecha"] for h in cro["hitos"] if h["fecha"].startswith("2016-07")],
     any(h["fecha"] == "2016-07-01" for h in cro["hitos"])),
    ("Paso 5", f"unos 2.000 nidos en {d0}", t[d0], round(t[d0], -2) == 2000),
    ("Paso 5", f"unos 3.200 en {d1}", t[d1], round(t[d1], -2) == 3200),
    ("Paso 5", "siete años de datos", len(per), len(per) == 7),
    ("Paso 6", "la mitad en dos días o menos", serie("dias_mediana"), max(serie("dias_mediana")) <= 2),
    # «alrededor de nueve de cada diez»: se admite del 85 % al 95,9 % (el máximo, 95,3 %, queda en el límite)
    ("Paso 6", "alrededor de nueve de cada diez en una semana", serie("pct_le7"),
     all(0.85 <= v < 0.96 for v in serie("pct_le7"))),
    ("Paso 7", "alrededor del 10 % hasta 2022", round(pooled(d0, 2022), 4), round(100 * pooled(d0, 2022)) == 10),
    ("Paso 7", "alrededor del 6 % desde 2023", round(pooled(2023, d1), 4), round(100 * pooled(2023, d1)) == 6),
    ("Paso 8", "uno de cada diez avisos en primavera", men["estaciones"]["primavera"],
     round(men["estaciones"]["primavera"], 1) == 0.1),
    ("Paso 9", "entre el 16 % y el 24 %", [min(serie("pct_elim_despues_1nov")), max(serie("pct_elim_despues_1nov"))],
     round(100 * min(serie("pct_elim_despues_1nov"))) == 16 and round(100 * max(serie("pct_elim_despues_1nov"))) == 24),
    ("Paso 10", "Asturias unos 1.000 por 1.000 km²", meseta.get("Asturias"), round(meseta.get("Asturias", 0), -2) == 1000),
    ("Paso 10", "Bizkaia unos 1.200 por 1.000 km²", meseta.get("Bizkaia"), round(meseta.get("Bizkaia", 0), -2) == 1200),
    ("Paso 11", "unos 70-100 euros por nido", [min(coste), max(coste)], 65 <= min(coste) and max(coste) <= 100),
    ("Paso 11", "encargo de más de 2 millones", [min(encargo), max(encargo)], min(encargo) > 2e6),
    ("Paso 12", "unos 16 nidos por 1.000 en los de menos de 2.000", tam.get("<2.000"), round(tam.get("<2.000", 0)) == 16),
    ("Paso 12", "uno en los de más de 20.000", tam.get(">20.000"), round(tam.get(">20.000", 0)) == 1),
]
mal = 0
for paso, frase, valor, ok in C:
    mal += not ok
    print(f"{'OK ' if ok else 'MAL'} {paso:8} «{frase}» -> {valor}")
print(f"\n{len(C) - mal} de {len(C)} cifras del texto cuadran con los datos.")
sys.exit(1 if mal else 0)
