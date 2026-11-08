// Mapa de Bizkaia con MapLibre GL JS (sin mapa base externo: solo límites municipales).
// Estado:
//   { modo: "puntos", temporadas: [2019, ..., 2025], meses: [4, ..., 12] }
//       los nidos con coordenadas aparecen temporada a temporada (acumulados); sin animación
//       si la persona pide reducir el movimiento.
//   { modo: "tasa" }  nidos al año por cada 1.000 habitantes (media del periodo), por municipio.
// En los dos, Bilbao en gris rayado: «sin datos (servicio municipal propio)».
// Datos: web/data/nidos.json (columnas planas) y web/data/municipios.geojson (tasa, sin_datos, cortes_tasa).
import { duracion, formateador, plantilla, variableCss, tabla } from "../util.js";

const OPACIDAD = 0.55;

function puntosGeojson(n) {
  const c = n.campos.length, feats = [];
  for (let i = 0; i < n.datos.length; i += c) {
    feats.push({ type: "Feature", properties: { t: n.datos[i + 2], m: n.datos[i + 3] },
      geometry: { type: "Point", coordinates: [n.datos[i], n.datos[i + 1]] } });
  }
  return { type: "FeatureCollection", features: feats };
}

function limites(geo) {
  let x0 = 180, y0 = 90, x1 = -180, y1 = -90;
  const rec = (c) => (typeof c[0] === "number"
    ? (x0 = Math.min(x0, c[0]), y0 = Math.min(y0, c[1]), x1 = Math.max(x1, c[0]), y1 = Math.max(y1, c[1]))
    : c.forEach(rec));
  geo.features.forEach((f) => rec(f.geometry.coordinates));
  return [[x0, y0], [x1, y1]];
}

// Imagen de rayado para fill-pattern (la genera el propio navegador con un canvas)
function imagenRayado(color, fondo) {
  const n = 8, c = document.createElement("canvas");
  c.width = c.height = n;
  const x = c.getContext("2d");
  x.fillStyle = fondo; x.fillRect(0, 0, n, n);
  x.strokeStyle = color; x.lineWidth = 2;
  x.beginPath(); x.moveTo(0, n); x.lineTo(n, 0); x.moveTo(-1, 1); x.lineTo(1, -1); x.moveTo(n - 1, n + 1); x.lineTo(n + 1, n - 1); x.stroke();
  return x.getImageData(0, 0, n, n);
}

