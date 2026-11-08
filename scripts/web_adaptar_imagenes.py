"""Adapta las fotografías de Wikimedia Commons para integrarlas en la web (Pillow).

Uso:
    python -I scripts/web_adaptar_imagenes.py

Parte siempre del ORIGINAL a máxima resolución, en data/raw/commons/ (si falta, ejecuta antes
scripts/web_descargar_imagenes.py, que lo descarga y deja los créditos en web/data/imagenes.json).

Para todas las fotos, el mismo tratamiento:
- color común (sobre el original entero): ligera desaturación, un leve desplazamiento hacia la gama
  cálida (más rojo, menos azul) y un velo del color del papel de la paleta, para que las tres fotos
  casen entre sí y con la página;
- recorte con un punto focal definido por foto (fracción del ancho y del alto del original) en dos
  proporciones: 16:9 («ancho», escritorio y móvil en horizontal) y 4:5 («alto», móvil en vertical),
  con un acercamiento opcional por foto;
- anchuras 800, 1200, 1800 y 2400 px, sin pasar NUNCA del ancho del recorte del original: si el
  recorte no da para 2400, la mayor es la máxima que permite (no se amplía);
- reducción con LANCZOS y, después, un enfoque suave (UnsharpMask) para recuperar el detalle que
  pierde el filtro; la anchura máxima, si coincide con el recorte, no se reduce ni se enfoca;
- AVIF (calidad 62, soporte nativo de Pillow ≥ 11.2) y WebP (calidad 82) de reserva, sin
  metadatos; si un fichero pasa de su peso máximo, baja la calidad en pasos;
- un fondo diminuto y difuminado (WebP de 48 px, en data URI dentro del JSON) que la web pone
  detrás de la foto mientras carga y en los bordes cuando la pantalla pide más píxeles de los
  que tiene el original (la foto no se estira).
Los parámetros y la lista de ficheros se guardan en web/data/imagenes.json (campo «adaptacion»).
El crédito de la web dice «adaptada: recortada y retocada». Las tres fotos son CC BY-SA: la versión
adaptada se publica con la misma licencia.
"""
import base64
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, features

RAIZ = Path(__file__).resolve().parent.parent
ORIG = RAIZ / "data/raw/commons"
IMG = RAIZ / "web/img"
JSON = RAIZ / "web/data/imagenes.json"

# Punto focal (x, y en fracción del original): lo que tiene que quedar en el centro de cualquier
# recorte (revisado a ojo sobre los originales el 08/11/2026):
# - avispa: el insecto, algo a la izquierda del centro (en 4:5 cabe justo de la cabeza al abdomen);
# - nido_primario: la abertura con la reina (un poco por debajo del centro de la esfera);
# - nido_secundario: el nido, a la derecha y algo por debajo del centro.
FOCO = {"avispa": (0.47, 0.47), "nido_primario": (0.49, 0.55), "nido_secundario": (0.6, 0.55)}
# Acercamiento (1 = el mayor recorte posible con esa proporción). El nido secundario ocupa poco en
# la foto original: se acerca un 40 % para que se reconozca a primera vista sin perder el árbol.
ZOOM = {"avispa": 1.0, "nido_primario": 1.0, "nido_secundario": 1.4}
PROPORCIONES = {"ancho": (16, 9), "alto": (4, 5)}
ANCHURAS = [800, 1200, 1800, 2400]
# Si el recorte no llega a la siguiente anchura pero la supera en más de un 8 %, se añade a su
# ancho real (la versión más nítida posible); si no, la mayor anchura de la lista es la última.
MARGEN_MAXIMA = 1.08
SATURACION = 0.8           # 1 = sin cambio (ligera desaturación común)
TONO = (1.04, 1.0, 0.93)   # multiplicadores R, G, B: desplazamiento común hacia la gama cálida
VELO = (250, 247, 240)     # --fondo
VELO_ALFA = 0.07
ENFOQUE = {"radius": 0.8, "percent": 45, "threshold": 2}  # UnsharpMask suave tras reducir
FORMATOS = {  # formato: (calidad inicial, calidad mínima, paso, opciones de Pillow)
    "avif": (62, 44, 4, {"speed": 4}),
    "webp": (82, 66, 4, {"method": 6}),
}
# Peso máximo por fichero según la anchura (bytes). El móvil (390 px, dpr 3) baja la de 1200.
PESO_MAX = {800: 110_000, 1200: 240_000, 1800: 420_000, 2400: 650_000}
FONDO_ANCHO = 48           # px del fondo difuminado (data URI)


