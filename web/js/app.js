// Arranque: lee el contenido (content/<idioma>.json) y los datos (data/), crea los paneles,
// pinta los pasos y conecta cada paso con el estado del gráfico que activa.
import { json, listaFuentes } from "./util.js";
import { crearMapa } from "./componentes/mapa.js";
import { crearEsquema } from "./componentes/esquema.js";
import { crearEstimacion } from "./componentes/estimacion.js";
import { crearTramos } from "./componentes/tramos.js";
import { crearLinea } from "./componentes/linea.js";
import { crearMensual } from "./componentes/mensual.js";
import { crearRegiones } from "./componentes/regiones.js";
import { crearGasto } from "./componentes/gasto.js";
import { crearExplorador } from "./componentes/explorador.js";

const IDIOMAS = ["es"]; // añadir "eu" cuando exista content/eu.json
const PANELES = ["mapa", "esquema", "estimacion", "tramos", "linea", "mensual", "regiones", "gasto"];

function idioma() {
  const p = new URLSearchParams(location.search).get("lang");
  return IDIOMAS.includes(p) ? p : "es";
}

const $ = (id) => document.getElementById(id);
const parrafos = (lista) => (lista || []).map((t) => `<p>${t}</p>`).join("");

function crearPaneles(I) {
  const g = $("grafico");
  for (const id of PANELES) {
    const f = document.createElement("figure");
    f.className = "panel";
    f.id = `panel-${id}`;
    f.dataset.grafico = id;
    f.hidden = true;
    f.innerHTML = `
      <p class="titulo-grafico" id="titulo-${id}"></p>
      <div class="lienzo${id === "mapa" ? " lienzo-mapa" : ""} lienzo-${id}" id="lienzo-${id}"></div>
      ${id === "mapa" ? '<p class="leyenda" id="leyenda-mapa"></p>' : ""}
      <p class="nota-grafico" id="nota-${id}"></p>
      <figcaption class="alt" id="alt-${id}"></figcaption>
      <details class="datos"><summary>${I.ver_datos}</summary><div class="tabla"></div></details>`;
    g.insertBefore(f, $("anuncio"));
  }
}

function pintarTextos(c) {
  document.documentElement.lang = c.idioma;
  document.title = c.meta.titulo;
  $("titulo").textContent = c.meta.titulo;
  $("subtitulo").textContent = c.meta.subtitulo;
  $("autoria").textContent = c.meta.autoria;
  $("fecha").textContent = c.meta.fecha;
  $("intro").innerHTML = parrafos(c.intro);
  $("titulo-cierre").textContent = c.cierre.titulo;
  $("texto-cierre").innerHTML = parrafos(c.cierre.texto);
  $("enlaces-cierre").innerHTML = c.cierre.enlaces.map((e) => `<li><a href="${e.url}">${e.texto}</a></li>`).join("");
  const cr = c.creditos;
  $("titulo-fuentes").textContent = c.interfaz.fuentes_creditos;
  $("titulo-conjuntos").textContent = c.interfaz.conjuntos_odb;
  $("titulo-otras").textContent = c.interfaz.otras_fuentes;
  $("fuentes").innerHTML = listaFuentes(cr.conjuntos_odb);
  $("otras-fuentes").innerHTML = listaFuentes(cr.otras_fuentes);
  $("titulo-explorador").textContent = c.explorador.titulo;
  $("texto-explorador").textContent = c.explorador.texto;
  $("titulo-descargas").textContent = c.descargas.titulo;
  $("lista-descargas").innerHTML = c.descargas.ficheros
    .map((f) => `<li><a href="${f.url}" download>${f.nombre}</a> (CSV)</li>`).join("");
  $("notas").innerHTML = (cr.notas || []).map((n) => `<li>${n}</li>`).join("");
  $("herramientas").textContent = cr.herramientas;
  $("enlace-metodologia").href = cr.metodologia;
  $("enlace-metodologia").textContent = cr.texto_metodologia;

  $("pasos").innerHTML = c.pasos.map((p, i) =>
    `<div class="paso" id="paso-${p.id}" data-indice="${i}">${parrafos(p.texto)}${
      p.boton ? `<button type="button" class="boton" data-accion="${p.boton.accion}">${p.boton.texto}</button>` : ""}</div>`).join("");
}

