"""Correspondencia oficial municipio -> comarca de Bizkaia (Eustat), con contraste de la Diputación.

Uso:
    python -I scripts/descargar_comarcas.py [--sin-descarga]

Descarga (en data/raw/externos/comarcas/):
- eustat_municipios_cae.xlsx: Eustat, clasificación «Municipios de la C.A. de Euskadi» (códigos de
  territorio, comarca y municipio). Página: https://www.eustat.eus/estadisticas/tema_200162/opt_1/id_60/clasificaciones.html
  Fichero: https://www.eustat.eus/comun/ExtractorBlobCLADOC.ashx?id=186
- eustat_comarcas_cae.xlsx: Eustat, clasificación «Comarcas de la C.A. de Euskadi» (nombres en
  castellano y euskera). Página: https://www.eustat.eus/estadisticas/tema_200162/opt_1/id_51/clasificaciones.html
  Fichero: https://www.eustat.eus/comun/ExtractorBlobCLADOC.ashx?id=118
- dfb_udalerriak.json: Diputación Foral de Bizkaia, capa «Udalerriak / Términos municipales» del
  servicio ML_UdalMugarteak_LimitesMunicipales (geo.bizkaia.eus), atributos sin geometría. Trae un
  CodigoComarca propio (sin nombres y con otra numeración): sirve para contrastar la pertenencia.
- FUENTE.txt: URL, fecha de descarga y nombre del fichero servido.

Escribe outputs/municipio_comarca.csv: codigo_ine (5 cifras, 48xxx), municipio (nombre Eustat),
codigo_comarca_eustat, comarca_eustat (castellano), comarca_eustat_euskera, nombre_habitual.

nombre_habitual: denominación de uso corriente que se asocia a cada comarca Eustat. Solo
«Bilbo Handia», «Durangaldea» y «Arratia-Nerbioi» son nombres oficiales de Eustat (en euskera).
«Busturialdea», «Lea-Artibai», «Uribe» y «Enkarterri» son nombres de uso corriente que no tienen
una lista oficial descargable de municipios: es una etiqueta, no una delimitación comprobada
(ver avisos en la salida de consola).
"""
import argparse
import datetime as dt
import json
import sys
import unicodedata
import urllib.request
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DEST = RAIZ / "data/raw/externos/comarcas"
UA = {"User-Agent": "Mozilla/5.0 (investigacion datos abiertos)"}
FUENTES = {
    "eustat_municipios_cae.xlsx": "https://www.eustat.eus/comun/ExtractorBlobCLADOC.ashx?id=186",
    "eustat_comarcas_cae.xlsx": "https://www.eustat.eus/comun/ExtractorBlobCLADOC.ashx?id=118",
    "dfb_udalerriak.json": (
        "https://geo.bizkaia.eus/arcgisserverinspire/rest/services/Kartografia_Cartografia/"
        "ML_UdalMugarteak_LimitesMunicipales/MapServer/2/query?where=1%3D1&outFields=NombreMunicipio,"
        "CodigoProvincia,CodigoMunicipio,CodigoComarca,CodigoAreaFuncional&returnGeometry=false&f=json"),
}
# Comarca Eustat -> nombre de uso corriente (etiqueta; ver docstring)
HABITUAL = {
    "Arratia-Nervión": "Arratia-Nerbioi",
    "Gran Bilbao": "Bilbo Handia",
    "Duranguesado": "Durangaldea",
    "Encartaciones": "Enkarterri",
    "Gernika-Bermeo": "Busturialdea",
    "Markina-Ondarroa": "Lea-Artibai",
    "Plentzia-Mungia": "Uribe",
}


def clave(x: str) -> str:
    x = "".join(c for c in unicodedata.normalize("NFD", str(x).replace("ñ", "#").replace("Ñ", "#"))
                if unicodedata.category(c) != "Mn")
    return x.replace("#", "Ñ").upper().strip()