def recortar(im: Image.Image, prop_w: int, prop_h: int, foco, zoom: float = 1.0) -> Image.Image:
    w, h = im.size
    objetivo = prop_w / prop_h
    if w / h > objetivo:  # sobra ancho
        cw, ch = h * objetivo, h
    else:
        cw, ch = w, w / objetivo
    cw, ch = round(cw / zoom), round(ch / zoom)
    x = min(max(0, round(foco[0] * w - cw / 2)), w - cw)
    y = min(max(0, round(foco[1] * h - ch / 2)), h - ch)
    return im.crop((x, y, x + cw, y + ch))


def tratar(im: Image.Image) -> Image.Image:
    im = ImageEnhance.Color(im.convert("RGB")).enhance(SATURACION)
    r, g, b = im.split()
    im = Image.merge("RGB", [c.point(lambda v, k=k: min(255, round(v * k))) for c, k in zip((r, g, b), TONO)])
    return Image.blend(im, Image.new("RGB", im.size, VELO), VELO_ALFA)


def anchuras(maximo: int) -> list[int]:
    lista = [a for a in ANCHURAS if a <= maximo]
    if not lista or (maximo < ANCHURAS[-1] and maximo > lista[-1] * MARGEN_MAXIMA):
        lista.append(maximo)
    return lista


def guardar(out: Image.Image, destino: Path, formato: str, max_bytes: int) -> int:
    calidad, minima, paso, opciones = FORMATOS[formato]
    while True:
        out.save(destino, formato.upper(), quality=calidad, **opciones)
        if destino.stat().st_size <= max_bytes or calidad <= minima:
            return calidad
        calidad -= paso


def fondo(rec: Image.Image) -> str:
    pequena = rec.resize((FONDO_ANCHO, round(FONDO_ANCHO * rec.height / rec.width)), Image.LANCZOS)
    pequena = pequena.filter(ImageFilter.GaussianBlur(2.5))
    buf = io.BytesIO()
    pequena.save(buf, "WEBP", quality=50, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def main() -> None:
    if not features.check("avif"):
        sys.exit("Este Pillow no tiene soporte AVIF (hace falta Pillow >= 11.2 con libavif).")
    if not all(any(ORIG.glob(f"{c}.*")) for c in FOCO):
        subprocess.run([sys.executable, "-I", str(RAIZ / "scripts/web_descargar_imagenes.py")], check=True)
    creditos = json.loads(JSON.read_text(encoding="utf-8"))
    for viejo in IMG.glob("*-ancho-*.webp"):  # versiones anteriores (máximo 1600 px)
        viejo.unlink()
    for viejo in IMG.glob("*-alto-*.webp"):
        viejo.unlink()
    for clave, foco in FOCO.items():
        original = next(ORIG.glob(f"{clave}.*"))
        im = tratar(ImageOps.exif_transpose(Image.open(original)))
        variantes = {}
        for nombre, (pw, ph) in PROPORCIONES.items():
            rec = recortar(im, pw, ph, foco, ZOOM[clave])
            lista = []
            for a in anchuras(rec.width):
                alto = round(a * ph / pw)
                if a < rec.width:
                    out = rec.resize((a, alto), Image.LANCZOS).filter(ImageFilter.UnsharpMask(**ENFOQUE))
                else:
                    out = rec.resize((a, alto), Image.LANCZOS) if rec.size != (a, alto) else rec
                fila = {"w": a, "h": alto}
                for formato in FORMATOS:
                    destino = IMG / f"{clave}-{nombre}-{a}.{formato}"
                    q = guardar(out, destino, formato, PESO_MAX.get(a, PESO_MAX[min(PESO_MAX, key=lambda k: abs(k - a))]))
                    fila[formato] = f"img/{destino.name}"
                    print(f"{destino.name}: {a}x{alto}, {destino.stat().st_size / 1024:.0f} KB, calidad {q}")
                lista.append(fila)
            variantes[nombre] = {"recorte": list(rec.size), "fondo": fondo(rec), "anchuras": lista}
        r_, g_, b_ = im.resize((1, 1), Image.LANCZOS).getpixel((0, 0))  # color dominante (fondo mientras carga)
        creditos[clave]["adaptacion"] = {
            "foco": foco, "zoom": ZOOM[clave], "color": f"#{r_:02x}{g_:02x}{b_:02x}",
            "original": list(im.size), "proporciones": {k: f"{v[0]}:{v[1]}" for k, v in PROPORCIONES.items()},
            "saturacion": SATURACION, "tono": TONO, "velo": VELO, "velo_alfa": VELO_ALFA,
            "enfoque": ENFOQUE, "calidad": {f: v[0] for f, v in FORMATOS.items()},
            "variantes": variantes, "nota": "recortada y retocada"}
    JSON.write_text(json.dumps(creditos, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
