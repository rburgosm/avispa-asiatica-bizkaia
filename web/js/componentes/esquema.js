// Esquemas de los pasos 1-4, dibujados con D3 (sin imágenes externas):
//   llegada  — línea del tiempo con los hitos de la cronología (estado.hitos: fechas) y una avispa
//              esquemática (sin escala: es un icono, no una medida).
//   ciclo    — el año de un nido con los datos de Bizkaia: altura típica de los nidos retirados
//              en cada época (eje vertical, metros) y diámetro típico (tamaño del círculo).
//   circuito — vecino → ayuntamiento → Basalan, con el porcentaje de nidos que cierra Basalan.
//   censo    — un bosque con estado.nidos nidos, de los que solo estado.avisados se ven.
// Datos: web/data/esquemas.json, indicadores.json y cronologia.json. Textos: content/<idioma>.json.
import { duracion, formateador, porcentaje, medidas, alRedimensionar, plantilla, envolver, tabla } from "../util.js";

export function crearEsquema(contenedor, { esquemas, indicadores, cronologia }, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const pct = porcentaje(textos.idioma, 0);
  let estado = { vista: "llegada" };
  let vistaActual = null;

  const svg = d3.select(contenedor).append("svg").attr("role", "img").attr("class", "esquema");
  const raiz = svg.append("g");

  const hito = (fecha) => cronologia.hitos.find((h) => h.fecha === fecha);
  const [desde, hasta] = indicadores.periodo;
  const basalan = indicadores.temporadas.map((t, i) => ({ t, v: indicadores.pct_basalan[i] }))
    .filter((r) => r.t >= desde && r.t <= hasta);

  // ---------------------------------------------------------------- avispa (icono)
  function avispa(g, escala = 1) {
    const a = g.append("g").attr("transform", `scale(${escala})`);
    const clip = `clip-abdomen-${Math.random().toString(36).slice(2, 8)}`;
    a.append("clipPath").attr("id", clip).append("ellipse").attr("cx", 34).attr("cy", 0).attr("rx", 26).attr("ry", 13);
    // alas
    a.append("ellipse").attr("cx", 4).attr("cy", -16).attr("rx", 24).attr("ry", 8).attr("transform", "rotate(-12 4 -16)")
      .attr("fill", "var(--linea)").attr("opacity", 0.8).attr("stroke", "var(--gris-dato)");
    // patas (puntas amarillas)
    for (const [x0, x1] of [[-6, -14], [2, 0], [10, 14]]) {
      a.append("line").attr("x1", x0).attr("y1", 6).attr("x2", x1).attr("y2", 22).attr("stroke", "var(--tinta)").attr("stroke-width", 2);
      a.append("line").attr("x1", x1).attr("y1", 22).attr("x2", x1 + (x1 - x0) * 0.4).attr("y2", 28)
        .attr("stroke", "var(--rampa-1)").attr("stroke-width", 2.5);
    }
    // abdomen oscuro con la banda naranja
    a.append("ellipse").attr("cx", 34).attr("cy", 0).attr("rx", 26).attr("ry", 13).attr("fill", "var(--tinta)");
    a.append("rect").attr("x", 44).attr("y", -14).attr("width", 7).attr("height", 28).attr("fill", "var(--acento)")
      .attr("clip-path", `url(#${clip})`);
    // tórax y cabeza
    a.append("ellipse").attr("cx", 2).attr("cy", 0).attr("rx", 13).attr("ry", 11).attr("fill", "var(--tinta)");
    a.append("circle").attr("cx", -16).attr("cy", 0).attr("r", 9).attr("fill", "var(--tinta)");
    a.append("circle").attr("cx", -21).attr("cy", 2).attr("r", 4).attr("fill", "var(--acento)");
    a.append("path").attr("d", "M-20,-7 Q-28,-20 -34,-18 M-17,-8 Q-22,-22 -27,-24").attr("fill", "none")
      .attr("stroke", "var(--tinta)").attr("stroke-width", 1.5);
    return a;
  }

  // ---------------------------------------------------------------- vistas
  function llegada(g, w, h) {
    const lista = (estado.hitos || []).map(hito).filter(Boolean);
    const anio = (h) => +h.fecha.slice(0, 4);
    const x = d3.scaleLinear().domain([d3.min(lista, anio) - 1, Math.max(d3.max(lista, anio) + 2, hasta)]).range([20, w - 20]);
    const yl = h * 0.62;
    const ic = g.append("g").attr("transform", `translate(${w / 2 - 20},${Math.min(h * 0.2, 70)})`);
    avispa(ic, Math.min(1.6, w / 300));
    g.append("text").attr("class", "pequeno").attr("x", w / 2).attr("y", Math.min(h * 0.2, 70) + 56 * Math.min(1.6, w / 300))
      .attr("text-anchor", "middle").text(I.avispa_icono);
    g.append("line").attr("x1", x.range()[0]).attr("x2", x.range()[1]).attr("y1", yl).attr("y2", yl)
      .attr("stroke", "var(--tinta-suave)");
    const eje = g.append("g").attr("class", "eje").attr("transform", `translate(0,${yl})`)
      .call(d3.axisBottom(x).tickValues(d3.range(Math.ceil(x.domain()[0] / 4) * 4, x.domain()[1] + 1, 4)
        .filter((v) => !lista.some((hh) => Math.abs(anio(hh) - v) < 2))).tickFormat(String).tickSize(5));
    eje.select(".domain").remove();
    const posX = (hh) => x(anio(hh) + (hh.fecha.length > 4 ? (+hh.fecha.slice(5, 7) - 1) / 12 : 0));
    lista.forEach((hh, i) => {
      const arriba = i % 2 === 0;
      const xx = posX(hh);
      // Texto a la derecha del punto, hasta la siguiente etiqueta del mismo lado o el borde
      const sig = lista[i + 2];
      const anchoEt = Math.max(70, Math.min(160, (sig ? posX(sig) : w) - xx - 10));
      const gg = g.append("g").attr("opacity", 0);
      gg.append("line").attr("x1", xx).attr("x2", xx).attr("y1", yl).attr("y2", arriba ? yl - 34 : yl + 34)
        .attr("stroke", "var(--acento)");
      gg.append("circle").attr("cx", xx).attr("cy", yl).attr("r", 6).attr("fill", "var(--acento)");
      const anchor = "start";
      gg.append("text").attr("class", "grande").attr("x", xx).attr("y", arriba ? yl - 44 : yl + 50)
        .attr("text-anchor", anchor).text(hh.fecha.slice(0, 4));
      const t = gg.append("text").attr("x", xx).attr("y", arriba ? yl - 44 : yl + 50).attr("text-anchor", anchor)
        .text(I.llegada[hh.fecha] || hh.titulo).call(envolver, anchoEt);
      const n = +t.attr("data-lineas");
      // arriba: el texto crece hacia arriba desde el año; abajo, hacia abajo
      t.attr("transform", `translate(0,${arriba ? -(n * 15) - 2 : 18})`);
      if (arriba) gg.select("text.grande").attr("y", yl - 40);
      gg.transition().delay(i * 250).duration(duracion(500)).attr("opacity", 1);
    });
  }

  function ciclo(g, w, h) {
    const perfil = esquemas.perfil;
    const columnas = [...perfil.map((p) => p.epoca), "invierno"];
    const x = d3.scalePoint().domain(columnas).range([0, w]).padding(0.5);
    const estrecho = w < 480;
    const arriba = estrecho ? 70 : 56, suelo = h - (estrecho ? 78 : 50);
    const y = d3.scaleLinear().domain([0, d3.max(perfil, (p) => p.altura_m) * 1.15]).range([suelo, arriba]);
    const r = d3.scaleLinear().domain([0, d3.max(perfil, (p) => p.diam_cm)]).range([0, Math.min(x.step() * 0.32, 30)]);
    // suelo y escala de altura
    g.append("line").attr("x1", 0).attr("x2", w).attr("y1", suelo).attr("y2", suelo).attr("stroke", "var(--tinta-suave)");
    const eje = g.append("g").attr("class", "eje").call(d3.axisLeft(y).ticks(3).tickFormat((v) => `${fmt(v)} m`).tickSize(-w));
    eje.select(".domain").remove();
    eje.selectAll("text").attr("x", 2).attr("dy", -3).attr("text-anchor", "start");
    // títulos de época (arriba) y datos (debajo del suelo)
    columnas.forEach((c, i) => {
      const xx = x(c);
      const t = g.append("text").attr("x", xx).attr("y", 14).attr("text-anchor", "middle").attr("class", "grande")
        .text(I.epocas[c]).call(envolver, x.step() * 0.95);
      t.selectAll("tspan").attr("text-anchor", "middle");
      const p = perfil.find((q) => q.epoca === c);
      const gg = g.append("g").attr("opacity", 0);
      if (p) {
        const cy = y(p.altura_m);
        gg.append("line").attr("x1", xx).attr("x2", xx).attr("y1", suelo).attr("y2", cy)
          .attr("stroke", "var(--tinta-suave)").attr("stroke-dasharray", "3 3");
        gg.append("circle").attr("cx", xx).attr("cy", cy).attr("r", r(p.diam_cm))
          .attr("fill", "var(--acento)").attr("stroke", "var(--tinta)").attr("stroke-width", 1);
        const d = gg.append("text").attr("x", xx).attr("y", suelo + 18).attr("text-anchor", "middle")
          .text(plantilla(I.ciclo_dato, { d: fmt(p.diam_cm), a: fmt(p.altura_m), arbol: pct(p.pct_arbol) }))
          .call(envolver, x.step() * 0.95);
        d.selectAll("tspan").attr("text-anchor", "middle");
      } else {
        // invierno: el nido muere; las futuras reinas pasan el invierno escondidas fuera
        for (let k = 0; k < 5; k++) {
          gg.append("circle").attr("cx", xx - 16 + k * 8).attr("cy", suelo - 8 - (k % 2) * 6).attr("r", 2.5).attr("fill", "var(--tinta)");
        }
        const d = gg.append("text").attr("x", xx).attr("y", suelo + 18).attr("text-anchor", "middle")
          .text(I.ciclo_invierno).call(envolver, x.step() * 0.95);
        d.selectAll("tspan").attr("text-anchor", "middle");
      }
      gg.transition().delay(i * 300).duration(duracion(500)).attr("opacity", 1);
    });
  }

  function circuito(g, w, h) {
    const nodos = I.circuito_nodos;
    const vertical = w < 420;
    const n = nodos.length;
    const caja = vertical ? { w: Math.min(w * 0.8, 260), h: 54 } : { w: Math.min((w - 40) / n - 24, 170), h: 70 };
    const pos = nodos.map((_, i) => (vertical
      ? { x: w / 2, y: 62 + i * ((h - 170) / (n - 1)) }
      : { x: (i + 0.5) * (w / n), y: Math.max(h * 0.42, 80) }));
    const p16 = hito("2016-07-01");
    if (p16) {
      g.append("text").attr("x", w / 2).attr("y", pos[0].y - caja.h / 2 - 16).attr("text-anchor", "middle").attr("class", "pequeno")
        .text(plantilla(I.circuito_desde, { mes: I.meses_largos[+p16.fecha.slice(5, 7) - 1], anio: p16.fecha.slice(0, 4) }));
    }
    // flechas
    g.append("defs").append("marker").attr("id", "flecha").attr("viewBox", "0 0 10 10").attr("refX", 9).attr("refY", 5)
      .attr("markerWidth", 7).attr("markerHeight", 7).attr("orient", "auto-start-reverse")
      .append("path").attr("d", "M0,0 L10,5 L0,10 z").attr("fill", "var(--tinta-suave)");
    for (let i = 0; i < n - 1; i++) {
      const a = pos[i], b = pos[i + 1];
      g.append("line").attr("stroke", "var(--tinta-suave)").attr("stroke-width", 1.5).attr("marker-end", "url(#flecha)")
        .attr("x1", vertical ? a.x : a.x + caja.w / 2 + 2).attr("y1", vertical ? a.y + caja.h / 2 + 2 : a.y)
        .attr("x2", vertical ? b.x : b.x - caja.w / 2 - 4).attr("y2", vertical ? b.y - caja.h / 2 - 4 : b.y);
    }
    nodos.forEach((nd, i) => {
      const gg = g.append("g").attr("transform", `translate(${pos[i].x},${pos[i].y})`).attr("opacity", 0);
      const ultimo = i === n - 1;
      gg.append("rect").attr("x", -caja.w / 2).attr("y", -caja.h / 2).attr("width", caja.w).attr("height", caja.h).attr("rx", 4)
        .attr("fill", ultimo ? "var(--acento-2)" : "var(--fondo)").attr("stroke", ultimo ? "var(--acento-2)" : "var(--tinta-suave)");
      const t = gg.append("text").attr("text-anchor", "middle").attr("y", nd.detalle ? -4 : 5);
      t.append("tspan").attr("class", "grande").attr("x", 0).attr("fill", ultimo ? "var(--blanco)" : "var(--tinta)").text(nd.nombre);
      if (nd.detalle) t.append("tspan").attr("x", 0).attr("dy", "1.3em").attr("font-size", 12)
        .attr("fill", ultimo ? "var(--blanco)" : "var(--tinta-suave)").text(nd.detalle);
      gg.transition().delay(i * 300).duration(duracion(500)).attr("opacity", 1);
    });
    // Debajo: lo que hace Basalan (dato), los bomberos y el registro público
    const ult = pos[n - 1];
    const yb = vertical ? ult.y + caja.h / 2 + 22 : ult.y + caja.h / 2 + 24;
    const lineas = [
      plantilla(I.circuito_basalan, { min: pct(d3.min(basalan, (r) => r.v)), max: pct(d3.max(basalan, (r) => r.v)), desde, hasta }),
      I.circuito_bomberos, I.circuito_registro];
    const txt = g.append("text").attr("x", vertical ? w / 2 : w / 2).attr("y", yb).attr("text-anchor", "middle");
    lineas.forEach((l, k) => txt.append("tspan").attr("x", w / 2).attr("dy", k ? "1.4em" : 0)
      .attr("class", k ? "pequeno" : null).attr("font-weight", k ? 400 : 600).text(l));
  }

  function censo(g, w, h) {
    const N = estado.nidos || 10, A = estado.avisados || 2;
    const azar = d3.randomLcg(7);
    const cols = Math.max(5, Math.floor(w / 46)), filas = Math.max(4, Math.floor((h - 90) / 46));
    const dx = w / cols, dy = (h - 90) / filas;
    // árboles
    const arboles = [];
    for (let f = 0; f < filas; f++) for (let c = 0; c < cols; c++) {
      arboles.push({ x: (c + 0.5 + (f % 2 ? 0.25 : -0.25)) * dx, y: 40 + (f + 0.5) * dy });
    }
    g.append("g").selectAll("path").data(arboles).join("path")
      .attr("d", (a) => `M${a.x},${a.y - dy * 0.42} L${a.x + dx * 0.3},${a.y + dy * 0.3} L${a.x - dx * 0.3},${a.y + dy * 0.3} Z`)
      .attr("fill", "var(--linea)");
    // nidos: posiciones fijas (semilla) sobre árboles distintos
    const elegidos = d3.shuffler(azar)(arboles.slice()).slice(0, N)
      .map((a, i) => ({ ...a, avisado: i < A }));
    const gn = g.append("g").selectAll("g").data(elegidos).join("g").attr("transform", (a) => `translate(${a.x},${a.y - dy * 0.05})`);
    gn.append("circle").attr("r", 7).attr("fill", "var(--fondo)").attr("stroke", "var(--tinta-suave)").attr("stroke-dasharray", "2 2");
    gn.filter((a) => a.avisado).select("circle").transition().delay(500).duration(duracion(600))
      .attr("fill", "var(--acento)").attr("stroke", "var(--tinta)").attr("stroke-dasharray", null).attr("r", 9);
    gn.filter((a) => a.avisado).append("circle").attr("r", 9).attr("fill", "none").attr("stroke", "var(--acento)")
      .attr("opacity", 0).transition().delay(900).duration(duracion(600)).attr("r", 16).attr("opacity", 0.6);
    // leyenda directa
    const ly = h - 34;
    const l1 = g.append("g").attr("transform", `translate(4,${ly})`);
    l1.append("circle").attr("r", 8).attr("cx", 8).attr("fill", "var(--acento)").attr("stroke", "var(--tinta)");
    l1.append("text").attr("x", 22).attr("dy", "0.35em").text(plantilla(I.censo_avisados, { n: A }));
    const l2 = g.append("g").attr("transform", `translate(4,${ly + 22})`);
    l2.append("circle").attr("r", 7).attr("cx", 8).attr("fill", "var(--fondo)").attr("stroke", "var(--tinta-suave)").attr("stroke-dasharray", "2 2");
    l2.append("text").attr("x", 22).attr("dy", "0.35em").text(plantilla(I.censo_sin_ver, { n: N - A }));
    g.append("text").attr("class", "pequeno").attr("x", 0).attr("y", 16).text(I.censo_nota).call(envolver, w);
  }

  const VISTAS = { llegada, ciclo, circuito, censo };

  function dibujar(animar = true) {
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: 8, derecha: 8, abajo: 8, izquierda: 8 });
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    const cambia = vistaActual !== estado.vista;
    vistaActual = estado.vista;
    const vieja = raiz.selectAll("g.vista");
    if (cambia && animar && duracion()) vieja.transition().duration(duracion(300)).attr("opacity", 0).remove();
    else vieja.remove();
    const g = raiz.append("g").attr("class", "vista").attr("transform", `translate(${m.izquierda},${m.arriba})`);
    (VISTAS[estado.vista] || llegada)(g, w, h);
    if (cambia && animar && duracion()) g.attr("opacity", 0).transition().delay(150).duration(duracion(400)).attr("opacity", 1);
  }

  alRedimensionar(contenedor, () => { vistaActual = null; dibujar(false); });
  return {
    nota() { return estado.vista === "ciclo" ? plantilla(I.ciclo_nota, { desde, hasta }) : ""; },
    actualizar(nuevo, animar = true) { estado = { vista: "llegada", ...nuevo }; dibujar(animar); },
    tablaDatos() {
      // Dos tablas: el perfil de los nidos por época (paso 2) y los hitos de la línea del tiempo (paso 1)
      const caja = document.createElement("div");
      caja.appendChild(tabla([I.epoca, I.nidos_retirados, I.diametro_tipico, I.altura_tipica, I.en_arbol],
        esquemas.perfil.map((p) => [I.epocas[p.epoca], fmt(p.n), `${fmt(p.diam_cm)} cm`, `${fmt(p.altura_m)} m`, pct(p.pct_arbol)]),
        I.tabla_perfil));
      const fechas = textos.pasos.flatMap((p) => (p.estado && p.estado.hitos) || []);
      caja.appendChild(tabla([I.fecha, I.hito, I.fuente], fechas.map(hito).filter(Boolean).map((hh) => [hh.fecha, hh.titulo, hh.url]),
        I.tabla_hitos));
      return caja;
    },
    describir() {
      if (estado.vista === "ciclo") {
        return esquemas.perfil.map((p) => plantilla(I.ciclo_desc, { epoca: I.epocas[p.epoca], n: fmt(p.n), d: fmt(p.diam_cm),
          a: fmt(p.altura_m), arbol: pct(p.pct_arbol) })).join(" ");
      }
      if (estado.vista === "circuito") {
        return plantilla(I.circuito_basalan, { min: pct(d3.min(basalan, (r) => r.v)), max: pct(d3.max(basalan, (r) => r.v)), desde, hasta });
      }
      return "";
    },
  };
}
