// Calendario de avisos (pasos 8 y 9): porcentaje de los avisos de 2019-2025 que llega en cada
// mes, solo de abril a diciembre (enero-marzo no es comparable entre años).
// Estado: { resaltar: "primavera" | "noviembre" }
//   primavera: abril-junio en naranja, resto en gris, con el total de la estación.
//   noviembre: zona sombreada desde el 1 de noviembre y el rango de nidos retirados después.
// Datos: web/data/mensual.json y web/data/indicadores.json (pct_elim_despues_1nov).
import { duracion, porcentaje, medidas, tabla, alRedimensionar, plantilla, envolver, formateador } from "../util.js";

export function crearMensual(contenedor, { mensual, indicadores }, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const pct = porcentaje(textos.idioma, 1);
  const fmt = formateador(textos.idioma, 0);
  const meses = mensual.meses;
  const filas = meses.map((mm, i) => ({ mm, v: mensual.proporcion_total[i] }));
  const [desde, hasta] = indicadores.periodo;
  const despues = indicadores.temporadas.map((t, i) => ({ t, v: indicadores.pct_elim_despues_1nov[i] }))
    .filter((r) => r.t >= desde && r.t <= hasta);
  let estado = { resaltar: "primavera" };

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const g = svg.append("g");
  const zona = g.append("rect").attr("fill", "var(--sombra-zona)");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const gBarras = g.append("g");
  const gEtiq = g.append("g");
  const anot = g.append("g");

  const enZona = (mm) => (estado.resaltar === "primavera" ? mm >= 4 && mm <= 6 : mm >= 11);

  function dibujar(animar = true) {
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: 64, derecha: 8, abajo: 26, izquierda: 40 });
    const dur = animar ? duracion(600) : 0;
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const x = d3.scaleBand().domain(meses).range([0, w]).padding(0.2);
    const y = d3.scaleLinear().domain([0, d3.max(filas, (f) => f.v) * 1.12]).range([h, 0]);
    gEjeX.attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).tickSizeOuter(0)
      .tickFormat((mm) => I.meses[mm - 1]));
    gEjeY.call(d3.axisLeft(y).ticks(4).tickFormat((v) => pct(v).replace(",0", "")).tickSize(-w))
      .call((s) => s.select(".domain").remove());

    const prim = estado.resaltar === "primavera";
    const z0 = prim ? x(4) - x.step() * x.padding() / 2 : x(11) - x.step() * x.padding() / 2;
    const z1 = prim ? x(6) + x.bandwidth() + x.step() * x.padding() / 2 : w;
    zona.transition().duration(dur).attr("x", z0).attr("width", z1 - z0).attr("y", -m.arriba + 4).attr("height", h + m.arriba - 4);

    gBarras.selectAll("rect").data(filas, (f) => f.mm).join(
      (e) => e.append("rect").attr("x", (f) => x(f.mm)).attr("y", h).attr("height", 0))
      .attr("width", x.bandwidth())
      .transition().duration(dur)
      .attr("x", (f) => x(f.mm)).attr("y", (f) => y(f.v)).attr("height", (f) => h - y(f.v))
      .attr("fill", (f) => (enZona(f.mm) ? "var(--acento)" : "var(--gris-dato)"));
    gEtiq.selectAll("text").data(filas, (f) => f.mm).join("text").attr("class", "etiqueta-valor")
      .attr("text-anchor", "middle").attr("font-size", w < 360 ? 10 : 12)
      .attr("fill", (f) => (enZona(f.mm) ? "var(--tinta)" : "var(--tinta-suave)"))
      .text((f) => pct(f.v).replace(" %", w < 360 ? "" : " %"))
      .transition().duration(dur).attr("x", (f) => x(f.mm) + x.bandwidth() / 2).attr("y", (f) => y(f.v) - 5);

    // Anotación de la zona: total de primavera o rango de retirados después del 1 de noviembre
    const texto = prim
      ? plantilla(I.mensual_primavera, { v: pct(mensual.estaciones.primavera) })
      : plantilla(I.mensual_noviembre, { min: pct(d3.min(despues, (r) => r.v)), max: pct(d3.max(despues, (r) => r.v)) });
    const ta = anot.selectAll("text").data([texto]).join("text").attr("class", "etiqueta-serie")
      .attr("fill", "var(--tinta)").attr("data-texto", null);
    const anchoZona = z1 - z0;
    const izquierda = !prim && anchoZona < 150; // en el móvil, la nota de noviembre va a la izquierda de la zona
    ta.attr("x", izquierda ? z1 - 4 : z0 + 6).attr("y", -m.arriba + 20)
      .attr("text-anchor", izquierda ? "end" : "start").text(texto)
      .call(envolver, izquierda ? Math.min(w * 0.75, 260) : Math.max(anchoZona - 10, 120));
    // Si la nota se extiende más allá de la zona en primavera, se deja: el fondo es el del gráfico.
    if (izquierda) ta.selectAll("tspan").attr("text-anchor", "end");
    ta.attr("opacity", 0).transition().duration(dur).attr("opacity", 1);
  }

  function tablaDatos() {
    const T = Object.keys(mensual.temporadas);
    return tabla([I.mes, `${I.porcentaje} ${T[0]}-${T[T.length - 1]}`, ...T],
      meses.map((mm, i) => [I.meses_largos[mm - 1], pct(mensual.proporcion_total[i]),
        ...T.map((t) => fmt(mensual.temporadas[t][i]))]));
  }

  alRedimensionar(contenedor, () => dibujar(false));
  return {
    actualizar(nuevo, animar = true) { estado = { resaltar: "primavera", ...nuevo }; dibujar(animar); },
    tablaDatos,
    describir() {
      const max = filas.reduce((a, b) => (b.v > a.v ? b : a));
      return plantilla(I.mensual_desc, { primavera: pct(mensual.estaciones.primavera), verano: pct(mensual.estaciones.verano),
        otono: pct(mensual.estaciones.otono), mes: I.meses_largos[max.mm - 1], max: pct(max.v) });
    },
  };
}
