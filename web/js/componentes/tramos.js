// Rapidez de la retirada (paso 6): puntos apilados, 1 punto = 10 nidos retirados en 2019-2025, en
// columnas según los días entre el aviso y la retirada (0, 1, …, 7 y «más de 7»). Los puntos caen
// con el scroll, columna a columna, como un histograma que se llena; al completar cada tramo
// aparecen las anotaciones «la mitad, en N días o menos» y «nueve de cada diez, en una semana»,
// calculadas de los datos (y solo si son ciertas). Azul: acción pública; «más de 7», en gris.
// El nido de Morga (datos.hilo.nido.dias), con un anillo en su columna.
// Datos: web/data/indicadores.json → dias_distribucion (scripts/web_preparar_datos.py).
import { duracion, porcentaje, formateador, medidas, tabla, alRedimensionar, plantilla, envolver, tamano, tramo } from "../util.js";

const POR_PUNTO = 10; // nidos por punto
const FIN_CAIDA = 0.6; // parte del paso en la que caen todos los puntos (el resto, gráfico completo)

// Móvil: app.js limita el panel al 58 % de la pantalla aunque la tarjeta deje más sitio, y queda un
// hueco vacío entre el gráfico y la tarjeta. Los gráficos de la parada 2 crecen hasta la tarjeta
// (misma cuenta que app.js: alto de la pantalla menos la tarjeta activa y 28 px de margen).
export function altoMovil(contenedor) {
  if (innerWidth >= 900) return;
  const panel = contenedor.closest(".panel");
  const t = document.querySelector(".paso.activo .tarjeta");
  if (!panel || !t || panel.parentNode.querySelector(".fotos")) return;
  // En el último paso de la parada la tarjeta deja de estar fija un poco antes de que el gráfico
  // salga (el paso tiene un relleno inferior): se deja ese margen para que no se monten al salir
  // Se mide con la tarjeta más alta de los pasos del mismo gráfico: el alto no cambia entre pasos
  // (si cambiara, las columnas se moverían al pasar de «dibuja tu estimación» a los datos reales)
  const paso = t.closest(".paso");
  const grupo = paso ? [...paso.parentNode.querySelectorAll(`.paso[data-grafico="${paso.dataset.grafico}"]`)] : [];
  const ultimo = grupo.find((q) => !q.nextElementSibling);
  const extra = ultimo ? parseFloat(getComputedStyle(ultimo).paddingBottom) || 0 : 0;
  const altoT = Math.max(t.offsetHeight, ...grupo.map((q) => q.querySelector(".tarjeta").offsetHeight));
  const alto = Math.round(Math.min(innerHeight * 0.74, innerHeight - altoT - 28 - extra));
  if (alto > panel.offsetHeight + 1) {
    panel.style.height = `${alto}px`;
    panel.parentNode.style.setProperty("--alto-panel", `${alto}px`);
  }
}

