"""Medios y gasto público en el control de la avispa asiática en Bizkaia según Open Data Bizkaia.

Uso:
    python -I scripts/avispa_gasto.py [raiz_bizkaia] [carpeta_salida]
    (por defecto data/raw/bizkaia y outputs)

Para qué: saber cuánto dinero público se puede atribuir, con los datos abiertos, al control de la
avispa asiática cada año, y cruzarlo con los nidos por temporada.

Conjuntos de Open Data Bizkaia que lee (un subdirectorio por conjunto, bajados con
descargar_bizkaia.py): contratos-menores, contratos-no-menores, encomiendas-gestion, convenios,
subvenciones-otorgadas, subvenciones, plan-anual-contratacion, plan-anual-contratacion-basalan,
presupuestos-completos, liquidacion-presupuestos, modificaciones-presupuestos,
ejecucion-presupuestos, avispa_asiatica/nidos.csv y speis/intervenciones-speis-2023-2026.csv.

Método:
1. Búsqueda amplia con una expresión regular (castellano y euskera: velutina, avispa, nido,
   trampa, apicultura, abeja, colmena, insecto, plaga, invasora, exótica, biocida, pértiga,
   dron...) sobre todas las columnas de texto de cada fichero, con los textos en doble UTF-8
   arreglados y normalizados (mayúsculas, sin tildes).
2. Los ficheros trimestrales y mensuales son acumulados dentro del año: cada registro se
   identifica (ejercicio + expediente o beneficiario + programa) y se guarda el del último mes.
3. Cada candidato se clasifica con reglas explícitas (lista REGLAS, revisada a mano) en
   incluido / dudoso / contexto / excluido, con el motivo. Todos los candidatos van a
   avispa_gasto_candidatos.csv; los incluidos, a avispa_gasto_registros.csv.
4. Resumen anual por tipo de gasto, sin sumar importes de naturaleza distinta, y coste por nido
   donde el dato lo permite.

Salidas: avispa_gasto_candidatos.csv, avispa_gasto_registros.csv, avispa_gasto_anual.csv,
avispa_gasto_coste_nido.csv (coste por nido de cada línea con meses; lo usa la web) y avispa_gasto.txt.
"""
import io
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from avispa_llegamos_tarde import preparar  # noqa: E402

MESES = {m: i + 1 for i, m in enumerate(
    "ENERO FEBRERO MARZO ABRIL MAYO JUNIO JULIO AGOSTO SEPTIEMBRE OCTUBRE NOVIEMBRE DICIEMBRE".split())}
# Nidos de avispa asiática sin anuladas por temporada (avispa_estabilizacion.txt); se recalculan y comprueban.
NIDOS_REF = {2018: 4067, 2019: 2026, 2020: 2632, 2021: 2181, 2022: 2537, 2023: 3016, 2024: 2870, 2025: 3222}

PAT = re.compile(
    r"VELUT|VESPA|AVISP|LIZTOR|\bNIDOS?\b|HABIA|TRAMP|APICUL|ERLEZAIN|ERLAUNTZ|ABEJA|\bERLE|COLMEN|"
    r"INSECT|INTSEKT|PLAGA|IZURRI|INVASOR|INBADITZ|EXOTIC|EXOTIK|BIOCID|FUMIG|DESINSECT|PERTIG|\bDRON|"
    r"HIMENOP|HYMENOP|POLINIZ|\bMIEL\b|\bEZTI|TRAJES? DE PROTECCION AB")
# columnas que no se usan en la búsqueda (texto legal, identificadores, euskera duplicado)
SKIPCOL = re.compile(r"^_id$|NORMATIVA|BOB|NIF|DNI|_EU$|_EUS$|URL|ENLACE", re.I)
COL_NOMBRE = re.compile(r"ADJUDICATARIA|BENEFICIARI|^ENTIDAD$", re.I)

# tipo de gasto -> (naturaleza, ¿es gasto de control de la avispa?)
TIPOS = {
    "retirada_nidos_basalan": "Encomienda a Basalan: línea propia de retirada de nidos",
    "retirada_nidos_basalan_mixta": "Encomienda a Basalan: línea que mezcla avispa con otros trabajos",
    "material_retirada_nidos": "Material para la retirada de nidos (contrato menor)",
    "equipos_proteccion_bomberos": "Trajes de protección contra abejas y avispas del SPEIS",
    "ayudas_apicultura": "Ayudas a la apicultura (no mencionan la avispa)",
    "otros_pagos_apicultores": "Otros pagos a asociaciones o apicultores (seguros, razas, suministros)",
}
CONTROL = ["retirada_nidos_basalan", "material_retirada_nidos", "equipos_proteccion_bomberos"]