export function crearMapa(contenedor, leyenda, datos, textos) {
  const maplibregl = window.maplibregl;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const fmt1 = formateador(textos.idioma, 1);
  const geo = datos.municipios;
  const cortes = geo.cortes_tasa;
  const rampa = [1, 2, 3, 4, 5].map((k) => variableCss(`--rampa-${k}`));
  const caja = limites(geo);
  let estado = { modo: "puntos" }, listo = false, pendiente = null, temporizador = null;

  contenedor.setAttribute("role", "region");
  contenedor.setAttribute("aria-label", I.mapa_etiqueta);

  const mapa = new maplibregl.Map({
    container: contenedor,
    style: { version: 8, sources: {}, layers: [
      { id: "fondo", type: "background", paint: { "background-color": variableCss("--mapa-mar") } }] },
    bounds: caja,
    fitBoundsOptions: { padding: 12 },
    attributionControl: false,
    cooperativeGestures: true,
    dragRotate: false,
    pitchWithRotate: false,
    locale: I.maplibre,
  });
  mapa.touchZoomRotate.disableRotation();
  mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  mapa.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: I.mapa_atribucion }));

  // Marca de texto sobre Bilbao (HTML: el mapa no carga tipografías de un servidor externo)
  const bilbao = geo.features.find((f) => f.properties.sin_datos);
  let marca = null;
  if (bilbao) {
    const [[a, b], [c, d]] = limites({ features: [bilbao] });
    const el = document.createElement("div");
    el.className = "marca-mapa";
    el.textContent = plantilla(I.sin_datos_municipio, { municipio: bilbao.properties.nombre });
    marca = new maplibregl.Marker({ element: el, anchor: "top" }).setLngLat([(a + c) / 2, d + 0.004]).addTo(mapa);
  }

  mapa.on("load", () => {
    mapa.addImage("rayado", imagenRayado(variableCss("--gris-dato"), variableCss("--mapa-tierra")));
    mapa.addSource("municipios", { type: "geojson", data: geo });
    mapa.addSource("nidos", { type: "geojson", data: puntosGeojson(datos.nidos) });
    mapa.addLayer({ id: "muni-relleno", type: "fill", source: "municipios", filter: ["!", ["get", "sin_datos"]],
      paint: { "fill-color": variableCss("--mapa-tierra"), "fill-color-transition": { duration: duracion() } } });
    mapa.addLayer({ id: "muni-sin-datos", type: "fill", source: "municipios", filter: ["get", "sin_datos"],
      paint: { "fill-pattern": "rayado" } });
    mapa.addLayer({ id: "muni-borde", type: "line", source: "municipios",
      paint: { "line-color": variableCss("--mapa-borde"), "line-width": 0.6 } });
    mapa.addLayer({ id: "nidos", type: "circle", source: "nidos", filter: ["==", ["get", "t"], -1],
      paint: {
        "circle-color": variableCss("--acento"),
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 1.4, 11, 3, 14, 6],
        "circle-opacity": OPACIDAD,
      } });
    listo = true;
    // La atribución compacta empieza desplegada y en el móvil tapa medio mapa: se pliega (sigue el botón «i»)
    contenedor.querySelector(".maplibregl-ctrl-attrib")?.classList.remove("maplibregl-compact-show");
    aplicar(pendiente || estado, false);
  });

  function contar(temporadas, meses) {
    const d = datos.nidos.datos;
    let n = 0;
    for (let i = 0; i < d.length; i += 4) if (temporadas.includes(d[i + 2]) && meses.includes(d[i + 3])) n++;
    return n;
  }

  function filtroPuntos(temporadas, meses) {
    return ["all", ["in", ["get", "t"], ["literal", temporadas]], ["in", ["get", "m"], ["literal", meses]]];
  }

  function leyendaPuntos(temporadas, meses, completo) {
    const t0 = temporadas[0], t1 = temporadas[temporadas.length - 1];
    leyenda.innerHTML = `<span class="clase"><span class="muestra" style="background:${variableCss("--acento")};border-radius:50%"></span>${
      plantilla(completo ? I.nidos_mapa : I.nidos_mapa_hasta, { n: fmt(contar(temporadas, meses)), desde: t0, hasta: t1 })}</span>
      <span class="clase"><span class="muestra rayada"></span>${I.sin_datos_leyenda}</span>`;
  }

  function aplicar(nuevo, animar = true) {
    const e = { modo: "puntos", ...nuevo };
    estado = e;
    if (!listo) { pendiente = e; return; }
    clearInterval(temporizador);
    if (e.modo === "puntos") {
      const T = e.temporadas, M = e.meses;
      mapa.setPaintProperty("muni-relleno", "fill-color", variableCss("--mapa-tierra"));
      mapa.setLayoutProperty("nidos", "visibility", "visible");
      if (animar && duracion()) {
        // Temporada a temporada, acumulando
        let k = 0;
        const paso = () => {
          const hasta = T.slice(0, k + 1);
          mapa.setFilter("nidos", filtroPuntos(hasta, M));
          leyendaPuntos(hasta, M, k === T.length - 1);
          if (++k >= T.length) clearInterval(temporizador);
        };
        paso();
        temporizador = setInterval(paso, 700);
      } else {
        mapa.setFilter("nidos", filtroPuntos(T, M));
        leyendaPuntos(T, M, true);
      }
    } else {
      mapa.setLayoutProperty("nidos", "visibility", "none");
      mapa.setPaintProperty("muni-relleno", "fill-color",
        ["step", ["coalesce", ["get", "tasa"], 0], rampa[0], cortes[0], rampa[1], cortes[1], rampa[2], cortes[2], rampa[3], cortes[3], rampa[4]]);
      const clases = rampa.map((c, k) => `<span class="clase"><span class="muestra" style="background:${c}"></span>${
        k === 0 ? `&lt; ${fmt1(cortes[0])}` : k === rampa.length - 1 ? `≥ ${fmt1(cortes[k - 1])}` : `${fmt1(cortes[k - 1])}–${fmt1(cortes[k])}`}</span>`).join("");
      leyenda.innerHTML = `${plantilla(I.tasa_leyenda, { desde: geo.periodo[0], hasta: geo.periodo[1] })}: ${clases}
        <span class="clase"><span class="muestra rayada"></span>${I.sin_datos_leyenda}</span>`;
    }
  }

  return {
    actualizar(nuevo, animar = true, recienMostrado = false) {
      // La animación de aparición se ve también si el panel acaba de mostrarse
      aplicar(nuevo, animar || recienMostrado);
    },
    redimensionar: () => { mapa.resize(); mapa.fitBounds(caja, { padding: 12, animate: false }); },
    tablaDatos() {
      const filas = geo.features.map((f) => f.properties).sort((a, b) => (b.tasa ?? -1) - (a.tasa ?? -1))
        .map((p) => [p.nombre, p.sin_datos ? I.sin_datos_corto : fmt1(p.tasa), fmt(p.pob)]);
      return tabla([I.municipio, plantilla(I.tasa_columna, { desde: geo.periodo[0], hasta: geo.periodo[1] }), I.poblacion_2025], filas);
    },
    describir() {
      return estado.modo === "tasa" ? plantilla(I.tasa_desc, { desde: geo.periodo[0], hasta: geo.periodo[1] }) : "";
    },
    // Nota visible bajo el mapa de tasas: media por tamaño de municipio (sin Bilbao)
    nota() {
      if (estado.modo !== "tasa") return "";
      return plantilla(I.tasa_tamano, { desde: geo.periodo[0], hasta: geo.periodo[1] }) + " " +
        geo.tasas_tamano.map((r) => `${I.tamanos[r.tamano]}: ${fmt1(r.media)}`).join("; ") + ".";
    },
  };
}
