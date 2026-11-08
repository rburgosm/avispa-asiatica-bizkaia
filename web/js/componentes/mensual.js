// Calendario de avisos (pasos 8 y 9): porcentaje de los avisos de abril a diciembre que llega en
// cada mes. Barras de Bizkaia 2019-2025 (naranja, la avispa), que crecen mes a mes solas, por
// tiempo, al entrar el paso (sin leer el scroll), y encima la línea de Asturias 2023-2025 con el mismo reparto (gris oscuro, otra región).
// Iconos del nido primario (pequeño, bajo) sobre la primavera y del secundario (grande, en la
// copa) sobre el verano. Nido de Morga: anillo en su mes de aviso.
// Estado: { resaltar: "primavera" | "noviembre" }
//   primavera: zona sombreada de abril a junio con el total de la estación (Bizkaia y Asturias).
//   noviembre: zona sombreada desde el 1 de noviembre y el rango de nidos retirados después.
// Datos: web/data/mensual.json, indicadores.json (pct_elim_despues_1nov), asturias_mensual.json
// (scripts/digitalizar_asturias.py → scripts/web_preparar_datos.py) y nido_hilo.json.
import { duracion, porcentaje, medidas, tabla, alRedimensionar, plantilla, envolver, formateador, tamano } from "../util.js";

// envolver() corta por cualquier espacio: vuelve a pegar el «%» suelto a la cifra de la línea anterior
function pegarPorcentaje(texto) {
  texto.each(function () {
    const ts = [...this.querySelectorAll("tspan")];
    for (let i = ts.length - 1; i > 0; i--) {
      const t = ts[i].textContent;
      if (!t.startsWith("%")) continue;
      ts[i - 1].textContent += ` ${t.split(" ")[0]}`;
      const resto = t.split(" ").slice(1).join(" ");
      if (resto) ts[i].textContent = resto;
      else {
        // la línea queda vacía: se quita y la siguiente sube
        if (ts[i + 1]) ts[i + 1].setAttribute("dy", ts[i].getAttribute("dy"));
        ts[i].remove();
        this.setAttribute("data-lineas", +this.getAttribute("data-lineas") - 1);
      }
    }
  });
}

const ESCALON = 110; // ms entre el arranque de una barra y el de la siguiente
const CRECER = 650; // ms que tarda cada barra en crecer
const RETRASO_LINEA = 500, DIBUJO_LINEA = 1700; // la línea de Asturias, mientras crecen las barras

