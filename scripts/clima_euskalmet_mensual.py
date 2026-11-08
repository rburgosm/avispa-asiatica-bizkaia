"""Serie mensual de temperatura de estaciones de Euskalmet (Open Data Euskadi), para cruzar con los nidos.

Uso:
    python -I scripts/clima_euskalmet_mensual.py <carpeta_con_AAAA.zip> <salida.csv> <estación> [<estación> ...]

Fuente: «Estaciones meteorológicas: lecturas recogidas en AAAA» (Open Data Euskadi), un zip por año
(~140 MB) con un zip por estación y un XML por mes con lecturas cada 10 minutos:
https://opendata.euskadi.eus/contenidos/ds_meteorologicos/met_stations_ds_AAAA/opendata/AAAA.zip
Estaciones: https://opendata.euskadi.eus/contenidos/ds_meteorologicos/estaciones_meteorologicas/opendata/estaciones.geojson

Calcula, por estación y día, la media, mínima y máxima de la temperatura del aire (sensor «Tem.Aire»; se toma
el primero si hay varios) con al menos 120 de 144 lecturas, y luego por mes: media de las medias diarias,
nº de días válidos, nº de días con media < 10 °C y < 12 °C. Añade, por estación y año, la primera fecha
del otoño (desde el 1/9) con tres días seguidos de media < 10 °C (criterio aproximado de Bruxelles
Environnement para el fin de la actividad).
"""
import io
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd


def lecturas_mes(xml_bytes):
    filas = []
    root = ET.fromstring(xml_bytes)
    for dia in root.iter("dia"):
        f = dia.get("Dia")
        for hora in dia.iter("hora"):
            met = hora.find("Meteoros")
            if met is None:
                continue
            for c in met:
                if c.tag.startswith("Tem.Aire"):
                    try:
                        filas.append((f, float(c.text)))
                    except (TypeError, ValueError):
                        pass
                    break
    return filas


def estacion_anio(zip_anio, est, anio):
    with zipfile.ZipFile(zip_anio) as z:
        nombre = f"{anio}/{est}_{anio}.zip"
        if nombre not in z.namelist():
            return []
        with zipfile.ZipFile(io.BytesIO(z.read(nombre))) as ze:
            filas = []
            for n in ze.namelist():
                if n.endswith(".xml"):
                    filas += lecturas_mes(ze.read(n))
    return filas


def main():
    carpeta, salida, estaciones = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
    diarios = []
    for zp in sorted(carpeta.glob("[12][0-9][0-9][0-9].zip")):
        anio = int(zp.stem)
        for est in estaciones:
            f = estacion_anio(zp, est, anio)
            if not f:
                print(f"{est} {anio}: sin datos")
                continue
            d = pd.DataFrame(f, columns=["dia", "t"])
            d = d[d.t.between(-30, 50)]
            d["dia"] = pd.to_datetime(d.dia, format="%Y-%m-%d", errors="coerce")
            g = d.groupby("dia").t.agg(["mean", "min", "max", "count"]).reset_index()
            g["estacion"] = est
            diarios.append(g)
            print(f"{est} {anio}: {len(g)} días, {int(g['count'].sum())} lecturas")
    dd = pd.concat(diarios)
    dd = dd[dd["count"] >= 120]
    dd["anio"], dd["mes"] = dd.dia.dt.year, dd.dia.dt.month
    m = dd.groupby(["estacion", "anio", "mes"]).agg(
        t_media=("mean", "mean"), t_min_media=("min", "mean"), t_max_media=("max", "mean"),
        dias_validos=("mean", "size"), dias_media_lt10=("mean", lambda s: int((s < 10).sum())),
        dias_media_lt12=("mean", lambda s: int((s < 12).sum()))).reset_index().round(2)
    m.to_csv(salida, index=False)
    dd.to_csv(salida.with_name(salida.stem + "_diario.csv"), index=False)
    # Primer episodio otoñal de 3 días seguidos con media < 10 °C
    filas = []
    for (est, anio), g in dd[dd.mes >= 9].groupby(["estacion", "anio"]):
        g = g.set_index("dia").asfreq("D")
        frio = (g["mean"] < 10).astype(int)
        racha = frio.rolling(3).sum()
        hit = racha[racha >= 3]
        filas.append({"estacion": est, "anio": anio,
                      "primer_3dias_lt10": hit.index[0].date() - pd.Timedelta(days=2) if len(hit) else None,
                      "t_media_oct": round(g.loc[g.index.month == 10, "mean"].mean(), 2),
                      "t_media_nov": round(g.loc[g.index.month == 11, "mean"].mean(), 2)})
    o = pd.DataFrame(filas)
    o.to_csv(salida.with_name(salida.stem + "_otono.csv"), index=False)
    print(o.to_string(index=False))


if __name__ == "__main__":
    main()
