// Arranque: lee el contenido (content/<idioma>.json) y los datos (data/), crea las paradas (rótulo,
// gráfico fijo y tarjetas), el escenario del mapa y la navegación, y conecta cada paso (y su
// progreso dentro del paso, con Scrollama) con el estado del gráfico que activa.
import { json, sinMovimiento } from "./util.js";
import { crearMapa } from "./componentes/mapa.js";

const IDIOMAS = ["es"]; // añadir "eu" cuando exista content/eu.json
const PANELES = ["esquema", "estimacion", "tramos", "linea", "mensual", "regiones", "gasto"];

function idioma() {
  const p = new URLSearchParams(location.search).get("lang");
  return IDIOMAS.includes(p) ? p : "es";
}

const $ = (id) => document.getElementById(id);
const parrafos = (lista) => (lista || []).map((t) => `<p>${t}</p>`).join("");

function crearPaneles(I) {
  const almacen = $("almacen");
  for (const id of PANELES) {
    const f = document.createElement("figure");
    f.className = "panel";
    f.id = `panel-${id}`;
    f.dataset.grafico = id;
    f.hidden = true;
    f.addEventListener("animationend", (e) => { if (e.animationName === "entrar") f.classList.remove("entrando"); });
    f.innerHTML = `
      <p class="titulo-grafico" id="titulo-${id}"></p>
      <div class="lienzo lienzo-${id}" id="lienzo-${id}"></div>
      <p class="periodo" id="periodo-${id}" aria-hidden="true"></p>
      <p class="nota-grafico" id="nota-${id}"></p>
      <figcaption class="alt" id="alt-${id}"></figcaption>
      <details class="datos"><summary>${I.ver_datos}</summary><div class="tabla"></div></details>`;
    almacen.appendChild(f);
  }
  $("datos-mapa").querySelector("summary").textContent = I.ver_datos;
}

function pintarTextos(c) {
  document.documentElement.lang = c.idioma;
  document.title = c.meta.titulo;
  $("titulo").textContent = c.meta.titulo;
  $("subtitulo").textContent = c.meta.subtitulo;
  $("autoria").textContent = c.meta.autoria;
  $("fecha").textContent = c.meta.fecha;
  $("intro").innerHTML = parrafos(c.intro);
  // Final: la frase de paso de la última parada abre el cierre; después, el buscador
  const fraseFinal = c.paradas[c.paradas.length - 1].paso_siguiente;
  $("frase-cierre").textContent = fraseFinal || "";
  $("frase-cierre").hidden = !fraseFinal;
  $("titulo-cierre").textContent = c.cierre.titulo;
  $("texto-cierre").innerHTML = (c.cierre.hilo ? `<p class="hilo-cierre">${c.cierre.hilo}</p>` : "") + parrafos(c.cierre.texto);
  $("enlaces-cierre").innerHTML = c.cierre.enlaces.map((e) => `<li><a href="${e.url}">${e.texto}</a></li>`).join("");
  $("titulo-explorador").textContent = c.explorador.titulo;
  $("texto-explorador").textContent = c.explorador.texto;
  // Pie corto: el detalle de fuentes, créditos y descargas está en la metodología
  const I = c.interfaz;
  $("pie-titulo").textContent = c.meta.titulo;
  $("pie-fuentes").textContent = I.pie_fuentes;
  $("pie-enlaces").innerHTML = I.pie_enlaces.map((e) => `<li><a href="${e.url}">${e.texto}</a></li>`).join("");
  $("pie-creditos").textContent = I.pie_creditos;
  $("pie-firma").textContent = I.pie_firma;
  // Aviso de privacidad: solo si está cargado el script de estadísticas (Umami, sin cookies)
  $("pie-privacidad").textContent = I.pie_privacidad;
  $("pie-privacidad").hidden = !document.querySelector("script[data-website-id]");
}

