// Mapas de la historia, en el escenario fijo a pantalla completa (portada y pasos de mapa).
//   - Narración (portada, nidos mes a mes, densidad por temporadas, Bilbao, tasas): cartografía
//     propia en SVG y canvas con D3 (mapa_narrativo.js), sobre relieve sombreado.
//   - Detalle con zoom real (paso «un aviso no es un censo»): MapLibre + Protomaps (mapa_detalle.js).
// Cada paso de mapa trae en content/<idioma>.json un estado con «fases» que se recorren con el
// progreso del paso (Scrollama): capa, cámara, anotación con flecha curva y, en las fases
// temporales, el contador de tiempo (contador.js). Con movimiento reducido: cambios directos.
import { duracion, formateador, plantilla, variableCss, tabla, tramo } from "../util.js";
import { crearContador } from "./contador.js";
import { crearAnotador } from "./anotaciones.js";
import { crearMapaNarrativo } from "./mapa_narrativo.js";
import { crearMapaDetalle } from "./mapa_detalle.js";

const $ = (id) => document.getElementById(id);

function limites(geo) {
  let x0 = 180, y0 = 90, x1 = -180, y1 = -90;
  const rec = (c) => (typeof c[0] === "number"
    ? (x0 = Math.min(x0, c[0]), y0 = Math.min(y0, c[1]), x1 = Math.max(x1, c[0]), y1 = Math.max(y1, c[1]))
    : c.forEach(rec));
  (geo.features || [geo]).forEach((f) => rec(f.geometry.coordinates));
  return [[x0, y0], [x1, y1]];
}
const centro = (b) => [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2];

