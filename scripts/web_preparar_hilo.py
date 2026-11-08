"""Hilo narrativo y zona de la ilustración «un aviso no es un censo» (web/data/).

Uso (después de scripts/web_preparar_datos.py, que deja web/data/municipios.geojson):
    python -I scripts/web_preparar_hilo.py [nidos.csv] [carpeta_web_data]

1. nido_hilo.json: un nido real de 2025 que acompaña la historia. Criterio, en este orden:
   - temporada 2025, aviso de julio a septiembre (verano), ubicación en arbolado;
   - retirado (estado «eliminado») por Basalan;
   - altura a ±1 m de la mediana de los nidos de árbol avisados en verano de 2025 y diámetro igual
     o mayor que su mediana (nido secundario típico);
   - días entre aviso y retirada iguales a la mediana de los nidos retirados en 2025;
   - en un municipio con tasa de nidos por 1.000 habitantes igual o mayor que la mediana de los
     municipios (los más rurales y arbolados), sin Bilbao.
   Entre los que cumplen todo: altura más cercana a la mediana, después diámetro más cercano a la
   mediana, después municipio con más nidos en 2025 y, por último, el primer número de actuación.
   Se publican el municipio, las fechas, la altura, el diámetro y las coordenadas redondeadas a
   3 decimales (~100 m), como en nidos.json; nunca la dirección.
2. censo_ilustracion.json: ventana de unos 4 x 4 km centrada en el nido del hilo, con los nidos
   avisados en 2025 dentro de ella (de nidos.json, ya redondeados) y CUATRO «nidos fantasma» por
   cada uno (con el avisado, cinco nidos reales por cada aviso), colocados al azar (semilla fija) a 150-900 m del avisado. Es una ilustración de la
   proporción del estudio de Lagoa y otros (2025) en un pinar de Vigo (al menos cinco nidos reales
   por cada avisado): los fantasmas NO son ubicaciones reales y la web lo dice en el propio mapa.
"""
import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from avispa_cifras_guion import base  # noqa: E402
from explorar_avispa import sin_tildes  # noqa: E402

TEMPORADA = 2025
MESES_VERANO = (7, 8, 9)
# Lagoa y otros (2025): al menos cinco nidos reales por cada avisado. El avisado es uno de esos
# cinco, así que se dibujan cuatro sin avisar por cada avisado (la misma proporción que el esquema
# anterior: 2 avisados de 10 nidos).
FANTASMAS_POR_NIDO = 4
DIST_M = (150, 900)
MEDIA_VENTANA_KM = 2.0
SEMILLA = 2025
DECIMALES = 3