function crearParadas(c) {
  const historia = $("historia");
  const porId = Object.fromEntries(c.pasos.map((p, i) => [p.id, { ...p, indice: i }]));
  let lado = 0;
  const nav = [];
  const total = c.paradas.length;
  c.paradas.forEach((pa, n) => {
    // La frase de paso de la parada anterior abre esta parada, encima de su número y su pregunta
    const anterior = n > 0 ? c.paradas[n - 1].paso_siguiente : "";
    const pasos = pa.pasos.map((id) => porId[id]);
    // Parada de mapa (solo mapa), de gráfico o mixta (mapa y gráficos): el rótulo es transparente si
    // la parada empieza con el mapa
    const soloMapa = pasos.every((p) => p.grafico === "mapa");
    const empiezaMapa = pasos[0].grafico === "mapa";
    const s = document.createElement("section");
    s.className = `parada ${soloMapa ? "parada-mapa" : "parada-grafico"}${empiezaMapa ? " empieza-mapa" : ""}`;
    s.id = `parada-${pa.id}`;
    s.dataset.id = pa.id;
    s.setAttribute("aria-labelledby", `pregunta-${pa.id}`);
    const alto = (p) => (p.estado && p.estado.alto) || (pasos.length === 1 ? 220 : 150);
    s.innerHTML = `
      <header class="rotulo">${anterior ? `<p class="frase-paso">${anterior}</p>` : ""}
        <p class="rotulo-numero">${n + 1} / ${total}</p>
        <h2 class="pregunta" id="pregunta-${pa.id}">${pa.pregunta}</h2>
        <span class="rotulo-linea" aria-hidden="true"></span>
        ${pa.entradilla ? `<p class="entradilla">${pa.entradilla}</p>` : ""}</header>
      <div class="parada-cuerpo">
        <div class="grafico" id="grafico-${pa.id}"></div>
        <div class="pasos">${pasos.map((p) => `
          <div class="paso ${p.grafico === "mapa" ? `paso-mapa ${lado++ % 2 ? "derecha" : "izquierda"}` : "paso-grafico"}"
            id="paso-${p.id}" data-indice="${p.indice}" data-parada="${pa.id}" data-grafico="${p.grafico}" style="--alto-paso:${alto(p)}svh">
            <div class="tarjeta">${p.titular ? `<p class="titular">${p.titular}</p>` : ""}${parrafos(p.texto)}${
              p.boton ? `<button type="button" class="boton" data-accion="${p.boton.accion}">${p.boton.texto}</button>` : ""}</div>
          </div>`).join("")}
        </div>
      </div>`;
    historia.insertBefore(s, $("anuncio"));
    nav.push(`<li><a href="#parada-${pa.id}" data-parada="${pa.id}"><span class="nombre">${pa.pregunta}</span><span class="punto"></span></a>` +
      `<span class="actual" aria-hidden="true">${pa.pregunta}</span></li>`);
  });
  $("navegacion").setAttribute("aria-label", c.interfaz.navegacion);
  $("navegacion").innerHTML = `<ol>${nav.join("")}</ol>`;
  // Al llegar al cierre y al buscador ya no hay parada que marcar: la navegación se funde
  const navEl = $("navegacion");
  const finales = ["cierre", "seccion-explorador"].map((id) => document.getElementById(id)).filter(Boolean);
  if ("IntersectionObserver" in window && finales.length) {
    const vistos = new Set();
    const io = new IntersectionObserver((es) => {
      es.forEach((e) => (e.isIntersecting ? vistos.add(e.target) : vistos.delete(e.target)));
      navEl.classList.toggle("oculta-final", vistos.size > 0);
    }, { rootMargin: "0px 0px -40% 0px" });
    finales.forEach((el) => io.observe(el));
  }
}

// Datos de cada fichero (se piden una sola vez) y gráficos que se crean al acercarse su parada
const RUTAS = {
  indicadores: "data/indicadores.json", mensual: "data/mensual.json", esquemas: "data/esquemas.json",
  regiones: "data/regiones.json", gasto: "data/gasto.json", cronologia: "data/cronologia.json",
  nidos: "data/nidos.json", municipios: "data/municipios.geojson", serieMunicipios: "data/municipios_serie.json",
  situacion: "data/situacion.geojson", hilo: "data/nido_hilo.json", censo: "data/censo_ilustracion.json",
  imagenes: "data/imagenes.json", densidad: "data/densidad.geojson", lugares: "data/lugares.geojson",
  contorno: "data/contorno.geojson", relieve: "data/relieve.json", apertura: "data/apertura.json",
  comarcas: "data/comarcas.geojson", asturias: "data/asturias_mensual.json",
};
const pedidos = {};
const dato = (k) => (pedidos[k] ??= json(RUTAS[k]).catch((e) => { delete pedidos[k]; throw e; }));
// Las claves con «?» al final son opcionales: si el fichero falta, llega null y el gráfico sigue sin esa capa
const datos = async (claves) => Object.fromEntries(await Promise.all(claves.map(async (k) => {
  const opcional = k.endsWith("?"), c = k.replace("?", "");
  return [c, opcional ? await dato(c).catch(() => null) : await dato(c)];
})));

