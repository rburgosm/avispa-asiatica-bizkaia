// Gasto identificable en la retirada de nidos, 2017-2025 (paso 11), todo en la misma escala:
// - 2017-2019: barras azules (acción pública) con el importe de las líneas propias y su coste por nido.
// - 2020: columna rayada «mezclado con otros trabajos» (sin altura de dato), rotulada en horizontal
//   arriba a la izquierda con una flecha.
// - 2021-2025: un bloque proporcional al encargo anual a Basalan (Patrimonio Natural) de cada año,
//   con una franja difusa abajo: el escenario de lo que costaría la retirada al coste por nido de
//   2018 (no es un dato), rotulada «aquí dentro, sin desglose»; en el móvil, el texto del escenario
//   va bajo el eje, a todo el ancho.
// Aparece con el scroll: barras año a año, 2020, el bloque (crece desde la base) y la franja.
// Sin contador de periodo (periodoEl vacío).
// Datos: web/data/gasto.json (outputs/avispa_gasto_anual.csv y avispa_gasto_coste_nido.csv;
// escenario_2018 calculado en scripts/web_preparar_datos.py como el apartado 3c de avispa_gasto.txt).
import { duracion, formateador, porcentaje, medidas, rayado, tabla, alRedimensionar, plantilla, envolver, tamano } from "../util.js";

let nGrad = 0;
const DIFUSO = 1.3; // la franja se difumina entre el 70 % y el 130 % del escenario