def main() -> None:
    a = sys.argv[1:]
    ruta = Path(a[0]) if a else RAIZ / "data/raw/bizkaia/avispa_asiatica/nidos.csv"
    web = Path(a[1]) if len(a) > 1 else RAIZ / "web/data"
    d = base(ruta)
    geo = json.loads((web / "municipios.geojson").read_text(encoding="utf-8"))
    props = [f["properties"] for f in geo["features"]]
    corte_alto = float(np.median([p["tasa"] for p in props if p["tasa"] is not None]))
    altos = {sin_tildes(p["nombre"]).upper(): p["nombre"] for p in props
             if not p["sin_datos"] and p["tasa"] is not None and p["tasa"] >= corte_alto}
    # El registro usa los nombres en mayúsculas; se cruzan sin tildes y por cada parte de los bilingües
    def clave_muni(m):
        k = sin_tildes(str(m)).upper().strip()
        for c, nombre in altos.items():
            if k == c or k in [x.strip() for x in c.replace("-", "/").split("/")]:
                return nombre
        return None

    t = d[d.temporada.eq(TEMPORADA)].copy()
    arbol = t.ubic.astype(str).str.contains("ARBOL|ÁRBOL", case=False)
    verano_arbol = t[arbol & t.mes_alta.isin(MESES_VERANO)]
    alt_valida = verano_arbol.altura.where((verano_arbol.altura > 0) & (verano_arbol.altura <= 60))
    diam_valido = verano_arbol.diam.where((verano_arbol.diam > 0) & (verano_arbol.diam < 250))
    alt_med, diam_med = float(alt_valida.median()), float(diam_valido.median())
    elim = t[t.eliminado & t.dias.ge(0)]
    dias_med = float(elim.dias.median())

    c = verano_arbol[verano_arbol.eliminado & verano_arbol.agente.eq("BASALAN")
                     & verano_arbol.altura.sub(alt_med).abs().le(1) & verano_arbol.diam.ge(diam_med)
                     & verano_arbol.dias.eq(dias_med) & verano_arbol.lat.notna()].copy()
    c["municipio"] = c.muni.map(clave_muni)
    c = c[c.municipio.notna()]
    n_muni = t.groupby("muni").size()
    c["n_muni"] = c.muni.map(n_muni)
    c["dif_alt"] = (c.altura - alt_med).abs()
    c["dif_diam"] = (c.diam - diam_med).abs()
    c = c.sort_values(["dif_alt", "dif_diam", "n_muni", "num"], ascending=[True, True, False, True])
    if c.empty:
        raise SystemExit("Ningún nido cumple el criterio")
    h = c.iloc[0]
    hilo = {
        "criterio": ("Nido de 2025 avisado en verano (julio-septiembre), en arbolado, retirado por Basalan, "
                     "a ±1 m de la altura mediana de los nidos de árbol avisados en verano de 2025, con diámetro "
                     "igual o mayor que su mediana y los días de retirada medianos de 2025, en un municipio con "
                     "tasa de nidos por 1.000 habitantes igual o mayor que la mediana municipal (sin Bilbao). "
                     "Desempate: altura y diámetro más cercanos a la mediana, municipio con más nidos en 2025 "
                     "y número de actuación."),
        "candidatos": int(len(c)),
        "referencias": {"altura_mediana_m": alt_med, "diametro_mediano_cm": diam_med, "dias_medianos_2025": dias_med,
                        "nidos_arbol_verano_2025": int(len(verano_arbol)), "tasa_mediana_municipal": corte_alto},
        "nido": {"temporada": TEMPORADA, "municipio": h.municipio, "nidos_municipio_2025": int(h.n_muni),
                 "fecha_aviso": h.alta.date().isoformat(), "fecha_retirada": h.cierre.date().isoformat(),
                 "dias": int(h.dias), "altura_m": float(h.altura), "diametro_cm": float(h.diam),
                 "ubicacion": "arbolado", "retira": "Basalan", "mes": int(h.mes_alta),
                 "lon": round(float(h.lon), DECIMALES), "lat": round(float(h.lat), DECIMALES)},
    }
    (web / "nido_hilo.json").write_text(json.dumps(hilo, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- Ilustración del censo ---
    nj = json.loads((web / "nidos.json").read_text(encoding="utf-8"))
    p = np.array(nj["datos"], dtype=float).reshape(-1, len(nj["campos"]))
    lon0, lat0 = hilo["nido"]["lon"], hilo["nido"]["lat"]
    kx = 111.32 * np.cos(np.radians(lat0))  # km por grado de longitud
    dlon, dlat = MEDIA_VENTANA_KM / kx, MEDIA_VENTANA_KM / 110.57
    caja = [lon0 - dlon, lat0 - dlat, lon0 + dlon, lat0 + dlat]
    sel = p[(p[:, 2] == TEMPORADA) & (p[:, 0] >= caja[0]) & (p[:, 0] <= caja[2])
            & (p[:, 1] >= caja[1]) & (p[:, 1] <= caja[3])]
    rng = np.random.default_rng(SEMILLA)
    fant = []
    for lon, lat, *_ in sel:
        dist = rng.uniform(*DIST_M, FANTASMAS_POR_NIDO) / 1000
        ang = rng.uniform(0, 2 * np.pi, FANTASMAS_POR_NIDO)
        for r, g in zip(dist, ang):
            fant += [round(float(lon + r * np.cos(g) / kx), 4), round(float(lat + r * np.sin(g) / 110.57), 4)]
    censo = {"temporada": TEMPORADA, "municipio": h.municipio, "caja": [round(x, 4) for x in caja],
             "por_nido": FANTASMAS_POR_NIDO, "distancia_m": list(DIST_M), "semilla": SEMILLA,
             "avisados": [round(x, DECIMALES) for x in sel[:, :2].ravel().tolist()],
             "fantasmas": fant, "fuente_proporcion": "Lagoa y otros (2025), pinar de Vigo"}
    (web / "censo_ilustracion.json").write_text(json.dumps(censo, ensure_ascii=False), encoding="utf-8")
    print(f"Hilo: {hilo['nido']} ({len(c)} candidatos); referencias {hilo['referencias']}")
    print(f"Censo: {len(sel)} nidos avisados en {TEMPORADA} en la ventana; {len(fant) // 2} fantasmas")


if __name__ == "__main__":
    main()