export async function iniciar() {
  const lang = idioma();
  // Lo imprescindible para la portada y el mapa (el resto, por paradas)
  const contenido = await json(`content/${lang}.json`);
  const I = contenido.interfaz;
  crearPaneles(I);
  crearParadas(contenido);
  const imagenes = await dato("imagenes").catch(() => ({}));
  pintarTextos(contenido);
  document.documentElement.classList.add("listo");

  const capaFotos = document.createElement("div");
  capaFotos.className = "fotos";
  const lienzo = (k) => $(`lienzo-${k}`), periodo = (k) => $(`periodo-${k}`);
  // Cada gráfico: módulo, datos que necesita y cómo se crea
  const DEFINICION = {
    esquema: { m: () => import("./componentes/esquema.js"), d: ["esquemas", "indicadores", "cronologia", "imagenes", "hilo"],
      crear: (M, D) => M.crearEsquema(lienzo("esquema"), D, contenido, capaFotos) },
    estimacion: { m: () => import("./componentes/estimacion.js"), d: ["indicadores"],
      crear: (M, D) => M.crearEstimacion(lienzo("estimacion"), D.indicadores, contenido, periodo("estimacion")) },
    tramos: { m: () => import("./componentes/tramos.js"), d: ["indicadores", "hilo"],
      crear: (M, D) => M.crearTramos(lienzo("tramos"), { ...D.indicadores, hilo: D.hilo }, contenido) },
    linea: { m: () => import("./componentes/linea.js"), d: ["indicadores"],
      crear: (M, D) => M.crearLinea(lienzo("linea"), D.indicadores, contenido, periodo("linea")) },
    mensual: { m: () => import("./componentes/mensual.js"), d: ["mensual", "indicadores", "asturias?", "hilo"],
      crear: (M, D) => M.crearMensual(lienzo("mensual"), D, contenido) },
    regiones: { m: () => import("./componentes/regiones.js"), d: ["regiones"],
      crear: (M, D) => M.crearRegiones(lienzo("regiones"), D.regiones, contenido, periodo("regiones")) },
    gasto: { m: () => import("./componentes/gasto.js"), d: ["gasto"],
      crear: (M, D) => M.crearGasto(lienzo("gasto"), D.gasto, contenido, periodo("gasto")) },
  };
  const graficos = {};
  const cargas = {};

  function tablaDe(k) {
    const t = graficos[k].tablaDatos && graficos[k].tablaDatos();
    const caja = k === "mapa" ? $("datos-mapa") : $(`panel-${k}`).querySelector(".datos");
    if (t && caja) caja.querySelector(".tabla").replaceChildren(t); else if (caja) caja.remove();
  }

  // Carga un gráfico: esqueleto con brillo mientras tanto, «Cargando datos…» si tarda más de 2 s y,
  // si falla, un mensaje con «Reintentar» (nunca un error de JavaScript a la vista).
  function cargar(k) {
    if (graficos[k]) return Promise.resolve(graficos[k]);
    if (cargas[k]) return cargas[k];
    const def = DEFINICION[k], lz = lienzo(k);
    lz.classList.add("cargando");
    const aviso = document.createElement("p");
    aviso.className = "estado-carga";
    const tarda = setTimeout(() => { aviso.textContent = I.cargando; lz.after(aviso); }, 2000);
    cargas[k] = Promise.all([def.m(), datos(def.d)]).then(([M, D]) => {
      clearTimeout(tarda);
      aviso.remove();
      lz.classList.remove("cargando");
      graficos[k] = def.crear(M, D);
      tablaDe(k);
      if (k === "estimacion") conectarEstimacion();
      const paso = contenido.pasos[actual];
      if (paso && paso.grafico === k) { const i = actual; actual = -1; activar(i, false); }
      return graficos[k];
    }).catch((e) => {
      console.warn(k, e);
      clearTimeout(tarda);
      delete cargas[k];
      lz.classList.remove("cargando");
      aviso.textContent = `${I.error_carga} `;
      const b = document.createElement("button");
      b.type = "button"; b.className = "boton"; b.textContent = I.reintentar;
      b.onclick = () => { aviso.remove(); cargar(k); };
      aviso.appendChild(b);
      lz.after(aviso);
    });
    return cargas[k];
  }

  // Mapa: lo primero (portada). Si sus datos fallan, la portada sigue con la imagen estática.
  try {
    const D = await datos(["nidos", "municipios", "situacion", "hilo", "censo", "densidad", "lugares", "contorno", "relieve",
      "apertura", "comarcas"]);
    graficos.mapa = crearMapa(D, contenido);
    tablaDe("mapa");
  } catch (e) {
    console.warn("mapa", e);
    window.__avisoCarga(I.error_carga, () => location.reload());
    graficos.mapa = { actualizar() {}, describir: () => "" };
  }

  // Cada parada carga sus gráficos cuando está a una pantalla y media de entrar
  const graficosDeParada = (id) => [...new Set(contenido.paradas.find((p) => p.id === id).pasos
    .map((pid) => contenido.pasos.find((q) => q.id === pid).grafico).filter((g) => g !== "mapa"))];
  const vigia = new IntersectionObserver((entradas) => entradas.forEach((e) => {
    if (!e.isIntersecting) return;
    vigia.unobserve(e.target);
    graficosDeParada(e.target.dataset.id).forEach(cargar);
  }), { rootMargin: "150% 0px 150% 0px" });
  document.querySelectorAll(".parada").forEach((el) => { el.dataset.id = el.id.replace("parada-", ""); vigia.observe(el); });
  // MapLibre (mapa de detalle del censo), solo cuando su paso se acerca
  const pasoCenso = $("paso-censo");
  if (pasoCenso && graficos.mapa.precargarDetalle) {
    const v2 = new IntersectionObserver(([e]) => { if (e.isIntersecting) { v2.disconnect(); graficos.mapa.precargarDetalle(); } },
      { rootMargin: "200% 0px 200% 0px" });
    v2.observe(pasoCenso);
  }
  // Explorador «Tu municipio», al acercarse
  const v3 = new IntersectionObserver(([e]) => {
    if (!e.isIntersecting) return;
    v3.disconnect();
    Promise.all([import("./componentes/explorador.js"), dato("serieMunicipios")])
      .then(([M, serie]) => M.crearExplorador($("explorador"), serie, contenido))
      .catch((err) => { console.warn(err); $("explorador").textContent = I.error_carga; });
  }, { rootMargin: "150% 0px 150% 0px" });
  v3.observe($("explorador"));

  // Precarga silenciosa (sin spinner): con la portada ya pintada y la red libre (después del evento
  // «load»), en momentos libres y de uno en uno, se piden en el orden de la historia los datos, los
  // módulos de los gráficos y las fotos de las paradas siguientes, para que al llegar a cada una no
  // haya esqueletos ni esperas. Las fotos se piden con el mismo <picture> (srcset y sizes) que pone
  // esquema.js y se decodifican (img.decode()); con ahorro de datos o una conexión 2G/3G, no se
  // precargan. El mapa base de Protomaps no entra aquí: se pide solo al acercarse su paso (arriba).
  const libre = (ms = 3000) => new Promise((ok) => (window.requestIdleCallback
    ? requestIdleCallback(ok, { timeout: ms }) : setTimeout(ok, 250)));
  const conexionLenta = () => {
    const c = navigator.connection;
    return !!c && (c.saveData || /(^|-)(2g|3g)$/.test(c.effectiveType || ""));
  };
  const fotosPrecargadas = new Set();
  function precargarFoto(f) {
    const v = f.adaptacion && f.adaptacion.variantes;
    if (!v || fotosPrecargadas.has(f)) return Promise.resolve();
    fotosPrecargadas.add(f);
    const srcset = (l, fmt) => l.map((x) => `${x[fmt]} ${x.w}w`).join(", ");
    const an = v.ancho.anchuras, al = v.alto.anchuras;
    const SIZES = { ancho: "(max-aspect-ratio: 16/9) 178vh, 100vw", alto: "(max-aspect-ratio: 4/5) 80vh, 100vw" };  // como esquema.js
    const pic = document.createElement("picture");
    pic.innerHTML = `<source media="(min-width: 900px)" type="image/avif" srcset="${srcset(an, "avif")}" sizes="${SIZES.ancho}">
      <source media="(min-width: 900px)" type="image/webp" srcset="${srcset(an, "webp")}" sizes="${SIZES.ancho}">
      <source type="image/avif" srcset="${srcset(al, "avif")}" sizes="${SIZES.alto}">
      <img src="${al[0].webp}" srcset="${srcset(al, "webp")}" sizes="${SIZES.alto}" alt="" decoding="async" fetchpriority="low">`;
    return pic.querySelector("img").decode().catch(() => {});
  }
  async function precargar() {
    if (document.readyState !== "complete") await new Promise((ok) => addEventListener("load", ok, { once: true }));
    await libre();
    // MapLibre y sus complementos (solo el código; el mapa base se pide al acercarse su paso)
    await libre(); await Promise.all(["vendor/maplibre-gl.js", "vendor/pmtiles.js", "vendor/basemaps.js", "vendor/maplibre-gl.css"]
      .map((u) => fetch(u, { priority: "low" }).then((r) => r.blob()).catch(() => {})));
    for (const pa of contenido.paradas) {
      for (const k of graficosDeParada(pa.id)) {
        const def = DEFINICION[k];
        await libre(); await datos(def.d).catch(() => {});
        await libre(); await def.m().catch(() => {});
        if (k === "esquema" && !conexionLenta()) {
          for (const f of Object.values(imagenes)) { await libre(); await precargarFoto(f); }
        }
      }
    }
    await libre(); await Promise.all([import("./componentes/explorador.js"), dato("serieMunicipios")]).catch(() => {});
  }
  precargar().catch((e) => console.warn("precarga", e));

  // Botón «Ver los datos reales» del paso de la estimación
  function conectarEstimacion() {
    document.querySelectorAll('[data-accion="revelar"]').forEach((b) =>
      b.addEventListener("click", () => { graficos.estimacion.revelar(); b.disabled = true; }));
    graficos.estimacion.alRevelar(() => document.querySelectorAll('[data-accion="revelar"]').forEach((b) => (b.disabled = true)));
  }

  // Salida del fundido cruzado: el panel viejo se desvanece y se oculta al terminar (si vuelve a
  // activarse antes, activar() cancela la salida y recupera la opacidad desde donde iba)
  const FUNDIDO = 700;
  function fundirSalida(p) {
    if (p.classList.contains("saliendo")) return;
    // Si aún estaba entrando (animación «entrar»), se congela su opacidad actual para que el
    // fundido de salida parta de ahí y no de golpe
    if (p.classList.contains("entrando")) {
      p.style.opacity = getComputedStyle(p).opacity;
      p.classList.remove("entrando");
      void p.offsetWidth;
      p.style.opacity = "";
    }
    p.classList.add("saliendo");
    clearTimeout(p._fundido);
    p._fundido = setTimeout(() => { p.hidden = true; p.classList.remove("saliendo"); }, FUNDIDO + 50);
  }
  const altoTarjetaGrupo = (elPaso) => Math.max(...[...elPaso.parentNode.querySelectorAll(`.paso[data-grafico="${elPaso.dataset.grafico}"] .tarjeta`)]
    .map((t) => t.offsetHeight));

  const escenario = $("escenario");
  const nav = $("navegacion");
  let actual = -1, portadaVisible = true;
  const verEscenario = () => {
    const paso = contenido.pasos[actual];
    const ver = portadaVisible || (paso && paso.grafico === "mapa");
    escenario.classList.toggle("visible", !!ver);
    escenario.setAttribute("aria-hidden", ver ? "false" : "true");
    document.body.classList.toggle("modo-mapa", !!ver);
  };

  function activar(i, animar = true) {
    const paso = contenido.pasos[i];
    if (i === actual || !paso) return;
    if (!graficos[paso.grafico]) {  // aún cargando: se muestra el esqueleto y se activa al terminar
      if (DEFINICION[paso.grafico]) {
        actual = i;
        const panel = $(`panel-${paso.grafico}`), destino = $(`grafico-${$(`paso-${paso.id}`).dataset.parada}`);
        if (panel.parentNode !== destino) destino.appendChild(panel);
        document.querySelectorAll(".panel").forEach((p) => { p.hidden = p !== panel; });
        $(`titulo-${paso.grafico}`).textContent = paso.titulo || "";
        verEscenario();
        cargar(paso.grafico);
      }
      return;
    }
    const anterior = contenido.pasos[actual];
    actual = i;
    const elPaso = $(`paso-${paso.id}`);
    document.querySelectorAll(".paso").forEach((el) => el.classList.toggle("activo", el === elPaso));
    nav.classList.add("visible");
    document.body.classList.add("historia-empezada");
    let cambiaPanel = false;
    const k = paso.grafico;
    if (k !== "mapa") {
      const panel = $(`panel-${k}`);
      const destino = $(`grafico-${elPaso.dataset.parada}`);
      cambiaPanel = panel.hidden || panel.parentNode !== destino;
      if (panel.parentNode !== destino) destino.appendChild(panel);
      if (k === "esquema" && capaFotos.parentNode !== destino) destino.insertBefore(capaFotos, destino.firstChild);
      cambiaPanel = cambiaPanel || panel.classList.contains("saliendo");
      // Cambio de gráfico dentro de la misma parada: fundido cruzado en el mismo sitio (el viejo se
      // desvanece mientras el nuevo aparece); fuera de la parada, el viejo se oculta sin más
      let fundir = false;
      document.querySelectorAll(".panel").forEach((p) => {
        if (p === panel) return;
        if (p.parentNode === destino && !p.hidden && !sinMovimiento()) { fundirSalida(p); fundir = true; }
        else { clearTimeout(p._fundido); p.classList.remove("saliendo"); p.hidden = true; }
      });
      if (cambiaPanel) {
        clearTimeout(panel._fundido);
        panel.classList.remove("entrando", "saliendo");
        if (sinMovimiento()) panel.hidden = false;
        else if (fundir) {
          panel.classList.add("fundido-0"); panel.hidden = false;
          void panel.offsetWidth; panel.classList.remove("fundido-0");
        } else { panel.hidden = false; void panel.offsetWidth; panel.classList.add("entrando"); }
      }
    } else {
      cambiaPanel = !anterior || anterior.grafico !== "mapa";
      document.querySelectorAll(".panel").forEach((p) => { p.hidden = true; });
    }
    if (k !== "esquema" && graficos.esquema && graficos.esquema.ocultarFotos) graficos.esquema.ocultarFotos();
    verEscenario();
    // === maquetación móvil (ronda 4) ===
    // Móvil: la tarjeta va fija abajo (objetivo: 42 % de la pantalla; tope: 50 %, para no cortar texto) y el gráfico ocupa el resto
    // por encima. Mismo alto en todos los pasos del mismo gráfico (se mide con la tarjeta más alta):
    // así el gráfico no cambia de tamaño al pasar de un paso a otro.
    if (k !== "mapa") {
      const panel = $(`panel-${k}`);
      elPaso.classList.remove("tarjeta-plegada");
      if (innerWidth < 900) {
        const alto = Math.round(innerHeight - Math.min(innerHeight * 0.5, altoTarjetaGrupo(elPaso)) - 12 - 12);
        panel.style.height = `${alto}px`;
        panel.parentNode.style.setProperty("--alto-panel", `${alto}px`);
      } else panel.style.height = "";
    }
    $(`titulo-${k}`).textContent = paso.titulo || "";
    // Un panel recién mostrado se dibuja sin la transición de salida (venía oculto, sin tamaño).
    graficos[k].actualizar(paso.estado || {}, animar && !cambiaPanel, cambiaPanel);
    if (graficos[k].hilo) graficos[k].hilo(paso.hilo || "");
    $(`nota-${k}`).textContent = paso.nota || (graficos[k].nota ? graficos[k].nota() : "");
    const desc = graficos[k].describir ? graficos[k].describir() : "";
    const alt = [paso.alt, desc].filter(Boolean).join(" ");
    $(`alt-${k}`).textContent = alt;
    $("anuncio").textContent = alt;
    const svg = k !== "mapa" && $(`lienzo-${k}`).querySelector("svg");
    if (svg) svg.setAttribute("aria-label", alt);
  }

  // === navegación (ronda 5) ===
  // El punto activo cambia cuando la apertura de la parada (.rotulo) cruza el centro de la pantalla
  // (no con su primera tarjeta). Junto al punto activo, su nombre en pequeño; al cambiar, los puntos
  // se desplazan con una transición (FLIP: solo transform) y el nombre nuevo entra con un fundido.
  const rotulos = [...document.querySelectorAll(".parada > .rotulo")];
  let paradaNav = null;
  function marcarParada(id) {
    if (id === paradaNav) return;
    paradaNav = id;
    const items = [...nav.querySelectorAll("li")];
    const antes = items.map((li) => li.getBoundingClientRect().top);
    items.forEach((li) => {
      const si = li.firstElementChild.dataset.parada === id;
      li.firstElementChild.setAttribute("aria-current", si ? "true" : "false");
      li.classList.toggle("con-nombre", si);
    });
    if (sinMovimiento()) return;
    const despues = items.map((li) => li.getBoundingClientRect().top);
    items.forEach((li, k) => {
      const d = antes[k] - despues[k];
      li.style.transition = "none";
      li.style.transform = d ? `translateY(${d}px)` : "";
    });
    requestAnimationFrame(() => requestAnimationFrame(() => items.forEach((li) => {
      li.style.transition = ""; li.style.transform = "";
    })));
  }
  const revisarNav = () => {
    const centro = innerHeight / 2;
    let id = rotulos.length ? rotulos[0].parentNode.dataset.id : null;
    for (const r of rotulos) if (r.getBoundingClientRect().top < centro) id = r.parentNode.dataset.id;
    marcarParada(id);
  };
  const vigiaNav = new IntersectionObserver(revisarNav, { rootMargin: "-50% 0px -50% 0px" });
  rotulos.forEach((r) => vigiaNav.observe(r));
  revisarNav();

  // Portada: el mapa se enciende detrás del título
  graficos.mapa.portada();
  new IntersectionObserver(([e]) => {
    portadaVisible = e.isIntersecting;
    if (portadaVisible) nav.classList.remove("visible"); else if (actual >= 0) nav.classList.add("visible");
    verEscenario();
  }, { threshold: 0.05 }).observe(document.querySelector(".portada"));
  // Fuera de la historia (explorador, cierre) no hay navegación ni escenario
  new IntersectionObserver(([e]) => {
    if (!e.isIntersecting && e.boundingClientRect.top < 0) { nav.classList.remove("visible"); escenario.classList.remove("visible"); }
    else if (e.isIntersecting && actual >= 0) { nav.classList.add("visible"); verEscenario(); }
  }).observe($("historia"));

  // Línea de activación. El primer paso de cada parada se activa al 75 % de la pantalla (su gráfico
  // ya está a la vista). En los siguientes pasos de gráfico, el cambio va con la tarjeta: se activa
  // cuando la tarjeta nueva entra en la zona de lectura (escritorio: su borde de arriba llega al
  // 60 % de la pantalla; móvil: llega a su sitio fijo abajo), no antes.
  const LINEA = 0.75;
  // === maquetación móvil (ronda 4) ===
  // Móvil: una sola tarjeta a la vista, la del paso activo, y solo mientras su parada ocupa la
  // pantalla: desde que el gráfico queda fijo arriba (en las paradas que empiezan con el mapa, desde
  // que el rótulo deja libre la zona de la tarjeta) hasta que el final de la parada asoma por abajo.
  // Se comprueba con la posición del cuerpo de la parada cada vez que Scrollama avisa (entrada,
  // salida o progreso de un paso) y al detenerse el scroll; la clase «dentro» la usa el CSS.
  const cuerpos = [...document.querySelectorAll(".parada")].map((pa) => ({ pa, c: pa.querySelector(".parada-cuerpo"),
    arriba: pa.classList.contains("empieza-mapa") || pa.classList.contains("parada-mapa") ? 0.55 : 0 }));
  const revisarDentro = () => cuerpos.forEach(({ pa, c, arriba }) => {
    const r = c.getBoundingClientRect();
    pa.classList.toggle("dentro", r.top < innerHeight * arriba && r.bottom > innerHeight);
  });
  // Móvil: el primer paso de las paradas de gráfico (que no empiezan con el mapa) se activa cuando el
  // gráfico ya está fijo en su sitio (sticky, arriba): su borde de arriba, que coincide con el del
  // gráfico, llega a lo alto de la pantalla. Así el gráfico no empieza a dibujarse mientras sube.
  // Su progreso se cuenta desde esa línea (lo mide Scrollama).
  const LINEA_FIJO = 0.002;
  const primeroDeGrafico = (el) => innerWidth < 900 && el.matches(".parada-grafico:not(.empieza-mapa) .paso:first-child");

  function lineaDe(el) {
    if (primeroDeGrafico(el)) return LINEA_FIJO;
    if (!el.classList.contains("paso-grafico") || !el.previousElementSibling) return LINEA;
    const t = el.querySelector(".tarjeta");
    if (innerWidth >= 900) return Math.max(0.05, Math.min(LINEA, 0.6 - (parseFloat(getComputedStyle(t).marginTop) || 0) / innerHeight));
    return LINEA; // móvil: la tarjeta no se mueve (fija abajo), se cambia con el paso
  }
  const ponerLineas = () => document.querySelectorAll(".paso").forEach((el) => {
    el._linea = lineaDe(el);
    if (el._linea !== LINEA) el.dataset.offset = el._linea.toFixed(3); else delete el.dataset.offset;
  });
  ponerLineas();
  const scroller = window.scrollama();
  const montar = () => scroller.setup({ step: ".paso", offset: LINEA, progress: true })
    .onStepEnter(({ element }) => { activar(+element.dataset.indice); revisarDentro(); })
    .onStepExit(revisarDentro)
    .onStepProgress(({ element, progress }) => {
      revisarDentro();
      const i = +element.dataset.indice;
      if (i !== actual) return;
      const g = graficos[contenido.pasos[i].grafico];
      if (g && g.progreso) g.progreso(progress);
    });
  montar();
  // Al redimensionar se recalculan las líneas por paso (dependen del alto de la pantalla y de la
  // tarjeta) y se vuelve a montar Scrollama, que las lee al montar
  // (solo si cambia el ancho o el alto de verdad: la barra del navegador móvil no cuenta)
  let esperaResize, medida = [innerWidth, innerHeight];
  const remontar = () => { medida = [innerWidth, innerHeight]; ponerLineas(); scroller.destroy(); montar(); };
  window.addEventListener("resize", () => {
    clearTimeout(esperaResize);
    esperaResize = setTimeout(() => {
      if (innerWidth !== medida[0] || Math.abs(innerHeight - medida[1]) > 120) remontar(); else scroller.resize();
    }, 200);
  });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(remontar);
  // Respaldo: con un desplazamiento muy rápido el observador puede saltarse pasos; al
  // detenerse el scroll se activa el último paso que ha cruzado la línea de activación.
  let espera;
  window.addEventListener("scroll", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      let ultimo = null;
      document.querySelectorAll(".paso").forEach((el) => { if (el.getBoundingClientRect().top < window.innerHeight * (el._linea ?? LINEA)) ultimo = el; });
      if (ultimo) {
        activar(+ultimo.dataset.indice);
        const linea = window.innerHeight * (ultimo._linea ?? LINEA);
        const r = ultimo.getBoundingClientRect();
        const p = Math.max(0, Math.min(1, (linea - r.top) / r.height));
        const g = graficos[contenido.pasos[actual].grafico];
        if (g && g.progreso) g.progreso(p);
      }
      revisarDentro();
    }, 150);
  }, { passive: true });
  // Barra fina de progreso de lectura
  const barra = $("progreso-lectura");
  const leer = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    barra.style.transform = `scaleX(${max > 0 ? Math.min(1, scrollY / max) : 0})`;
  };
  window.addEventListener("scroll", () => requestAnimationFrame(leer), { passive: true });
  leer();
  window.__historia = { activar, contenido, graficos }; // para pruebas
}