# Reglas de clasificación, en orden; la primera que casa decide. (conjuntos o None, regex sobre el
# texto normalizado, decisión, tipo, motivo). Revisadas a mano sobre la lista completa de candidatos.
REGLAS = [
    ({"encomiendas-gestion"}, r"AVISP|VELUT|VESPA", r"TRAB(AJOS)? EXTRAORD|SERVICIOS PARQUES",
     "incluido", "retirada_nidos_basalan_mixta",
     "La línea nombra la avispa velutina pero la mezcla con trabajos extraordinarios o de parques: no aislable"),
    ({"encomiendas-gestion"}, r"AVISP|VELUT|VESPA", None, "incluido", "retirada_nidos_basalan",
     "Línea de la encomienda a Basalan (Patrimonio Natural) que nombra la retirada de nidos de avispa asiática"),
    ({"contratos-menores"}, r"ACTUACIONES VESPA", None, "incluido", "material_retirada_nidos",
     "Suministro de materiales a Basalan para actuaciones contra Vespa velutina"),
    ({"contratos-menores", "contratos-no-menores"},
     r"TRAJES? (PARA )?VESPA|TRAJES ABEJAS|TRAJES DE PROTECCION (DE |PARA )?AB", None,
     "incluido", "equipos_proteccion_bomberos",
     "Trajes de protección contra abejas y avispas para el SPEIS (en 2023 el texto viene cortado: «TRAJES DE "
     "PROTECCIÓN AB…», mismo proveedor y contrato de vestuario que 2021, 2024 y 2025)"),
    ({"subvenciones"}, r"APICUL|ERLEZAIN|APICULTORES|BEMEPE", None, "excluido", "",
     "Misma ayuda que en subvenciones-otorgadas (aquí, importe concedido): no se suma para no duplicar"),
    ({"subvenciones-otorgadas"}, r"\| AYUDAS (A LA|'MINIMIS ') APICULTURA", None, "incluido", "ayudas_apicultura",
     "Programa de ayudas a la apicultura del Servicio de Ganadería; el texto no menciona la avispa"),
    (None, r"ASOCIACION DE APICULTORES|ERLEZAIN ELKARTEA|BEMEPE BASKONIAR", None, "incluido",
     "otros_pagos_apicultores",
     "Pago a una asociación apícola por otro programa o contrato de objeto genérico; no consta relación con la avispa"),
    (None, r"ESPECIES INVASORAS", None, "contexto", "",
     "Encargo a Basalan de especies invasoras en Urdaibai (crédito 2026); no consta que incluya la velutina"),
    (None, r"DRONE BY DRONE", None, "dudoso", "",
     "Drones y servicios de dron sin objeto detallado ni departamento; no consta uso contra la avispa"),
    (None, r"IDENTIFICACION DE INSECTOS", None, "dudoso", "",
     "Análisis e identificación de insectos (Neiker, 2017): objeto genérico, no consta relación con la avispa"),
    (None, r"TRAMPAS CAPTURA VISON", None, "excluido", "", "Trampas para visón americano (otra especie)"),
    (None, r"CONIFERA EXOTICA", None, "excluido", "", "Transformación de coníferas exóticas (trabajo forestal)"),
    (None, r"INSECTICIDAS|LIMPIEZA E INSEC|LIMPIEZA INSECT", None, "excluido", "", "Productos de limpieza e insecticidas para edificios"),
    (None, r"DESRATIZ|DESINSECT|LEGIONEL|TRATAMIENTO (DE )?PLAGAS|CONTROL, PREVENCION Y TRATAMIENTO|PREVENCION Y TRATAMIENTO DE PLAGAS",
     None, "excluido", "", "Control de plagas en edificios (desratización, desinsectación, legionela)"),
    (None, r"LIFE INVASORAS", None, "excluido", "",
     "Transferencia de 2016 a la Fundación EDE para un proyecto LIFE de especies invasoras: anterior al periodo y sin "
     "mención de la velutina"),
    (None, r"ERLETXE", None, "excluido", "", "Topónimo (Erletxe)"),
    (None, r"JOXE MIEL|MIEL BARANDIARAN", None, "excluido", "", "Nombre propio (residencia Joxe Miel Barandiaran)"),
    (None, r"CANIDOS", None, "excluido", "", "Peritaje de daños de cánidos al ganado"),
]


# ----------------------------------------------------------------------------- lectura
def leer(path: Path) -> pd.DataFrame:
    """CSV de ODB como texto; arregla el doble UTF-8 y deja el nombre de columna en castellano."""
    t = path.read_bytes().decode("utf-8-sig", errors="replace")
    if "Ã" in t[:300000]:
        t = t.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
    d = pd.read_csv(io.StringIO(t), dtype=str, on_bad_lines="skip")
    d.columns = [c.split("/", 1)[-1].strip() for c in d.columns]
    for c in d.columns:  # celdas que siguen en doble UTF-8 (ficheros con codificación mezclada)
        m = d[c].fillna("").str.contains("Ã|Â", regex=True)
        if m.any():
            d.loc[m, c] = d.loc[m, c].map(arreglar)
    return d


def arreglar(x: str) -> str:
    for enc in ("latin-1", "cp1252"):
        try:
            return x.encode(enc).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return re.sub(r"Ã.?", "", x)


