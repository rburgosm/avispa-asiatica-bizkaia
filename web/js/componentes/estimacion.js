// «Dibuja tu estimación» (paso 5): la persona marca cuántos nidos cree que se avisaron cada
// temporada después de la primera del periodo; después se revela la serie real.
// En el móvil se toca la columna de cada año para fijar la altura (no se arrastra, para no
// chocar con el desplazamiento); con ratón también se puede arrastrar; con teclado, flechas.
// Estado: { revelar: false | true }
// Datos: web/data/indicadores.json (nidos avisados de abril a diciembre; 2018 incompleta).
import { duracion, formateador, medidas, rayado, tabla, alRedimensionar, plantilla, envolver, tamano } from "../util.js";
import { altoMovil } from "./tramos.js";

export function crearEstimacion(contenedor, datos, textos, periodoEl) {
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
  let revelado = false, estado = { revelar: false }, avisar = () => {}, tendFase = 0; // tendencia: 0 sin dibujar, 1 dibujándose, 2 dibujada
  const PASO = 50; // nidos por pulsación de flecha

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const patron = rayado(svg);
  const g = svg.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const gReal = g.append("g");
  const gEst = g.append("g");
  // Tendencia y etiquetas van por encima de la zona táctil: no deben capturar toques ni clics
  const gTend = g.append("g").attr("class", "tendencia").attr("opacity", 0).attr("pointer-events", "none");
  const gTendFondo = gTend.append("g"), gTendLinea = gTend.append("g"), gTendNotas = gTend.append("g");
  const gEtiq = g.append("g").attr("pointer-events", "none");
  // Textura punteada para la banda de incertidumbre de la tendencia
  const idPuntos = `puntos-${Math.random().toString(36).slice(2, 7)}`;
  const pp = svg.append("defs").append("pattern").attr("id", idPuntos).attr("patternUnits", "userSpaceOnUse").attr("width", 5).attr("height", 5);
  pp.append("circle").attr("cx", 2.5).attr("cy", 2.5).attr("r", 1.1).attr("fill", "var(--tinta)");
  svg.select("defs").append("marker").attr("id", `${idPuntos}-f`).attr("viewBox", "0 0 10 10").attr("refX", 8).attr("refY", 5)
    .attr("markerWidth", 7).attr("markerHeight", 7).attr("orient", "auto")
    .append("path").attr("d", "M0,1 L9,5 L0,9").attr("fill", "none").attr("stroke", "var(--tinta)").attr("stroke-width", 1.6);
  const ayuda = g.append("text").attr("class", "etiqueta-nota").attr("text-anchor", "middle");
  const leyenda = g.append("g").attr("class", "leyenda-svg");
  const zona = g.append("rect").attr("fill", "transparent").style("cursor", "crosshair");
  let esc = null, medida = "";

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
    const te = tamano("--t-etiqueta"), tj = tamano("--t-eje");
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: te * 2.8, derecha: 12, abajo: tj * 2, izquierda: tj * 3.6 });
    const dur = animar ? duracion(900) : 0;
    medida = `${contenedor.clientWidth}x${contenedor.clientHeight}`;
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
    // Al revelar, las columnas crecen solas una tras otra, por tiempo (sin leer el scroll)
    const reales = todas.filter((t) => t === desde || (revelado && visibles.includes(t)))
      .map((t) => ({ t, v: valor.get(t), inc: incompletas.has(t) }));
    const escalon = animar ? duracion(180) : 0;
    const retraso = new Map(reales.map((r, i) => [r.t, i * escalon]));
    gReal.selectAll("rect").data(reales, (r) => r.t).join(
      (e) => e.append("rect").attr("x", (r) => x(r.t)).attr("width", x.bandwidth()).attr("y", h).attr("height", 0),
      (u) => u,
      (s) => s.transition("salida").duration(duracion(500)).ease(d3.easeCubicInOut).attr("y", h).attr("height", 0).remove())
      .attr("fill", (r) => (r.inc ? patron : "var(--acento)"))
      .attr("stroke", (r) => (r.inc ? "var(--gris-dato)" : "none"))
      .transition().duration(dur || duracion(700)).ease(d3.easeCubicInOut).delay((r) => retraso.get(r.t))
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
    // Etiquetas: entran con un fundido cuando la barra ya ha crecido; salen con fundido
    gEtiq.selectAll("text.valor").data(etiq, (r) => r.t).join(
      (e) => e.append("text").attr("opacity", 0).call((q) => q.transition("ver").delay((r) => retraso.get(r.t) + duracion(550)).duration(duracion(350)).attr("opacity", 1)),
      (u) => u,
      (q) => q.transition("ver").duration(duracion(250)).attr("opacity", 0).remove())
      .attr("class", "valor etiqueta-valor")
      .attr("text-anchor", "middle").text((r) => fmt(r.v))
      .transition().duration(dur).attr("x", (r) => x(r.t) + x.bandwidth() / 2).attr("y", (r) => {
        const e = estimacion.get(r.t);
        const yy = y(r.v) - 5;
        return e != null && y(e) < y(r.v) && y(r.v) - y(e) < 16 ? y(e) - 5 : yy;
      });
    // Estimación propia sobre su marca (antes de revelar) para que se lea el número
    gEtiq.selectAll("text.propia").data(revelado ? [] : est.filter((r) => r.v != null), (r) => r.t)
      .join("text").attr("class", "propia etiqueta-nota").attr("text-anchor", "middle")
      
      .attr("x", (r) => x(r.t) + x.bandwidth() / 2).attr("y", (r) => y(r.v) - 5).text((r) => fmt(r.v));
    // 2018: etiqueta de registro incompleto (sobre la barra, en dos o más líneas)
    const inc = reales.filter((r) => r.inc);
    gEtiq.selectAll("text.incompleto").data(inc, (r) => r.t).join("text").attr("class", "incompleto etiqueta-nota")
      .attr("x", (r) => x(r.t)).attr("y", 0).attr("data-texto", null)
      .text(I.registro_incompleto_abril).call(envolver, Math.max(x.step() * 1.6, 145))
      .attr("y", function (r) { return y(r.v) - 8 - (+this.getAttribute("data-lineas") - 1) * te * 1.15; });

    // Tendencia log-lineal con su banda del 95 % (punteada) y la anotación de qué es la banda;
    // aparece cuando ya están todas las temporadas
    const td = datos.tendencia;
    const completa = revelado;
    if (td) {
      const xc = (t) => x(t) + x.bandwidth() / 2;
      const filas = td.temporadas.map((t, i) => ({ t, a: td.ajuste[i], lo: td.inferior[i], hi: td.superior[i] }));
      gTendFondo.selectAll("path.banda").data([filas]).join("path").attr("class", "banda")
        .attr("d", d3.area().x((r) => xc(r.t)).y0((r) => y(r.lo)).y1((r) => y(r.hi)).curve(d3.curveMonotoneX))
        .attr("fill", `url(#${idPuntos})`).attr("opacity", 0.55);
      gTendLinea.selectAll("path.linea").data([filas]).join("path").attr("class", "linea")
        .attr("d", d3.line().x((r) => xc(r.t)).y((r) => y(r.a)).curve(d3.curveMonotoneX))
        .attr("fill", "none").attr("stroke", "var(--tinta)").attr("stroke-width", 2.5);
      const u = filas[filas.length - 1];
      const pct = new Intl.NumberFormat(textos.idioma === "eu" ? "eu-ES" : "es-ES", { maximumFractionDigits: 0 }).format(td.crecimiento_anual * 100);
      gTendNotas.selectAll("text.lin").data([u]).join("text").attr("class", "lin etiqueta-serie").attr("text-anchor", "end")
        .attr("x", xc(u.t) + x.bandwidth() / 2).attr("y", y(u.hi) - te * 0.6).text(plantilla(I.tendencia_linea, { v: `+${pct} %` }));
      // Anotación de la banda: empieza en la columna de la primera temporada, por debajo de las
      // etiquetas de 2018 y de la tendencia si coinciden en horizontal, y lo más cerca posible de
      // la banda sin tocar barras ni cifras; la flecha apunta al borde de arriba de la banda en la
      // primera temporada (libre: su cifra queda dentro de la banda).
      const f00 = filas[0];
      const ax = x(f00.t);
      const t = gTendNotas.selectAll("text.anot").data([0]).join("text").attr("class", "anot etiqueta-nota").attr("x", ax).attr("y", 0);
      const lin = gTend.select("text.lin").node(), inc2018 = gEtiq.select("text.incompleto").node();
      // Se prueba de más ancho a más estrecho hasta que el texto cabe entre lo de arriba y la banda
      let top = 0, altoT = 0;
      for (let aw = Math.min(260, w * 0.62); ; aw -= 10) {
        t.attr("data-texto", null).text(I.tendencia_banda).call(envolver, aw);
        altoT = (+t.attr("data-lineas") || 1) * te * 1.15;
        const choca = (n) => { if (!n || !n.textContent) return null; const b = n.getBBox(); return b.width && b.x < ax + aw && b.x + b.width > ax ? b : null; };
        const arriba = d3.max([inc2018, lin].map(choca).filter(Boolean), (b) => b.y + b.height) ?? 0;
        // techo de lo que queda debajo: banda y cifras de las columnas que cubre el texto
        const suelo = (d3.min(filas.filter((r) => x(r.t) + x.bandwidth() > ax && x(r.t) < ax + aw),
          (r) => Math.min(y(r.hi), y(valor.get(r.t)) - te * 1.25)) ?? h) - te * 0.4;
        top = Math.max(arriba + te * 0.4, Math.min(suelo - altoT, y(f00.hi) - altoT - te * 2.6));
        if (top + altoT <= suelo || aw <= 120) break;
      }
      t.attr("y", top + te * 0.85).selectAll("tspan").attr("x", ax);
      const sx = ax + 10, sy = top + altoT + 3, ex = xc(f00.t) + 2, ey = y(f00.hi) - 3;
      gTendNotas.selectAll("path.flecha").data([0]).join("path").attr("class", "flecha").attr("fill", "none").attr("stroke", "var(--tinta)")
        .attr("stroke-width", 1.3).attr("marker-end", `url(#${idPuntos}-f)`)
        .attr("d", `M${sx},${sy} Q${sx - 6},${(sy + ey) / 2} ${ex},${ey}`)
        .attr("opacity", ey - sy > 10 ? 1 : 0);
      gTend.raise(); gEtiq.raise(); // las cifras, por encima de la línea (con su halo)
      // La línea de tendencia se traza sola por tiempo mientras crecen las columnas (1,8 s,
      // easeCubicInOut sobre stroke-dashoffset); la banda y sus notas, con un fundido al final.
      // Una vez empezada se completa aunque se salga del paso, y se queda dibujada.
      const linT = gTendLinea.select("path.linea");
      const final = () => {
        tendFase = 2;
        linT.interrupt("trazo").attr("stroke-dasharray", null).attr("stroke-dashoffset", null);
        gTendFondo.interrupt("ver").attr("opacity", 1); gTendNotas.interrupt("ver").attr("opacity", 1);
      };
      if (!completa) gTend.attr("opacity", 0);
      else if (tendFase === 0 && animar && duracion(600)) {
        tendFase = 1;
        gTend.attr("opacity", 1);
        const L = linT.node().getTotalLength();
        gTendFondo.attr("opacity", 0); gTendNotas.attr("opacity", 0);
        linT.attr("stroke-dasharray", `${L} ${L}`).attr("stroke-dashoffset", L)
          .transition("trazo").delay(escalon).duration(duracion(1800)).ease(d3.easeCubicInOut)
          .attr("stroke-dashoffset", 0).on("end", final);
        [gTendFondo, gTendNotas].forEach((gg) => gg.transition("ver").delay(escalon + duracion(1500)).duration(duracion(500)).attr("opacity", 1));
      } else if (tendFase !== 1 || !animar) { gTend.attr("opacity", 1); final(); }
    }
    // Sin contador de periodo: las temporadas ya no se revelan con el scroll
    if (periodoEl) periodoEl.textContent = "";
    const xa = Math.min(w / 2, Math.max(w / 2, (x(estimables[0]) + x(estimables[estimables.length - 1]) + x.bandwidth()) / 2));
    ayuda.attr("x", xa).attr("y", -m.arriba + te).attr("data-texto", null)
      .text(revelado ? "" : (est.every((r) => r.v != null) ? I.estimacion_lista : I.estimacion_ayuda)).call(envolver, w - 10);
    ayuda.selectAll("tspan").attr("text-anchor", "middle");

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

  // Solo se redibuja si el tamaño cambia de verdad respecto al último dibujo (y nunca con el panel
  // oculto, sin tamaño): un redibujo sin animación cortaría las columnas a medio crecer
  alRedimensionar(contenedor, () => {
    if (!contenedor.clientWidth || `${contenedor.clientWidth}x${contenedor.clientHeight}` === medida) return;
    dibujar(false);
  });
  return {
    actualizar(nuevo, animar = true) {
      estado = { revelar: false, ...nuevo };
      altoMovil(contenedor);
      // Si se sale del paso con la serie a medio revelar, se deja terminar (no se redibuja)
      if (estado.revelar && !revelado) { revelado = true; dibujar(animar); avisar(); }
      else if (!(revelado && tendFase === 1)) dibujar(false);
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
