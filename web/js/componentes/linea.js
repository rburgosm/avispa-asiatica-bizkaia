// Línea del porcentaje de nidos que no se pudieron retirar (paso 7), con una marca vertical
// en el cambio de registro del 01/01/2023 y la media de cada tramo (2019-2022 y 2023-2025).
// 2018, punto hueco en gris (registro incompleto), fuera de la línea.
// Datos: web/data/indicadores.json (no_eliminables, nidos, pct_no_eliminables, corte_registro).
import { duracion, porcentaje, medidas, tabla, alRedimensionar, plantilla, envolver, tamano } from "../util.js";
import { altoMovil } from "./tramos.js";

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
  // Estado inicial desde el primer fotograma: medias ocultas, línea sin dibujar y puntos ocultos
  const gCorte = g.append("g").attr("class", "corte").style("opacity", 0.35);
  const gMedias = g.append("g").attr("class", "medias").style("opacity", 0);
  const camino = g.append("path").attr("fill", "none").attr("stroke", "var(--acento)").attr("stroke-width", 2.5);
  const gPuntos = g.append("g");

  function dibujar(animar = true) {
    const te = tamano("--t-etiqueta"), tj = tamano("--t-eje");
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: te * 3.2, derecha: 20, abajo: tj * 2, izquierda: tj * 3.4 });
    medida = `${contenedor.clientWidth}x${contenedor.clientHeight}`;
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
    // El último tramo puede usar el margen derecho; la cifra («6,2 %») nunca se parte
    bordes[2] = Math.max(bordes[2], w + m.derecha);
    mg.select("text").attr("x", (d, i) => (bordes[i] + bordes[i + 1]) / 2).attr("y", y(0.025))
      .each(function (d, i) {
        const t = d3.select(this), ancho = bordes[i + 1] - bordes[i] - 8;
        t.attr("data-texto", null).text(plantilla(I.media_tramo, { v: pct(d.v), desde: d.t0, hasta: d.t1 }));
        if (t.node().getComputedTextLength() <= ancho) return;
        const [antes, despues = ""] = plantilla(I.media_tramo, { v: "\u0000", desde: d.t0, hasta: d.t1 }).split("\u0000");
        t.text(antes.trim()).call(envolver, ancho);
        t.append("tspan").attr("x", t.attr("x")).attr("dy", "1.15em").text(pct(d.v) + despues);
      });

    const linea = d3.line().x((p) => x(p.t)).y((p) => y(p.v));
    camino.attr("d", linea(enPeriodo));
    // Longitud acumulada hasta cada vértice: la línea avanza de forma continua entre puntos
    const xy = enPeriodo.map((p) => [x(p.t), y(p.v)]);
    const acum = [0];
    for (let i = 1; i < xy.length; i++) acum.push(acum[i - 1] + Math.hypot(xy[i][0] - xy[i - 1][0], xy[i][1] - xy[i - 1][1]));
    esc = { x, xy, acum, L: acum[acum.length - 1] || 1 };
    camino.attr("stroke-dasharray", `${esc.L} ${esc.L}`);

    const gp = gPuntos.selectAll("g").data(puntos, (p) => p.t).join((e) => {
      const gg = e.append("g").style("opacity", 0);
      gg.append("circle").attr("r", 4);
      gg.append("text").attr("class", "etiqueta-valor").attr("text-anchor", "middle");
      return gg;
    });
    gp.attr("transform", (p) => `translate(${x(p.t)},${y(p.v)})`).attr("class", "punto-serie");
    gp.select("circle").attr("fill", (p) => (p.inc ? "var(--fondo)" : "var(--acento)"))
      .attr("stroke", (p) => (p.inc ? "var(--gris-dato)" : "var(--acento)")).attr("stroke-width", 2);
    // Etiqueta de cada punto en el lado libre de la línea: debajo en los mínimos locales, encima
    // en los máximos y, en los tramos que bajan o suben, en diagonal, fuera del trazo
    const lado = (p) => {
      const i = enPeriodo.indexOf(p);
      if (i < 0) return { dx: 0, dy: -9, a: "middle" };
      const a = enPeriodo[i - 1], b = enPeriodo[i + 1];
      const sube = (q) => (q ? Math.sign(q.v - p.v) : 0); // vecino por encima (+1) o por debajo (-1)
      const sa = sube(a), sb = sube(b);
      if (sa >= 0 && sb >= 0 && (sa || sb)) return { dx: 0, dy: te + 6, a: "middle" };   // mínimo
      if (sa <= 0 && sb <= 0) return { dx: 0, dy: -9, a: "middle" };                       // máximo
      if (sa < 0) return { dx: -6, dy: -8, a: "end" };                                      // sube
      // baja: arriba a la derecha, salvo que ahí esté la marca del cambio de registro
      return xc > x(p.t) && xc < x(p.t) + te * 3.2 ? { dx: -6, dy: te + 4, a: "end" } : { dx: 6, dy: -8, a: "start" };
    };
    gp.select("text").attr("x", (p) => lado(p).dx).attr("y", (p) => lado(p).dy).attr("text-anchor", (p) => lado(p).a)
      .attr("fill", (p) => (p.inc ? "var(--tinta-suave)" : "var(--tinta)")).text((p) => pct(p.v));
    gp.selectAll("text.inc").data((p) => (p.inc ? [p] : [])).join("text").attr("class", "inc etiqueta-nota")
      .attr("x", -6).attr("y", 20).attr("text-anchor", "start").attr("data-texto", null)
      .text(I.registro_incompleto).call(envolver, Math.max(x.step() * 1.1, 60));
  }

  function tablaDatos() {
    return tabla([I.temporada, I.no_eliminables, I.avisos, "%"],
      puntos.map((p) => [p.t + (p.inc ? ` (${I.registro_incompleto})` : ""), p.k, p.n, pct(p.v)]));
  }

  // La línea se dibuja sola por tiempo en cuanto entra el paso (1,8 s, easeCubicInOut sobre
  // stroke-dashoffset), sin leer el scroll: una vez empezada se completa aunque el lector salga
  // del paso, y después se queda dibujada (al volver no se repite). Los puntos, sus etiquetas, la
  // marca del cambio de registro y las dos medias aparecen con un fundido cuando el trazo llega a
  // ellos. Con prefers-reduced-motion, dibujada desde el principio. Sin contador de años.
  const DIBUJO = 1800;
  let esc = null, medida = "", mostrado = 0, fase = 0; // fase: 0 sin empezar, 1 dibujando, 2 dibujada
  // Fracción del eje (0 = 2019, 1 = 2025) a longitud de trazo, avanzando de forma continua entre puntos
  function aLongitud(f) {
    const n = enPeriodo.length;
    if (n < 2) return 1;
    const fi = Math.min(1, Math.max(0, f)) * (n - 1);
    const i = Math.min(n - 2, Math.floor(fi));
    return (esc.acum[i] + (fi - i) * (esc.acum[i + 1] - esc.acum[i])) / esc.L;
  }
  function empezar() {
    if (fase) return;
    if (!duracion(600)) { fase = 2; mostrado = 1; pintar(false); return; }
    fase = 1; mostrado = 0; pintar(false);
    camino.transition("trazo").duration(DIBUJO).ease(window.d3.easeCubicInOut)
      .tween("trazo", () => (k) => { mostrado = aLongitud(k); pintar(true); })
      .on("end", () => { fase = 2; mostrado = 1; pintar(true); });
  }
  // Fundido de entrada o salida de un elemento (solo si cambia)
  function ver(nodo, v, animar) {
    if (nodo.__v === v) return;
    nodo.__v = v;
    const s = window.d3.select(nodo).interrupt("ver");
    if (animar) s.transition("ver").duration(duracion(350)).style("opacity", v); else s.style("opacity", v);
  }
  function pintar(animar = false) {
    if (!esc) return;
    const { x, xy, acum, L } = esc;
    const largo = mostrado * L;
    camino.attr("stroke-dashoffset", L - largo);
    // último vértice alcanzado y posición horizontal de la punta del trazo
    let i = 0;
    while (i < acum.length - 1 && acum[i + 1] <= largo + 0.5) i++;
    const xs = i < xy.length - 1 ? xy[i][0] + (xy[i + 1][0] - xy[i][0]) * (largo - acum[i]) / ((acum[i + 1] - acum[i]) || 1) : xy[i][0];
    gPuntos.selectAll("g.punto-serie").each(function (pp) {
      ver(this, pp.inc || (mostrado > 0 && x(pp.t) <= xs + 1) ? 1 : 0, animar);
    });
    ver(gMedias.node(), mostrado >= 0.999 ? 1 : 0, animar);
    ver(gCorte.node(), mostrado > 0 && enPeriodo[i].t >= corte ? 1 : 0.35, animar);
  }

  // Solo se redibuja si el tamaño cambia de verdad (y nunca con el panel oculto, sin tamaño)
  alRedimensionar(contenedor, () => {
    if (!contenedor.clientWidth || `${contenedor.clientWidth}x${contenedor.clientHeight}` === medida) return;
    dibujar(false); pintar(false);
  });
  return {
    actualizar(_, animar = true, recienMostrado = false) {
      altoMovil(contenedor); dibujar(animar);
      if (fase === 0) empezar(); else if (fase === 2) pintar(false);
    },
    tablaDatos,
    describir() {
      return plantilla(I.linea_desc, { a: pct(tramos[0].v), b: pct(tramos[1].v), corte,
        d0: tramos[0].t0, d1: tramos[0].t1, e0: tramos[1].t0, e1: tramos[1].t1 });
    },
  };
}