def num(s: pd.Series) -> pd.Series:
    """Importe con coma decimal y, a veces, punto de millares («1.234,56», «1234,56», ="01")."""
    s = s.astype(str).str.strip().str.strip('="')
    s = pd.Series(np.where(s.str.contains(",", regex=False),
                           s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False), s), index=s.index)
    return pd.to_numeric(s, errors="coerce")


def norm(x) -> str:
    x = "".join(c for c in unicodedata.normalize("NFD", str(x)) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", x.upper()).strip()


def mes_fichero(stem: str) -> int:
    m = re.search(r"-([A-Za-z]+)$", stem)
    return MESES.get(m.group(1).upper(), 12) if m else 12


def col(d, *nombres):
    for n in nombres:
        if n in d.columns:
            return n
    return None


# ----------------------------------------------------------------------------- búsqueda
def candidatos(raiz: Path, conjunto: str) -> pd.DataFrame:
    filas = []
    for f in sorted((raiz / conjunto).glob("*.csv")):
        if "ingreso" in f.name.lower():
            continue
        d = leer(f)
        cols = [c for c in d.columns if not SKIPCOL.search(c)]
        txt = d[cols].fillna("").astype(str).agg(" | ".join, axis=1).map(norm)
        nombres = [c for c in cols if COL_NOMBRE.search(c)]
        sin_nombre = d[[c for c in cols if c not in nombres]].fillna("").astype(str).agg(" | ".join, axis=1).map(norm)
        m = txt.str.contains(PAT)
        if not m.any():
            continue
        x = d[m]
        anio = pd.to_numeric(x[col(d, "EJERCICIO")], errors="coerce") if col(d, "EJERCICIO") else \
            pd.Series(int(re.search(r"20\d\d", f.stem).group()), index=x.index)
        mes = pd.to_numeric(x[col(d, "MES HASTA")], errors="coerce") if col(d, "MES HASTA") else \
            pd.Series(mes_fichero(f.stem), index=x.index)
        c_obj = [c for c in ("OBJETO_CAS", "ADMINISTRATIVO DESCRIPCION", "EXPEDIENTE CONTABLE DESCR.", "DENOMINACION_CAS",
                             "DENOMINACION", "DESCRIPCION PROGRAMA_CAS", "DESCRIPCION PROYECTO", "DESCRIPCION SUBCONCEPTO_CAS",
                             "CPV_PRINCIPAL") if c in d.columns]
        c_ben = col(d, "PERSONA ADJUDICATARIA", "PERSONA BENEFICIARIA", "NOMBRE BENEFICIARIO/A", "ENTIDAD")
        c_imp = col(d, "OBLIGACION", "IMPORTE CONCEDIDO", "PRESUPUESTO_BASE_LICITACION", "CREDITO INICIAL")
        c_fecha = col(d, "FECHA ADJUDICACION", "FECHA CONCESION", "FECHA")
        # clave del registro dentro del año (los ficheros son acumulados)
        if conjunto in ("contratos-menores", "contratos-no-menores", "encomiendas-gestion", "convenios"):
            clave = x[col(d, "EXPEDIENTE CONTABLE")].fillna("").str.replace(r"^\d\d/", "", regex=True) + "|" + \
                x[c_ben].fillna("").map(norm)
        elif conjunto == "subvenciones-otorgadas":
            clave = x["PERSONA BENEFICIARIA"].fillna("").map(norm) + "|" + x["ADMINISTRATIVO DESCRIPCION"].fillna("").map(norm)
        elif conjunto in ("presupuestos-completos", "liquidacion-presupuestos", "ejecucion-presupuestos",
                          "modificaciones-presupuestos"):
            clave = x[[c for c in ("PROGRAMA", "PROYECTO", "SUBCONCEPTO") if c in d.columns]
                      ].fillna("").astype(str).agg("|".join, axis=1)
        else:
            clave = f.stem + "|" + x["_id"].astype(str)
        for i in x.index:
            filas.append(dict(
                conjunto=conjunto, fichero=f.stem, anio=anio[i], mes_hasta=mes[i], clave=clave[i],
                fecha=str(x.at[i, c_fecha])[:10] if c_fecha and pd.notna(x.at[i, c_fecha]) else "",
                objeto=" | ".join(str(x.at[i, c]).strip() for c in c_obj if pd.notna(x.at[i, c]))[:300],
                adjudicatario_beneficiario=str(x.at[i, c_ben]).strip() if c_ben and pd.notna(x.at[i, c_ben]) else "",
                importe=num(pd.Series([x.at[i, c_imp]])).iloc[0] if c_imp else np.nan,
                columna_importe=c_imp or "",
                credito_final=num(pd.Series([x.at[i, "CREDITO FINAL"]])).iloc[0] if "CREDITO FINAL" in d.columns else np.nan,
                termino=",".join(sorted(set(PAT.findall(txt[i])))),
                solo_en_nombre=not bool(PAT.search(sin_nombre[i])),
                texto=txt[i][:600]))
    c = pd.DataFrame(filas)
    if c.empty:
        return c
    c = c.sort_values(["anio", "mes_hasta"]).drop_duplicates(["conjunto", "anio", "clave"], keep="last")
    return c


def clasificar(c: pd.DataFrame) -> pd.DataFrame:
    dec, tipo, mot = [], [], []
    for _, r in c.iterrows():
        for conj, rx, rx_no_si, d, t, m in REGLAS:
            if conj and r.conjunto not in conj:
                continue
            if re.search(rx, r.texto) and (rx_no_si is None or re.search(rx_no_si, r.texto)):
                dec.append(d); tipo.append(t); mot.append(m)
                break
        else:
            dec.append("excluido"); tipo.append("")
            mot.append("Coincidencia solo en el nombre de una persona o empresa" if r.solo_en_nombre
                       else "Revisado: el término aparece con otro sentido, sin relación con la avispa")
    c = c.assign(decision=dec, tipo_gasto=tipo, motivo=mot)
    return c


TIPO_IMPORTE = {
    "encomiendas-gestion": "obligación reconocida en el ejercicio (encargo a medio propio; el conjunto no informa de IVA)",
    "contratos-menores": "obligación reconocida en el ejercicio (el conjunto no indica si incluye IVA)",
    "contratos-no-menores": "obligación reconocida en el ejercicio (el conjunto no indica si incluye IVA)",
    "subvenciones-otorgadas": "obligación reconocida en el ejercicio (subvención)",
    "subvenciones": "importe concedido",
    "presupuestos-completos": "crédito inicial",
    "ejecucion-presupuestos": "obligación reconocida acumulada (ejecución)",
    "liquidacion-presupuestos": "obligación reconocida (liquidación)",
}


# ----------------------------------------------------------------------------- contexto
def ultimo_por_anio(carpeta: Path, prefijo: str) -> dict:
    res = {}
    for f in carpeta.glob(f"{prefijo}-*.csv"):
        m = re.search(r"(20\d\d)-([A-Za-z]+)$", f.stem)
        if m:
            y, mm = int(m.group(1)), MESES.get(m.group(2).upper(), 0)
            if y not in res or mm > res[y][0]:
                res[y] = (mm, f)
    return {y: v[1] for y, v in sorted(res.items())}


def encargo_basalan(raiz: Path) -> pd.DataFrame:
    """Obligaciones del encargo de Basalan al Servicio de Patrimonio Natural (contenedor de la retirada)."""
    filas = []
    for y, f in ultimo_por_anio(raiz / "encomiendas-gestion", "encomiendas-gestion").items():
        e = leer(f)
        e["o"] = num(e.OBLIGACION)
        b = e[e.ENTIDAD.fillna("").str.contains("BASALAN")]
        pn = b[b["ADMINISTRATIVO DESCRIPCION"].fillna("").map(norm).str.contains("PATRIMONIO NATURAL|PATRIM. NAT")]
        filas.append(dict(anio=y, mes_fichero=mes_fichero(f.stem), encargo_basalan_patrimonio_natural_eur=pn.o.sum(),
                          encomiendas_basalan_total_eur=b.o.sum()))
    return pd.DataFrame(filas).set_index("anio")


def cobertura(raiz: Path) -> pd.DataFrame:
    """Años y último mes disponibles por conjunto, y si el gasto trae texto libre para buscar."""
    filas = []
    for conj, campo in [("encomiendas-gestion", "EXPEDIENTE CONTABLE DESCR."), ("contratos-menores", "EXPEDIENTE CONTABLE DESCR."),
                        ("contratos-no-menores", "EXPEDIENTE CONTABLE DESCR."), ("convenios", "EXPEDIENTE CONTABLE DESCR."),
                        ("subvenciones-otorgadas", "ADMINISTRATIVO DESCRIPCION"), ("subvenciones", None),
                        ("plan-anual-contratacion", "OBJETO_CAS"), ("plan-anual-contratacion-basalan", "OBJETO_CAS"),
                        ("liquidacion-presupuestos", "DESCRIPCION PROYECTO"), ("ejecucion-presupuestos", "DESCRIPCION PROYECTO"),
                        ("modificaciones-presupuestos", None), ("presupuestos-completos", "DESCRIPCION PROYECTO")]:
        anios = {}
        for f in (raiz / conj).glob("*.csv"):
            if "ingreso" in f.name.lower():
                continue
            m = re.search(r"(20\d\d)", f.stem)
            if not m:
                continue
            y = int(m.group(1))
            mm = mes_fichero(f.stem) if re.search(r"-[A-Za-z]+$", f.stem) else 12
            if y not in anios or mm > anios[y][0]:
                anios[y] = (mm, f)
        for y, (mm, f) in sorted(anios.items()):
            cabecera = [c.split("/", 1)[-1].strip() for c in pd.read_csv(f, nrows=0, encoding="utf-8-sig").columns]
            filas.append(dict(conjunto=conj, anio=y, ultimo_mes=mm,
                              texto_libre=("sí" if campo is None or campo in cabecera else "no")))
    return pd.DataFrame(filas)


def nidos(raiz: Path):
    d = preparar(raiz / "avispa_asiatica" / "nidos.csv")
    por_temp = d.groupby("temporada").size()
    basalan = d[d.agente.eq("BASALAN")]
    por_temp_agente = d.groupby(["temporada", "agente"]).size().unstack(fill_value=0)
    cb = basalan[basalan.cierre.notna()]
    cierre_mes = cb.groupby([cb.cierre.dt.year, cb.cierre.dt.month]).size()
    return por_temp, por_temp_agente, cierre_mes


def speis(raiz: Path) -> pd.Series:
    f = raiz / "speis" / "intervenciones-speis-2023-2026.csv"
    if not f.exists():
        return pd.Series(dtype=int)
    sp = pd.read_csv(f, dtype=str)
    c = sp.columns
    tipo = sp[c[5]].str.encode("latin-1", errors="ignore").str.decode("utf-8", errors="ignore").map(norm)
    anio = pd.to_numeric(sp[c[1]], errors="coerce")
    return sp[tipo.str.contains("AVISPA|ABEJA", na=False) & anio.between(2023, 2025)].groupby(anio).size()


# ----------------------------------------------------------------------------- principal
def main() -> None:
    raiz = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/bizkaia")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "outputs")
    out.mkdir(parents=True, exist_ok=True)
    conjuntos = ["encomiendas-gestion", "contratos-menores", "contratos-no-menores", "convenios", "subvenciones-otorgadas",
                 "subvenciones", "plan-anual-contratacion", "plan-anual-contratacion-basalan", "presupuestos-completos",
                 "liquidacion-presupuestos", "modificaciones-presupuestos", "ejecucion-presupuestos"]
    C = pd.concat([candidatos(raiz, k) for k in conjuntos if (raiz / k).exists()], ignore_index=True)
    C = clasificar(C)
    C["anio"] = C.anio.astype(int)
    C.sort_values(["decision", "conjunto", "anio"]).drop(columns=["clave"]).to_csv(
        out / "avispa_gasto_candidatos.csv", index=False)

    R = C[C.decision.eq("incluido")].copy()
    R["tipo_importe"] = R.conjunto.map(TIPO_IMPORTE)
    R["es_control_avispa"] = np.where(R.tipo_gasto.isin(CONTROL), "sí",
                                      np.where(R.tipo_gasto.eq("retirada_nidos_basalan_mixta"), "en parte (mezclado)", "no"))
    R = R.rename(columns={"motivo": "motivo_inclusion"})
    R = R.sort_values(["anio", "tipo_gasto", "conjunto"])
    R[["conjunto", "fichero", "anio", "fecha", "objeto", "adjudicatario_beneficiario", "importe", "tipo_importe",
       "tipo_gasto", "es_control_avispa", "motivo_inclusion"]].to_csv(out / "avispa_gasto_registros.csv", index=False)

    # ---- anual
    piv = R.pivot_table(index="anio", columns="tipo_gasto", values="importe", aggfunc="sum").reindex(columns=list(TIPOS))
    nreg = R.pivot_table(index="anio", columns="tipo_gasto", values="importe", aggfunc="size").reindex(columns=list(TIPOS))
    eb = encargo_basalan(raiz)
    por_temp, por_temp_agente, cierre_mes = nidos(raiz)
    sp = speis(raiz)
    anios = range(2017, 2027)
    A = pd.DataFrame(index=pd.Index(anios, name="anio"))
    for t in TIPOS:
        A[f"{t}_eur"] = piv[t].reindex(anios).round(2) if t in piv else np.nan
        A[f"{t}_n"] = nreg[t].reindex(anios).fillna(0).astype(int) if t in nreg else 0
    A["control_identificable_eur"] = piv.reindex(columns=CONTROL).sum(axis=1, min_count=1).reindex(anios).round(2)
    A = A.join(eb.round(2))
    A["nidos_temporada"] = por_temp.reindex(anios)
    A["nidos_temporada_basalan"] = por_temp_agente.get("BASALAN", pd.Series(dtype=int)).reindex(anios)
    A["nidos_temporada_bomberos"] = por_temp_agente.get("BOMBEROS", pd.Series(dtype=int)).reindex(anios)
    A["nidos_temporada_ayuntamientos"] = por_temp_agente.get("AYUNTAMIENTO", pd.Series(dtype=int)).reindex(anios)
    A["nidos_cerrados_basalan_ano_natural"] = cierre_mes.groupby(level=0).sum().reindex(anios)
    A["salidas_speis_abejas_avispas"] = sp.reindex(anios)
    A["retirada_eur_por_nido_temporada"] = (A.retirada_nidos_basalan_eur / A.nidos_temporada).round(1).where(
        A.index.isin([2018, 2019]))  # solo 2018-2019 tienen líneas propias y temporada completa en el registro
    det = {2017: "línea anual propia", 2018: "líneas propias (may-jun, sep-oct, nov)", 2019: "líneas propias (jun, sep, nov)",
           2020: "líneas mezcladas con otros trabajos"}
    A["detalle_retirada_en_encomiendas"] = [det.get(y, "no: dentro del encargo anual de Patrimonio Natural")
                                            if y in eb.index else "sin fichero" for y in anios]
    cob = cobertura(raiz)
    tl = cob[cob.conjunto.eq("contratos-menores")].set_index("anio").texto_libre
    A["contratos_menores_con_texto_libre"] = tl.reindex(anios)
    A["ultimo_mes_encomiendas"] = A.mes_fichero
    A = A.drop(columns=["mes_fichero"])
    A.to_csv(out / "avispa_gasto_anual.csv")

    # ---- coste por nido con las líneas que nombran meses (cierres de Basalan en esos meses)
    def nb(y, meses):
        return int(sum(cierre_mes.get((y, m), 0) for m in meses))
    lineas = R[R.tipo_gasto.str.startswith("retirada_nidos")]
    casos = []
    for _, r in lineas.iterrows():
        o = norm(r.objeto.split("|")[-1])
        if r.anio == 2018:
            ms = [5, 6] if "MAYO-JUNIO" in o else [9, 10] if "SEPTIEMBRE Y OCTUBRE" in o else [11] if "NOVIEMBRE" in o else None
        elif r.anio == 2019:
            ms = [6] if "JUNIO" in o else [9] if o.endswith(" SE") else [11] if o.endswith(" NO") else None
        elif r.anio == 2020:
            ms = [1, 2] if "ENERO Y FEBRERO" in o else [5] if o.startswith("(DOK) MAYO") else \
                [10] if o.startswith("(DOK) OCT") else [11] if o.startswith("(DOK) NOV") else None
        else:
            ms = None
        n = nb(int(r.anio), ms) if ms else None
        casos.append(dict(anio=int(r.anio), linea=o[:70], eur=r.importe, meses=ms, nidos_basalan=n,
                          eur_nido=(r.importe / n) if n else None, tipo=r.tipo_gasto))
    K = pd.DataFrame(casos)
    # Coste por nido por línea (y 2018 con las tres líneas juntas), para el gráfico de gasto de la web
    k18 = K[(K.anio == 2018) & K.nidos_basalan.notna()]
    Kc = pd.concat([K.assign(meses=K.meses.map(lambda m: "-".join(map(str, m)) if m else "")),
                    pd.DataFrame([dict(anio=2018, linea="2018, LAS TRES LINEAS JUNTAS", eur=k18.eur.sum(),
                                       meses="5-6-9-10-11", nidos_basalan=k18.nidos_basalan.sum(),
                                       eur_nido=k18.eur.sum() / k18.nidos_basalan.sum(), tipo="total_2018")])],
                   ignore_index=True)
    Kc["eur_nido"] = Kc.eur_nido.round(1).where(~Kc.tipo.str.endswith("mixta"))  # mezcladas: no es coste por nido
    Kc.to_csv(out / "avispa_gasto_coste_nido.csv", index=False)

    # ---- texto
    L = []
    p = L.append
    p("# Medios y gasto público en el control de la avispa asiática (Open Data Bizkaia)")
    p(f"Candidatos de la búsqueda (sin duplicados de ficheros acumulados): {len(C)}. Decisión: "
      + ", ".join(f"{k} {v}" for k, v in C.decision.value_counts().items()) + ".")
    p("Detalle auditable: avispa_gasto_candidatos.csv (todos, con motivo) y avispa_gasto_registros.csv (incluidos).")
    p("Importes: obligaciones reconocidas del ejercicio (lo que la Diputación reconoce deber), salvo que se diga. "
      "Los conjuntos no indican si los contratos incluyen IVA. No se suman tipos de naturaleza distinta.")
    p("")
    p("## 1. Gasto identificable por año y tipo (€; n = registros)")
    cols = []
    for t in TIPOS:
        cols += [f"{t}_eur", f"{t}_n"]
    T = A[cols].copy()
    T.columns = [c.replace("retirada_nidos_basalan", "retirada").replace("equipos_proteccion_bomberos", "trajes_speis")
                 .replace("material_retirada_nidos", "material").replace("ayudas_apicultura", "ayud_apic")
                 .replace("otros_pagos_apicultores", "otros_apic") for c in T.columns]
    p(T.astype(object).fillna("").to_string())
    p("Tipos: " + "; ".join(f"{k} = {v}" for k, v in TIPOS.items()))
    p("Control identificable = retirada (líneas propias) + material + trajes SPEIS (todo obligaciones reconocidas). "
      "No incluye la parte de avispa de las líneas mixtas de 2020 ni las ayudas a la apicultura.")
    p(A[["control_identificable_eur", "retirada_nidos_basalan_mixta_eur", "ayudas_apicultura_eur"]].astype(object).fillna("").to_string())
    p("")
    p("## 2. El contenedor: encargo anual de Basalan para el Servicio de Patrimonio Natural (encomiendas-gestion)")
    p(A[["encargo_basalan_patrimonio_natural_eur", "encomiendas_basalan_total_eur", "detalle_retirada_en_encomiendas"]]
      .dropna(how="all").to_string())
    p("Desde 2021 la retirada de nidos va dentro de este encargo, que incluye mantenimiento de parques naturales, "
      "áreas de esparcimiento, San Juan de Gaztelugatxe y trabajos extraordinarios. Las líneas mensuales de 2021-2025 "
      "no nombran la avispa: el coste de la retirada no se puede aislar con los datos abiertos.")
    p("En presupuestos, liquidación (2017-2024), ejecución (2016-2026) y modificaciones presupuestarias no hay "
      "ninguna partida ni proyecto con avispa, velutina, nido o apicultura. El encargo figura como "
      "proyecto «BASALAN ENCARGO ESPACIOS NAT. PROTEGIDOS» del programa 172103 Patrimonio Natural en la liquidación "
      "de 2024 y la ejecución de 2025-2026. El contenido del encargo cambia entre años (en 2017 incluía la limpieza de "
      "las áreas de esparcimiento, que en 2024-2025 es un proyecto aparte de 2,5-2,8 M€): la serie no es homogénea.")
    ctx = C[C.decision.eq("contexto")]
    for _, r in ctx.iterrows():
        if r.conjunto == "ejecucion-presupuestos":
            p(f"Contexto ({r.conjunto} {r.anio}, hasta el mes {r.mes_hasta}): {r.objeto[:90]}: crédito final "
              f"{r.credito_final:,.0f} €, obligación {r.importe:,.0f} € (crédito inicial 0: entra por modificación). {r.motivo}.")
    p("")
    p("## 3. Coste por nido")
    p("a) Líneas de la encomienda que nombran meses, divididas entre los nidos de asiática cerrados por Basalan "
      "en esos meses (fecha de cierre; año natural):")
    for _, k in K.iterrows():
        if k.tipo.endswith("mixta"):
            p(f"  {k.anio} {k.linea[:60]}: {k.eur:,.0f} € (mezclada con otros trabajos; nidos de Basalan en esos "
              f"meses: {int(k.nidos_basalan) if pd.notna(k.nidos_basalan) else 'n/d'}; no se calcula €/nido)")
        elif pd.notna(k.nidos_basalan) and k.nidos_basalan > 0:
            p(f"  {k.anio} {k.linea[:60]}: {k.eur:,.0f} € / {int(k.nidos_basalan)} nidos = {k.eur_nido:.0f} €/nido")
        else:
            p(f"  {k.anio} {k.linea[:60]}: {k.eur:,.0f} € (sin meses identificables)")
    k18 = K[(K.anio == 2018) & K.nidos_basalan.notna()]
    eur18, n18 = k18.eur.sum(), int(k18.nidos_basalan.sum())
    p(f"  2018, las tres líneas juntas: {eur18:,.0f} € / {n18} nidos = {eur18 / n18:.0f} €/nido. "
      f"Julio-agosto de 2018 no tiene línea propia ({nb(2018, [7, 8])} nidos cerrados por Basalan).")
    p("  Las líneas de 2019 vienen cortadas a 60 caracteres («…ASIATICA SE», «…ASIATICA NO»): se asume septiembre y "
      f"noviembre. Si «SE» cubriera septiembre y octubre: {K[(K.anio == 2019) & K.linea.str.endswith(' SE')].eur.sum():,.0f} € / "
      f"{nb(2019, [9, 10])} nidos = {K[(K.anio == 2019) & K.linea.str.endswith(' SE')].eur.sum() / max(nb(2019, [9, 10]), 1):.0f} €/nido.")
    p("b) Por temporada (gasto de retirada con línea propia / nidos de la temporada). Cobertura parcial de meses: "
      "es una cota inferior, no el coste del año.")
    p(A[["retirada_nidos_basalan_eur", "retirada_nidos_basalan_mixta_eur", "nidos_temporada", "nidos_temporada_basalan",
         "retirada_eur_por_nido_temporada"]].loc[2017:2021].to_string())
    m20 = A.at[2020, "retirada_nidos_basalan_mixta_eur"] + (A.at[2020, "retirada_nidos_basalan_eur"]
                                                            if pd.notna(A.at[2020, "retirada_nidos_basalan_eur"]) else 0)
    p(f"  2020: las líneas que nombran la avispa suman {m20:,.0f} €, casi todo mezclado con otros trabajos; "
      f"dividido entre los {A.at[2020, 'nidos_temporada_basalan']} nidos de Basalan de la temporada = {m20 / A.at[2020, 'nidos_temporada_basalan']:.0f} €/nido "
      "como cota superior (no es un coste real).")
    p("c) Escenario, no dato: si el coste por nido de 2018 se mantuviera, la retirada por Basalan costaría "
      + ", ".join(f"{y}: {A.at[y, 'nidos_temporada_basalan'] * eur18 / n18 / 1000:,.0f} mil €" for y in range(2021, 2026))
      + " (precios de 2018, sin actualizar). Frente al encargo de Patrimonio Natural de cada año sería: "
      + ", ".join(f"{y}: {A.at[y, 'nidos_temporada_basalan'] * eur18 / n18 / A.at[y, 'encargo_basalan_patrimonio_natural_eur']:.0%}"
                  for y in range(2021, 2026)) + ".")
    p("")
    p("## 4. Medios")
    p(A[["nidos_temporada", "nidos_temporada_basalan", "nidos_temporada_bomberos", "nidos_temporada_ayuntamientos",
         "salidas_speis_abejas_avispas"]].loc[2018:2025].to_string())
    ok = all(int(A.at[y, "nidos_temporada"]) == v for y, v in NIDOS_REF.items())
    p(f"  Comprobación con avispa_estabilizacion.txt (nidos por temporada): {'coinciden' if ok else 'NO COINCIDEN'}.")
    p("  Salidas del SPEIS por «neutralización de abejas y avispas»: solo 2023-2025 son comparables (ruptura de "
      "serie a finales de 2022); no distinguen especie y no traen coste.")
    tr = R[R.tipo_gasto.eq("equipos_proteccion_bomberos")]
    p("  Trajes del SPEIS: " + "; ".join(f"{r.anio}: {r.importe:,.2f} €" for _, r in tr.iterrows())
      + ". 2019, 2020 y 2022 tienen compras de vestuario a Protec Solana sin desglose (contratos menores sin texto "
      "desde 2019; lotes de vestuario genéricos): no se puede saber si incluyen trajes.")
    p("")
    p("## 5. Ayudas a la apicultura (subvenciones-otorgadas; no se suman al control)")
    ap = R[R.tipo_gasto.eq("ayudas_apicultura")]
    p(ap.groupby("anio").agg(eur=("importe", "sum"), beneficiarios=("importe", "size")).round(2).to_string())
    p("  Ninguna línea de ayudas menciona la avispa, el trampeo ni los nidos. 2026 aún no aparece (fichero hasta "
      "septiembre). El conjunto «subvenciones» (concesiones) solo trae estas ayudas en 2019, con importes "
      "concedidos algo distintos de las obligaciones (23.734 € frente a 23.674 €; 15.519 € frente a 14.765 €).")
    oa = R[R.tipo_gasto.eq("otros_pagos_apicultores")]
    p("  Otros pagos a asociaciones apícolas (seguros y sustituciones, razas puras, pequeños suministros): "
      + "; ".join(f"{y}: {v:,.0f} €" for y, v in oa.groupby("anio").importe.sum().items()) + ".")
    p("")
    p("## 6. Lo que no aparece en los datos")
    p("- Coste de la retirada de nidos desde 2021: no hay línea propia; va dentro del encargo de Patrimonio Natural.")
    p("- Meses sin línea propia de retirada: 2018 enero-abril, julio-agosto y diciembre; 2019 enero-mayo, "
      "julio-agosto, octubre (si «SE» es solo septiembre) y diciembre; 2020 casi todo (solo 1.667 € en líneas propias).")
    p("- Fechas: solo los contratos menores desde 2019 traen fecha de adjudicación; el resto, solo ejercicio y mes "
      "del fichero acumulado.")
    p("- Contratos propios de Basalan (compras de material, pértigas, biocidas, plataformas): no están en ODB; su "
      "plan de contratación solo existe para 2024-2025 y no nombra la avispa.")
    p("- Trampeo, ayudas a ayuntamientos o particulares por trampas o retirada: 0 registros en subvenciones, "
      "subvenciones-otorgadas y convenios.")
    p("- Drones: hay compras a Drone by Drone SL (2019, 2023-2025) sin objeto ni departamento: marcadas como dudosas.")
    p("- Contratos menores desde 2019: solo traen la categoría económica o el CPV, no el objeto; la búsqueda por "
      "texto solo es completa en 2017-2018.")
    p("- Gasto de los ayuntamientos (Bilbao tiene servicio propio) y del Gobierno Vasco: fuera de ODB.")
    p("- Coste de las salidas de bomberos (horas, vehículos): no está.")
    p("")
    p("## 7. Cobertura de cada fuente (último mes del último fichero; ¿trae texto libre del gasto?)")
    cv = cob.pivot_table(index="conjunto", columns="anio", values="ultimo_mes", aggfunc="first")
    p(cv.reindex(columns=range(2017, 2027)).astype(object).fillna("").to_string())
    p("  (12 = año completo; en contratos menores, texto libre solo en: "
      + ", ".join(str(y) for y, v in tl.items() if v == "sí") + ")")
    (out / "avispa_gasto.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
