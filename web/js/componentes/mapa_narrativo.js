// Mapa de la narración: cartografía propia con D3 en SVG (y los puntos en un <canvas>), sin teselas.
// Proyección cilíndrica equidistante con paralelo estándar de 43,2° (x = λ·cos 43,2°, y = φ), en
// kilómetros: a la escala de Bizkaia la deformación es despreciable y el relieve sombreado
// (data/relieve.webp, en grados) encaja como un rectángulo. La cámara es una transformación del
// grupo SVG y del canvas (interpolación de zoom de D3, el equivalente de un «vuelo»), así que los
// trazos y los rótulos no se deforman.
// Capas, de abajo arriba: relieve, densidad por bandas (una capa por temporada y la media),
// coroplético de tasas, Bilbao rayado, límites municipales finos, contorno de Bizkaia, resalte de los
// municipios pequeños; puntos (canvas); rótulos de comarcas y cabeceras; marcador del nido hilo.
import { duracion, sinMovimiento, variableCss } from "../util.js";

const K = Math.cos((43.2 * Math.PI) / 180);
const LON0 = -2.9, LAT0 = 43.2;
const X = (lon) => (lon - LON0) * K * 111.32;
const Y = (lat) => -(lat - LAT0) * 110.57;

export function crearMapaNarrativo(contenedor, datos, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const proy = d3.geoTransform({ point(x, y) { this.stream.point(X(x), Y(y)); } });
  const camino = d3.geoPath(proy);
  const rampa = [1, 2, 3, 4, 5].map((k) => variableCss(`--rampa-${k}`));
  const geo = datos.municipios, cortes = geo.cortes_tasa;

  contenedor.innerHTML = "";
  const svgF = d3.select(contenedor).append("svg").attr("class", "mapa-fondo").attr("aria-hidden", "true")
    .style("transform-origin", "0 0").style("will-change", "transform");
  const defs = svgF.append("defs");
  const pat = defs.append("pattern").attr("id", "rayado-mapa").attr("patternUnits", "userSpaceOnUse")
    .attr("width", 7).attr("height", 7).attr("patternTransform", "rotate(45)");
  pat.append("rect").attr("width", 7).attr("height", 7).attr("fill", "var(--mapa-tierra)");
  pat.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 7).attr("stroke", "var(--gris-dato)").attr("stroke-width", 2.6);
  const mundo = svgF.append("g").attr("class", "mundo");
  const r = datos.relieve.caja;
  mundo.append("image").attr("href", "data/relieve.webp").attr("preserveAspectRatio", "none")
    .attr("x", X(r[0])).attr("y", Y(r[3])).attr("width", X(r[2]) - X(r[0])).attr("height", Y(r[1]) - Y(r[3]));
  const gDens = mundo.append("g");
  const capasDens = {};
  for (const capa of ["media", ...datos.densidad.temporadas.map(String)]) {
    const g = gDens.append("g").attr("class", "capa-densidad").attr("opacity", 0).style("display", "none");
    g.selectAll("path").data(datos.densidad.features.filter((f) => f.properties.capa === capa)).join("path")
      .attr("d", camino).attr("fill", (f) => rampa[Math.min(f.properties.banda, 4)]).attr("fill-rule", "evenodd");
    capasDens[capa] = g;
  }
  // Capas que no salen en la portada (tasas, comarcas, municipios pequeños): sus grupos se crean ya
  // (para el orden de dibujo) y sus trazados en momentos libres (requestIdleCallback), uno por turno;
  // si una hace falta antes, se construye en el momento (construir()).
  const gTasa = mundo.append("g").attr("opacity", 0).style("display", "none");
  // Comarcas (sin Bilbao): coroplético por la medida activa, con transición de color
  const gComarcas = mundo.append("g").attr("opacity", 0).style("display", "none");
  const comarcas = datos.comarcas ? datos.comarcas.features : [];
  let pComarcas = null;
  mundo.append("path").datum(geo.features.find((f) => f.properties.sin_datos)).attr("d", camino)
    .attr("fill", "url(#rayado-mapa)").attr("opacity", 0.9);
  mundo.append("g").selectAll("path").data(geo.features).join("path").attr("d", camino).attr("class", "limite-municipal");
  mundo.append("path").datum(datos.contorno).attr("d", camino).attr("class", "contorno-bizkaia");
  const gPeq = mundo.append("g").attr("opacity", 0).style("display", "none");
  const PENDIENTES = new Map([
    [gTasa, () => gTasa.selectAll("path").data(geo.features.filter((f) => !f.properties.sin_datos)).join("path").attr("d", camino)
      .attr("fill", (f) => { const t = f.properties.tasa ?? 0; return rampa[cortes.filter((c) => t >= c).length]; })],
    [gPeq, () => gPeq.selectAll("path").data(geo.features.filter((f) => f.properties.pob < 2000)).join("path").attr("d", camino)
      .attr("class", "resalte-municipio")],
    [gComarcas, () => { pComarcas = gComarcas.selectAll("path").data(comarcas).join("path").attr("d", camino)
      .attr("fill", "var(--mapa-tierra)").attr("class", "comarca"); }],
  ]);
  function construir(g) {
    const f = PENDIENTES.get(g);
    if (f) { PENDIENTES.delete(g); f(); }
  }
  const enReposo = window.requestIdleCallback || ((fn) => setTimeout(() => fn({ timeRemaining: () => 8 }), 300));
  const siguiente = (plazo) => {
    if (!PENDIENTES.size) return;
    if (plazo.timeRemaining() > 6) construir(PENDIENTES.keys().next().value);
    enReposo(siguiente, { timeout: 4000 });
  };
  // Empieza cuando la portada ya está pintada (tras la carga de la página)
  const empezarConstruccion = () => setTimeout(() => enReposo(siguiente, { timeout: 4000 }), 1500);
  if (document.readyState === "complete") empezarConstruccion(); else addEventListener("load", empezarConstruccion, { once: true });

  // Puntos en canvas (miles de nidos: SVG sería lento en un móvil)
  const lienzo = d3.select(contenedor).append("canvas").attr("class", "mapa-puntos").attr("aria-hidden", "true")
    .style("transform-origin", "0 0");
  const ctx = lienzo.node().getContext("2d");
  const pts = [];
  const nidos = datos.nidos, c = nidos.campos.length;
  for (let i = 0; i < nidos.datos.length; i += c) pts.push([X(nidos.datos[i]), Y(nidos.datos[i + 1]), datos.indice(nidos.datos[i + 2], nidos.datos[i + 3])]);
  pts.sort((a, b) => a[2] - b[2]);

  // Rótulos (en pantalla, para que no se escalen con el zoom)
  const svgR = d3.select(contenedor).append("svg").attr("class", "mapa-rotulos").attr("aria-hidden", "true");
  const lug = datos.lugares.features;
  const gCom = svgR.append("g").selectAll("text").data(lug.filter((f) => f.properties.tipo === "comarca")).join("text")
    .attr("class", "rotulo-comarca").attr("text-anchor", "middle").text((f) => f.properties.nombre.toUpperCase());
  const gCab = svgR.append("g").selectAll("g").data(lug.filter((f) => f.properties.tipo === "cabecera")).join("g").attr("class", "cabecera");
  gCab.append("circle").attr("r", 2.8);
  gCab.append("text").attr("x", 6).attr("dy", "0.35em").text((f) => f.properties.nombre.split("/")[0]);
  // Rótulos de comarca con su valor (modo comarcas)
  const centroComarca = (f) => { const b = d3.geoBounds(f); return [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2]; };
  const lugarComarca = Object.fromEntries(lug.filter((f) => f.properties.tipo === "comarca").map((f) => [f.properties.nombre, f.geometry.coordinates]));
  const gComVPadre = svgR.append("g").attr("class", "comarcas-valor").attr("opacity", 0);
  const gComV = gComVPadre.selectAll("g").data(comarcas).join("g");
  gComV.append("text").attr("class", "rotulo-comarca").attr("text-anchor", "middle").attr("dy", "-0.2em").text((f) => f.properties.nombre.toUpperCase());
  gComV.append("text").attr("class", "valor-comarca").attr("text-anchor", "middle").attr("dy", "1.05em");
  let modoComarcas = false;
  const gHilo = svgR.append("g").attr("class", "marca-hilo").attr("opacity", 0);
  gHilo.append("circle").attr("r", 13).attr("class", "hilo-anillo");
  gHilo.append("circle").attr("r", 5).attr("fill", "var(--acento)").attr("stroke", "var(--fondo)").attr("stroke-width", 2);

  let W = 0, H = 0, t = d3.zoomIdentity, frame = -1, tenue = false, vista = null, alMover = () => {};
  // Mientras el escenario está oculto (gráficos de otras paradas), el mapa no dibuja ni recoloca nada:
  // solo apunta que está «sucio» y se pone al día, de una vez, cuando vuelve a verse.
  const escenario = contenedor.closest(".escenario");
  const seVe = () => !escenario || escenario.classList.contains("visible");
  let sucio = false;
  // Con el mapa de detalle (MapLibre) delante, este mapa se queda transparente: al terminar el fundido
  // se oculta del todo (visibility), para que el navegador no lo siga componiendo en cada fotograma.
  let ocultarTrasFundido = 0;
  const revisarDetalle = () => {
    const det = escenario.classList.contains("detalle");
    clearTimeout(ocultarTrasFundido);
    if (det) ocultarTrasFundido = setTimeout(() => { contenedor.style.visibility = "hidden"; }, 900);
    else contenedor.style.visibility = "";
  };
  if (escenario) {
    new MutationObserver(() => { revisarDetalle(); if (seVe() && sucio) { sucio = false; aplicarTransformacion(); } })
      .observe(escenario, { attributes: true, attributeFilter: ["class"] });
  }
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const colorPunto = variableCss("--acento"), colorMes = variableCss("--rampa-1");

  // El lienzo de puntos solo cubre la caja de los puntos en pantalla (recortada a la pantalla), no la
  // pantalla entera: en la vista de Bizkaia en el móvil son varias veces menos píxeles que pintar y
  // componer en cada fotograma. Cambia de tamaño solo cuando cambia esa caja (al mover la cámara).
  let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
  for (const q of pts) if (q[2] >= 0) { xMin = Math.min(xMin, q[0]); xMax = Math.max(xMax, q[0]); yMin = Math.min(yMin, q[1]); yMax = Math.max(yMax, q[1]); }
  const caja = { x: 0, y: 0, w: 0, h: 0 };
  function ajustarLienzo(m) {
    const x0 = Math.max(0, Math.floor(t.x + t.k * xMin - m)), x1 = Math.min(W, Math.ceil(t.x + t.k * xMax + m));
    const y0 = Math.max(0, Math.floor(t.y + t.k * yMin - m)), y1 = Math.min(H, Math.ceil(t.y + t.k * yMax + m));
    const w = Math.max(0, x1 - x0), h = Math.max(0, y1 - y0);
    if (w !== caja.w || h !== caja.h) {
      lienzo.attr("width", Math.round(w * dpr)).attr("height", Math.round(h * dpr)).style("width", `${w}px`).style("height", `${h}px`);
    }
    if (x0 !== caja.x || y0 !== caja.y) lienzo.style("left", `${x0}px`).style("top", `${y0}px`);
    Object.assign(caja, { x: x0, y: y0, w, h });
  }
  let pedido = 0, vacio = true, vuelo = false, tDibujo = null, msDibujo = 0;
  // Durante un vuelo de cámara, el lienzo de puntos no se redibuja en cada fotograma: entre dos
  // dibujos (como mucho cada 90 ms) se desplaza y escala con una transformación CSS (solo
  // composición, sin repintar ni subir el lienzo a la GPU); al terminar el vuelo, dibujo nítido.
  function puntosEnVuelo() {
    if (!vuelo || !tDibujo || vacio || performance.now() - msDibujo > 90) { dibujarPuntos(); return; }
    const r = t.k / tDibujo.k;
    lienzo.style("transform", `translate(${r * (caja.x - tDibujo.x) + t.x - caja.x}px,${r * (caja.y - tDibujo.y) + t.y - caja.y}px) scale(${r})`);
  }
  const pedirPuntos = () => { if (!pedido) pedido = requestAnimationFrame(() => { pedido = 0; dibujarPuntos(); }); };
  function dibujarPuntos() {
    if (pedido) { cancelAnimationFrame(pedido); pedido = 0; }
    if (!seVe()) { sucio = true; return; }
    if (frame < 0 && vacio) return;
    const rr = Math.max(1.1, 1.25 * Math.sqrt(t.k / 9)) / t.k;
    ajustarLienzo(rr * 2.2 * t.k + 2);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, lienzo.node().width, lienzo.node().height);
    if (tDibujo) lienzo.style("transform", null);
    tDibujo = t; msDibujo = performance.now();
    vacio = frame < 0 || !caja.w;
    lienzo.style("visibility", vacio ? "hidden" : null);  // lienzo vacío: fuera de la composición
    if (vacio) return;
    ctx.setTransform(dpr * t.k, 0, 0, dpr * t.k, dpr * (t.x - caja.x), dpr * (t.y - caja.y));
    ctx.globalAlpha = tenue ? 0.3 : 0.78;
    ctx.fillStyle = colorPunto;
    ctx.beginPath();
    for (const p of pts) {
      if (p[2] < 0) continue;
      if (p[2] > frame) break;
      ctx.moveTo(p[0] + rr, p[1]);
      ctx.arc(p[0], p[1], rr, 0, 2 * Math.PI);
    }
    ctx.fill();
    if (!tenue && frame < datos.N - 1) {  // los del mes en curso, encendidos
      ctx.globalAlpha = 0.9;
      ctx.fillStyle = colorMes;
      ctx.beginPath();
      for (const p of pts) {
        if (p[2] !== frame) continue;
        ctx.moveTo(p[0] + rr * 2.2, p[1]);
        ctx.arc(p[0], p[1], rr * 2.2, 0, 2 * Math.PI);
      }
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  // Fondo (relieve, capas y límites, en SVG): durante un vuelo de cámara se repinta como mucho cada
  // 120 ms; entre medias se mueve con una transformación CSS del SVG entero (solo composición).
  let tFondo = null, msFondo = 0;
  function moverFondo() {
    if (vuelo && tFondo && performance.now() - msFondo < 120) {
      const r = t.k / tFondo.k;
      svgF.style("transform", `translate(${t.x - r * tFondo.x}px,${t.y - r * tFondo.y}px) scale(${r})`);
      return;
    }
    mundo.attr("transform", t);
    pat.attr("patternTransform", `scale(${1 / t.k}) rotate(45)`);
    svgF.style("transform", null);
    tFondo = t; msFondo = performance.now();
  }
  function aplicarTransformacion() {
    if (!seVe()) { sucio = true; return; }
    moverFondo();
    const p = (ll) => [t.x + t.k * X(ll[0]), t.y + t.k * Y(ll[1])];
    gCom.attr("transform", (f) => `translate(${p(f.geometry.coordinates)})`);
    gCab.attr("transform", (f) => `translate(${p(f.geometry.coordinates)})`);
    gComV.attr("transform", (f) => `translate(${p(lugarComarca[f.properties.nombre] || centroComarca(f))})`);
    const h = datos.hilo.nido;
    gHilo.attr("transform", `translate(${p([h.lon, h.lat])})`);
    puntosEnVuelo();
    ajustarPortada();
    alMover();  // primero se recolocan las anotaciones: son obstáculos para los rótulos
    evitarSolapes();
  }

  // Rótulos sin solapes ni cortes. Orden de prioridad: el rótulo del paso (p. ej. Mungia), las
  // cabeceras de más cerca a más lejos del foco de la cámara y, al final, las comarcas (solo si
  // Bizkaia se ve grande). Cada rótulo se oculta si choca con uno ya colocado, con un obstáculo
  // (cabecera del mapa, anotaciones) o si no cabe entero dentro de la pantalla.
  let obstaculos = () => [], prioridad = null;
  // Caja de un rótulo en pantalla: su caja propia (getBBox, medida una vez y guardada; se borra al
  // cambiar el tamaño) desplazada a su posición. Así no se fuerza la maquetación por cada rótulo.
  const cajasPropias = new Map();
  if (document.fonts) document.fonts.ready.then(() => cajasPropias.clear());  // medidas con la letra definitiva
  function cajaRotulo(nodo, x, y, lim) {
    let b = cajasPropias.get(nodo);
    if (!b) {
      const d = nodo.style.display;
      nodo.style.display = "";
      const bb = nodo.getBBox();
      nodo.style.display = d;
      b = { x: bb.x, y: bb.y, width: bb.width, height: bb.height };
      if (b.width) cajasPropias.set(nodo, b);
    }
    const left = lim.left + x + b.x, top = lim.top + y + b.y;
    return { left, top, right: left + b.width, bottom: top + b.height, width: b.width, height: b.height };
  }
  function evitarSolapes() {
    if (!seVe()) { sucio = true; return; }
    const lim = contenedor.getBoundingClientRect(), M = 6;
    const puestas = obstaculos().map((r) => ({ x: r.left, y: r.top, w: r.width, h: r.height }));
    const choca = (b) => puestas.some((q) => b.x < q.x + q.w && b.x + b.w > q.x && b.y < q.y + q.h && b.y + b.h > q.y);
    if (modoComarcas) {
      // Las 7 comarcas se rotulan siempre: cada rótulo (nombre y valor) se desplaza lo justo para
      // caber en la pantalla y, si choca con otro ya colocado, se prueba un poco más arriba o abajo
      gCab.style("display", "none"); gCom.style("display", "none");
      gComV.each(function (f) {
        const ll = lugarComarca[f.properties.nombre] || centroComarca(f);
        const bx = t.x + t.k * X(ll[0]), by = t.y + t.k * Y(ll[1]);
        const base = `translate(${bx},${by})`;
        this.setAttribute("transform", base);
        const r = cajaRotulo(this, bx, by, lim);
        const dx = r.left < lim.left + M ? lim.left + M - r.left : r.right > lim.right - M ? lim.right - M - r.right : 0;
        const desp = [0, -12, 12, -24, 24, -36, 36, -48, 48].find((dy) => !choca({ x: r.left + dx - 2, y: r.top + dy - 1, w: r.width + 4, h: r.height + 2 })) ?? 0;
        puestas.push({ x: r.left + dx - 2, y: r.top + desp - 1, w: r.width + 4, h: r.height + 2 });
        if (dx || desp) this.setAttribute("transform", `${base} translate(${dx},${desp})`);
      });
      return;
    }
    const cabe = (r) => r.left >= lim.left + M && r.right <= lim.right - M && r.top >= lim.top + M && r.bottom <= lim.bottom - M;
    const colocar = (nodo, extra = false) => {
      const ll = d3.select(nodo).datum().geometry.coordinates;
      const r = cajaRotulo(nodo, t.x + t.k * X(ll[0]), t.y + t.k * Y(ll[1]), lim);
      nodo.style.display = "";
      const b = { x: r.left - 3, y: r.top - 2, w: r.width + 6, h: r.height + 4 };
      if (extra || !cabe(r) || choca(b)) nodo.style.display = "none"; else puestas.push(b);
    };
    const pad = vista ? vista.pad : { left: 0, right: 0, top: 0, bottom: 0 };
    const fx = (pad.left + W - pad.right) / 2, fy = (pad.top + H - pad.bottom) / 2;
    const dist = (f) => { const ll = f.geometry.coordinates, x = t.x + t.k * X(ll[0]) - fx, y = t.y + t.k * Y(ll[1]) - fy; return x * x + y * y; };
    const nombre = (f) => f.properties.nombre.split("/")[0];
    gCab.nodes().map((n) => [n, d3.select(n).datum()])
      .sort((a, b) => (nombre(b[1]) === prioridad) - (nombre(a[1]) === prioridad) || dist(a[1]) - dist(b[1]))
      .forEach(([n]) => colocar(n));
    const anchoBizkaia = t.k * (X(-2.41) - X(-3.46));
    gCom.each(function () { colocar(this, anchoBizkaia < 520 || t.k > 60); });
  }

  function medir() {
    cajasPropias.clear();
    W = contenedor.clientWidth; H = contenedor.clientHeight;
    svgF.attr("viewBox", `0 0 ${W} ${H}`); svgR.attr("viewBox", `0 0 ${W} ${H}`);
    caja.w = caja.h = -1;  // el lienzo se vuelve a medir en el próximo dibujo
  }

  // Transformación que encaja una caja [[oeste, sur], [este, norte]] en la pantalla con márgenes
  function encajar(caja, pad) {
    const x0 = X(caja[0][0]), x1 = X(caja[1][0]), y0 = Y(caja[1][1]), y1 = Y(caja[0][1]);
    const aw = Math.max(50, W - pad.left - pad.right), ah = Math.max(50, H - pad.top - pad.bottom);
    const k = Math.min(aw / (x1 - x0), ah / (y1 - y0));
    return d3.zoomIdentity.translate(pad.left + (aw - k * (x1 - x0)) / 2 - k * x0, pad.top + (ah - k * (y1 - y0)) / 2 - k * y0).scale(k);
  }

  // Cámara con d3-zoom programático (sin gestos: la mueve el scroll). zoom.transform sobre una
  // transición interpola con d3.interpolateZoom (van Wijk y Nuij): entre dos focos alejados se aleja
  // hacia la vista de Bizkaia y vuelve a acercarse en un solo movimiento continuo. 1-1,5 s con
  // easeCubicInOut; una cámara nueva interrumpe la anterior desde donde esté (sin saltos).
  const zoom = d3.zoom().on("zoom", (e) => { t = e.transform; aplicarTransformacion(); });
  function camara(caja, pad, animar = true) {
    vista = { caja, pad };
    const destino = encajar(caja, pad);
    svgF.interrupt("camara");
    vuelo = false;
    svgF.node().__zoom = t;
    if (!animar || sinMovimiento() || !W || !seVe()) { zoom.transform(svgF, destino); return; }
    const a = [(W / 2 - t.x) / t.k, (H / 2 - t.y) / t.k, W / t.k];
    const b = [(W / 2 - destino.x) / destino.k, (H / 2 - destino.y) / destino.k, W / destino.k];
    const ms = Math.max(1200, Math.min(1500, d3.interpolateZoom(a, b).duration * 0.6));
    if (Math.abs(destino.k / t.k - 1) < 1e-3 && Math.hypot(destino.x - t.x, destino.y - t.y) < 0.5) { zoom.transform(svgF, destino); return; }
    vuelo = true;
    svgF.transition("camara").duration(ms).ease(d3.easeCubicInOut).call(zoom.transform, destino)
      .on("end", () => { vuelo = false; dibujarPuntos(); moverFondo(); });
  }

  // Imagen estática de la portada (debajo del mapa vivo hasta que este termina su fundido): se
  // ajusta al píxel al encuadre de la cámara, con la extensión del relieve (la misma que la imagen)
  const imgPortada = document.getElementById("portada-mapa");
  function ajustarPortada() {
    if (!imgPortada || imgPortada.hidden || !vista) return;
    const s = imgPortada.style;
    s.left = `${t.x + t.k * X(r[0])}px`; s.top = `${t.y + t.k * Y(r[3])}px`;
    s.width = `${t.k * (X(r[2]) - X(r[0]))}px`; s.height = `${t.k * (Y(r[1]) - Y(r[3]))}px`;
  }

  // Fundidos de capas con transiciones CSS de opacity (no con d3 sobre el atributo): el navegador no
  // tiene que volver a pintar el SVG entero en cada fotograma del fundido. Una capa a 0 sale del
  // dibujo (display: none) al terminar su fundido.
  function opacidad(sel, v, ms = 700) {
    const n = sel.node();
    if (v > 0) construir(sel);
    const antes = n.__op ?? +sel.attr("opacity");
    if (antes === v) return;
    n.__op = v;
    clearTimeout(n.__fin);
    cancelAnimationFrame(n.__raf);
    const d = duracion(ms);
    const poner = () => { n.style.transition = d ? `opacity ${d}ms ease` : "none"; n.style.opacity = String(v); };
    if (v > 0 && n.style.display === "none") {
      n.style.transition = "none"; n.style.opacity = "0"; n.style.display = "";
      if (d) n.__raf = requestAnimationFrame(() => { n.__raf = requestAnimationFrame(poner); }); else poner();
    } else poner();
    if (v === 0) n.__fin = setTimeout(() => { if (n.__op === 0) n.style.display = "none"; }, d + 60);
  }


  new ResizeObserver(() => {
    medir();
    if (vista) t = encajar(vista.caja, vista.pad);
    aplicarTransformacion();
  }).observe(contenedor);
  medir();

  return {
    camara,
    // capas: { densidad: "media" | "2019"... | null, tasa: bool, pequenos: bool, tenue: bool }
    capas({ densidad = null, tasa = false, pequenos = false } = {}) {
      for (const [k, g] of Object.entries(capasDens)) opacidad(g, k === densidad ? (k === "media" ? 0.82 : 0.55) : 0);
      opacidad(gTasa, tasa ? 0.9 : 0);
      opacidad(gPeq, pequenos ? 1 : 0);
    },
    // medida: "km2" | "hab" | "tarde" | null (apaga la capa). Colores de la rampa por quintiles de las 7 comarcas.
    comarcas(medida, fmt) {
      modoComarcas = !!medida;
      opacidad(gComarcas, medida ? 0.92 : 0);
      opacidad(gComVPadre, medida ? 1 : 0);
      if (!medida) { aplicarTransformacion(); return; }
      const campo = { km2: "por_km2", hab: "por_1000hab", tarde: "tras_1nov" }[medida];
      const vals = comarcas.map((f) => f.properties[campo]);
      const esc = d3.scaleQuantize().domain(d3.extent(vals)).range(rampa);
      construir(gComarcas);
      pComarcas.transition().duration(duracion(900)).ease(d3.easeCubicInOut).attr("fill", (f) => esc(f.properties[campo]));
      gComV.select(".valor-comarca").text((f) => fmt(f.properties[campo], medida));
      aplicarTransformacion();
    },
    puntos(f, { tenue: te = false } = {}) { if (f === frame && te === tenue) return; frame = f; tenue = te; pedirPuntos(); },
    hilo(si) { opacidad(gHilo, si ? 1 : 0, 400); },
    proyectar: (ll) => [t.x + t.k * X(ll[0]), t.y + t.k * Y(ll[1])],
    alMover(fn) { alMover = fn; },
    rotulos(si) { svgR.attr("opacity", si ? 1 : 0); },
    // fn() → rectángulos de pantalla que los rótulos no pueden pisar; nombre: rótulo prioritario
    obstaculos(fn) { obstaculos = fn; },
    prioridad(nombre) { prioridad = nombre || null; },
    reetiquetar: () => evitarSolapes(),
  };
}
