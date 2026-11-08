// Barras apiladas horizontales (paso 6): reparto de los días entre el aviso y la retirada en
// cada temporada (mismo día, 1-3, 4-7, más de 7 días). Un solo tono (azul, acción pública) en
// intensidad decreciente; «más de 7 días» en gris. 2018, rayada como registro incompleto.
// Datos: web/data/indicadores.json (tramos, pct_le7).
import { duracion, porcentaje, medidas, rayado, tabla, alRedimensionar, plantilla } from "../util.js";

const OPACIDAD = [1, 0.72, 0.45];

export function crearTramos(contenedor, datos, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const pct = porcentaje(textos.idioma, 0);
  const pct1 = porcentaje(textos.idioma, 1);
  const T = datos.temporadas;
  const inc = new Set(datos.incompletas);
  const claves = datos.tramos.claves;
  const filas = T.map((t, i) => {
    let acum = 0;
    return { t, inc: inc.has(t), le7: datos.pct_le7[i],
      seg: datos.tramos.valores[i].map((v, k) => ({ k, v, x0: acum, x1: (acum += v), t })) };
  });

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const patron = rayado(svg);
  const g = svg.append("g");
  const gLeyenda = g.append("g");
  const gFilas = g.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const cab7 = g.append("text").attr("class", "etiqueta-nota").attr("text-anchor", "end");

  const color = (k) => (k < 3 ? "var(--acento-2)" : "var(--gris-dato)");

  function dibujar(animar = true) {
    const estrecho = (contenedor.clientWidth || 320) < 480;
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: estrecho ? 64 : 44, derecha: 58, abajo: 22, izquierda: 40 });
    const dur = animar ? duracion(700) : 0;
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const x = d3.scaleLinear().domain([0, 1]).range([0, w]);
    const y = d3.scaleBand().domain(T).range([0, h]).padding(0.22);

    gEjeX.attr("transform", `translate(0,${h})`)
      .call(d3.axisBottom(x).ticks(4).tickFormat((v) => pct(v)).tickSizeOuter(0));

    // Leyenda directa: los cuatro tramos en una o dos filas
    const items = claves.map((k, i) => ({ i, t: I.tramos[k] }));
    const li = gLeyenda.selectAll("g").data(items).join((e) => {
      const gg = e.append("g");
      gg.append("rect").attr("width", 12).attr("height", 10).attr("y", -9);
      gg.append("text").attr("x", 16).attr("class", "etiqueta-nota");
      return gg;
    });
    li.select("rect").attr("fill", (d) => color(d.i)).attr("opacity", (d) => (d.i < 3 ? OPACIDAD[d.i] : 1));
    li.select("text").text((d) => d.t);
    let cx = 0, cy = -(m.arriba - 16);
    li.attr("transform", function () {
      const bw = this.getBBox().width;
      if (cx > 0 && cx + bw > w + m.derecha) { cx = 0; cy += 18; }
      const tr = `translate(${cx},${cy})`;
      cx += bw + 14;
      return tr;
    });
    cab7.attr("x", w + m.derecha - 2).attr("y", -6).text(I.en_7_dias);

    const fila = gFilas.selectAll("g.fila").data(filas, (f) => f.t).join((e) => {
      const gg = e.append("g").attr("class", "fila");
      gg.append("text").attr("class", "anio eje").attr("text-anchor", "end").attr("dy", "0.35em");
      gg.append("text").attr("class", "le7 etiqueta-valor").attr("text-anchor", "end").attr("dy", "0.35em");
      gg.append("rect").attr("class", "velo");
      return gg;
    });
    fila.attr("transform", (f) => `translate(0,${y(f.t)})`);
    fila.select(".anio").attr("x", -6).attr("y", y.bandwidth() / 2).attr("fill", "var(--tinta-suave)")
      .attr("font-size", 12).text((f) => f.t);
    fila.select(".le7").attr("x", w + m.derecha - 2).attr("y", y.bandwidth() / 2)
      .attr("fill", (f) => (f.inc ? "var(--tinta-suave)" : "var(--tinta)")).text((f) => pct1(f.le7));
    fila.selectAll("rect.seg").data((f) => f.seg, (s) => s.k).join(
      (e) => e.insert("rect", ".velo").attr("class", "seg").attr("x", 0).attr("width", 0))
      .attr("y", 0).attr("height", y.bandwidth())
      .attr("fill", (s) => color(s.k)).attr("opacity", (s) => (s.k < 3 ? OPACIDAD[s.k] : 1))
      .attr("stroke", "var(--fondo)").attr("stroke-width", 1)
      .transition().duration(dur).delay((s) => s.k * 120)
      .attr("x", (s) => x(s.x0)).attr("width", (s) => Math.max(0, x(s.x1) - x(s.x0)));
    // 2018 tapada con el rayado (registro incompleto) y su etiqueta
    fila.select(".velo").attr("x", 0).attr("y", 0).attr("height", y.bandwidth())
      .attr("width", (f) => (f.inc ? w : 0)).attr("fill", patron).attr("opacity", 0.75);
    fila.selectAll("text.inc").data((f) => (f.inc ? [f] : [])).join("text").attr("class", "inc etiqueta-valor")
      .attr("x", 6).attr("y", y.bandwidth() / 2).attr("dy", "0.35em").attr("font-size", 11)
      .text(I.registro_incompleto);
    // Porcentaje dentro de cada tramo si cabe
    fila.selectAll("text.v").data((f) => (f.inc ? [] : f.seg.filter((s) => x(s.x1) - x(s.x0) > 30)), (s) => s.k)
      .join("text").attr("class", "v").attr("text-anchor", "middle").attr("dy", "0.35em").attr("font-size", 11)
      .attr("fill", (s) => (s.k < 2 ? "var(--blanco)" : "var(--tinta)"))
      .attr("x", (s) => x((s.x0 + s.x1) / 2)).attr("y", y.bandwidth() / 2).text((s) => pct(s.v));
  }

  function tablaDatos() {
    return tabla([I.temporada, ...claves.map((k) => I.tramos[k]), I.en_7_dias],
      filas.map((f) => [f.t + (f.inc ? ` (${I.registro_incompleto})` : ""), ...f.seg.map((s) => pct1(s.v)), pct1(f.le7)]));
  }

  alRedimensionar(contenedor, () => dibujar(false));
  return {
    actualizar(_, animar = true) { dibujar(animar); },
    tablaDatos,
    describir() {
      const p = filas.filter((f) => !f.inc);
      return plantilla(I.tramos_desc, { min: pct1(d3.min(p, (f) => f.le7)), max: pct1(d3.max(p, (f) => f.le7)),
        desde: p[0].t, hasta: p[p.length - 1].t });
    },
  };
}
