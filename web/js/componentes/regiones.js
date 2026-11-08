// Curvas de las regiones alineadas por años desde la llegada de la avispa (paso 10), en nidos
// por cada 1.000 km² y escala logarítmica. Bizkaia en naranja; el resto en gris con etiqueta
// directa. 2018 de Bizkaia, punto hueco (registro incompleto).
// Datos: web/data/regiones.json (outputs/avispa_comparativa_regiones.csv y _meseta.csv).
import { duracion, formateador, medidas, tabla, alRedimensionar, plantilla, separar } from "../util.js";

export function crearRegiones(contenedor, datos, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const series = datos.series;
  const principal = "Bizkaia";

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const g = svg.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const gSeries = g.append("g");
  const gEtiq = g.append("g");
  const tituloX = g.append("text").attr("class", "titulo-eje").attr("text-anchor", "end");

  function dibujar(animar = true) {
    const estrecho = (contenedor.clientWidth || 320) < 480;
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: 14, derecha: estrecho ? 92 : 100, abajo: 40, izquierda: 46 });
    const dur = animar ? duracion(900) : 0;
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const todos = series.flatMap((s) => s.puntos);
    const x = d3.scaleLinear().domain([0, d3.max(todos, (p) => p.a)]).range([0, w]);
    const y = d3.scaleLog().domain([0.5, 3000]).range([h, 0]).clamp(true);
    gEjeX.attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).ticks(Math.min(13, Math.floor(w / 28))).tickFormat(fmt).tickSizeOuter(0));
    gEjeY.call(d3.axisLeft(y).tickValues([1, 10, 100, 1000]).tickFormat(fmt).tickSize(-w))
      .call((s) => s.select(".domain").remove());
    tituloX.attr("x", w).attr("y", h + 34).text(I.anios_desde_llegada);

    const orden = [...series].sort((a, b) => (a.region === principal) - (b.region === principal)); // Bizkaia encima
    const linea = d3.line().x((p) => x(p.a)).y((p) => y(p.densidad));
    const gs = gSeries.selectAll("g.serie").data(orden, (s) => s.region).join((e) => {
      const gg = e.append("g").attr("class", "serie");
      gg.append("path").attr("fill", "none");
      return gg;
    });
    gs.each(function (s) {
      const color = s.region === principal ? "var(--acento)" : "var(--gris-dato)";
      const gg = d3.select(this);
      const camino = gg.select("path").attr("stroke", color).attr("stroke-width", s.region === principal ? 3 : 2)
        .attr("d", linea(s.puntos));
      if (animar && dur) {
        const L = camino.node().getTotalLength();
        camino.attr("stroke-dasharray", `${L} ${L}`).attr("stroke-dashoffset", L)
          .transition().duration(dur).attr("stroke-dashoffset", 0).on("end", () => camino.attr("stroke-dasharray", null));
      }
      gg.selectAll("circle").data(s.puntos, (p) => p.anio).join("circle")
        .attr("r", s.region === principal ? 3.5 : 2.5)
        .attr("cx", (p) => x(p.a)).attr("cy", (p) => y(p.densidad))
        .attr("fill", (p) => (p.incompleto ? "var(--fondo)" : color))
        .attr("stroke", (p) => (p.incompleto ? "var(--gris-dato)" : color)).attr("stroke-width", 1.5);
    });

    // Etiquetas directas al final de cada curva (separadas si se pisan)
    const etiq = series.map((s) => {
      const u = s.puntos[s.puntos.length - 1];
      const texto = s.meseta && s.meseta.desde !== s.meseta.hasta
        ? plantilla(I.region_meseta, { region: s.region, v: fmt(s.meseta.densidad) }) : s.region;
      return { s, x: x(u.a) + 6, y: y(u.densidad), texto, principal: s.region === principal };
    });
    separar(etiq, 26, h);
    const ge = gEtiq.selectAll("text.region").data(etiq, (e) => e.s.region).join("text").attr("class", "region etiqueta-serie")
      .attr("fill", (e) => (e.principal ? "var(--acento-texto)" : "var(--tinta-suave)"));
    ge.attr("x", (e) => e.x).attr("y", (e) => e.y).attr("dy", "0.35em").each(function (e) {
      const t = d3.select(this).text(null);
      const [nombre, ...resto] = e.texto.split("\n");
      t.append("tspan").attr("x", e.x).text(nombre);
      if (resto.length) t.append("tspan").attr("x", e.x).attr("dy", "1.1em").attr("font-weight", 400).text(resto.join(" "));
    });
    // Nota del 2018 de Bizkaia
    const b = series.find((s) => s.region === principal);
    const p18 = b.puntos.find((p) => p.incompleto);
    gEtiq.selectAll("text.inc").data(p18 ? [p18] : []).join("text").attr("class", "inc etiqueta-nota")
      .attr("x", (p) => x(p.a)).attr("y", (p) => y(p.densidad) - 9).attr("text-anchor", "middle").attr("font-size", 11)
      .text((p) => plantilla(I.region_incompleto, { anio: p.anio }));
  }

  function tablaDatos() {
    const filas = series.flatMap((s) => s.puntos.map((p) => [s.region, p.anio, p.a, fmt(p.nidos), fmt(p.densidad),
      s.que_mide + (p.incompleto ? ` (${I.registro_incompleto})` : "")]));
    return tabla([I.region, I.anio, I.anios_desde_llegada, I.nidos, I.por_1000_km2, I.que_mide], filas);
  }

  alRedimensionar(contenedor, () => dibujar(false));
  return {
    actualizar(_, animar = true) { dibujar(animar); },
    tablaDatos,
    describir() {
      return series.filter((s) => s.meseta && s.meseta.desde !== s.meseta.hasta).map((s) =>
        plantilla(I.region_desc, { region: s.region, v: fmt(s.meseta.densidad), desde: s.meseta.desde, hasta: s.meseta.hasta }))
        .join(" ");
    },
  };
}