export async function iniciar() {
  const lang = idioma();
  const [contenido, indicadores, mensual, esquemas, regiones, gasto, cronologia, nidos, municipios, serieMunicipios] =
    await Promise.all([
      json(`content/${lang}.json`), json("data/indicadores.json"), json("data/mensual.json"),
      json("data/esquemas.json"), json("data/regiones.json"), json("data/gasto.json"),
      json("data/cronologia.json"), json("data/nidos.json"), json("data/municipios.geojson"),
      json("data/municipios_serie.json"),
    ]);
  const I = contenido.interfaz;
  crearPaneles(I);
  pintarTextos(contenido);

  const graficos = {
    mapa: crearMapa($("lienzo-mapa"), $("leyenda-mapa"), { nidos, municipios }, contenido),
    esquema: crearEsquema($("lienzo-esquema"), { esquemas, indicadores, cronologia }, contenido),
    estimacion: crearEstimacion($("lienzo-estimacion"), indicadores, contenido),
    tramos: crearTramos($("lienzo-tramos"), indicadores, contenido),
    linea: crearLinea($("lienzo-linea"), indicadores, contenido),
    mensual: crearMensual($("lienzo-mensual"), { mensual, indicadores }, contenido),
    regiones: crearRegiones($("lienzo-regiones"), regiones, contenido),
    gasto: crearGasto($("lienzo-gasto"), gasto, contenido),
  };
  crearExplorador($("explorador"), serieMunicipios, contenido);
  for (const k of PANELES) {
    const t = graficos[k].tablaDatos && graficos[k].tablaDatos();
    const caja = $(`panel-${k}`).querySelector(".datos");
    if (t) caja.querySelector(".tabla").appendChild(t); else caja.remove();
  }

  // Botón «Ver los datos reales» del paso de la estimación
  document.querySelectorAll('[data-accion="revelar"]').forEach((b) =>
    b.addEventListener("click", () => {
      graficos.estimacion.revelar();
      b.disabled = true;
    }));
  graficos.estimacion.alRevelar(() => document.querySelectorAll('[data-accion="revelar"]').forEach((b) => (b.disabled = true)));

  let visible = null, actual = -1;
  function activar(i, animar = true) {
    const paso = contenido.pasos[i];
    if (i === actual || !paso || !graficos[paso.grafico]) return;
    actual = i;
    document.querySelectorAll(".paso").forEach((el) => el.classList.toggle("activo", +el.dataset.indice === i));
    const cambiaPanel = visible !== paso.grafico;
    if (cambiaPanel) {
      document.querySelectorAll(".panel").forEach((p) => (p.hidden = p.dataset.grafico !== paso.grafico));
      visible = paso.grafico;
      if (paso.grafico === "mapa") graficos.mapa.redimensionar();
    }
    $(`titulo-${paso.grafico}`).textContent = paso.titulo || "";
    // Un panel recién mostrado se dibuja sin la transición de salida (venía oculto, sin tamaño).
    graficos[paso.grafico].actualizar(paso.estado || {}, animar && !cambiaPanel, cambiaPanel);
    $(`nota-${paso.grafico}`).textContent = paso.nota || (graficos[paso.grafico].nota ? graficos[paso.grafico].nota() : "");
    const desc = graficos[paso.grafico].describir ? graficos[paso.grafico].describir() : "";
    const alt = [paso.alt, desc].filter(Boolean).join(" ");
    $(`alt-${paso.grafico}`).textContent = alt;
    $("anuncio").textContent = alt;
    const svg = $(`lienzo-${paso.grafico}`).querySelector("svg");
    if (svg) svg.setAttribute("aria-label", alt);
  }

  activar(0, false);
  const LINEA = window.matchMedia("(min-width: 900px)").matches ? 0.6 : 0.8;
  const scroller = window.scrollama();
  scroller.setup({ step: ".paso", offset: LINEA })
    .onStepEnter(({ index }) => activar(index));
  window.addEventListener("resize", () => scroller.resize());
  // Respaldo: con un desplazamiento muy rápido el observador puede saltarse pasos; al
  // detenerse el scroll se activa el último paso que ha cruzado la línea de activación.
  let espera;
  window.addEventListener("scroll", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      const linea = window.innerHeight * LINEA;
      let ultimo = -1;
      document.querySelectorAll(".paso").forEach((el, i) => { if (el.getBoundingClientRect().top < linea) ultimo = i; });
      if (ultimo >= 0) activar(ultimo);
    }, 150);
  }, { passive: true });
  window.__historia = { activar, contenido, graficos }; // para pruebas
}
