// Línea del porcentaje de nidos que no se pudieron retirar (paso 7), con una marca vertical
// en el cambio de registro del 01/01/2023 y la media de cada tramo (2019-2022 y 2023-2025).
// 2018, punto hueco en gris (registro incompleto), fuera de la línea.
// Datos: web/data/indicadores.json (no_eliminables, nidos, pct_no_eliminables, corte_registro).
import { duracion, porcentaje, medidas, tabla, alRedimensionar, plantilla, envolver } from "../util.js";

export function crearLinea(contenedor, datos, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const pct = porcentaje(textos.idioma, 1);
  const T = datos.temporadas;
  const inc = new Set(datos.incompletas);
  const [desde, hasta] = datos.periodo;
  const corte = +datos.corte_registro.slice(0, 4);
  const puntos = T.map((t, i) => ({ t, v: datos.pct_no_eliminables[i], inc: inc.has(t),
    n: datos.nidos[i], k: datos.no_eliminables[i] }));
  const enPeriodo = puntos.filter((p) => p.t >= desde && p.t <= hasta);
  // Media de cada tramo, ponderada por nidos (suma de no eliminables / suma de avisos)
  const media = (lista) => d3.sum(lista, (p) => p.k) / d3.sum(lista, (p) => p.n);
  const tramos = [enPeriodo.filter((p) => p.t < corte), enPeriodo.filter((p) => p.t >= corte)]
    .map((l) => ({ t0: l[0].t, t1: l[l.length - 1].t, v: media(l) }));

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const g = svg.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const gCorte = g.append("g");
  const gMedias = g.append("g");
  const camino = g.append("path").attr("fill", "none").attr("stroke", "var(--acento)").attr("stroke-width", 2.5);
  const gPuntos = g.append("g");

  function dibujar(animar = true) {
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: 46, derecha: 20, abajo: 26, izquierda: 44 });
    const dur = animar ? duracion(800) : 0;
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const x = d3.scalePoint().domain(T).range([0, w]).padding(w < 400 ? 0.8 : 0.4);
    const y = d3.scaleLinear().domain([0, 0.14]).range([h, 0]);
    gEjeX.attr("transform", `translate(0,${h})`)
      .call(d3.axisBottom(x).tickSizeOuter(0).tickFormat((t) => (w < 330 ? `'${String(t).slice(2)}` : t)));
    gEjeY.call(d3.axisLeft(y).ticks(5).tickFormat((v) => pct(v).replace(",0", "")).tickSize(-w))
      .call((s) => s.select(".domain").remove());

    // Marca vertical: entre la temporada anterior al corte y la del corte
    const xc = (x(corte - 1) + x(corte)) / 2;
    gCorte.selectAll("line").data([xc]).join("line").attr("x1", (d) => d).attr("x2", (d) => d)
      .attr("y1", -8).attr("y2", h).attr("stroke", "var(--tinta)").attr("stroke-dasharray", "4 3");
    gCorte.selectAll("text").data([xc]).join("text").attr("class", "etiqueta-serie").attr("fill", "var(--tinta)")
      .attr("x", (d) => d - 4).attr("y", -30).attr("text-anchor", "end").attr("data-texto", null)
      .text(I.cambia_registro).call(envolver, Math.max(xc - 8, 80));

    // Medias de cada tramo (líneas grises discontinuas con etiqueta)
    const mg = gMedias.selectAll("g").data(tramos).join((e) => {
      const gg = e.append("g");
      gg.append("line").attr("stroke", "var(--tinta-suave)").attr("stroke-dasharray", "2 3");
      gg.append("text").attr("class", "etiqueta-nota").attr("text-anchor", "middle");
      return gg;
    });
    mg.select("line").attr("x1", (d) => x(d.t0) - 8).attr("x2", (d) => x(d.t1) + 8)
      .attr("y1", (d) => y(d.v)).attr("y2", (d) => y(d.v));
    // La etiqueta de cada media va abajo, en la franja vacía del gráfico, centrada en su tramo
    const bordes = [x(desde) - x.step() / 2, xc, x(hasta) + x.step() / 2];
    mg.select("text").attr("x", (d, i) => (bordes[i] + bordes[i + 1]) / 2).attr("y", y(0.025))
      .attr("data-texto", null).text((d) => plantilla(I.media_tramo, { v: pct(d.v), desde: d.t0, hasta: d.t1 }))
      .each(function (d, i) { d3.select(this).call(envolver, bordes[i + 1] - bordes[i] - 10); });

    const linea = d3.line().x((p) => x(p.t)).y((p) => y(p.v));
    camino.transition().duration(dur).attr("d", linea(enPeriodo));
    if (animar && dur) {
      const L = camino.node().getTotalLength();
      camino.attr("stroke-dasharray", `${L} ${L}`).attr("stroke-dashoffset", L)
        .transition().duration(dur).attr("stroke-dashoffset", 0).on("end", () => camino.attr("stroke-dasharray", null));
    }

    const gp = gPuntos.selectAll("g").data(puntos, (p) => p.t).join((e) => {
      const gg = e.append("g");
      gg.append("circle").attr("r", 4);
      gg.append("text").attr("class", "etiqueta-valor").attr("text-anchor", "middle");
      return gg;
    });
    gp.attr("transform", (p) => `translate(${x(p.t)},${y(p.v)})`);
    gp.select("circle").attr("fill", (p) => (p.inc ? "var(--fondo)" : "var(--acento)"))
      .attr("stroke", (p) => (p.inc ? "var(--gris-dato)" : "var(--acento)")).attr("stroke-width", 2);
    gp.select("text").attr("y", -9).attr("font-size", w < 330 ? 10 : 12)
      .attr("fill", (p) => (p.inc ? "var(--tinta-suave)" : "var(--tinta)")).text((p) => pct(p.v));
    gp.selectAll("text.inc").data((p) => (p.inc ? [p] : [])).join("text").attr("class", "inc etiqueta-nota")
      .attr("x", -6).attr("y", 20).attr("text-anchor", "start").attr("font-size", 11).attr("data-texto", null)
      .text(I.registro_incompleto).call(envolver, Math.max(x.step() * 1.1, 60));
  }

  function tablaDatos() {
    return tabla([I.temporada, I.no_eliminables, I.avisos, "%"],
      puntos.map((p) => [p.t + (p.inc ? ` (${I.registro_incompleto})` : ""), p.k, p.n, pct(p.v)]));
  }

  alRedimensionar(contenedor, () => dibujar(false));
  return {
    actualizar(_, animar = true) { dibujar(animar); },
    tablaDatos,
    describir() {
      return plantilla(I.linea_desc, { a: pct(tramos[0].v), b: pct(tramos[1].v), corte,
        d0: tramos[0].t0, d1: tramos[0].t1, e0: tramos[1].t0, e1: tramos[1].t1 });
    },
  };
}
