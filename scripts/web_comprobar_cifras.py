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
coste = [c["min"] for c in gas["coste_nido"].values()]
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
    ("Paso 11", "en 2018 salen unos 70 euros por nido", coste, len(coste) == 1 and round(coste[0], -1) == 70),
    ("Paso 11", "encargo de más de 2 millones", [min(encargo), max(encargo)], min(encargo) > 2e6),
    ("Paso 12", "unos 16 nidos por 1.000 en los de menos de 2.000", tam.get("<2.000"), round(tam.get("<2.000", 0)) == 16),
    ("Paso 12", "uno en los de más de 20.000", tam.get(">20.000"), round(tam.get(">20.000", 0)) == 1),
]
# --- Guion v2: apertura, revelación, comarcas y nido hilo ---
ap, com, hil = J("apertura.json"), J("comarcas.geojson"), J("nido_hilo.json")
av = dict(zip(ap["temporadas"], ap["avisos"]))
prim = {r["temporada"]: r["municipio"] for r in ap["primero_por_temporada"]}
mas = {r["municipio"]: r["n"] for r in ap["mas_avisos_periodo"]}
ast, comun = dict(zip(ind["temporadas"], ind["avisos_asiatica"])), dict(zip(ind["temporadas"], ind["avisos_comun"]))
crece = lambda d_: (d_[d1] / d_[d0] - 1)  # noqa: E731
cp = {f["properties"]["nombre"]: f["properties"] for f in com["features"]}
ref = com["bizkaia_sin_bilbao"]
nh = hil["nido"]
C += [
    ("Apert. 1", "15 de septiembre de 2025, Morga, árbol, 7 m, retirado 2 días después por Basalan",
     [nh["fecha_aviso"], nh["municipio"], nh["altura_m"], nh["dias"], nh["retira"]],
     nh["fecha_aviso"] == "2025-09-15" and nh["municipio"] == "Morga" and nh["altura_m"] == 7 and nh["dias"] == 2
     and nh["retira"] == "Basalan" and nh["ubicacion"] == "arbolado"),
    ("Apert. 2", "1.990 nidos en 2019", av[2019], av[2019] == 1990),
    ("Apert. 2", "109 de los 113 municipios en 2019", [ap["municipios_con_avisos"][0], ap["municipios_total"]],
     ap["municipios_con_avisos"][0] == 109 and ap["municipios_total"] == 113),
    ("Apert. 3", "2.599 en 2020, 2.138 en 2021, 2.469 en 2022", [av[2020], av[2021], av[2022]],
     [av[2020], av[2021], av[2022]] == [2599, 2138, 2469]),
    ("Apert. 4", "Mungia, primero casi todos los años (todas salvo 2020)", prim,
     all(v == "Mungia" for k, v in prim.items() if k != 2020) and prim[2020] != "Mungia"),
    ("Apert. 4", "Mungia 871 en 2019-2025; le siguen Getxo y Galdakao", list(mas.items())[:3],
     list(mas)[:3] == ["Mungia", "Getxo", "Galdakao"] and mas["Mungia"] == 871),
    ("Apert. 4", "Getxo 646 y Galdakao 607 (comprobación)", [mas.get("Getxo"), mas.get("Galdakao")],
     mas.get("Getxo") == 646 and mas.get("Galdakao") == 607),
    ("Apert. 5", "3.222 avisos en 2025, el máximo desde 2019", av[2025], av[2025] == 3222 and av[2025] == max(av.values())),
    ("Apert. 6", "más de 18.000 nidos (suma de la apertura)", sum(av.values()), 18000 < sum(av.values()) < 19000
     and sum(av.values()) == ind["total_periodo"]),
    ("Revel.", "asiática +62 % (1.990 -> 3.222)", round(crece(ast), 4), round(100 * crece(ast)) == 62),
    ("Revel.", "común +117 % (127 -> 276), «todavía más»", [comun[d0], comun[d1], round(crece(comun), 4)],
     comun[d0] == 127 and comun[d1] == 276 and round(100 * crece(comun)) == 117 and crece(comun) > crece(ast)),
    ("Revel.", "tendencia log-lineal creciente (IC 95 % sobre cero)", ind["tendencia"]["crecimiento_ic95"],
     ind["tendencia"]["crecimiento_ic95"][0] > 0),
    ("Calend.", "septiembre cae en «verano» (julio-septiembre) y el hilo se avisó en septiembre", nh["mes"], nh["mes"] in (7, 8, 9)),
    ("Comarc.", "Gran Bilbao y Plentzia-Mungia, las más densas por km²",
     sorted(cp, key=lambda k: -cp[k]["por_km2"])[:2], sorted(cp, key=lambda k: -cp[k]["por_km2"])[:2] == ["Gran Bilbao", "Plentzia-Mungia"]),
    ("Comarc.", "Gran Bilbao casi tres veces más por km² que el resto", cp["Gran Bilbao"]["rr_km2"], 2.5 <= cp["Gran Bilbao"]["rr_km2"] < 3),
    ("Comarc.", "Arratia-Nervión unos 9 por 1.000; Gran Bilbao menos de 2",
     [cp["Arratia-Nervión"]["por_1000hab"], cp["Gran Bilbao"]["por_1000hab"]],
     round(cp["Arratia-Nervión"]["por_1000hab"]) == 9 and cp["Gran Bilbao"]["por_1000hab"] < 2
     and max(cp, key=lambda k: cp[k]["por_1000hab"]) == "Arratia-Nervión"),
    ("Comarc.", "después del 1/11: Markina-Ondarroa 30 %, Encartaciones 27 %, media 20 %",
     [cp["Markina-Ondarroa"]["tras_1nov"], cp["Encartaciones"]["tras_1nov"], ref["tras_1nov"]],
     round(100 * cp["Markina-Ondarroa"]["tras_1nov"]) == 30 and round(100 * cp["Encartaciones"]["tras_1nov"]) == 27
     and round(100 * ref["tras_1nov"]) == 20),
    ("Cierre", "3.222 avisos en 2025, más que ningún año desde 2019", av[2025], av[2025] == max(av.values())),
]

mal = 0
for paso, frase, valor, ok in C:
    mal += not ok
    print(f"{'OK ' if ok else 'MAL'} {paso:8} «{frase}» -> {valor}")
print(f"\n{len(C) - mal} de {len(C)} cifras del texto cuadran con los datos.")
sys.exit(1 if mal else 0)
