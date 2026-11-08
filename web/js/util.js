// Utilidades comunes a los componentes.

export const sinMovimiento = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Duración de las transiciones (0 si la persona pide reducir el movimiento).
export const duracion = (ms = 600) => (sinMovimiento() ? 0 : ms);

const locale = (idioma) => (idioma === "eu" ? "eu-ES" : "es-ES");

export function formateador(idioma, decimales = 1, fijos = false) {
  const f = new Intl.NumberFormat(locale(idioma), { maximumFractionDigits: decimales,
    minimumFractionDigits: fijos ? decimales : 0, useGrouping: true });
  // Intl no agrupa los miles de 4 cifras en es-ES («1990»); la norma de la RAE tampoco obliga,
  // pero en los gráficos se agrupan siempre para que 1.990 y 18.098 se lean igual.
  return (x) => {
    if (x == null || Number.isNaN(x)) return "–";
    const s = f.format(x);
    return Math.abs(x) >= 1000 && Math.abs(x) < 10000 ? s.replace(/^(-?\d)(\d{3})/, "$1.$2") : s;
  };
}

// Proporción (0-1) como porcentaje con coma decimal: 0.0965 -> «9,6 %».
export function porcentaje(idioma, decimales = 1) {
  const f = formateador(idioma, decimales, true);
  return (p) => (p == null ? "–" : `${f(Math.round(p * 100 * 10 ** decimales) / 10 ** decimales)} %`);
}

// Sustituye {clave} en una plantilla de texto.
export const plantilla = (t, v) => (t || "").replace(/\{(\w+)\}/g, (_, k) => (k in v ? v[k] : ""));

// Valor de una variable CSS (para MapLibre, que no entiende var()).
export const variableCss = (nombre) =>
  getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();

// Patrón rayado (datos incompletos o sin desglose) dentro de un <svg>. Devuelve la url para fill.
let nPatrones = 0;
export function rayado(svg, color = "var(--gris-dato)", fondo = "var(--fondo)") {
  const id = `rayado-${++nPatrones}`;
  const p = svg.append("defs").append("pattern").attr("id", id).attr("patternUnits", "userSpaceOnUse")
    .attr("width", 6).attr("height", 6).attr("patternTransform", "rotate(45)");
  p.append("rect").attr("width", 6).attr("height", 6).attr("fill", fondo);
  p.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 6)
    .attr("stroke", color).attr("stroke-width", 3);
  return `url(#${id})`;
}

// Separa en vertical etiquetas que se pisan (lista de {y}); modifica y devuelve la lista.
export function separar(etiquetas, minimo = 14, alto = Infinity) {
  const orden = [...etiquetas].sort((a, b) => a.y - b.y);
  for (let i = 1; i < orden.length; i++) {
    if (orden[i].y - orden[i - 1].y < minimo) orden[i].y = orden[i - 1].y + minimo;
  }
  const exceso = orden.length ? orden[orden.length - 1].y - alto : 0;
  if (exceso > 0) {
    orden[orden.length - 1].y -= exceso;
    for (let i = orden.length - 2; i >= 0; i--) {
      if (orden[i + 1].y - orden[i].y < minimo) orden[i].y = orden[i + 1].y - minimo;
    }
  }
  return etiquetas;
}

// Parte un texto en líneas de como mucho `ancho` px dentro de un <text> de D3 (con tspans).
export function envolver(texto, ancho, interlineado = 1.15) {
  texto.each(function () {
    const t = window.d3.select(this);
    const palabras = (t.attr("data-texto") ?? t.text()).split(/\s+/).filter(Boolean);
    t.attr("data-texto", palabras.join(" "));
    const x = t.attr("x") || 0;
    t.text(null);
    let linea = [], tspan = t.append("tspan").attr("x", x).attr("dy", 0), n = 0;
    for (const p of palabras) {
      linea.push(p);
      tspan.text(linea.join(" "));
      if (tspan.node().getComputedTextLength() > ancho && linea.length > 1) {
        linea.pop();
        tspan.text(linea.join(" "));
        linea = [p];
        tspan = t.append("tspan").attr("x", x).attr("dy", `${interlineado}em`).text(p);
        n++;
      }
    }
    t.attr("data-lineas", n + 1);
  });
}

// Tabla HTML accesible para los <details> «Ver los datos».
export function tabla(cabeceras, filas, titulo) {
  const t = document.createElement("table");
  if (titulo) t.createCaption().textContent = titulo;
  const thead = t.createTHead().insertRow();
  cabeceras.forEach((c) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = c;
    thead.appendChild(th);
  });
  const tb = t.createTBody();
  filas.forEach((f) => {
    const tr = tb.insertRow();
    f.forEach((v, i) => {
      const c = i === 0 ? document.createElement("th") : tr.insertCell();
      if (i === 0) { c.scope = "row"; tr.appendChild(c); }
      c.textContent = v;
    });
  });
  return t;
}

// Llama a fn cuando cambia el tamaño del elemento (agrupando los avisos).
export function alRedimensionar(el, fn) {
  let t, w = 0, h = 0;
  new ResizeObserver(([e]) => {
    const { width, height } = e.contentRect;
    if (Math.abs(width - w) < 1 && Math.abs(height - h) < 1) return;
    w = width; h = height;
    clearTimeout(t); t = setTimeout(fn, 100);
  }).observe(el);
}

// Medidas del lienzo y márgenes; crea o reutiliza el <svg>.
export function medidas(contenedor, m) {
  const ancho = contenedor.clientWidth || 320;
  const alto = contenedor.clientHeight || 240;
  return { ancho, alto, m, w: Math.max(ancho - m.izquierda - m.derecha, 60), h: Math.max(alto - m.arriba - m.abajo, 60) };
}

export async function json(ruta) {
  const r = await fetch(ruta);
  if (!r.ok) throw new Error(`${ruta}: ${r.status}`);
  return r.json();
}

// Lista <li> de fuentes {titulo, url, uso} (pie de la historia y metodología).
export const listaFuentes = (l) => (l || []).map((f) =>
  `<li>${f.url ? `<a href="${f.url}">${f.titulo}</a>` : f.titulo}${f.uso ? `. ${f.uso}` : ""}</li>`).join("");