def descargar() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    hoy = dt.date.today().isoformat()
    lineas = [f"Descargado el {hoy} con scripts/descargar_comarcas.py", ""]
    for nombre, url in FUENTES.items():
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            datos, disp = r.read(), r.headers.get("Content-Disposition", "")
        (DEST / nombre).write_bytes(datos)
        lineas.append(f"{nombre}\n  {url}\n  {len(datos)} bytes; servido como: {disp or '-'}")
    lineas += ["", "Páginas de las clasificaciones de Eustat (Nomenclaturas, operación 200162):",
               "  https://www.eustat.eus/estadisticas/tema_200162/opt_1/id_60/clasificaciones.html (municipios)",
               "  https://www.eustat.eus/estadisticas/tema_200162/opt_1/id_51/clasificaciones.html (comarcas)",
               "Condiciones de reutilización: las del aviso legal de Eustat (citar la fuente)."]
    (DEST / "FUENTE.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def construir() -> pd.DataFrame:
    m = pd.read_excel(DEST / "eustat_municipios_cae.xlsx", header=None, skiprows=9, dtype=str)
    m.columns = ["prov", "cod_comarca", "cod_muni", "municipio"]
    pie = m.prov.str.contains("actualizaci", case=False, na=False)
    print("Pie del fichero de municipios:", "; ".join(m.loc[pie, "prov"].str.strip()) or "-")
    m = m.dropna(subset=["municipio"])
    m = m[m.prov.eq("48")].copy()
    c = pd.read_excel(DEST / "eustat_comarcas_cae.xlsx", dtype=str)
    c.columns = ["prov", "cod_comarca", "nombre_es", "nombre_eu", "alta", "baja"]
    c = c[c.prov.eq("48")]
    if c.baja.notna().any():
        sys.exit("Hay comarcas de Bizkaia dadas de baja: revisar")
    # «Bilbo Handia / Gran Bilbao» -> castellano = parte tras « / » si existe
    c["comarca_eustat"] = c.nombre_es.str.split(" / ").str[-1].str.strip()
    m = m.merge(c[["cod_comarca", "comarca_eustat", "nombre_eu"]], on="cod_comarca", how="left", validate="m:1")
    out = pd.DataFrame({
        "codigo_ine": "48" + m.cod_muni.str.zfill(3),
        "municipio": m.municipio.str.strip(),
        "codigo_comarca_eustat": "48" + m.cod_comarca,
        "comarca_eustat": m.comarca_eustat,
        "comarca_eustat_euskera": m.nombre_eu.str.strip(),
    })
    out["nombre_habitual"] = out.comarca_eustat.map(HABITUAL)
    out = out.sort_values("codigo_ine").reset_index(drop=True)

    # Comprobaciones
    assert len(out) == out.codigo_ine.nunique(), "códigos repetidos"
    assert out[["comarca_eustat", "nombre_habitual"]].notna().all().all(), "municipios sin comarca"
    assert out.comarca_eustat.nunique() == 7, "no salen 7 comarcas"
    assert not out.municipio.str.contains("Amurrio").any()
    print(f"Municipios de Bizkaia en Eustat: {len(out)}; comarcas: {out.comarca_eustat.nunique()}")

    # Contraste con la capa de la Diputación (pertenencia, no nombres)
    j = json.loads((DEST / "dfb_udalerriak.json").read_text(encoding="utf-8"))
    dfb = pd.DataFrame([f["attributes"] for f in j["features"]])
    dfb["codigo_ine"] = "48" + dfb.CodigoMunicipio.astype(int).astype(str).str.zfill(3)
    x = out.merge(dfb[["codigo_ine", "NombreMunicipio", "CodigoComarca"]], on="codigo_ine", how="outer", indicator=True)
    print(f"Diputación: {len(dfb)} municipios; cruce por código: {x._merge.value_counts().to_dict()}")
    t = pd.crosstab(x.comarca_eustat, x.CodigoComarca)
    biyectiva = ((t > 0).sum(axis=1) == 1).all() and ((t > 0).sum(axis=0) == 1).all()
    print("Pertenencia Eustat = Diputación (cada comarca Eustat cae entera en un solo código DFB):", biyectiva)
    nom = x[x._merge.eq("both") & (x.municipio.map(clave) != x.NombreMunicipio.map(clave))]
    print(f"Nombres distintos entre Eustat y Diputación (mismo código): {len(nom)}",
          "; ".join(f"{a} / {b.strip()}" for a, b in zip(nom.municipio, nom.NombreMunicipio)))
    print("Municipios por comarca:", out.comarca_eustat.value_counts().sort_index().to_dict())
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-descarga", action="store_true", help="reutiliza los brutos ya descargados")
    a = ap.parse_args()
    if not a.sin_descarga:
        descargar()
    out = construir()
    (RAIZ / "outputs").mkdir(exist_ok=True)
    out.to_csv(RAIZ / "outputs/municipio_comarca.csv", index=False)
    print("Escrito outputs/municipio_comarca.csv")
    print("Aviso: «Busturialdea», «Lea-Artibai», «Uribe» y «Enkarterri» son etiquetas de uso corriente sin lista"
          " oficial descargable de municipios; no se ha podido comprobar municipio a municipio que coincidan con la"
          " comarca Eustat. En la web conviene usar el nombre Eustat o «Busturialdea (Gernika-Bermeo)».")


if __name__ == "__main__":
    main()
