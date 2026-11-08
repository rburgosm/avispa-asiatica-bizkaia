"""Digitaliza la gráfica «Flujo de recepción de avisos» (avisos por semana) del informe
de actividad 2025 de Asturias (pág. 40 del PDF), para las tres series (2023, 2024, 2025).

Uso: python -I digitalizar_asturias.py <informe_2025.pdf> <salida.csv> [salida_mensual.csv]
Método: render a 300 ppp con pdftoppm, detección de píxeles por color de cada serie,
mediana vertical en una ventana de ±6 px alrededor de cada semana. Calibración de ejes
medida a mano sobre el render (semana 10 -> x=485, semana 53 -> x=2144; 0 avisos -> y=1260,
800 avisos -> y=385). Error esperable: ±10-15 avisos por semana; las líneas discontinuas
(2023, 2024) tienen huecos y se interpolan.

Salida mensual (por defecto, asturias_avisos_mensual.csv junto a <salida.csv>), para comparar el
calendario de avisos con el de Bizkaia en la web (paso «La primavera, casi sin avisos»):
- los avisos de cada semana ISO se reparten a partes iguales entre sus 7 días (de lunes a
  domingo) y se suman por mes; así un mes no pesa más por tener 5 jueves en lugar de 4 (con la
  semana entera en el mes de su jueves, septiembre salía con un hueco artificial). La gráfica
  llega a la semana 53 también en los años con 52 semanas ISO: sus días, y cualquier día que
  caiga fuera del año, cuentan en el 31 de diciembre. La gráfica empieza en la semana 10, así que
  no hay enero ni febrero y marzo está incompleto: marzo se deja en el CSV, pero fuera del reparto;
- reparto = avisos del mes / avisos de abril a diciembre, la misma ventana que se usa en Bizkaia
  (web/data/mensual.json: avisos de 2019-2025, de abril a diciembre);
- filas por año (2023, 2024, 2025) y «2023-2025» (suma de los tres años, igual que Bizkaia suma
  sus temporadas: pesa más el año con más avisos).
Son avisos de nidos, como en Bizkaia, pero de otra región y otro sistema de recogida, leídos de
una gráfica (±10-15 avisos por semana): solo sirven para comparar la forma del calendario.
"""
import subprocess, sys, tempfile, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
from PIL import Image

pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
out_mes = Path(sys.argv[3]) if len(sys.argv) > 3 else out.with_name("asturias_avisos_mensual.csv")
with tempfile.TemporaryDirectory() as d:
    subprocess.run(["pdftoppm", "-f", "40", "-l", "40", "-r", "300", "-png", str(pdf), f"{d}/p"], check=True)
    im = np.asarray(Image.open(next(Path(d).glob("p*.png"))).convert("RGB")).astype(int)
X10, X53, Y0, Y800 = 485, 2144, 1260, 385
R, G, B = im[..., 0], im[..., 1], im[..., 2]
masks = {
    2025: (G > 110) & (R < 150) & (B < 90) & (G - R > 30),          # verde
    2024: (B > 140) & (R > 90) & (R < 170) & (G < 120) & (B - G > 50),  # morado
    2023: (R > 200) & (G > 120) & (G < 185) & (B > 120) & (B < 190) & (R - G > 40),  # rosa
}
rows = []
for w in range(10, 54):
    x = round(X10 + (w - 10) * (X53 - X10) / 43)
    for anio, m in masks.items():
        sub = m[Y800 - 60:Y0 + 10, x - 6:x + 7]
        ys = np.nonzero(sub)[0]
        val = np.nan if len(ys) == 0 else (Y0 - (np.median(ys) + Y800 - 60)) * 800 / (Y0 - Y800)
        rows.append({"anio": anio, "semana": w, "avisos": val})
df = pd.DataFrame(rows).sort_values(["anio", "semana"])
df["avisos"] = df.groupby("anio")["avisos"].transform(lambda s: s.interpolate(limit_direction="both")).clip(lower=0).round()
# Mes de cada semana ISO: el del jueves de esa semana
df["mes"] = [dt.date.fromisocalendar(int(a), int(min(w, 52 if a != 2020 else 53)), 4).month for a, w in zip(df.anio, df.semana)]
df.to_csv(out, index=False)
print(df.groupby("anio").avisos.sum())
print(df.pivot_table(index="anio", columns="mes", values="avisos", aggfunc="sum"))

# --- Salida mensual: avisos por mes y reparto sobre abril-diciembre (marzo, incompleto, fuera) ---
dias = []
for a, w, v in zip(df.anio, df.semana, df.avisos):
    lunes = dt.date.fromisocalendar(int(a), min(int(w), 52), 1) + dt.timedelta(weeks=max(0, int(w) - 52))
    for k in range(7):
        dia = min(max(lunes + dt.timedelta(days=k), dt.date(int(a), 1, 1)), dt.date(int(a), 12, 31))
        dias.append({"anio": int(a), "mes": dia.month, "avisos": v / 7})
mes = pd.DataFrame(dias).groupby(["anio", "mes"]).agg(avisos=("avisos", "sum"), dias=("avisos", "size")).reset_index()
tot = mes.groupby("mes").agg(avisos=("avisos", "sum"), dias=("dias", "sum")).reset_index()
tot.insert(0, "anio", "2023-2025")
mes = pd.concat([mes.astype({"anio": str}), tot], ignore_index=True)
abr_dic = mes.mes.between(4, 12)
mes["avisos"] = mes.avisos.round(1)
mes["proporcion_abr_dic"] = (mes.avisos / mes[abr_dic].groupby("anio").avisos.transform("sum")).where(abr_dic).round(6)
mes.to_csv(out_mes, index=False)
print(mes.pivot(index="anio", columns="mes", values="proporcion_abr_dic").round(3))