export function crearMensual(contenedor, { mensual, indicadores, asturias, hilo }, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const pct = porcentaje(textos.idioma, 1);
  const pct0 = porcentaje(textos.idioma, 0);
  const fmt = formateador(textos.idioma, 0);
  const meses = mensual.meses;
  const T = Object.keys(mensual.temporadas);
  const filas = meses.map((mm, i) => ({ mm, i, v: mensual.proporcion_total[i] }));
  const ast = asturias && asturias.meses ? meses.map((mm) => {
    const k = asturias.meses.indexOf(mm);
    return k < 0 ? null : { mm, v: asturias.proporcion[k] };
  }).filter(Boolean) : [];
  const [desde, hasta] = indicadores.periodo;
  const despues = indicadores.temporadas.map((t, i) => ({ t, v: indicadores.pct_elim_despues_1nov[i] }))
    .filter((r) => r.t >= desde && r.t <= hasta);
  const mesHilo = hilo && hilo.nido ? hilo.nido.mes : null;
  let estado = { resaltar: "primavera" }, hiloTexto = "", esc = null;
  // fase: 0 sin empezar, 1 creciendo, 2 completo; n: barras ya mostradas (iconos y nido hilo)
  let fase = 0, n = 0, medida = "", inicio = 0;

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const g = svg.append("g");
  const zona = g.append("rect").attr("fill", "var(--sombra-zona)");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const gBarras = g.append("g");
  const gAst = g.append("g");
  const lineaAst = gAst.append("path").attr("fill", "none").attr("stroke", "var(--tinta-suave)").attr("stroke-width", 2.2)
    .attr("stroke-linejoin", "round");
  const etAst = gAst.append("text").attr("class", "etiqueta-serie etiqueta-asturias").attr("fill", "var(--tinta-suave)")
    .attr("text-anchor", "end").attr("opacity", 0);
  const gIconos = g.append("g");
  const gHilo = g.append("g").attr("class", "hilo").attr("opacity", 0);
  gHilo.append("rect").attr("class", "hilo-anillo").attr("rx", 3);
  gHilo.append("text").attr("class", "hilo-texto");
  const anot = g.append("g");
  const gLeyenda = g.append("g");

  const prim = () => estado.resaltar !== "noviembre";

  // Icono del nido: árbol (tronco y copa en gris) con el nido en naranja; primario, pequeño y
  // bajo, junto al tronco; secundario, grande y en lo alto de la copa.
  function icono(gg, tipo, a) {
    const datosIcono = [
      { k: "suelo", d: `M${-a * 0.55},0H${a * 0.55}` },
      { k: "tronco", d: `M0,0V${-a * 0.62}` },
    ];
    gg.selectAll("path").data(datosIcono, (q) => q.k).join("path").attr("d", (q) => q.d)
      .attr("stroke", "var(--tinta-suave)").attr("stroke-width", (q) => (q.k === "tronco" ? 2.5 : 1.2)).attr("fill", "none");
    gg.selectAll("ellipse.copa").data([0]).join("ellipse").attr("class", "copa")
      .attr("cx", 0).attr("cy", -a * 0.68).attr("rx", a * 0.42).attr("ry", a * 0.32)
      .attr("fill", "var(--gris-dato)").attr("opacity", 0.55);
    const nido = tipo === "primario"
      ? { cx: a * 0.15, cy: -a * 0.12, rx: a * 0.095, ry: a * 0.11 }
      : { cx: a * 0.08, cy: -a * 0.8, rx: a * 0.17, ry: a * 0.2 };
    gg.selectAll("ellipse.nido").data([nido]).join("ellipse").attr("class", "nido")
      .attr("cx", (q) => q.cx).attr("cy", (q) => q.cy).attr("rx", (q) => q.rx).attr("ry", (q) => q.ry)
      .attr("fill", "var(--acento)").attr("stroke", "var(--fondo)").attr("stroke-width", 1);
  }

  function dibujar(animar = true) {
    const te = tamano("--t-etiqueta"), tj = tamano("--t-eje"), tl = tamano("--t-leyenda");
    const estrecho = (contenedor.clientWidth || 320) < 520;
    const a = Math.round(Math.min(estrecho ? 46 : 64, (contenedor.clientHeight || 300) * 0.13)); // tamaño del icono
    // en el móvil, los rótulos largos de los iconos ocupan dos líneas
    const arriba = Math.max(a + te * (estrecho ? 4.4 : 3.2), te * 5.2);
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba, derecha: 6, abajo: tj * 2 + tl * 1.9, izquierda: tj * 3.2 });
    const dur = animar ? duracion(700) : 0;
    medida = `${contenedor.clientWidth}x${contenedor.clientHeight}`;
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const x = d3.scaleBand().domain(meses).range([0, w]).padding(0.2);
    const vmax = d3.max([...filas, ...ast], (f) => f.v);
    const y = d3.scaleLinear().domain([0, vmax * 1.55]).range([h, 0]);
    esc = { x, y, h, w, te, m };
    gEjeX.attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).tickSizeOuter(0)
      .tickFormat((mm) => I.meses[mm - 1]));
    gEjeY.call(d3.axisLeft(y).ticks(4).tickFormat((v) => pct0(v)).tickSize(-w))
      .call((s) => s.select(".domain").remove());

    // Zona resaltada (primavera o desde el 1 de noviembre)
    const medio = x.step() * x.padding() / 2;
    const z0 = prim() ? x(4) - medio : x(11) - medio;
    const z1 = prim() ? x(6) + x.bandwidth() + medio : w;
    zona.interrupt().transition().duration(dur).ease(d3.easeCubicInOut)
      .attr("x", z0).attr("width", z1 - z0).attr("y", -m.arriba + 4).attr("height", h + m.arriba - 4);

    // Barras (la altura la ponen empezar() y completar())
    gBarras.selectAll("rect").data(filas, (f) => f.mm).join((e) => e.append("rect").attr("y", h).attr("height", 0))
      .attr("x", (f) => x(f.mm)).attr("width", x.bandwidth()).attr("fill", "var(--acento)");

    // Línea de Asturias con puntos
    const linea = d3.line().x((f) => x(f.mm) + x.bandwidth() / 2).y((f) => y(f.v));
    lineaAst.attr("d", ast.length ? linea(ast) : null);
    gAst.selectAll("circle").data(ast, (f) => f.mm).join((e) => e.append("circle").attr("opacity", 0)).attr("r", 3.6)
      .attr("cx", (f) => x(f.mm) + x.bandwidth() / 2).attr("cy", (f) => y(f.v))
      .attr("fill", "var(--tinta-suave)").attr("stroke", "var(--fondo)").attr("stroke-width", 1.5);

    // Etiqueta directa de la línea de Asturias, arriba a la izquierda de su punto de julio (donde
    // la línea queda por encima de las barras); en el móvil, en dos líneas
    const pAst = ast.find((f) => f.mm === 7) || ast[0];
    etAst.datum(pAst || null).attr("data-texto", null).text(null);  // la coloca colocarAsturias()

    // Iconos en la franja superior: primario sobre mayo, secundario sobre agosto (en el móvil se
    // aparta a la derecha si los rótulos se pisan)
    const ic = [{ k: "primario", mm: 5, texto: I.mensual_primario },
      { k: "secundario", mm: 8, texto: I.mensual_secundario }];
    const gi = gIconos.selectAll("g.icono").data(ic, (q) => q.k).join((e) => {
      const gg = e.append("g").attr("class", "icono").attr("opacity", 0);
      gg.append("g").attr("class", "dibujo");
      gg.append("text").attr("class", "etiqueta-nota").attr("text-anchor", "middle");
      return gg;
    });
    let finPrevio = -Infinity;
    gi.each(function (q) {
      const gg = d3.select(this);
      const suelo = -m.arriba + a + te * 0.3;
      const tx = gg.select("text").attr("x", 0).attr("y", suelo + te * 1.05).attr("data-texto", null).text(q.texto)
        .call(envolver, estrecho ? Math.max(x.step() * 3.6, 118) : Math.max(x.step() * 3, 90));
      const anchoT = d3.max(tx.selectAll("tspan").nodes(), (n) => n.getComputedTextLength());
      const cx = Math.min(Math.max(x(q.mm) + x.bandwidth() / 2, finPrevio + anchoT / 2 + 16), w - anchoT / 2);
      finPrevio = cx + anchoT / 2;
      tx.attr("x", cx).selectAll("tspan").attr("x", cx);
      icono(gg.select("g.dibujo").attr("transform", `translate(${cx},${suelo})`), q.k, a);
    });

    // Leyenda bajo el eje: barra de Bizkaia y línea de Asturias
    const ley = [{ k: "biz", t: plantilla(I.mensual_bizkaia, { desde, hasta }) },
      ...(ast.length ? [{ k: "ast", t: plantilla(I.mensual_asturias, { desde: asturias.periodo[0], hasta: asturias.periodo[1] }) }] : [])];
    const li = gLeyenda.selectAll("g.item").data(ley, (q) => q.k).join((e) => {
      const gg = e.append("g").attr("class", "item");
      gg.append("g").attr("class", "muestra");
      gg.append("text").attr("class", "etiqueta-pequena").attr("fill", "var(--tinta)").attr("x", 22).attr("dy", "0.35em");
      return gg;
    });
    li.each(function (q) {
      const s = d3.select(this).select("g.muestra");
      s.selectAll("*").remove();
      if (q.k === "biz") s.append("rect").attr("x", 2).attr("y", -6).attr("width", 14).attr("height", 12).attr("fill", "var(--acento)");
      else {
        s.append("path").attr("d", "M0,0H18").attr("stroke", "var(--tinta-suave)").attr("stroke-width", 2.2);
        s.append("circle").attr("cx", 9).attr("r", 3.6).attr("fill", "var(--tinta-suave)").attr("stroke", "var(--fondo)").attr("stroke-width", 1.5);
      }
    });
    li.select("text").text((q) => q.t);
    let cx = 0, cy = h + tj * 2.1 + tl * 0.6;
    li.attr("transform", function () {
      const bw = this.getBBox().width;
      if (cx > 0 && cx + bw > w) { cx = 0; cy += tl * 1.3; }
      const tr = `translate(${cx},${cy})`;
      cx += bw + 18;
      return tr;
    });

    // Anotación de la zona
    const texto = prim()
      ? plantilla(I.mensual_primavera, { v: pct(mensual.estaciones.primavera) })
        + (asturias && asturias.primavera != null ? `. ${plantilla(I.mensual_primavera_asturias, { v: pct(asturias.primavera) })}` : "")
      : plantilla(I.mensual_noviembre, { min: pct(d3.min(despues, (r) => r.v)), max: pct(d3.max(despues, (r) => r.v)) });
    const ta = anot.selectAll("text").data([estado.resaltar], (k) => k).join(
      (e) => e.append("text").attr("class", "etiqueta-serie").attr("fill", "var(--tinta)").attr("opacity", 0),
      (u) => u,
      (s) => s.transition().duration(dur ? duracion(250) : 0).attr("opacity", 0).remove());
    const anchoZona = z1 - z0;
    if (prim()) {
      // Primavera: dentro del gráfico, sobre las barras bajas de la zona. Anchos posibles, por
      // preferencia (colocarEtiquetas elige el primero que no pisa nada)
      const anchos = estrecho
        // en el móvil puede salir de la zona hasta el rótulo del nido hilo (septiembre)
        ? [Math.max((mesHilo ? x(mesHilo) - 3 : w) - z0 - 18, anchoZona - 8), anchoZona - 8 + x.step(), anchoZona - 8]
        : [Math.max(anchoZona - 10, Math.min(150, w * 0.45))];
      esc.anot = { texto, anchos: anchos.filter((v, k) => k === 0 || v < anchos[0] - 1) };
      ta.attr("x", z0 + 6).attr("y", te * 0.6).attr("text-anchor", "start").attr("data-texto", null).text(texto)
        .call(envolver, esc.anot.anchos[0]).call(pegarPorcentaje);
    } else {
      esc.anot = null;
      // Noviembre: en la franja superior (los iconos se apagan); en el móvil, a la izquierda de la zona
      const izquierda = anchoZona < 260;
      ta.attr("x", izquierda ? z1 - 4 : z0 + 6).attr("y", -m.arriba + te * 1.1)
        .attr("text-anchor", izquierda ? "end" : "start").attr("data-texto", null).text(texto)
        .call(envolver, izquierda ? Math.min(w * 0.8, estrecho ? 300 : 380) : Math.max(anchoZona - 10, 120))
        .call(pegarPorcentaje);
      if (izquierda) ta.selectAll("tspan").attr("text-anchor", "end");
    }
    ta.transition().duration(dur).delay(dur ? duracion(200) : 0).attr("opacity", 1);
    esc.ta = ta;
    esc.etAst = { punto: pAst, estrecho };
    colocarEtiquetas();
  }

  // ---------------------------------------------------------------- etiquetas sin solaparse
  // Prueba de colisión con cajas (getBBox, en coordenadas de g, con un margen): por orden, la
  // anotación de la zona (varios anchos), el texto del nido hilo (sobre su mes o alineado a la
  // derecha, más ancho y con menos líneas) y la etiqueta directa de Asturias (junto a uno de sus
  // puntos; si ninguno está libre se omite: la leyenda ya la nombra). Obstáculos: barras, línea y
  // puntos de Asturias, anillo del nido hilo e iconos con sus rótulos (en primavera).
  const MARGEN = 1.5;  // por caja: entre dos textos quedan al menos 3 px
  const caja = (node, dy = 0) => {
    const b = node.getBBox();
    return { x0: b.x - MARGEN, y0: b.y + dy - MARGEN, x1: b.x + b.width + MARGEN, y1: b.y + b.height + dy + MARGEN };
  };
  const solape = (c, lista) => lista.reduce((s, o) => s
    + Math.max(0, Math.min(c.x1, o.x1) - Math.max(c.x0, o.x0)) * Math.max(0, Math.min(c.y1, o.y1) - Math.max(c.y0, o.y0)), 0);
  function obstaculos() {
    const { x, y, h } = esc;
    const bw = x.bandwidth();
    const lista = filas.map((f) => ({ x0: x(f.mm), y0: y(f.v), x1: x(f.mm) + bw, y1: h }));
    const xy = ast.map((f) => [x(f.mm) + bw / 2, y(f.v)]);
    xy.forEach(([px, py], k) => {
      lista.push({ x0: px - 4, y0: py - 4, x1: px + 4, y1: py + 4 });
      if (!k) return;
      const [qx, qy] = xy[k - 1], pasos = Math.ceil(Math.hypot(px - qx, py - qy) / 3);
      for (let j = 1; j < pasos; j++) {
        const cx = qx + (px - qx) * j / pasos, cy = qy + (py - qy) * j / pasos;
        lista.push({ x0: cx - 1.5, y0: cy - 1.5, x1: cx + 1.5, y1: cy + 1.5 });
      }
    });
    const anillo = gHilo.select("rect");
    if (hiloActivo() && anillo.attr("width")) {
      lista.push({ x0: +anillo.attr("x"), y0: +anillo.attr("y"), x1: +anillo.attr("x") + +anillo.attr("width"), y1: h });
    }
    const iconos = [];
    if (prim()) {
      gIconos.selectAll("g.icono").each(function () {
        const gg = d3.select(this);
        iconos.push(caja(gg.select("text").node()));
        const b = gg.select("g.dibujo").node().getBBox(), tr = gg.select("g.dibujo").attr("transform");
        const [, tx, ty] = /translate\(([-\d.e]+),([-\d.e]+)\)/.exec(tr) || [0, 0, 0];
        iconos.push({ x0: b.x + +tx, y0: b.y + +ty, x1: b.x + b.width + +tx, y1: b.y + b.height + +ty });
      });
    }
    return { bajos: lista, iconos };
  }
  const hiloActivo = () => !!(hiloTexto && mesHilo && meses.indexOf(mesHilo) >= 0);
  // Fuera del lienzo (arriba o a los lados) también cuenta como choque
  const fuera = (c) => {
    const { w, m } = esc;
    return (Math.max(0, -m.arriba - c.y0) + Math.max(0, c.x1 - (w + m.derecha)) + Math.max(0, -m.izquierda - c.x0)) * 50;
  };

  // Texto del nido hilo: candidatos {ancla, x, ancho}; la base de la última línea queda por
  // encima de todo lo que hay debajo en su franja horizontal (barras, línea, anillo)
  function candidatosHilo() {
    const { x, w } = esc;
    const i = meses.indexOf(mesHilo), x0 = x(mesHilo) - 3;
    const lista = [{ ancla: "start", x: x0, ancho: Math.max(120, w - x0) }];
    for (let j = i - 1; j >= 0; j--) lista.push({ ancla: "end", x: w, ancho: w - (x(meses[j]) - 3) });
    return lista;
  }
  function ponerHilo(c, bajos) {
    const { te } = esc;
    const t = gHilo.select("text").attr("x", c.x).attr("y", 0).attr("text-anchor", c.ancla).attr("data-texto", null)
      .text(hiloTexto).call(envolver, c.ancho);
    const b = t.node().getBBox();
    const lineas = +t.attr("data-lineas");
    const debajo = bajos.filter((o) => o.x1 > b.x && o.x0 < b.x + b.width);
    const techo = d3.min(debajo, (o) => o.y0) ?? esc.h;
    const dy = techo - 12 - (lineas - 1) * te * 1.15;
    t.attr("transform", `translate(0,${dy})`);
    return caja(t.node(), dy);
  }
  function colocarEtiquetas() {
    if (!esc || !esc.ta || !esc.ta.node()) return;
    ponerAnillo();
    const { bajos, iconos } = obstaculos();  // barras, línea y anillo; iconos con sus rótulos
    const obst = [...bajos, ...iconos];
    const nodoAnot = esc.ta.node();
    const anchos = esc.anot ? esc.anot.anchos : [null];
    const conHilo = hiloActivo();
    const cands = conHilo ? candidatosHilo() : [null];
    let mejor = null;
    buscar: for (const wa of anchos) {
      if (wa != null) esc.ta.attr("data-texto", null).text(esc.anot.texto).call(envolver, wa).call(pegarPorcentaje);
      const A = caja(nodoAnot);
      const pa = solape(A, obst) + fuera(A);
      for (const c of cands) {
        const H = c ? ponerHilo(c, bajos) : null;
        const pen = pa + (H ? solape(H, obst) + solape(H, [A]) + fuera(H) : 0);
        if (!mejor || pen < mejor.pen) mejor = { pen, wa, c };
        if (pen === 0) break buscar;
      }
    }
    if (mejor.wa != null && mejor.wa !== anchos[anchos.length - 1]) {
      esc.ta.attr("data-texto", null).text(esc.anot.texto).call(envolver, mejor.wa).call(pegarPorcentaje);
    }
    let H = null;
    if (mejor.c) H = ponerHilo(mejor.c, bajos);
    gHilo.raise();
    colocarAsturias([...obst, caja(nodoAnot), ...(H ? [H] : [])]);
  }
  // Etiqueta directa de Asturias: arriba a la izquierda (o a la derecha) de uno de sus puntos,
  // empezando por julio, donde la línea queda por encima de las barras
  function colocarAsturias(obst) {
    const { x, y, te } = esc, { punto, estrecho } = esc.etAst;
    etAst.text(null);
    if (!punto) return;
    const nombre = plantilla(I.mensual_asturias, { desde: asturias.periodo[0], hasta: asturias.periodo[1] });
    const partes = estrecho ? [nombre.slice(0, nombre.indexOf(" ")), nombre.slice(nombre.indexOf(" ") + 1)] : [nombre];
    const orden = [punto, ...ast.filter((f) => f !== punto).sort((a, b) => Math.abs(a.mm - punto.mm) - Math.abs(b.mm - punto.mm))];
    for (const f of orden) {
      for (const ancla of ["end", "start"]) {
        const xa = x(f.mm) + x.bandwidth() / 2 + (ancla === "end" ? -8 : 8);
        etAst.text(null).attr("text-anchor", ancla);
        partes.forEach((t, k) => etAst.append("tspan").attr("x", xa).attr("dy", k ? "1.1em" : 0).text(t));
        etAst.attr("x", xa).attr("y", y(f.v) - 8 - (partes.length - 1) * te * 1.1);
        const c = caja(etAst.node());
        if (!solape(c, obst) && !fuera(c)) return;
      }
    }
    etAst.text(null);  // sin sitio libre: la leyenda identifica la línea
  }

  // Entrada por tiempo, sin leer el scroll: las barras crecen mes a mes (escalonadas) y, mientras,
  // la línea de Asturias se traza (easeCubicInOut sobre stroke-dashoffset) con sus puntos y su
  // etiqueta apareciendo con un fundido cuando el trazo llega a ellos; los iconos y el anillo del
  // nido hilo, cuando crece su mes. Una vez empezada se completa aunque se salga del paso, y
  // después se queda completo (al volver no se repite).
  function verIconos(animar) {
    gIconos.selectAll("g.icono").transition("ver").duration(animar ? duracion(500) : 0)
      .attr("opacity", (q) => (prim() && n > meses.indexOf(q.mm) ? 1 : 0));
  }
  function fundir(sel, v, animar) {
    sel.each(function () {
      if (this.__v === v) return;
      this.__v = v;
      const t = d3.select(this).interrupt("ver");
      if (animar) t.transition("ver").duration(duracion(350)).attr("opacity", v); else t.attr("opacity", v);
    });
  }
  function empezar() {
    if (fase || !esc) return;
    if (!prim() || !duracion(600)) { completar(false); return; }
    fase = 1; n = 0; inicio = performance.now();
    const { x, y, h } = esc;
    gBarras.selectAll("rect").interrupt().attr("y", h).attr("height", 0)
      .transition().delay((f) => f.i * ESCALON).duration(CRECER).ease(d3.easeCubicInOut)
      .on("start", (f) => { n = Math.max(n, f.i + 1); verIconos(true); pintarHilo(n, true); })
      .attr("y", (f) => y(f.v)).attr("height", (f) => h - y(f.v));
    // Longitud del trazo hasta cada punto (la línea es recta entre puntos)
    const xy = ast.map((f) => [x(f.mm) + x.bandwidth() / 2, y(f.v)]);
    const acum = xy.map((p, i) => (i ? Math.hypot(p[0] - xy[i - 1][0], p[1] - xy[i - 1][1]) : 0));
    for (let i = 1; i < acum.length; i++) acum[i] += acum[i - 1];
    const L = acum[acum.length - 1] || 0;
    const pE = etAst.datum(), iE = pE ? ast.indexOf(pE) : -1;
    const circulos = gAst.selectAll("circle");
    fundir(circulos, 0, false); fundir(etAst, 0, false);
    lineaAst.interrupt().attr("stroke-dasharray", `${L} ${L}`).attr("stroke-dashoffset", L)
      .transition().delay(RETRASO_LINEA).duration(DIBUJO_LINEA).ease(d3.easeCubicInOut)
      .tween("trazo", () => (k) => {
        const largo = k * L;
        lineaAst.attr("stroke-dashoffset", L - largo);
        circulos.each(function (f) { fundir(d3.select(this), acum[ast.indexOf(f)] <= largo + 0.5 ? 1 : 0, true); });
        if (iE >= 0) fundir(etAst, acum[iE] <= largo + 0.5 ? 1 : 0, true);
      })
      .on("end", () => { if (fase === 1) completar(true); });
  }
  // Estado completo: todas las barras, la línea entera con sus puntos; iconos solo en primavera
  function completar(animar) {
    fase = 2; n = filas.length;
    if (!esc) return;
    const { y, h } = esc;
    gBarras.selectAll("rect").interrupt().transition().duration(animar ? duracion(700) : 0).ease(d3.easeCubicInOut)
      .attr("y", (f) => y(f.v)).attr("height", (f) => h - y(f.v));
    lineaAst.interrupt().attr("stroke-dasharray", null).attr("stroke-dashoffset", null);
    fundir(gAst.selectAll("circle"), 1, animar);
    fundir(etAst, etAst.datum() ? 1 : 0, animar);
    verIconos(animar);
    pintarHilo(n, animar);
  }

  // Anillo del nido hilo alrededor de su mes (barra y punto de Asturias)
  function ponerAnillo() {
    const i = mesHilo ? meses.indexOf(mesHilo) : -1;
    if (!esc || i < 0) return;
    const { x, y, h } = esc;
    const f = filas[i], q = ast.find((r) => r.mm === f.mm);
    const top = Math.min(y(f.v), q ? y(q.v) : Infinity);
    gHilo.select("rect").attr("x", x(f.mm) - 3).attr("y", top - 6).attr("width", x.bandwidth() + 6).attr("height", h - top + 6);
  }

  function pintarHilo(n, animar = true) {
    const i = mesHilo ? meses.indexOf(mesHilo) : -1;
    if (!esc || !hiloTexto || i < 0 || n <= i) { gHilo.interrupt().attr("opacity", 0); return; }
    ponerAnillo();
    gHilo.raise();
    if (+gHilo.attr("opacity") < 1) gHilo.transition().duration(animar ? duracion(500) : 0).delay(animar ? duracion(400) : 0).attr("opacity", 1);
  }

  function tablaDatos() {
    const cab = [I.mes, `${I.porcentaje} ${T[0]}-${T[T.length - 1]}`, ...T];
    if (ast.length) cab.splice(2, 0, `${plantilla(I.mensual_asturias, { desde: asturias.periodo[0], hasta: asturias.periodo[1] })} (%)`);
    return tabla(cab, meses.map((mm, i) => {
      const fila = [I.meses_largos[mm - 1], pct(mensual.proporcion_total[i]), ...T.map((t) => fmt(mensual.temporadas[t][i]))];
      if (ast.length) { const q = ast.find((r) => r.mm === mm); fila.splice(2, 0, q ? pct(q.v) : "–"); }
      return fila;
    }));
  }

  // Cambio de tamaño (solo si cambia de verdad; nunca con el panel oculto, sin tamaño). Justo al
  // mostrarse el panel, el lienzo se ajusta a su título: la entrada vuelve a empezar desde cero
  // con las medidas nuevas (apenas ha crecido nada). Más tarde, se completa con una transición.
  alRedimensionar(contenedor, () => {
    if (!contenedor.clientWidth || `${contenedor.clientWidth}x${contenedor.clientHeight}` === medida) return;
    dibujar(false);
    if (fase === 1 && performance.now() - inicio < 450) { fase = 0; empezar(); }
    else if (fase === 1) completar(true);
    else if (fase === 2) completar(false);
  });
  return {
    actualizar(nuevo, animar = true, recienMostrado = false) {
      estado = { resaltar: "primavera", ...nuevo };
      dibujar(animar);
      // Primera entrada: arranca la animación. Si ya ha empezado, solo cambia lo que depende del
      // estado (iconos de primavera); si llega «noviembre» a mitad, se completa con transición.
      if (fase === 0) empezar();
      else if (fase === 1 && !prim()) completar(animar);
      else if (fase === 2) completar(animar && !recienMostrado);
    },
    hilo(texto) { hiloTexto = texto; ponerAnillo(); colocarEtiquetas(); pintarHilo(n, true); },
    tablaDatos,
    nota() {
      return ast.length ? plantilla(I.mensual_nota_asturias, { desde: asturias.periodo[0], hasta: asturias.periodo[1] }) : "";
    },
    describir() {
      const max = filas.reduce((a, b) => (b.v > a.v ? b : a));
      const base = plantilla(I.mensual_desc, { primavera: pct(mensual.estaciones.primavera), verano: pct(mensual.estaciones.verano),
        otono: pct(mensual.estaciones.otono), mes: I.meses_largos[max.mm - 1], max: pct(max.v) });
      return ast.length ? `${base} ${plantilla(I.mensual_desc_asturias, { desde: asturias.periodo[0], hasta: asturias.periodo[1], v: pct(asturias.primavera) })}` : base;
    },
  };
}