export function crearTramos(contenedor, datos, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const pct = porcentaje(textos.idioma, 0);
  const fmt = formateador(textos.idioma, 0);
  const dd = datos.dias_distribucion;
  const total = d3.sum(dd.n);
  // Columnas: días 0..mas_de y «más de N»; acumulado para las anotaciones
  let acum = 0;
  const cols = dd.n.map((n, i) => ({ i, n, p: n / total, acum: (acum += n) / total,
    etiqueta: i < dd.dias.length ? String(dd.dias[i]) : plantilla(I.tramos_mas_de, { n: dd.mas_de }),
    puntos: Math.round(n / POR_PUNTO) }));
  // Puntos en orden de caída: columna a columna, de abajo arriba
  const puntos = [];
  cols.forEach((c) => d3.range(c.puntos).forEach((j) => puntos.push({ id: `${c.i}-${j}`, c: c.i, j, orden: puntos.length })));
  const finColumna = cols.map((c) => d3.sum(cols.slice(0, c.i + 1), (q) => q.puntos)); // nº de puntos al completar
  // Anotaciones (comprobadas con los datos): mediana y semana
  const iMitad = cols.findIndex((c) => c.acum >= 0.5);
  const iSemana = dd.dias.indexOf(7);
  const semana = cols[iSemana].acum;
  const anots = [
    { k: "mitad", hasta: iMitad, texto: plantilla(I.tramos_mitad, { d: dd.dias[iMitad], v: pct(cols[iMitad].acum) }) },
    // «nueve de cada diez» solo si redondea a 9 de cada 10
    ...(Math.round(semana * 10) === 9 ? [{ k: "semana", hasta: iSemana, texto: plantilla(I.tramos_nueve, { v: pct(semana) }) }] : []),
  ];
  const colorDe = (c) => (c < dd.dias.length ? "var(--acento-2)" : "var(--gris-dato)");

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const g = svg.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const tituloX = g.append("text").attr("class", "titulo-eje").attr("text-anchor", "middle");
  const unidad = g.append("g");
  unidad.append("circle").attr("fill", "var(--acento-2)");
  unidad.append("text").attr("class", "etiqueta-nota").attr("dy", "0.35em");
  const gPuntos = g.append("g");
  const gAnot = g.append("g");
  const gHilo = g.append("g").attr("class", "hilo").attr("opacity", 0);
  gHilo.append("circle").attr("class", "hilo-anillo");
  gHilo.append("text").attr("class", "hilo-texto");

  let esc = null, visibles = 0, prog = 0, hiloTexto = "", medida = "", objetivo = 0, raf = 0;
  const nh = datos.hilo && datos.hilo.nido;

  function dibujar() {
    const te = tamano("--t-etiqueta"), tj = tamano("--t-eje");
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: te * 1.6, derecha: 4, abajo: tj * 3.4, izquierda: 4 });
    medida = `${contenedor.clientWidth}x${contenedor.clientHeight}`;
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const x = d3.scaleBand().domain(cols.map((c) => c.i)).range([0, w]).paddingInner(0.16).paddingOuter(0.04);
    gEjeX.attr("transform", `translate(0,${h})`)
      .call(d3.axisBottom(x).tickSize(0).tickPadding(6).tickFormat((i) => (i === cols.length - 1 && x.bandwidth() < 48
        ? plantilla(I.tramos_mas_de_corto, { n: dd.mas_de }) : cols[i].etiqueta)))
      .call((s) => s.select(".domain").attr("stroke", "var(--tinta-suave)"));
    tituloX.attr("x", w / 2).attr("y", h + tj * 3).text(I.tramos_eje);

    // Anotaciones: se componen primero para reservar su altura encima de las columnas
    const ta = gAnot.selectAll("g.anot").data(anots, (a) => a.k).join((e) => {
      const gg = e.append("g").attr("class", "anot").attr("opacity", 0);
      gg.append("path").attr("fill", "none").attr("stroke", "var(--tinta)").attr("stroke-width", 1.2);
      gg.append("text").attr("class", "etiqueta-serie").attr("fill", "var(--tinta)");
      return gg;
    });
    ta.select("text").attr("x", 0).attr("y", 0).attr("data-texto", null).text((a) => a.texto).call(envolver, w - 4);
    const altoTexto = (a) => +ta.filter((b) => b.k === a.k).select("text").attr("data-lineas") * te * 1.15;
    const reserva = d3.sum(anots, (a) => altoTexto(a) + te * 0.9) + te * 0.4;

    // Tamaño del punto: el mayor que hace caber la columna más alta en el alto disponible
    const hp = Math.max(40, h - reserva);
    const nMax = d3.max(cols, (c) => c.puntos);
    let s = Math.min(x.bandwidth(), hp);
    while (s > 2 && Math.floor(x.bandwidth() / s) * Math.floor(hp / s) < nMax) s -= 0.25;
    const k = Math.max(1, Math.floor(x.bandwidth() / s));
    const r = Math.max(1, s * 0.4);
    const pos = (q) => ({ cx: x(q.c) + (x.bandwidth() - k * s) / 2 + (q.j % k) * s + s / 2,
      cy: h - Math.floor(q.j / k) * s - s / 2 });
    const tope = (i) => h - Math.ceil(cols[i].puntos / k) * s; // y de lo alto de la columna
    esc = { x, s, r, pos, tope, h, te };

    gPuntos.selectAll("circle").data(puntos, (q) => q.id).join((e) => e.append("circle").attr("opacity", 0))
      .attr("r", r).attr("fill", (q) => colorDe(q.c))
      .each(function (q) { const p = pos(q); this.setAttribute("cx", p.cx); if (!this.__cayendo) this.setAttribute("cy", p.cy); });

    // Corchetes sobre las columnas que suman cada anotación (el más amplio, más arriba)
    let y = d3.min(cols, (c) => tope(c.i)) - te * 0.5;
    ta.each(function (a) {
      const gg = d3.select(this);
      const x0 = x(0), x1 = x(a.hasta) + x.bandwidth();
      gg.select("path").attr("d", `M${x0},${y + 6}V${y}H${x1}V${y + 6}`);
      const lineas = +gg.select("text").attr("data-lineas");
      gg.select("text").attr("transform", `translate(${x0},${y - 6 - (lineas - 1) * te * 1.15})`);
      y -= altoTexto(a) + te * 0.9;
    });
    // Unidad: arriba a la derecha
    unidad.select("circle").attr("r", Math.max(r, 2.5));
    unidad.select("text").attr("x", Math.max(r, 2.5) + 6).text(plantilla(I.tramos_unidad, { n: POR_PUNTO, desde: dd.periodo[0], hasta: dd.periodo[1] }));
    const bu = unidad.select("text").node().getBBox();
    unidad.attr("transform", `translate(${Math.max(r, w - bu.width - r - 8)},${-m.arriba + te * 0.7})`);
  }

  // Caída de los puntos hasta el progreso p (0-1). Los puntos no caen a tandas por cada evento de
  // scroll: un bucle de requestAnimationFrame suelta unos pocos en cada fotograma hacia el objetivo,
  // y cada punto cae con su propia transición, así que el chorro es continuo aunque el scroll vaya
  // a saltos. Al subir, los puntos sobrantes se desvanecen.
  function llenar(p, animar) {
    prog = p;
    if (!esc) return;
    objetivo = Math.round(tramo(p, 0, FIN_CAIDA) * puntos.length);
    if (!animar || !duracion(700)) {
      cancelAnimationFrame(raf); raf = 0;
      mostrar(objetivo, false);
      return;
    }
    if (objetivo < visibles) mostrar(objetivo, true);
    if (!raf && objetivo > visibles) raf = requestAnimationFrame(soltar);
  }
  function soltar() {
    raf = 0;
    if (!esc || objetivo <= visibles) return;
    mostrar(Math.min(objetivo, visibles + Math.max(3, Math.ceil((objetivo - visibles) * 0.1))), true);
    if (objetivo > visibles) raf = requestAnimationFrame(soltar);
  }
  function mostrar(n, animar) {
    const d = animar ? duracion(650) : 0;
    const antes = visibles;
    visibles = n;
    const sel = gPuntos.selectAll("circle");
    if (n > antes) {
      sel.filter((q) => q.orden >= antes && q.orden < n)
        .each(function () { this.__cayendo = true; })
        .interrupt().attr("opacity", 0)
        .attr("cy", (q) => (d ? esc.pos(q).cy - esc.h * 0.3 : esc.pos(q).cy))
        .transition().duration(d).ease(d3.easeCubicInOut)
        .attr("opacity", 1).attr("cy", (q) => esc.pos(q).cy)
        .on("end interrupt", function () { this.__cayendo = false; });
    } else if (n < antes) {
      sel.filter((q) => q.orden >= n && q.orden < antes).interrupt()
        .each(function (q) { this.__cayendo = false; this.setAttribute("cy", esc.pos(q).cy); })
        .transition().duration(animar ? duracion(300) : 0).attr("opacity", 0);
    }
    // Anotaciones, cuando sus columnas están completas (después de las marcas); la transición solo
    // se lanza cuando cambia su estado (si no, se reiniciaría en cada fotograma)
    gAnot.selectAll("g.anot").each(function (a) {
      const ver = n >= finColumna[a.hasta];
      if (!animar) { d3.select(this).interrupt("ver").attr("opacity", ver ? 1 : 0); this.__ver = ver; return; }
      if (this.__ver === ver) return;
      this.__ver = ver;
      d3.select(this).transition("ver").duration(duracion(500)).delay(ver ? duracion(550) : 0).attr("opacity", ver ? 1 : 0);
    });
    pintarHilo(animar);
  }

  // Nido hilo: anillo en el punto más alto de su columna y texto a su derecha
  function pintarHilo(animar = true) {
    const c = nh ? Math.min(nh.dias, cols.length - 1) : -1;
    const ver = esc && hiloTexto && c >= 0 && cols[c].puntos > 0 && visibles >= finColumna[c];
    if (!ver) { gHilo.interrupt().attr("opacity", 0); gHilo.node().__ver = false; return; }
    const { pos, r, te, x } = esc;
    const q = { c, j: cols[c].puntos - 1 };
    const p = pos(q);
    gHilo.select("circle").attr("cx", p.cx).attr("cy", p.cy).attr("r", r + 4);
    const x0 = Math.max(p.cx + r + 8, x(c) + x.bandwidth() + 4);
    const ancho = Math.max(110, x.range()[1] - x0);
    const t = gHilo.select("text").attr("x", x0).attr("y", 0).attr("data-texto", null).text(hiloTexto).call(envolver, ancho);
    const lineas = +t.attr("data-lineas");
    t.attr("transform", `translate(0,${p.cy - (lineas - 1) * te * 1.15 + te * 0.35})`);
    gHilo.raise();
    if (!animar) { gHilo.interrupt().attr("opacity", 1); gHilo.node().__ver = true; return; }
    if (gHilo.node().__ver) return;
    gHilo.node().__ver = true;
    gHilo.transition().duration(animar ? duracion(500) : 0).delay(animar ? duracion(300) : 0).attr("opacity", 1);
  }

  function tablaDatos() {
    return tabla([I.tramos_tabla_dias, I.nidos_retirados, I.porcentaje || "%", I.tramos_tabla_acum],
      cols.map((c) => [c.etiqueta, fmt(c.n), pct(c.p), pct(c.acum)]));
  }

  // Solo se redibuja si el tamaño cambia de verdad (y nunca con el panel oculto): si no, los puntos
  // que van cayendo se cortarían de golpe en su sitio final
  alRedimensionar(contenedor, () => {
    if (!contenedor.clientWidth || `${contenedor.clientWidth}x${contenedor.clientHeight}` === medida) return;
    dibujar(); visibles = 0; llenar(prog, false);
  });
  return {
    actualizar(_, animar = true, recienMostrado = false) {
      altoMovil(contenedor);
      dibujar();
      if (recienMostrado) {
        // Panel recién mostrado: se parte de cero (sin restos de una visita anterior)
        cancelAnimationFrame(raf); raf = 0;
        gPuntos.selectAll("circle").interrupt().each(function () { this.__cayendo = false; }).attr("opacity", 0);
        visibles = 0; llenar(0, false);
      } else llenar(prog, animar);
    },
    progreso(p) { llenar(p, true); },
    hilo(texto) { hiloTexto = texto; pintarHilo(); },
    tablaDatos,
    describir() {
      return plantilla(I.tramos_desc_puntos, { n: fmt(total), desde: dd.periodo[0], hasta: dd.periodo[1],
        d: dd.dias[iMitad], v2: pct(cols[iMitad].acum), v7: pct(semana) });
    },
  };
}
