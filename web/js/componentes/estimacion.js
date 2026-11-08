// «Dibuja tu estimación» (paso 5): la persona marca cuántos nidos cree que se avisaron cada
// temporada después de la primera del periodo; después se revela la serie real.
// En el móvil se toca la columna de cada año para fijar la altura (no se arrastra, para no
// chocar con el desplazamiento); con ratón también se puede arrastrar; con teclado, flechas.
// Estado: { revelar: false | true }
// Datos: web/data/indicadores.json (nidos avisados de abril a diciembre; 2018 incompleta).
import { duracion, formateador, medidas, rayado, tabla, alRedimensionar, plantilla, envolver } from "../util.js";

export function crearEstimacion(contenedor, datos, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const [desde, hasta] = datos.periodo;
  const todas = datos.temporadas;
  const valor = new Map(todas.map((t, i) => [t, datos.nidos[i]]));
  const incompletas = new Set(datos.incompletas);
  const periodo = todas.filter((t) => t >= desde && t <= hasta);
  const estimables = periodo.slice(1); // la primera temporada se da como punto de partida
  const estimacion = new Map(estimables.map((t) => [t, null]));
  let revelado = false, estado = { revelar: false }, avisar = () => {};
  const PASO = 50; // nidos por pulsación de flecha

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const patron = rayado(svg);
  const g = svg.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const gReal = g.append("g");
  const gEst = g.append("g");
  const gEtiq = g.append("g");
  const ayuda = g.append("text").attr("class", "etiqueta-nota").attr("text-anchor", "middle");
  const leyenda = g.append("g").attr("class", "leyenda-svg");
  const zona = g.append("rect").attr("fill", "transparent").style("cursor", "crosshair");
  let esc = null;

  function fijar(evento) {
    if (revelado || !esc) return;
    const [px, py] = d3.pointer(evento, g.node());
    const t = esc.x.domain().find((d) => px >= esc.x(d) - esc.x.step() * esc.x.padding() / 2 &&
                                          px <= esc.x(d) + esc.x.bandwidth() + esc.x.step() * esc.x.padding() / 2);
    if (!estimacion.has(t)) return;
    const v = Math.max(0, Math.min(esc.y.domain()[1], esc.y.invert(py)));
    estimacion.set(t, Math.round(v / 10) * 10);
    dibujar(false);
  }
  zona.on("click", fijar)
    .on("pointermove", (e) => { if (e.pointerType === "mouse" && e.buttons === 1) fijar(e); })
    .on("pointerdown", (e) => { if (e.pointerType === "mouse") fijar(e); });

  function dibujar(animar = true) {
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: 40, derecha: 12, abajo: 26, izquierda: 46 });
    const dur = animar ? duracion(900) : 0;
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const visibles = revelado ? todas : periodo;
    const x = d3.scaleBand().domain(todas).range([0, w]).padding(0.28);
    const y = d3.scaleLinear().domain([0, d3.max(datos.nidos) * 1.1]).nice().range([h, 0]);
    esc = { x, y };
    zona.attr("x", x(estimables[0]) - x.step() * x.padding() / 2).attr("y", 0)
      .attr("width", x(estimables[estimables.length - 1]) + x.bandwidth() - x(estimables[0]) + x.step() * x.padding())
      .attr("height", h).style("display", revelado ? "none" : null);

    gEjeX.attr("transform", `translate(0,${h})`)
      .call(d3.axisBottom(x).tickSizeOuter(0).tickFormat((t) => (w < 330 ? `'${String(t).slice(2)}` : t)))
      .selectAll(".tick").attr("opacity", (t) => (visibles.includes(t) ? 1 : 0));
    gEjeY.call(d3.axisLeft(y).ticks(5).tickFormat(fmt).tickSize(-w)).call((s) => s.select(".domain").remove());

    // Barras reales: la primera del periodo siempre; el resto al revelar. 2018, rayada.
    const reales = todas.filter((t) => t === desde || (revelado && visibles.includes(t)))
      .map((t) => ({ t, v: valor.get(t), inc: incompletas.has(t) }));
    gReal.selectAll("rect").data(reales, (r) => r.t).join(
      (e) => e.append("rect").attr("x", (r) => x(r.t)).attr("width", x.bandwidth()).attr("y", h).attr("height", 0),
      (u) => u,
      (s) => s.remove())
      .attr("fill", (r) => (r.inc ? patron : "var(--acento)"))
      .attr("stroke", (r) => (r.inc ? "var(--gris-dato)" : "none"))
      .transition().duration(dur).delay((r, i) => (animar ? i * 80 : 0))
      .attr("x", (r) => x(r.t)).attr("width", x.bandwidth())
      .attr("y", (r) => y(r.v)).attr("height", (r) => h - y(r.v));

    // Estimaciones: hueco discontinuo si falta; barra con contorno de tinta si se ha marcado.
    const est = estimables.map((t) => ({ t, v: estimacion.get(t) }));
    const ge = gEst.selectAll("g.barra-estimacion").data(est, (r) => r.t).join((e) => {
      const gg = e.append("g").attr("class", "barra-estimacion").attr("tabindex", 0).attr("role", "slider")
        .attr("aria-valuemin", 0);
      gg.append("rect").attr("class", "hueco");
      gg.append("rect").attr("class", "marca");
      gg.append("text").attr("class", "interrogante etiqueta-nota").attr("text-anchor", "middle");
      return gg;
    });
    ge.attr("aria-label", (r) => plantilla(I.estimacion_aria, { temporada: r.t }))
      .attr("aria-valuemax", Math.round(y.domain()[1]))
      .attr("aria-valuenow", (r) => r.v ?? 0)
      .attr("aria-valuetext", (r) => (r.v == null ? I.estimacion_sin_marcar : `${fmt(r.v)} ${I.nidos}`));
    ge.select(".hueco").attr("x", (r) => x(r.t)).attr("width", x.bandwidth()).attr("y", 0).attr("height", h)
      .attr("fill", "none").attr("stroke", "var(--linea)").attr("stroke-dasharray", "3 3")
      .attr("opacity", revelado ? 0 : 1);
    ge.select(".marca").attr("x", (r) => x(r.t) - (revelado ? 4 : 0)).attr("width", x.bandwidth() + (revelado ? 8 : 0))
      .attr("y", (r) => (r.v == null ? h : y(r.v) - (revelado ? 1.5 : 0)))
      .attr("height", (r) => (r.v == null ? 0 : revelado ? 3 : h - y(r.v)))
      .attr("fill", revelado ? "var(--tinta)" : "var(--sombra-zona)").attr("stroke", revelado ? "none" : "var(--tinta)")
      .attr("stroke-width", 2);
    if (revelado) gEst.raise(); else gEst.lower();
    ge.select(".interrogante").attr("x", (r) => x(r.t) + x.bandwidth() / 2).attr("y", h - 8)
      .text((r) => (r.v == null && !revelado ? "?" : ""));

    // Etiquetas de valor: la primera del periodo y, al revelar, todas las del periodo.
    const etiq = reales.filter((r) => !r.inc && (revelado || r.t === desde));
    gEtiq.selectAll("text.valor").data(etiq, (r) => r.t).join("text").attr("class", "valor etiqueta-valor")
      .attr("text-anchor", "middle").attr("font-size", w < 330 ? 10 : 12).text((r) => fmt(r.v))
      .transition().duration(dur).attr("x", (r) => x(r.t) + x.bandwidth() / 2).attr("y", (r) => {
        const e = estimacion.get(r.t);
        const yy = y(r.v) - 5;
        return e != null && y(e) < y(r.v) && y(r.v) - y(e) < 16 ? y(e) - 5 : yy;
      });
    // Estimación propia sobre su marca (antes de revelar) para que se lea el número
    gEtiq.selectAll("text.propia").data(revelado ? [] : est.filter((r) => r.v != null), (r) => r.t)
      .join("text").attr("class", "propia etiqueta-nota").attr("text-anchor", "middle")
      .attr("font-size", w < 330 ? 10 : 12)
      .attr("x", (r) => x(r.t) + x.bandwidth() / 2).attr("y", (r) => y(r.v) - 5).text((r) => fmt(r.v));
    // 2018: etiqueta de registro incompleto (sobre la barra, en dos o más líneas)
    const inc = reales.filter((r) => r.inc);
    gEtiq.selectAll("text.incompleto").data(inc, (r) => r.t).join("text").attr("class", "incompleto etiqueta-nota")
      .attr("x", (r) => x(r.t)).attr("y", (r) => y(r.v) - 30).attr("data-texto", null)
      .text(I.registro_incompleto_abril).call(envolver, Math.max(x.step() * 1.6, 90));

    ayuda.attr("x", (x(estimables[0]) + x(estimables[estimables.length - 1]) + x.bandwidth()) / 2).attr("y", -24)
      .text(revelado ? "" : (est.every((r) => r.v != null) ? I.estimacion_lista : I.estimacion_ayuda));

    // Leyenda directa al revelar: barra naranja = avisos reales; contorno discontinuo = tu estimación
    const items = revelado ? [{ k: "real", t: I.avisos_reales }, ...(est.some((r) => r.v != null) ? [{ k: "est", t: I.tu_estimacion }] : [])] : [];
    const li = leyenda.attr("transform", "translate(0,-24)").selectAll("g").data(items, (d) => d.k).join((e) => {
      const gg = e.append("g");
      gg.append("rect").attr("width", 14).attr("height", 10).attr("y", -9);
      gg.append("text").attr("x", 19).attr("class", "etiqueta-nota");
      return gg;
    });
    li.select("rect").attr("fill", (d) => (d.k === "real" ? "var(--acento)" : "var(--tinta)"))
      .attr("height", (d) => (d.k === "real" ? 10 : 3)).attr("y", (d) => (d.k === "real" ? -9 : -5));
    li.select("text").text((d) => d.t);
    let xx = 0;
    li.attr("transform", function () {
      const tx = xx;
      xx += this.getBBox().width + 16;
      return `translate(${tx},0)`;
    });
  }

  gEst.on("keydown", (e) => {
    const t = d3.select(e.target).datum()?.t;
    if (revelado || !estimacion.has(t) || !["ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    const v = estimacion.get(t) ?? valor.get(desde);
    estimacion.set(t, Math.max(0, v + (e.key === "ArrowUp" ? PASO : -PASO)));
    dibujar(false);
  });

  function revelar() {
    if (revelado) return;
    revelado = true;
    dibujar(true);
    avisar();
  }

  function tablaDatos() {
    return tabla([I.temporada, I.avisos_reales],
      todas.map((t) => [t + (incompletas.has(t) ? ` (${I.registro_incompleto})` : ""), fmt(valor.get(t))]));
  }

  alRedimensionar(contenedor, () => dibujar(false));
  return {
    actualizar(nuevo, animar = true) {
      estado = { revelar: false, ...nuevo };
      if (estado.revelar && !revelado) { revelado = true; dibujar(animar); avisar(); } else dibujar(false);
    },
    revelar,
    alRevelar(fn) { avisar = fn; },
    tablaDatos,
    describir() {
      return revelado
        ? plantilla(I.estimacion_desc_real, { desde, hasta, inicio: fmt(valor.get(desde)), fin: fmt(valor.get(hasta)) })
        : plantilla(I.estimacion_desc, { desde, inicio: fmt(valor.get(desde)) });
    },
  };
}
