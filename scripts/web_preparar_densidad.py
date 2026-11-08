"""Superficie continua de densidad de nidos (isobandas) y rótulos del mapa (web/data/).

Uso (después de scripts/web_preparar_datos.py):
    python -I scripts/web_preparar_densidad.py [carpeta_web_data]

1. densidad.geojson: densidad de nidos avisados por km² y año, como superficie suave por bandas
   (estilo de los mapas de temperatura del Washington Post). Método estándar de estimación de
   densidad por núcleos sobre una rejilla («binned KDE»): se cuentan los nidos de nidos.json en
   celdas de CELDA_M metros (EPSG:25830) y se suaviza con un núcleo gaussiano de desviación
   NUCLEO_M metros (scipy.ndimage.gaussian_filter, que conserva la suma). Las bandas se trazan con
   matplotlib.contourf con los mismos cortes para todas las capas y se recortan a Bizkaia sin Bilbao
   (sin datos: servicio municipal propio). Capas: cada temporada 2019-2025 y la media anual
   2019-2025 («media»).
2. contorno.geojson: contorno de Bizkaia (unión de los municipios, simplificado a 40 m).
3. comarcas.geojson: las 7 comarcas de Eustat sin Bilbao, con nidos por km² y año, por 1.000
   habitantes y % retirado después del 1 de noviembre (outputs/avispa_comarcas_resumen.csv).
4. lugares.geojson: los nombres de las 7 comarcas de Eustat (outputs/municipio_comarca.csv, de
   scripts/descargar_comarcas.py) en el polo de inaccesibilidad de cada comarca, y las cabeceras de comarca
   y otras localidades de referencia (centro del municipio) para rotular el mapa.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402
from shapely.geometry import Polygon, mapping  # noqa: E402
from shapely.ops import polylabel, unary_union  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CRS = "EPSG:25830"
CELDA_M = 250
NUCLEO_M = 1500
TEMPORADAS = list(range(2019, 2026))
# Cortes de las bandas, en nidos por km² y año (la rampa ámbar tiene 5 tonos; la primera banda
# empieza en 0,5 para que el fondo casi vacío no se pinte)
CORTES = [0.5, 1, 2, 3.5, 5.5, 1000]
SIMPLIFICAR_M = 90
SIN_DATOS = "Bilbao"
CABECERAS = ["Bilbao", "Getxo", "Barakaldo", "Durango", "Gernika-Lumo", "Bermeo", "Mungia", "Balmaseda",
             "Lekeitio", "Markina-Xemein", "Igorre"]


def bandas(z, x, y, recorte):
    cs = plt.contourf(x, y, z, levels=CORTES)
    capas = []
    for k, segs in enumerate(cs.allsegs):
        polis = []
        for kinds, seg in zip(cs.allkinds[k], segs):
            # cada «seg» puede tener varios anillos (exterior y agujeros): se separan por los códigos
            anillos, actual = [], []
            for punto, cod in zip(seg, kinds if kinds is not None else [None] * len(seg)):
                if cod == 1 and actual:
                    anillos.append(actual)
                    actual = []
                actual.append(punto)
            if actual:
                anillos.append(actual)
            anillos = [a for a in anillos if len(a) >= 4]
            if not anillos:
                continue
            ext = Polygon(anillos[0])
            agujeros = [Polygon(a) for a in anillos[1:]]
            p = ext.buffer(0)
            for a in agujeros:
                p = p.difference(a.buffer(0))
            polis.append(p)
        g = unary_union(polis).intersection(recorte).simplify(SIMPLIFICAR_M) if polis else None
        capas.append(g)
    plt.close("all")
    return capas


def main() -> None:
    web = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "web/data"
    m = gpd.read_file(web / "municipios.geojson").to_crs(CRS)
    bizkaia = unary_union(m.geometry)
    recorte = bizkaia.difference(unary_union(m[m.nombre.eq(SIN_DATOS)].geometry))
    x0, y0, x1, y1 = bizkaia.bounds
    x0, y0, x1, y1 = x0 - 3000, y0 - 3000, x1 + 3000, y1 + 3000
    xs = np.arange(x0, x1 + CELDA_M, CELDA_M)
    ys = np.arange(y0, y1 + CELDA_M, CELDA_M)
    nj = json.loads((web / "nidos.json").read_text(encoding="utf-8"))
    d = pd.DataFrame(np.array(nj["datos"]).reshape(-1, len(nj["campos"])), columns=nj["campos"])
    d = d[d.temporada.isin(TEMPORADAS)]
    pts = gpd.GeoSeries(gpd.points_from_xy(d.lon, d.lat), crs="EPSG:4326").to_crs(CRS)
    d["x"], d["y"] = pts.x.values, pts.y.values
    km2 = (CELDA_M / 1000) ** 2

    def superficie(sub, anios):
        h, _, _ = np.histogram2d(sub.y, sub.x, bins=[ys, xs])
        return gaussian_filter(h, NUCLEO_M / CELDA_M, mode="constant") / km2 / anios

    xc, yc = (xs[:-1] + xs[1:]) / 2, (ys[:-1] + ys[1:]) / 2
    feats, resumen = [], []
    capas = [("media", d, len(TEMPORADAS))] + [(t, d[d.temporada.eq(t)], 1) for t in TEMPORADAS]
    for clave, sub, anios in capas:
        z = superficie(sub, anios)
        resumen.append(f"{clave}: {len(sub)} nidos, máximo {z.max():.1f} nidos/km²/año")
        for k, g in enumerate(bandas(z, xc, yc, recorte)):
            if g is None or g.is_empty:
                continue
            gg = gpd.GeoSeries([g], crs=CRS).to_crs("EPSG:4326").iloc[0]
            geo = json.loads(json.dumps(mapping(gg)))

            def r(c):
                return [round(c[0], 3), round(c[1], 3)] if isinstance(c[0], (int, float)) else [r(v) for v in c]
            geo["coordinates"] = r(geo["coordinates"])
            feats.append({"type": "Feature", "properties": {"capa": str(clave), "banda": k,
                                                            "desde": CORTES[k], "hasta": CORTES[k + 1]},
                          "geometry": geo})
    out = {"type": "FeatureCollection", "cortes": CORTES[:-1], "unidad": "nidos por km² y año",
           "nucleo_m": NUCLEO_M, "celda_m": CELDA_M, "temporadas": TEMPORADAS, "features": feats}
    (web / "densidad.geojson").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # --- Rótulos: comarcas y cabeceras ---
    cc = pd.read_csv(RAIZ / "outputs/municipio_comarca.csv")
    m["cod_ine"] = 48000 + m.cod.astype(int)
    mc = m.merge(cc[["codigo_ine", "comarca_eustat"]], left_on="cod_ine", right_on="codigo_ine", how="left")
    if mc.comarca_eustat.isna().any():
        raise SystemExit(f"Municipios sin comarca: {mc[mc.comarca_eustat.isna()].nombre.tolist()}")
    lugares = []
    for nombre, g in mc.dissolve(by="comarca_eustat").iterrows():
        # polo de inaccesibilidad (el punto interior más alejado del borde): rótulo bien centrado
        geom = max(g.geometry.geoms, key=lambda x: x.area) if g.geometry.geom_type == "MultiPolygon" else g.geometry
        p = gpd.GeoSeries([polylabel(geom, tolerance=50)], crs=CRS).to_crs("EPSG:4326").iloc[0]
        lugares.append({"type": "Feature", "properties": {"tipo": "comarca", "nombre": nombre},
                        "geometry": {"type": "Point", "coordinates": [round(p.x, 4), round(p.y, 4)]}})
    # Comarcas (sin Bilbao, que no está en el registro) con las cifras de outputs/avispa_comarcas_resumen.csv
    res = pd.read_csv(RAIZ / "outputs/avispa_comarcas_resumen.csv").set_index("comarca")
    cg = mc[~mc.nombre.eq(SIN_DATOS)].dissolve(by="comarca_eustat").reset_index()
    cg["geometry"] = cg.geometry.simplify(SIMPLIFICAR_M)
    cg = cg.to_crs("EPSG:4326")
    cfeats = []
    for _, r_ in cg.iterrows():
        x = res.loc[r_.comarca_eustat]
        geo = json.loads(json.dumps(mapping(r_.geometry)))
        geo["coordinates"] = json.loads(json.dumps(geo["coordinates"]), parse_float=lambda v: round(float(v), 4))
        cfeats.append({"type": "Feature", "geometry": geo, "properties": {
            "nombre": r_.comarca_eustat, "municipios": int(x.municipios), "km2": float(x.superficie_km2),
            "por_km2": round(float(x.nidos_1000km2_anual) / 1000, 3), "por_1000hab": round(float(x.nidos_1000hab_anual), 3),
            "tras_1nov": round(float(x.pct_tras_1nov), 4), "rr_km2": round(float(x.rr_km2), 3), "rr_hab": round(float(x.rr_hab), 3)}})
    ref = res.loc["Bizkaia sin Bilbao"]
    (web / "comarcas.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": cfeats,
        "bizkaia_sin_bilbao": {"por_km2": round(float(ref.nidos_1000km2_anual) / 1000, 3),
                               "por_1000hab": round(float(ref.nidos_1000hab_anual), 3), "tras_1nov": round(float(ref.pct_tras_1nov), 4)},
        "fuente": "outputs/avispa_comarcas_resumen.csv (scripts/avispa_comarcas.py), comarcas de Eustat"},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    faltan = [c for c in CABECERAS if c not in set(m.nombre)]
    if faltan:
        raise SystemExit(f"Cabeceras sin municipio: {faltan}")
    for _, r_ in m[m.nombre.isin(CABECERAS)].iterrows():
        p = gpd.GeoSeries([r_.geometry.representative_point()], crs=CRS).to_crs("EPSG:4326").iloc[0]
        lugares.append({"type": "Feature", "properties": {"tipo": "cabecera", "nombre": r_.nombre},
                        "geometry": {"type": "Point", "coordinates": [round(p.x, 4), round(p.y, 4)]}})
    (web / "lugares.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": lugares},
                                                    ensure_ascii=False), encoding="utf-8")
    # Contorno de Bizkaia (unión de los municipios), para el trazo exterior de los mapas
    cont = gpd.GeoSeries([bizkaia.simplify(40)], crs=CRS).to_crs("EPSG:4326").iloc[0]
    gc = json.loads(json.dumps(mapping(cont)))
    gc["coordinates"] = json.loads(json.dumps(gc["coordinates"]), parse_float=lambda v: round(float(v), 5))
    (web / "contorno.geojson").write_text(json.dumps({"type": "Feature", "properties": {"nombre": "Bizkaia"},
                                                      "geometry": gc}, separators=(",", ":")), encoding="utf-8")
    print("\n".join(resumen))
    print(f"densidad.geojson: {len(feats)} bandas, {(web / 'densidad.geojson').stat().st_size / 1024:.0f} KB; "
          f"lugares: {len(lugares)}")


if __name__ == "__main__":
    main()