export function crearGasto(contenedor, datos, textos, periodoEl) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const fmtM = formateador(textos.idioma, 1);
  const pct0 = porcentaje(textos.idioma, 0);
  const anios = datos.anios;
  const millones = (v) => `${fmtM(v / 1e6)} M€`;
  const miles = (v) => `${fmt(Math.round(v / 1000))} mil €`;
  const esc18 = datos.escenario_2018 || {};
  const escAnio = (a) => (esc18.anios ? esc18.anios[a.anio] : null);
  const conImporte = anios.filter((a) => a.estado === "importe");
  const mezclado = anios.filter((a) => a.estado === "mezclado");
  const bloque = anios.filter((a) => a.estado === "sin_desglose" && a.encargo_eur != null);
  if (periodoEl) periodoEl.textContent = "";

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const patron = rayado(svg);
  // Degradado vertical de la franja: sólida abajo, difusa arriba (es un escenario, no un dato)
  const idGrad = `franja-gasto-${++nGrad}`;
  const grad = svg.select("defs").append("linearGradient").attr("id", idGrad).attr("x1", 0).attr("x2", 0).attr("y1", 1).attr("y2", 0);
  [[0, 0.7], [0.54, 0.7], [1, 0]].forEach(([o, op]) => grad.append("stop").attr("offset", o)
    .attr("stop-color", "var(--acento-2)").attr("stop-opacity", op));
  const g = svg.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const gBloque = g.append("g");
  const gFranja = g.append("g");
  const gBarras = g.append("g");
  const gMezcla = g.append("g");
  const gEtiq = g.append("g");
  const gTextoBloque = g.append("g");
  const gTextoFranja = g.append("g");

  let esc = null, fase = -1;

  function dibujar() {
    const te = tamano("--t-etiqueta"), tj = tamano("--t-eje");
    // Móvil: el texto del escenario va bajo el eje, a todo el ancho (dentro del bloque no cabe holgado)
    const angosto = (contenedor.clientWidth || 320) < 520;
    const filasEsc = bloque.map(escAnio).filter(Boolean);
    const sub = filasEsc.length ? plantilla(I.gasto_franja_sub, { eur: fmt(esc18.eur_nido),
      min: miles(d3.min(filasEsc, (f) => f.eur)).replace(" mil €", ""), max: miles(d3.max(filasEsc, (f) => f.eur)),
      pmin: fmt(Math.round(d3.min(filasEsc, (f) => f.pct_encargo) * 100)), pmax: pct0(d3.max(filasEsc, (f) => f.pct_encargo)) }) : null;
    const tsub = gTextoFranja.selectAll("text.sub").data(sub ? [sub] : [])
      .join((e) => e.append("text").attr("class", "sub etiqueta-nota").attr("opacity", 0));
    const izq = tj * 3.6;
    let abajo = tj * 2;
    if (sub && angosto) {
      tsub.attr("x", -izq + 2).attr("y", 0).attr("data-texto", null).text(sub).call(envolver, (contenedor.clientWidth || 320) - 8);
      abajo += te * 0.6 + +tsub.attr("data-lineas") * te * 1.15;
    }
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: te * 0.8, derecha: 8, abajo, izquierda: izq });
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const x = d3.scaleBand().domain(anios.map((a) => a.anio)).range([0, w]).padding(0.18);
    const max = d3.max(anios, (a) => Math.max(a.retirada_eur || 0, a.estado === "sin_desglose" ? a.encargo_eur || 0 : 0));
    const y = d3.scaleLinear().domain([0, max * 1.04]).range([h, 0]);
    esc = { x, y, h, w, te };
    gEjeX.attr("transform", `translate(0,${h})`)
      .call(d3.axisBottom(x).tickSizeOuter(0).tickFormat((t) => (w < 420 ? `'${String(t).slice(2)}` : t)));
    gEjeY.call(d3.axisLeft(y).ticks(3).tickFormat((v) => (v === 0 ? "0" : `${fmt(v / 1e6)} M€`)).tickSize(-w))
      .call((s) => s.select(".domain").remove());

    // Bloque del encargo (columnas pegadas, una por año, misma escala)
    const paso = x.step(), medio = paso * x.padding() / 2;
    const bx0 = (a) => x(a.anio) - medio, bx1 = (a) => x(a.anio) + x.bandwidth() + medio;
    gBloque.selectAll("rect").data(bloque, (a) => a.anio).join((e) => e.append("rect").attr("y", h).attr("height", 0))
      .attr("x", bx0).attr("width", (a) => bx1(a) - bx0(a))
      .attr("fill", "var(--acento-2)").attr("fill-opacity", 0.1);
    // Contorno escalonado del bloque
    const contorno = bloque.length ? d3.line()([[bx0(bloque[0]), h],
      ...bloque.flatMap((a) => [[bx0(a), y(a.encargo_eur)], [bx1(a), y(a.encargo_eur)]]),
      [bx1(bloque[bloque.length - 1]), h]]) : null;
    gBloque.selectAll("path").data(contorno ? [contorno] : []).join("path").attr("d", (d) => d)
      .attr("fill", "none").attr("stroke", "var(--acento-2)").attr("stroke-width", 1.5);
    // Franja del escenario en cada año del bloque
    gFranja.selectAll("rect").data(bloque.filter(escAnio), (a) => a.anio).join("rect")
      .attr("x", bx0).attr("width", (a) => bx1(a) - bx0(a))
      .attr("y", (a) => y(escAnio(a).eur * DIFUSO)).attr("height", (a) => h - y(escAnio(a).eur * DIFUSO))
      .attr("fill", `url(#${idGrad})`);

    // Barras 2017-2019
    gBarras.selectAll("rect").data(conImporte, (a) => a.anio).join((e) => e.append("rect").attr("y", h).attr("height", 0))
      .attr("x", (a) => x(a.anio)).attr("width", x.bandwidth()).attr("fill", "var(--acento-2)");
    // 2020: rayado a toda la altura; su rótulo, en horizontal arriba a la izquierda con una flecha
    const gm = gMezcla.selectAll("g").data(mezclado, (a) => a.anio).join((e) => {
      const gg = e.append("g").attr("opacity", 0);
      gg.append("rect");
      gg.append("text").attr("class", "etiqueta-nota");
      gg.append("path").attr("class", "flecha").attr("fill", "none").attr("stroke", "var(--tinta-suave)")
        .attr("stroke-width", 1.4).attr("stroke-linecap", "round").attr("stroke-linejoin", "round");
      return gg;
    });
    gm.select("rect").attr("x", (a) => x(a.anio)).attr("width", x.bandwidth()).attr("y", 0).attr("height", h)
      .attr("fill", patron).attr("stroke", "var(--gris-dato)").attr("stroke-dasharray", "3 2").attr("opacity", 0.8);
    gm.each(function (a) {
      const gg = d3.select(this);
      const x0 = conImporte.length ? x(conImporte[0].anio) : 0, xc = x(a.anio) - 3;
      const tm = gg.select("text").attr("x", x0).attr("y", te * 0.9).attr("fill", "var(--tinta)")
        .attr("data-texto", null).text(I.gasto_mezclado).call(envolver, Math.max(xc - x0 - 26, 60));
      const l1 = tm.select("tspan").node().getComputedTextLength();
      const ya = te * 0.9 - te * 0.32, xa = Math.min(x0 + l1 + 6, xc - 12);
      gg.select("path.flecha").attr("d", `M${xa},${ya}H${xc}M${xc - 6},${ya - 4}L${xc},${ya}L${xc - 6},${ya + 4}`);
    });

    // Importe y coste por nido sobre cada barra (pueden subir por encima: las barras son bajas)
    const estrecho = x.bandwidth() < 52;
    const et = gEtiq.selectAll("text.imp").data(conImporte, (a) => a.anio)
      .join((e) => e.append("text").attr("class", "imp etiqueta-valor").attr("text-anchor", "middle").attr("opacity", 0));
    et.each(function (a) {
      const cx = x(a.anio) + x.bandwidth() / 2;
      const c = datos.coste_nido[a.anio];
      const t = d3.select(this).text(null);
      if (estrecho) {
        // Móvil: importe en vertical sobre la barra (el coste por nido va en un rótulo común)
        t.attr("x", 0).attr("y", 0).attr("text-anchor", "start")
          .attr("transform", `translate(${cx + te * 0.35},${y(a.retirada_eur) - 5}) rotate(-90)`).text(miles(a.retirada_eur));
        return;
      }
      const lineas = c ? 2 : 1;
      t.attr("transform", null).attr("text-anchor", "middle").attr("x", cx).attr("y", y(a.retirada_eur) - 6 - (lineas - 1) * te * 1.15);
      t.append("tspan").attr("x", cx).text(miles(a.retirada_eur));
      if (c) {
        const v = c.min === c.max ? fmt(c.min) : `${fmt(c.min)}-${fmt(c.max)}`;
        t.append("tspan").attr("x", cx).attr("dy", "1.15em").attr("font-weight", 400).attr("fill", "var(--tinta-suave)")
          .text(plantilla(I.eur_nido, { v }));
      }
    });
    // Móvil: coste por nido de 2017-2019, un solo rótulo encima de los importes
    const costes = Object.entries(datos.coste_nido).filter(([a]) => conImporte.some((q) => String(q.anio) === a)).map(([, c]) => c);
    const largo = d3.max(gEtiq.selectAll("text.imp").nodes(), (n) => n.getComputedTextLength()) || 0;
    gEtiq.selectAll("text.coste").data(estrecho && costes.length ? [0] : [])
      .join((e) => e.append("text").attr("class", "coste etiqueta-nota").attr("opacity", 0))
      .attr("x", x(conImporte[0].anio)).attr("y", d3.min(conImporte, (a) => y(a.retirada_eur)) - largo - 14)
      .text(plantilla(I.eur_nido, { v: d3.min(costes, (c) => c.min) === d3.max(costes, (c) => c.max) ? fmt(d3.min(costes, (c) => c.min))
        : `${fmt(d3.min(costes, (c) => c.min))}-${fmt(d3.max(costes, (c) => c.max))}` }));

    // Rótulos del bloque (arriba, dentro) y de la franja (justo encima de ella)
    if (bloque.length) {
      const x0 = bx0(bloque[0]) + 8, anchoB = bx1(bloque[bloque.length - 1]) - bx0(bloque[0]) - 16;
      const enc = bloque.map((a) => a.encargo_eur);
      const tb = gTextoBloque.selectAll("text").data([0]).join((e) => e.append("text").attr("class", "etiqueta-valor").attr("opacity", 0));
      tb.attr("x", x0).attr("y", 0).attr("data-texto", null)
        .text(plantilla(I.gasto_bloque, { min: millones(d3.min(enc)), max: millones(d3.max(enc)) })).call(envolver, anchoB);
      tb.attr("transform", `translate(0,${d3.max(bloque, (a) => y(a.encargo_eur)) + te * 1.4})`);
      const tf = gTextoFranja.selectAll("text.titulo").data(sub ? [0] : [])
        .join((e) => e.append("text").attr("class", "titulo etiqueta-serie").attr("fill", "var(--acento-2)").attr("opacity", 0));
      if (sub) {
        tf.attr("x", x0).attr("y", 0).attr("data-texto", null).text(I.gasto_franja).call(envolver, anchoB);
        const lt = +tf.attr("data-lineas");
        const topeF = d3.min(bloque.filter(escAnio), (a) => y(escAnio(a).eur * DIFUSO));
        if (angosto) {
          // Título sobre la franja; el escenario, bajo las etiquetas del eje
          tf.attr("transform", `translate(0,${topeF - 8 - (lt - 1) * te * 1.15})`);
          tsub.attr("transform", `translate(0,${h + tj * 2 + te * 0.95})`);
        } else {
          tsub.attr("x", x0).attr("y", 0).attr("data-texto", null).text(sub).call(envolver, anchoB);
          const lineas = +tsub.attr("data-lineas");
          const ySub = topeF - 8 - (lineas - 1) * te * 1.15;
          tsub.attr("transform", `translate(0,${ySub})`);
          tf.attr("transform", `translate(0,${ySub - te * 1.3 - (lt - 1) * te * 1.15})`);
        }
      }
    }
  }

  // Fases con el scroll: 0-2 barras 2017-2019, 3 = 2020, 4 = bloque, 5 = franja
  function revelar(nueva, animar) {
    fase = nueva;
    if (!esc) return;
    const { y, h } = esc;
    const d = animar ? duracion(700) : 0;
    const t = (sel, nombre = "ver") => sel.interrupt(nombre).transition(nombre).duration(d).ease(d3.easeCubicInOut);
    t(gBarras.selectAll("rect")).delay(0)
      .attr("y", (a, i) => (fase >= i ? y(a.retirada_eur) : h)).attr("height", (a, i) => (fase >= i ? h - y(a.retirada_eur) : 0));
    t(gEtiq.selectAll("text.imp")).delay(animar ? duracion(350) : 0).attr("opacity", (a, i) => (fase >= i ? 1 : 0));
    t(gEtiq.selectAll("text.coste")).delay(animar ? duracion(350) : 0).attr("opacity", fase >= 2 ? 1 : 0);
    t(gMezcla.selectAll("g")).attr("opacity", fase >= 3 ? 1 : 0);
    t(gBloque.selectAll("rect")).delay((a, i) => (animar ? i * 80 : 0))
      .attr("y", (a) => (fase >= 4 ? y(a.encargo_eur) : h)).attr("height", (a) => (fase >= 4 ? h - y(a.encargo_eur) : 0));
    t(gBloque.selectAll("path")).delay(animar && fase >= 4 ? duracion(500) : 0).attr("opacity", fase >= 4 ? 1 : 0);
    t(gTextoBloque.selectAll("text")).delay(animar && fase >= 4 ? duracion(600) : 0).attr("opacity", fase >= 4 ? 1 : 0);
    t(gFranja.selectAll("rect")).attr("opacity", fase >= 5 ? 1 : 0);
    t(gTextoFranja.selectAll("text")).delay(animar && fase >= 5 ? duracion(400) : 0).attr("opacity", fase >= 5 ? 1 : 0);
  }

  function tablaDatos() {
    return tabla([I.anio, I.retirada_nidos, I.eur_por_nido, I.encargo_basalan, I.gasto_escenario, I.detalle],
      anios.map((a) => {
        const c = datos.coste_nido[a.anio];
        const e = escAnio(a);
        return [a.anio, a.retirada_eur != null ? `${fmt(a.retirada_eur)} €` : (a.estado === "mezclado" ? I.gasto_mezclado_corto : I.sin_desglose),
          c ? (c.min === c.max ? `${fmt(c.min)} €` : `${fmt(c.min)}-${fmt(c.max)} €`) : "–",
          a.encargo_eur != null ? `${fmt(a.encargo_eur)} €` : "–",
          e ? `${fmt(e.eur)} € (${pct0(e.pct_encargo)})` : "–", a.detalle];
      }));
  }

  alRedimensionar(contenedor, () => { dibujar(); revelar(fase, false); });
  return {
    actualizar(_, animar = true, recienMostrado = false) {
      if (periodoEl) periodoEl.textContent = "";
      dibujar();
      revelar(recienMostrado ? 0 : Math.max(fase, 0), false);
    },
    progreso(p) {
      const n = Math.min(5, Math.floor(Math.min(1, p / 0.7) * 5 + 1e-6));
      if (n !== fase) revelar(n, true);
    },
    tablaDatos,
    describir() {
      const enc = bloque.map((a) => a.encargo_eur);
      return plantilla(I.gasto_desc, { desde: bloque[0].anio, hasta: bloque[bloque.length - 1].anio,
        min: millones(d3.min(enc)), max: millones(d3.max(enc)) });
    },
  };
}
