// Mapa base propio: recorte de Bizkaia de Protomaps (web/data/mapa_base/bizkaia.pmtiles, generado
// por scripts/web_descargar_mapa_base.py) con el plugin oficial `pmtiles` y las capas de
// @protomaps/basemaps (versiones fijadas en web/vendor/). Sin servicios externos: teselas y glifos
// se sirven desde la propia web.
//
// Estilo: el sabor «light» de Protomaps con los colores sustituidos por los de la paleta
// (docs/paleta_colores.md): tierra en el tono del papel, mar gris azulado, ciudad y carreteras en
// grises cálidos, nombres en gris. Sin puntos de interés ni iconos: el único color es el dato.
import { variableCss } from "../util.js";

const RUTA_PMTILES = "data/mapa_base/bizkaia.pmtiles";
const RUTA_GLIFOS = "data/mapa_base/fuentes/";

// Fuente de bytes para PMTiles. Pide rangos HTTP (Range); si el servidor no los admite y devuelve el
// fichero entero (p. ej. `python -m http.server`), se queda con esa respuesta y sirve los rangos
// desde memoria, sin volver a descargarla. En un servidor normal solo baja las teselas que se ven.
class FuenteRango {
  constructor(url) { this.url = url; this.todo = null; }
  getKey() { return this.url; }
  async getBytes(offset, length, signal) {
    if (this.todo) return { data: (await this.todo).slice(offset, offset + length) };
    const r = await fetch(this.url, { headers: { Range: `bytes=${offset}-${offset + length - 1}` }, signal });
    if (r.status === 206) {
      return { data: await r.arrayBuffer(), etag: r.headers.get("ETag") || undefined,
        cacheControl: r.headers.get("Cache-Control") || undefined, expires: r.headers.get("Expires") || undefined };
    }
    if (r.ok) {
      if (!this.todo) this.todo = r.arrayBuffer();
      else r.body?.cancel();
      return { data: (await this.todo).slice(offset, offset + length) };
    }
    throw new Error(`${this.url}: ${r.status}`);
  }
}

function sabor() {
  const B = window.basemaps;
  const f = { ...B.namedFlavor("light") };
  const tierra = variableCss("--mapa-tierra"), mar = variableCss("--mapa-mar");
  const urbano = variableCss("--mapa-urbano"), bosque = variableCss("--mapa-bosque");
  const ctra = variableCss("--mapa-carretera"), borde = variableCss("--mapa-carretera-borde");
  const etiqueta = variableCss("--mapa-etiqueta"), linea = variableCss("--linea");
  Object.assign(f, {
    background: mar, earth: tierra, water: mar,
    park_a: bosque, park_b: bosque, wood_a: bosque, wood_b: bosque, scrub_a: bosque, scrub_b: bosque,
    glacier: tierra, sand: tierra, beach: tierra, zoo: urbano, military: urbano,
    hospital: urbano, industrial: urbano, school: urbano, pedestrian: urbano, aerodrome: urbano,
    runway: borde, pier: urbano, buildings: linea,
    other: ctra, minor_service: ctra, minor_a: ctra, minor_b: ctra, link: ctra, major: ctra, highway: ctra,
    minor_service_casing: borde, minor_casing: borde, link_casing: borde, major_casing_late: borde,
    highway_casing_late: borde, major_casing_early: borde, highway_casing_early: borde,
    railway: borde, boundaries: variableCss("--gris-dato"),
    roads_label_minor: etiqueta, roads_label_minor_halo: tierra, roads_label_major: etiqueta, roads_label_major_halo: tierra,
    ocean_label: variableCss("--tinta-suave"), subplace_label: etiqueta, subplace_label_halo: tierra,
    city_label: etiqueta, city_label_halo: tierra, state_label: etiqueta, state_label_halo: tierra,
    country_label: etiqueta, address_label: etiqueta, address_label_halo: tierra,
    regular: "Noto Sans Regular", bold: "Noto Sans Medium", italic: "Noto Sans Italic",
    pois: undefined,
  });
  for (const k of Object.keys(f)) if (k.startsWith("tunnel_") || k.startsWith("bridges_")) f[k] = k.endsWith("casing") ? borde : ctra;
  if (f.landcover) {
    f.landcover = { barren: tierra, farmland: tierra, forest: bosque, glacier: tierra, grassland: tierra, scrub: bosque, urban_area: urbano };
  }
  return f;
}

// Capas que no aportan nada aquí (iconos, direcciones, calles menores)
const FUERA = /pois|oneway|address|roads_labels_minor|shield|landcover/;

export function estiloBase() {
  const { pmtiles, maplibregl } = window;
  const protocolo = new pmtiles.Protocol();
  maplibregl.addProtocol("pmtiles", protocolo.tile);
  const url = new URL(RUTA_PMTILES, location.href).href;
  protocolo.add(new pmtiles.PMTiles(new FuenteRango(url)));
  const capas = window.basemaps.layers("protomaps", sabor(), { lang: "es" })
    .filter((c) => !FUERA.test(c.id) && !(c.layout && c.layout["icon-image"]));
  for (const c of capas) {
    // Nombres de lugar más discretos: gris y sin mayúsculas forzadas
    if (c.type === "symbol" && c.layout) {
      if (c.id.startsWith("places_locality")) c.paint = { ...c.paint, "text-color": variableCss("--mapa-etiqueta") };
    }
  }
  return {
    version: 8,
    glyphs: new URL(RUTA_GLIFOS, location.href).href + "{fontstack}/{range}.pbf",
    sources: {
      protomaps: { type: "vector", url: `pmtiles://${url}`,
        attribution: '<a href="https://protomaps.com">Protomaps</a> © <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>' },
    },
    layers: capas,
  };
}

// Primera capa de etiquetas del mapa base: las capas de datos se colocan debajo de los nombres
export const primeraEtiqueta = (mapa) => mapa.getStyle().layers.find((c) => c.type === "symbol")?.id;
