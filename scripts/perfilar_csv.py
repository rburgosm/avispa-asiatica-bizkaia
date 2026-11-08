"""Perfil compacto de todos los CSV de una carpeta.

Uso: perfilar_csv.py <carpeta> <salida.txt> [--max-cols N]

Para cada fichero: separador y codificación detectados, filas x columnas, y por
columna: nº de valores distintos, % nulos y hasta 4 valores más frecuentes
(recortados). Repara textos con doble UTF-8 («Ã“») cuando los detecta.
"""
import argparse
import csv
import io
from pathlib import Path

import pandas as pd


def leer(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if "Ã" in txt[:200000]:
        try:
            txt = txt.encode("latin-1").decode("utf-8")
            enc += "+mojibake-fix"
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    muestra = txt[:20000]
    try:
        sep = csv.Sniffer().sniff(muestra, delimiters=",;\t|").delimiter
    except csv.Error:
        sep = ","
    df = pd.read_csv(io.StringIO(txt), sep=sep, dtype=str, low_memory=False, on_bad_lines="warn")
    return df, sep, enc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta")
    ap.add_argument("salida")
    ap.add_argument("--max-cols", type=int, default=40)
    ap.add_argument("--solo", default=None, help="subcadena del nombre de fichero")
    a = ap.parse_args()
    out = []
    for f in sorted(Path(a.carpeta).glob("*.csv")):
        if a.solo and a.solo not in f.name:
            continue
        try:
            df, sep, enc = leer(f)
        except Exception as e:  # noqa: BLE001
            out.append(f"## {f.name}: ERROR {e}")
            continue
        out.append(f"## {f.name}  [{enc}, sep={sep!r}]  {df.shape[0]} filas x {df.shape[1]} cols")
        for c in list(df.columns)[: a.max_cols]:
            s = df[c].str.strip()
            vc = s.value_counts()
            top = "; ".join(f"{str(k)[:30]}({v})" for k, v in vc.head(4).items())
            out.append(f"  - {str(c)[:40]}: uniq={s.nunique()} nulos={s.isna().mean():.0%} | {top}")
        if df.shape[1] > a.max_cols:
            out.append(f"  ... {df.shape[1] - a.max_cols} columnas más: {list(df.columns)[a.max_cols:a.max_cols+30]}")
    Path(a.salida).write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