export function crearMapa(datos, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const fmt1 = formateador(textos.idioma, 1);
  const geo = datos.municipios, dens = datos.densidad;
  const cortes = geo.cortes_tasa;
  const caja = limites(geo);
  const escritorio = () => window.matchMedia("(min-width: 900px)").matches;

  // ---- tiempo: índice de mes (abril-diciembre de cada temporada) y acumulados
  const apertura = textos.pasos.find((p) => p.grafico === "mapa" && p.estado.modo === "puntos");
  const T = apertura.estado.temporadas, M = apertura.estado.meses;
  const nM = M.length, N = T.length * nM;
  const indice = (t, m) => (T.includes(t) && M.includes(m) ? T.indexOf(t) * nM + M.indexOf(m) : -1);
  const porFrame = new Array(N).fill(0);
  const dd = datos.nidos.datos, nc = datos.nidos.campos.length;
  const ptsLL = [];
  for (let i = 0; i < dd.length; i += nc) {
    const f = indice(dd[i + 2], dd[i + 3]);
    if (f >= 0) porFrame[f]++;
    ptsLL.push([dd[i], dd[i + 1], f]);
  }
  // El contador cuenta todos los avisos (con y sin coordenadas: data/apertura.json); el mapa, solo los
  // que tienen coordenadas (se dice en una nota bajo el contador)
  const avisosMes = datos.apertura ? datos.apertura.avisos_mes.flat() : porFrame;
  const acumulado = d3.cumsum(avisosMes);
  const hiloN = datos.hilo.nido;
  const hiloFrame = indice(hiloN.temporada, hiloN.mes);

  const escenario = $("escenario");
  const contador = crearContador($("contador"), { temporadas: T, meses: M }, textos);
  const anotador = crearAnotador($("anotaciones"), $("etiquetas-mapa"));
  const narrativo = crearMapaNarrativo($("mapa-svg"), { ...datos, indice, N }, textos);
  const detalle = crearMapaDetalle($("mapa"), datos);
  narrativo.alMover(() => { if (!enDetalle) anotador.recolocar(); });
  // Los rótulos del mapa no pisan la cabecera (contador y leyenda) ni las anotaciones
  narrativo.obstaculos(() => [...document.querySelectorAll(".cabeza-mapa > :not(.oculto):not([hidden]), .situacion, .navegacion.visible ol")]
    .map((e) => e.getBoundingClientRect()).filter((r) => r.width).concat(anotador.cajas(), rotulosVisibles()));
  const ponerAnotaciones = (lista) => {
    anotador.poner(lista, enDetalle ? detalle.proyectar : narrativo.proyectar);
    if (!enDetalle) narrativo.reetiquetar();
  };
  // Rótulo de la parada (la pregunta) que sube por encima del mapa: mientras pisa la cabecera del
  // mapa, la cabecera se funde; mientras pisa una anotación, las anotaciones se funden. Se mira con el
  // progreso del paso (Scrollama), sin escuchar el scroll.
  // (También la cabecera de la portada, opaca, mientras sale por arriba.) Los rótulos del mapa que
  // quedarían debajo se ocultan.
  const rotulosParada = [...document.querySelectorAll(".cabecera.portada, .parada-mapa .rotulo h2, .empieza-mapa .rotulo h2")];
  const rotulosVisibles = () => (estado ? rotulosParada.map((h) => h.getBoundingClientRect()).filter((r) => r.bottom > 0 && r.top < innerHeight) : []);
  const pisa = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  let habiaRotulo = false;
  function comprobarRotulo() {
    const hs = rotulosVisibles();
    if (hs.length || habiaRotulo) narrativo.reetiquetar();
    habiaRotulo = hs.length > 0;
    const cab = [...document.querySelectorAll(".cabeza-mapa > :not(.oculto):not([hidden])")].map((e) => e.getBoundingClientRect());
    const margen = (r) => ({ left: r.left - 8, right: r.right + 8, top: r.top - 8, bottom: r.bottom + 8 });
    escenario.classList.toggle("rotulo-encima", hs.some((h) => cab.some((c) => pisa(margen(h), c))));
    escenario.classList.toggle("rotulo-tapa", hs.some((h) => anotador.cajas().some((c) => pisa(margen(h), c))));
  }
  // El mapa vivo aparece con un fundido sobre la imagen estática de la portada (mismo encuadre)
  requestAnimationFrame(() => {
    $("mapa-svg").classList.add("listo");
    setTimeout(() => { const im = $("portada-mapa"); if (im) im.hidden = true; }, 1200);
  });
  detalle.alMover(() => { if (enDetalle) anotador.recolocar(); });
  $("mapa-svg").setAttribute("role", "img");
  $("mapa-svg").setAttribute("aria-label", I.mapa_etiqueta);

  // Mapa de situación: Bizkaia en la península (D3, estático)
  (function situacion() {
    const s = d3.select("#situacion"), W = 150, H = 130, sit = datos.situacion;
    const [x0, y0, x1, y1] = sit.caja;
    const kk = Math.cos((40 * Math.PI) / 180);
    const pr = d3.geoTransform({ point(x, y) { this.stream.point(x * kk, -y); } });
    const sx = (W - 8) / ((x1 - x0) * kk), sy = (H - 8) / (y1 - y0), e = Math.min(sx, sy);
    s.attr("viewBox", `${x0 * kk - 4 / e} ${-y1 - 4 / e} ${W / e} ${H / e}`).attr("aria-label", I.situacion);
    s.selectAll("path").data(sit.features).join("path").attr("class", (f) => f.properties.tipo).attr("d", d3.geoPath(pr))
      .attr("vector-effect", "non-scaling-stroke").attr("fill-rule", "evenodd");
  })();
  const atribucion = (det) => { $("atribucion-mapa").innerHTML = det ? I.mapa_base
    : `${datos.relieve.fuente.split(" (")[0]} · ${I.mapa_atribucion}`; };

  let estado = null, fase = -1, faseActual = null, prog = 0, frame = -1, enDetalle = false;
  let hiloTexto = "", portadaActiva = false, temporizador = null;

  // ---- cámara: zonas
  const bilbao = geo.features.find((f) => f.properties.sin_datos);
  const cajaBilbao = bilbao ? limites(bilbao) : caja;
  const maxTasa = geo.features.filter((f) => f.properties.tasa != null).sort((a, b) => b.properties.tasa - a.properties.tasa)[0];
  const bandaAlta = dens.features.filter((f) => f.properties.capa === "media").sort((a, b) => b.properties.banda - a.properties.banda)[0];
  const cajaAlta = bandaAlta ? limites(bandaAlta) : caja;
  const mungia = geo.features.find((f) => f.properties.nombre === (datos.apertura?.mas_avisos_periodo[0].municipio));
  const ampliar = (b, dx, dy) => [[b[0][0] - dx, b[0][1] - dy], [b[1][0] + dx, b[1][1] + dy]];
  const CAJAS = {
    bizkaia: caja,
    maximo: ampliar(cajaAlta, 0.12, 0.07),
    bilbao: ampliar(cajaBilbao, 0.16, 0.1),
    censo: [[datos.censo.caja[0], datos.censo.caja[1]], [datos.censo.caja[2], datos.censo.caja[3]]],
    morga: [[hiloN.lon - 0.16, hiloN.lat - 0.1], [hiloN.lon + 0.16, hiloN.lat + 0.1]],
    mungia: mungia ? ampliar(limites(mungia), 0.1, 0.06) : caja,
  };
  function relleno() {
    const W = innerWidth, H = innerHeight;
    const cab = document.querySelector(".cabeza-mapa").getBoundingClientRect();
    if (!escritorio()) {
      if (portadaActiva && !estado) return { top: 40, bottom: H * 0.5, left: 10, right: 10 };
      // Abajo, el sitio de la tarjeta activa (fija abajo): el foco queda en la mitad de arriba
      const tj = document.querySelector(".paso-mapa.activo .tarjeta");
      const abajo = Math.min(H * 0.45, Math.max(H * 0.34, (tj ? tj.offsetHeight : 0) + 40));
      return { top: Math.min(cab.bottom + 12, H * 0.42), bottom: abajo, left: 14, right: 14 };
    }
    if (portadaActiva && !estado) return { top: 30, bottom: H * 0.4, left: 80, right: 80 };
    const lado = estado && estado.lado;
    // Tarjeta a la derecha: el mapa ocupa la mitad izquierda, por debajo de la cabecera del mapa
    if (lado === "derecha") return { top: Math.min(cab.bottom + 16, H * 0.45), bottom: 50, left: 50, right: W * 0.42 };
    return { top: 60, bottom: 60, left: lado === "izquierda" ? W * 0.4 : Math.max(80, cab.right + 20), right: 200 };
  }
  atribucion(false);
  // Si la cabecera del mapa cambia de alto (nota, interruptor, leyenda), la cámara se reencaja
  let altoCabeza = 0;
  new ResizeObserver(() => {
    const h = Math.round(document.querySelector(".cabeza-mapa").getBoundingClientRect().height);
    if (h === altoCabeza) return;
    altoCabeza = h;
    if (estado && faseActual && estado.modo !== "censo") camara(faseActual.camara || "bizkaia");
  }).observe(document.querySelector(".cabeza-mapa"));
  function camara(nombre, animar = true) {
    narrativo.camara(CAJAS[nombre] || caja, relleno(), animar);
  }

  // ---- tiempo
  function ponerFrame(f, { animar = true } = {}) {
    frame = Math.max(0, Math.min(N - 1, f));
    narrativo.puntos(frame, { tenue: faseActual && faseActual.capa === "densidad" });
    contador.poner(frame, acumulado[frame], { animar, soloAnio: true });
    if (!faseActual || faseActual.capa !== "densidad") narrativo.capas({ densidad: String(T[Math.floor(frame / nM)]) });
    const marcar = (hiloTexto || (faseActual && faseActual.marcarHilo)) && frame >= hiloFrame;
    narrativo.hilo(!!marcar && (!estado || estado.modo === "puntos"));
  }

  // Portada: el mapa de nidos se enciende mes a mes detrás del título (una vez)
  function iniciarPortada() {
    portadaActiva = true;
    contador.mostrar(true);
    pintarLeyenda({ capa: "puntos" });
    camara("bizkaia", false);
    if (!duracion()) { ponerFrame(N - 1, { animar: false }); return; }
    let f = 0;
    clearInterval(temporizador);
    temporizador = setInterval(() => {
      if (estado) { clearInterval(temporizador); return; }
      // Si el lector ya ha bajado y el mapa no se ve, se deja en el último mes sin animar
      if (!escenario.classList.contains("visible")) { clearInterval(temporizador); ponerFrame(N - 1, { animar: false }); return; }
      ponerFrame(f);
      if (++f >= N) clearInterval(temporizador);
    }, 190);
  }

  // ---- leyenda
  const sinDatos = `<span class="clase"><span class="muestra rayada"></span>${I.sin_datos_leyenda}</span>`;
  const muestra = (col) => `<span class="muestra" style="background:${col}"></span>`;
  const rampa = [1, 2, 3, 4, 5].map((k) => variableCss(`--rampa-${k}`));
  function rampaHtml() {
    return `<span class="titulo-leyenda">${plantilla(I.densidad_unidad, { desde: T[0], hasta: T[T.length - 1] })}</span><br>${
      rampa.map((col, k) => `<span class="clase">${muestra(col)}${k === rampa.length - 1 ? "≥ " : ""}${fmt1(dens.cortes[k])}</span>`).join("")}`;
  }
  function pintarLeyenda(f) {
    const m = estado ? estado.modo : "puntos";
    const ley = $("leyenda-mapa");
    if (m === "comarcas") {
      const md = medidaElegida || (f && f.medida) || "km2";
      const campo = { km2: "por_km2", hab: "por_1000hab", tarde: "tras_1nov" }[md];
      const ref = datos.comarcas.bizkaia_sin_bilbao[campo];
      ley.innerHTML = `<span class="titulo-leyenda">${I[`comarca_${md}`]}</span><br>
        <span class="clase"><span class="degradado"></span>${I.menos} → ${I.mas}</span>
        <span class="clase">${plantilla(I.media_bizkaia, { v: fmtComarca(ref, md) })}</span> ${sinDatos}`;
      return;
    }
    if (m === "tasa") {
      const clases = rampa.map((col, k) => `<span class="clase">${muestra(col)}${
        k === 0 ? `&lt; ${fmt1(cortes[0])}` : k === rampa.length - 1 ? `≥ ${fmt1(cortes[k - 1])}` : `${fmt1(cortes[k - 1])}–${fmt1(cortes[k])}`}</span>`).join("");
      ley.innerHTML = `<span class="titulo-leyenda">${plantilla(I.tasa_leyenda, { desde: geo.periodo[0], hasta: geo.periodo[1] })}</span><br>${clases} ${sinDatos}`;
    } else if (m === "censo") {
      const nA = datos.censo.avisados.length / 2;
      ley.innerHTML = `<span class="clase"><span class="muestra punto" style="background:${variableCss("--acento")}"></span>${plantilla(I.censo_avisados, { n: fmt(nA) })}</span>
        <span class="clase"><span class="muestra hueco"></span>${plantilla(I.censo_sin_ver, { n: fmt(detalle.total) })}</span>`;
    } else if (f.capa === "densidad") {
      ley.innerHTML = `${rampaHtml()} ${sinDatos}`;
    } else {
      ley.innerHTML = `<span class="clase"><span class="muestra punto" style="background:${variableCss("--acento")}"></span>${I.anot_punto}</span>
        <span class="clase">${muestra(rampa[2])}${I.densidad_leyenda}</span> ${sinDatos}`;
    }
  }

  // ---- comarcas: formato, interruptor «por territorio / por habitante» y leyenda
  let medidaElegida = null;
  const fmtComarca = (v, medida) => (medida === "tarde" ? `${fmt(v * 100)} %` : fmt1(v));
  function interruptor(medida) {
    let caja = document.getElementById("interruptor-comarcas");
    if (!medida) { if (caja) caja.hidden = true; return; }
    if (!caja) {
      caja = document.createElement("div");
      caja.id = "interruptor-comarcas";
      caja.className = "interruptor";
      caja.setAttribute("role", "group");
      caja.setAttribute("aria-label", I.interruptor_aria);
      caja.innerHTML = [["km2", I.por_territorio], ["hab", I.por_habitante]]
        .map(([k, t]) => `<button type="button" data-medida="${k}">${t}</button>`).join("");
      caja.addEventListener("click", (e) => {
        const b = e.target.closest("button");
        if (!b) return;
        medidaElegida = b.dataset.medida;
        narrativo.comarcas(medidaElegida, fmtComarca);
        interruptor(medidaElegida);
        pintarLeyenda(faseActual);
      });
      $("caja-mapa").insertBefore(caja, $("leyenda-mapa"));
    }
    caja.hidden = medida === "tarde";
    caja.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.medida === medida ? "true" : "false"));
  }

  // ---- anotaciones de cada fase
  function anotacionesDe(f) {
    const lista = [];
    const n = f.anotacion;
    if (n === "punto") {
      const cc = centro(caja);
      const p = ptsLL.filter((q) => q[2] >= 0 && q[2] < nM)
        .sort((a, b) => d3.geoDistance(a, cc) - d3.geoDistance(b, cc))[0];
      if (p) lista.push({ lnglat: [p[0], p[1]], html: I.anot_punto, dist: 60, radio: 4 });
    }
    if (f.fijo === "hilo") lista.push({ lnglat: [hiloN.lon, hiloN.lat], html: hiloN.municipio, dist: 70, radio: 15 });
    if (n === "mungia" && mungia && datos.apertura) {
      const q = datos.apertura.mas_avisos_periodo[0];
      lista.push({ lnglat: centro(limites(mungia)), dist: 80, radio: 10,
        html: plantilla(I.anot_mungia, { municipio: q.municipio, n: fmt(q.n), desde: T[0], hasta: T[T.length - 1] }) });
    }
    if (n === "densidad") lista.push({ lnglat: centro(cajaAlta), html: I.anot_densidad, dist: 80, radio: 14 });
    if (n === "bilbao" && bilbao) lista.push({ lnglat: centro(cajaBilbao), dist: 70, vertical: "abajo", radio: 18,
      html: plantilla(I.sin_datos_municipio, { municipio: bilbao.properties.nombre }) });
    if (n === "fantasma") {
      const k = Math.floor(datos.censo.fantasmas.length / 4) * 2;
      lista.push({ lnglat: [datos.censo.fantasmas[k], datos.censo.fantasmas[k + 1]], html: I.anot_fantasma, clase: "ilustracion", dist: escritorio() ? 90 : 60, radio: 9,
        lado: escritorio() ? "derecha" : "izquierda" });  // en escritorio, lejos de la tarjeta (a la izquierda)
    }
    if (n === "tasa" && maxTasa) lista.push({ lnglat: centro(limites(maxTasa)), dist: 110, radio: 6, vertical: "abajo",
      html: plantilla(I.anot_tasa, { municipio: maxTasa.properties.nombre, v: fmt1(maxTasa.properties.tasa) }) });
    const m = estado ? estado.modo : "puntos";
    if (hiloTexto && m !== "tasa" && (m !== "puntos" || frame >= hiloFrame)) {
      lista.push({ lnglat: [hiloN.lon, hiloN.lat], html: hiloTexto, dist: 80, radio: 14 });
    }
    return lista;
  }

  function verDetalle(si) {
    enDetalle = si;
    escenario.classList.toggle("detalle", si);
    atribucion(si);
  }

  function aplicarFase(k, animar) {
    const f = estado.fases[k];
    faseActual = f;
    const m = estado.modo;
    if (m === "censo") {
      const desde = narrativo && CAJAS[faseActual.desde || "bizkaia"];
      detalle.entrar(desde, relleno(), () => { verDetalle(false); camara("censo"); });
      verDetalle(true);
      detalle.hilo(!!hiloTexto);
    } else {
      verDetalle(false);
    }
    narrativo.comarcas(m === "comarcas" ? (medidaElegida || f.medida) : null, fmtComarca);
    interruptor(m === "comarcas" ? (medidaElegida || f.medida) : null);
    if (m === "puntos") {
      if (f.capa === "densidad") { narrativo.capas({ densidad: "media" }); narrativo.puntos(N - 1, { tenue: true }); frame = N - 1; contador.poner(N - 1, acumulado[N - 1], { animar, soloAnio: true }); }
      if (f.fijo === "hilo") { narrativo.capas({}); frame = hiloFrame; narrativo.puntos(hiloFrame, { tenue: true }); narrativo.hilo(true); }
    } else if (m === "tasa") {
      narrativo.capas({ tasa: true, pequenos: f.resaltar === "pequenos" });
      narrativo.puntos(-1);
      narrativo.hilo(false);
    } else if (m === "comarcas") {
      narrativo.capas({});
      narrativo.puntos(-1);
      narrativo.hilo(false);
    }
    contador.mostrar(m === "puntos" && f.fijo !== "hilo");
    pintarLeyenda(f);
    // La cámara, cuando la cabecera del mapa ya tiene su alto definitivo (interruptor y leyenda)
    if (m !== "censo") camara(f.camara || "bizkaia", animar);
    narrativo.prioridad({ mungia: mungia?.properties.nombre, bilbao: bilbao?.properties.nombre, morga: hiloN.municipio }[f.camara]);
    ponerAnotaciones(anotacionesDe(f));
  }

  function progreso(p) {
    prog = p;
    if (!estado) return;
    const fs = estado.fases;
    let k = fs.findIndex((f) => p <= f.hasta);
    if (k < 0) k = fs.length - 1;
    if (k !== fase) { fase = k; aplicarFase(k, true); }
    const f = fs[k], ini = k ? fs[k - 1].hasta : 0;
    const local = tramo(p, ini, ini + (f.hasta - ini) * 0.9);
    if (f.tiempo) {
      // tramo de años de la tarjeta: de abril del primero a diciembre del último
      const [a0, a1] = f.anios || [T[0], T[T.length - 1]];
      const i0 = (a0 - T[0]) * nM, i1 = (a1 - T[0]) * nM + nM - 1;
      const nuevo = Math.round(i0 + local * (i1 - i0));
      if (nuevo !== frame) ponerFrame(nuevo);
      if (hiloTexto && frame >= hiloFrame && !anotador.tiene(hiloTexto)) ponerAnotaciones(anotacionesDe(f));
    }
    if (estado.modo === "censo") detalle.fantasmas(f.fantasmas ? Math.ceil(local * detalle.total) : 0);
    comprobarRotulo();
  }

  function aplicar(nuevo, animar) {
    clearInterval(temporizador);
    portadaActiva = false;
    estado = { ...nuevo, fases: nuevo.fases || [{ hasta: 1, camara: "bizkaia" }] };
    fase = -1;
    progreso(prog);
  }

  return {
    actualizar(nuevo, animar = true) {
      medidaElegida = null;
      const lado = document.querySelector(".paso-mapa.activo")?.classList.contains("derecha") ? "derecha" : "izquierda";
      prog = 0;
      aplicar({ ...nuevo, lado }, animar);
    },
    progreso,
    hilo(texto) {
      hiloTexto = texto;
      if (!estado || !faseActual) return;
      if (estado.modo === "puntos") narrativo.hilo((!!texto || !!faseActual.marcarHilo) && frame >= hiloFrame);
      if (estado.modo === "censo") detalle.hilo(!!texto);
      ponerAnotaciones(anotacionesDe(faseActual));
    },
    portada() { iniciarPortada(); },
    precargarDetalle() { return detalle.precargar(); },
    tablaDatos() {
      const filas = geo.features.map((f) => f.properties).sort((a, b) => (b.tasa ?? -1) - (a.tasa ?? -1))
        .map((p) => [p.nombre, p.sin_datos ? I.sin_datos_corto : fmt1(p.tasa), fmt(p.pob)]);
      return tabla([I.municipio, plantilla(I.tasa_columna, { desde: geo.periodo[0], hasta: geo.periodo[1] }), I.poblacion_2025], filas);
    },
    describir() {
      if (!estado) return "";
      if (estado.modo === "tasa") return plantilla(I.tasa_desc, { desde: geo.periodo[0], hasta: geo.periodo[1] });
      if (estado.modo === "puntos") return plantilla(I.nidos_mapa, { n: fmt(acumulado[N - 1]), desde: T[0], hasta: T[T.length - 1] });
      return "";
    },
    nota() {
      if (!estado || estado.modo !== "tasa") return "";
      return plantilla(I.tasa_tamano, { desde: geo.periodo[0], hasta: geo.periodo[1] }) + " " +
        geo.tasas_tamano.map((r) => `${I.tamanos[r.tamano]}: ${fmt1(r.media)}`).join("; ") + ".";
    },
  };
}
