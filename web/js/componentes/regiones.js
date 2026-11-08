// Curvas de las regiones alineadas por años desde la llegada de la avispa (paso 10), en nidos
// por cada 1.000 km² y escala logarítmica. Bizkaia en naranja grueso (la avispa en Bizkaia); el
// resto, en gris con su nombre al final de la línea (contexto; Gipuzkoa, que acaba pronto, al principio). Las líneas se dibujan a la vez, solas
// por tiempo al entrar el paso (sin leer el scroll), y cada etiqueta aparece cuando su línea termina.
// 2018 de Bizkaia, punto hueco (registro incompleto). Sin contador de periodo (periodoEl vacío).
// Datos: web/data/regiones.json (outputs/avispa_comparativa_regiones.csv y _meseta.csv).
import { duracion, formateador, medidas, tabla, alRedimensionar, plantilla, separar, tamano } from "../util.js";

let nClip = 0;
const DIBUJO = 2000; // ms que tarda el trazo de las líneas

export function crearRegiones(contenedor, datos, textos, periodoEl) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const series = datos.series;
  const principal = "Bizkaia";
  const esP = (s) => s.region === principal;
  const color = (s) => (esP(s) ? "var(--acento)" : "var(--gris-dato)");
  const colorTexto = (s) => (esP(s) ? "var(--acento-texto)" : "var(--tinta-suave)");
  if (periodoEl) periodoEl.textContent = "";

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const idClip = `clip-regiones-${++nClip}`;
  const clip = svg.append("defs").append("clipPath").attr("id", idClip).append("rect");
  const g = svg.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const gSeries = g.append("g").attr("clip-path", `url(#${idClip})`);
  const gEtiq = g.append("g");
  const tituloX = g.append("text").attr("class", "titulo-eje").attr("text-anchor", "end");

  let esc = null, fase = 0, medida = ""; // fase: 0 sin empezar, 1 dibujando, 2 dibujadas

  function dibujar() {
    const estrecho = (contenedor.clientWidth || 320) < 480;
    const te = tamano("--t-etiqueta"), tj = tamano("--t-eje");
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: te, derecha: te * (estrecho ? 6.6 : 7.4), abajo: tj * 3, izquierda: tj * 3.4 });
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    medida = `${contenedor.clientWidth}x${contenedor.clientHeight}`;
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const todos = series.flatMap((s) => s.puntos);
    const amax = d3.max(todos, (p) => p.a);
    const x = d3.scaleLinear().domain([0, amax]).range([0, w]);
    const y = d3.scaleLog().domain([0.5, 3000]).range([h, 0]).clamp(true);
    esc = { x, y, w, h, amax };
    gEjeX.attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).ticks(Math.min(13, Math.floor(w / 28))).tickFormat(fmt).tickSizeOuter(0));
    gEjeY.call(d3.axisLeft(y).tickValues([1, 10, 100, 1000]).tickFormat(fmt).tickSize(-w))
      .call((s) => s.select(".domain").remove());
    tituloX.attr("x", w).attr("y", h + tj * 2.6).text(I.anios_desde_llegada);
    // El recorte cubre también los puntos que sobresalen del eje
    clip.attr("x", -8).attr("y", -m.arriba).attr("height", h + m.arriba + 8);

    const orden = [...series].sort((a, b) => esP(a) - esP(b)); // Bizkaia encima
    const linea = d3.line().x((p) => x(p.a)).y((p) => y(p.densidad));
    const gs = gSeries.selectAll("g.serie").data(orden, (s) => s.region).join((e) => {
      const gg = e.append("g").attr("class", "serie");
      gg.append("path").attr("fill", "none").attr("stroke-linejoin", "round").attr("stroke-linecap", "round");
      return gg;
    });
    gs.each(function (s) {
      const gg = d3.select(this);
      gg.select("path").attr("stroke", color(s)).attr("stroke-width", esP(s) ? 4 : 2).attr("d", linea(s.puntos));
      gg.selectAll("circle").data(s.puntos, (p) => p.anio).join("circle")
        .attr("r", esP(s) ? 4 : 2.6)
        .attr("cx", (p) => x(p.a)).attr("cy", (p) => y(p.densidad))
        .attr("fill", (p) => (p.incompleto ? "var(--fondo)" : color(s)))
        .attr("stroke", (p) => (p.incompleto ? "var(--acento)" : "var(--fondo)")).attr("stroke-width", (p) => (p.incompleto ? 2 : 1));
    });

    // Etiquetas directas al final de cada curva (separadas si se pisan)
    // Una serie que termina pronto (Gipuzkoa, hasta 2015) lleva el nombre a la izquierda de su
    // primer punto: a la derecha de su final la cruzan las curvas que siguen subiendo.
    const etiq = series.map((s) => {
      const u = s.puntos[s.puntos.length - 1], p0 = s.puntos[0];
      const texto = s.meseta && s.meseta.desde !== s.meseta.hasta
        ? plantilla(I.region_meseta, { region: s.region, v: fmt(s.meseta.densidad) }) : s.region;
      const corta = u.a < amax * 0.6;
      return corta ? { s, a: u.a, x: x(p0.a) - 8, y: y(p0.densidad), texto, ancla: "end" }
        : { s, a: u.a, x: x(u.a) + 8, y: y(u.densidad), texto, ancla: "start" };
    });
    separar(etiq.filter((e) => e.ancla === "start"), te * 2.3, h);
    const ge = gEtiq.selectAll("text.region").data(etiq, (e) => e.s.region)
      .join((e) => e.append("text").attr("class", "region etiqueta-serie").attr("opacity", 0))
      .attr("fill", (e) => colorTexto(e.s));
    ge.attr("x", (e) => e.x).attr("y", (e) => e.y).attr("dy", "0.35em").attr("text-anchor", (e) => e.ancla).each(function (e) {
      const t = d3.select(this).text(null);
      const [nombre, ...resto] = e.texto.split("\n");
      t.append("tspan").attr("x", e.x).attr("font-weight", esP(e.s) ? 700 : 600).text(nombre);
      if (resto.length) t.append("tspan").attr("x", e.x).attr("dy", "1.1em").attr("font-weight", 400).text(resto.join(" "));
    });
    // Nota del 2018 de Bizkaia
    const b = series.find(esP);
    const p18 = b.puntos.find((p) => p.incompleto);
    gEtiq.selectAll("text.inc").data(p18 ? [p18] : []).join((e) => e.append("text").attr("class", "inc etiqueta-nota").attr("opacity", 0))
      .attr("x", (p) => x(p.a)).attr("y", (p) => y(p.densidad) - 11).attr("text-anchor", "middle")
      .text((p) => plantilla(I.region_incompleto, { anio: p.anio }));
  }

  function tablaDatos() {
    const filas = series.flatMap((s) => s.puntos.map((p) => [s.region, p.anio, p.a, fmt(p.nidos), fmt(p.densidad),
      s.que_mide + (p.incompleto ? ` (${I.registro_incompleto})` : "")]));
    return tabla([I.region, I.anio, I.anios_desde_llegada, I.nidos, I.por_1000_km2, I.que_mide], filas);
  }

  // Trazo por tiempo: el recorte avanza por los años desde la llegada (2 s, easeCubicInOut) y cada
  // etiqueta aparece con un fundido cuando su línea termina. Una vez empezado se completa aunque
  // el lector salga del paso, y las líneas se quedan dibujadas durante la parada (al volver no se
  // repite; el paso siguiente las reutiliza).
  function ver(sel, aFin, animar) {
    sel.each(function (e) {
      const v = aFin >= e.a - 1e-6 ? 1 : 0;
      if (this.__v === v) return;
      this.__v = v;
      const t = d3.select(this).interrupt("ver");
      if (animar) t.transition("ver").duration(duracion(450)).attr("opacity", v); else t.attr("opacity", v);
    });
  }
  function pintar(aFin, animar) {
    if (!esc) return;
    const { x, amax, w } = esc;
    clip.attr("width", aFin >= amax ? w + 16 + 200 : Math.max(0, x(aFin) + 8));
    ver(gEtiq.selectAll("text.region"), aFin, animar);
    ver(gEtiq.selectAll("text.inc"), aFin, animar);
  }
  function empezar() {
    if (fase || !esc) return;
    if (!duracion(600)) { fase = 2; pintar(Infinity, false); return; }
    fase = 1; pintar(-1, false);
    clip.transition("trazo").duration(DIBUJO).ease(d3.easeCubicInOut)
      .tween("trazo", () => (k) => pintar(k < 1 ? k * esc.amax : Infinity, true))
      .on("end", () => { fase = 2; pintar(Infinity, true); });
  }

  // Durante el trazo, el tamaño nuevo lo recoge el propio trazo en el fotograma siguiente
  alRedimensionar(contenedor, () => {
    if (!contenedor.clientWidth || `${contenedor.clientWidth}x${contenedor.clientHeight}` === medida) return;
    dibujar(); if (fase === 2) pintar(Infinity, false);
  });
  return {
    actualizar(_, animar = true, recienMostrado = false) {
      if (periodoEl) periodoEl.textContent = "";
      dibujar();
      if (fase === 0) empezar(); else if (fase === 2) pintar(Infinity, false);
    },
    tablaDatos,
    describir() {
      return series.filter((s) => s.meseta && s.meseta.desde !== s.meseta.hasta).map((s) =>
        plantilla(I.region_desc, { region: s.region, v: fmt(s.meseta.densidad), desde: s.meseta.desde, hasta: s.meseta.hasta }))
        .join(" ");
    },
  };
}
