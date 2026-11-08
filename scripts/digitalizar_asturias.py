"""Digitaliza la gráfica «Flujo de recepción de avisos» (avisos por semana) del informe
de actividad 2025 de Asturias (pág. 40 del PDF), para las tres series (2023, 2024, 2025).

Uso: python -I digitalizar_asturias.py <informe_2025.pdf> <salida.csv>
Método: render a 300 ppp con pdftoppm, detección de píxeles por color de cada serie,
mediana vertical en una ventana de ±6 px alrededor de cada semana. Calibración de ejes
medida a mano sobre el render (semana 10 -> x=485, semana 53 -> x=2144; 0 avisos -> y=1260,
800 avisos -> y=385). Error esperable: ±10-15 avisos por semana; las líneas discontinuas
(2023, 2024) tienen huecos y se interpolan.
"""
import subprocess, sys, tempfile, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
from PIL import Image

pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
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
