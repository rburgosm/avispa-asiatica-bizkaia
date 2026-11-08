// Mapa de detalle con zoom real (MapLibre GL JS + mapa base propio de Protomaps): solo para el paso
// «un aviso no es un censo», a escala de barrio, con los nidos avisados de una ventana y los «nidos
// fantasma» de la ilustración (data/censo_ilustracion.json). Se crea la primera vez que hace falta.
// Sin controles ni gestos: la cámara la mueve el scroll.
// Sin parpadeos: el mapa se crea oculto al acercarse su paso, y al entrar se coloca en el encuadre
// de partida (Bizkaia) y no se enseña hasta que está pintado (clase «preparando»); luego aparece con
// un fundido y la cámara acerca al barrio con un vuelo continuo. Si se cambia entre este mapa y el
// de D3 mientras el escenario estaba oculto (venía un gráfico de otro tipo), el cambio es directo,
// sin fundido entre ambos: así nunca asoma el estado anterior.
import { duracion, sinMovimiento, variableCss } from "../util.js";
import { estiloBase, primeraEtiqueta } from "./fondo_mapa.js";

export function crearMapaDetalle(contenedor, datos) {
  const d3 = window.d3;
  let mapa = null, listo = false, pendiente = [], alMover = () => {};
  const cz = datos.censo;
  const cajaCenso = [[cz.caja[0], cz.caja[1]], [cz.caja[2], cz.caja[3]]];
  const bz = datos.municipios.bbox || (() => {
    let x0 = 180, y0 = 90, x1 = -180, y1 = -90;
    const rec = (c) => (typeof c[0] === "number" ? (x0 = Math.min(x0, c[0]), y0 = Math.min(y0, c[1]), x1 = Math.max(x1, c[0]), y1 = Math.max(y1, c[1])) : c.forEach(rec));
    datos.municipios.features.forEach((f) => rec(f.geometry.coordinates));
    return [x0, y0, x1, y1];
  })();
  const cajaBizkaia = [[bz[0], bz[1]], [bz[2], bz[3]]];
  const escenario = contenedor.closest(".escenario");
  let turno = 0, temporizadores = [];

  // Al reaparecer el escenario, o al cambiar de mapa (clase «detalle») con el escenario oculto, el
  // estado nuevo se pone directo, sin fundido desde el anterior (mapa, contador, leyenda, anotaciones)
  if (escenario) {
    const clave = () => `${escenario.classList.contains("detalle")}|${escenario.classList.contains("visible")}`;
    let antes = clave();
    new MutationObserver(() => {
      const ahora = clave();
      if (ahora === antes) return;
      antes = ahora;
      if (!escenario.classList.contains("visible") || parseFloat(getComputedStyle(escenario).opacity) > 0.5) return;
      escenario.classList.add("sin-fundido");
      requestAnimationFrame(() => requestAnimationFrame(() => escenario.classList.remove("sin-fundido")));
    }).observe(escenario, { attributes: true, attributeFilter: ["class"] });
  }

  function crear(cajaInicial) {
    mapa = new window.maplibregl.Map({
      container: contenedor, style: estiloBase(), bounds: cajaInicial, interactive: false,
      attributionControl: false, fadeDuration: 0,
    });
    mapa.on("load", () => {
      const tr = { duration: duracion(700) };
      const antes = primeraEtiqueta(mapa);
      const fz = cz.fantasmas, fantasmas = [];
      for (let i = 0; i < fz.length; i += 2) fantasmas.push([fz[i], fz[i + 1]]);
      orden = d3.shuffler(d3.randomLcg(1))(fantasmas);
      mapa.addSource("fantasmas", { type: "geojson", data: geoFantasmas(orden) });
      const av = cz.avisados, avisados = [];
      for (let i = 0; i < av.length; i += 2) avisados.push({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [av[i], av[i + 1]] } });
      mapa.addSource("avisados", { type: "geojson", data: { type: "FeatureCollection", features: avisados } });
      mapa.addSource("hilo", { type: "geojson", data: { type: "Point", coordinates: [datos.hilo.nido.lon, datos.hilo.nido.lat] } });
      mapa.addLayer({ id: "fantasmas", type: "circle", source: "fantasmas", filter: ["<", ["get", "k"], 0],
        paint: { "circle-color": variableCss("--fondo"), "circle-opacity": 0.45, "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 4.5, 14, 8],
          "circle-stroke-color": variableCss("--tinta-suave"), "circle-stroke-width": 1.6 } }, antes);
      mapa.addLayer({ id: "avisados", type: "circle", source: "avisados",
        paint: { "circle-color": variableCss("--acento"), "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 5, 14, 9],
          "circle-stroke-color": variableCss("--tinta"), "circle-stroke-width": 1.2, "circle-opacity": 0, "circle-stroke-opacity": 0,
          "circle-opacity-transition": tr, "circle-stroke-opacity-transition": tr } }, antes);
      mapa.addLayer({ id: "hilo", type: "circle", source: "hilo",
        paint: { "circle-color": "rgba(0,0,0,0)", "circle-radius": 14, "circle-stroke-color": variableCss("--tinta"), "circle-stroke-width": 2.5,
          "circle-stroke-opacity": 0, "circle-stroke-opacity-transition": tr } });
      // Nombres de lugar por encima de los nidos y de los nidos fantasma, con halo del color del papel
      const fondo = variableCss("--fondo");
      for (const c of mapa.getStyle().layers.filter((c) => c.type === "symbol")) {
        mapa.moveLayer(c.id);
        mapa.setPaintProperty(c.id, "text-halo-color", fondo);
        mapa.setPaintProperty(c.id, "text-halo-width", 1.5);
      }
      // Hueco invisible en cada nido avisado (capa de símbolos por encima de todas, que se coloca
      // primero): los nombres de lugar no se ponen encima de un nido real; si chocan, prueban otra
      // posición alrededor de su punto (text-variable-anchor) o, sin sitio, no se rotulan.
      mapa.addImage("hueco", { width: 20, height: 20, data: new Uint8Array(20 * 20 * 4) });
      mapa.addLayer({ id: "huecos", type: "symbol", source: "avisados",
        layout: { "icon-image": "hueco", "icon-allow-overlap": true, "icon-ignore-placement": false,
          "icon-size": ["interpolate", ["linear"], ["zoom"], 11, 0.6, 14, 1] } });
      for (const c of mapa.getStyle().layers) {
        if (c.type !== "symbol" || c.id === "huecos" || !c.layout || !c.layout["text-field"] || c.layout["symbol-placement"] === "line") continue;
        mapa.setLayoutProperty(c.id, "text-variable-anchor", ["center", "top", "bottom", "left", "right"]);
        mapa.setLayoutProperty(c.id, "text-radial-offset", 0.9);
      }
      mapa.on("move", () => alMover());
      listo = true;
      pendiente.forEach((f) => f());
      pendiente = [];
    });
  }
  const cuando = (f) => (listo ? f() : pendiente.push(f));
  let orden = [];
  const geoFantasmas = (lista) => ({ type: "FeatureCollection",
    features: lista.map((p, k) => ({ type: "Feature", properties: { k }, geometry: { type: "Point", coordinates: p } })) });

  // Los nidos fantasma (ilustración, no son ubicaciones reales) no se dibujan encima de los nombres de
  // lugar: con la cámara ya en el barrio, los que caen dentro de la caja de un rótulo se desplazan en
  // vertical lo justo para salir de ella. Mismo número de fantasmas; los nidos avisados no se tocan.
  // (se pregunta a MapLibre por los rótulos que hay de verdad bajo cada círculo: queryRenderedFeatures
  // usa sus cajas de colisión, así que vale también para los rótulos desplazados)
  let apartados = "";
  function apartarDeRotulos() {
    const capas = mapa.getStyle().layers.filter((c) => c.type === "symbol" && c.id !== "huecos").map((c) => c.id);
    const z = mapa.getZoom(), r = 4.5 + (Math.min(14, Math.max(11, z)) - 11) * (3.5 / 3) + 2;
    const clave = `${Math.round(z * 100)}|${Math.round(mapa.getCenter().lng * 1e4)}|${Math.round(mapa.getCenter().lat * 1e4)}`;
    if (clave === apartados) return;
    apartados = clave;
    const choca = (p) => mapa.queryRenderedFeatures([[p.x - r, p.y - r], [p.x + r, p.y + r]], { layers: capas }).length > 0;
    const PASOS = [0, -1, 1, -2, 2, -3, 3, -4, 4].map((k) => k * r);
    const nuevos = orden.map((ll) => {
      const p = mapa.project(ll);
      if (!choca(p)) return ll;
      for (const dy of PASOS) for (const dx of [0, -r, r, -2 * r, 2 * r]) {
        const q = { x: p.x + dx, y: p.y + dy };
        if (!choca(q)) { const u = mapa.unproject([q.x, q.y]); return [u.lng, u.lat]; }
      }
      return ll;
    });
    mapa.getSource("fantasmas").setData(geoFantasmas(nuevos));
  }

  return {
    // Vuela desde la vista de Bizkaia (cajaDesde) hasta la ventana del censo
    // Carga MapLibre la primera vez (no va en la carga inicial de la página)
    // y lo crea ya (oculto) en la vista de Bizkaia, para que las teselas estén listas al entrar
    precargar() {
      // (en un momento libre: crear el mapa es trabajo pesado y no debe caer en mitad del scroll)
      const libre = () => new Promise((ok) => (window.requestIdleCallback ? requestIdleCallback(ok, { timeout: 2500 }) : setTimeout(ok, 200)));
      return window.__cargarMapLibre().then(libre).then(() => { if (!mapa) crear(cajaBizkaia); }).catch(() => {});
    },
    entrar(cajaDesde, pad, alFallar) {
      window.__cargarMapLibre().then(() => {
        if (!mapa) crear(cajaDesde);
        cuando(() => this.volar(cajaDesde, pad));
      }).catch((e) => { console.warn(e); if (alFallar) alFallar(); });
    },
    volar(cajaDesde, pad) {
      const yo = ++turno;
      temporizadores.forEach(clearTimeout);
      temporizadores = [];
      contenedor.classList.add("preparando");
      cuando(() => {
        if (yo !== turno) return;
        mapa.resize();
        mapa.setPaintProperty("avisados", "circle-opacity", 1);
        mapa.setPaintProperty("avisados", "circle-stroke-opacity", 1);
        const destino = mapa.cameraForBounds(cajaCenso, { padding: pad });
        mapa.stop();
        if (sinMovimiento()) { mapa.jumpTo(destino); mapa.once("idle", apartarDeRotulos); }
        else mapa.fitBounds(cajaDesde, { padding: pad, animate: false });
        // Se enseña cuando está pintado en el encuadre de partida (o, como mucho, al segundo y medio)
        let hecho = false;
        const mostrar = () => {
          if (hecho || yo !== turno) return;
          hecho = true;
          contenedor.classList.remove("preparando");
          if (!sinMovimiento()) {
            // Tras el fundido de entrada, vuelo continuo de Bizkaia al barrio (1,5 s, suave)
            temporizadores.push(setTimeout(() => {
              if (yo !== turno) return;
              mapa.once("moveend", () => { if (yo === turno) mapa.once("idle", apartarDeRotulos); });
              mapa.flyTo({ ...destino, duration: 1500, curve: 1.42, easing: d3.easeCubicInOut, essential: true });
            }, 450));
          }
        };
        mapa.once("idle", mostrar);
        mapa.triggerRepaint();
        temporizadores.push(setTimeout(mostrar, 1500));
      });
    },
    fantasmas(n) { cuando(() => mapa.setFilter("fantasmas", ["<", ["get", "k"], n])); },
    hilo(si) { cuando(() => mapa.setPaintProperty("hilo", "circle-stroke-opacity", si ? 1 : 0)); },
    proyectar: (ll) => { if (!mapa) return [0, 0]; const p = mapa.project(ll); return [p.x, p.y]; },
    alMover(fn) { alMover = fn; },
    total: cz.fantasmas.length / 2,
  };
}
