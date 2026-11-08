// Pinta la página de metodología desde content/<idioma>.json (sección «metodologia», y «creditos»
// y «descargas» para las fuentes y los ficheros) y desde web/data/ (nido del hilo, cartografía,
// fotos y tamaños de las descargas). Ningún dato se escribe aquí.
import { json } from "./util.js";

const lang = new URLSearchParams(location.search).get("lang") === "eu" ? "eu" : "es";
const sufijo = lang === "es" ? "" : "?lang=" + lang;
const c = await json(`content/${lang}.json?v=8c5a1dfc`);
const m = c.metodologia, cr = c.creditos, I = c.interfaz, MI = m.interfaz || {};
document.documentElement.lang = c.idioma;
document.title = `${m.titulo} · ${c.meta.titulo}`;

const [img, relieve, dens, censo, base, hilo, meta] = await Promise.all(["data/imagenes.json", "data/relieve.json",
  "data/densidad.geojson", "data/censo_ilustracion.json", "data/mapa_base/mapa_base.json", "data/nido_hilo.json",
  "data/meta.json"].map((r) => json(r).catch(() => null)));
const pl = (t, v) => (t || "").replace(/\{(\w+)\}/g, (_, k) => (k in v ? v[k] : ""));
const nf = new Intl.NumberFormat("es-ES");
const kb = (b) => (b >= 1e6 ? `${(b / 1e6).toLocaleString("es-ES", { maximumFractionDigits: 1 })} MB`
  : `${nf.format(Math.max(1, Math.round(b / 1e3)))} kB`);
const lista = (l, cls = "") => `<ul${cls ? ` class="${cls}"` : ""}>${l.map((x) => `<li>${x}</li>`).join("")}</ul>`;

// Valores para los textos con {marcadores} (nido del hilo e ilustración del censo)
const v = {
  municipio: hilo?.nido?.municipio ?? "", criterio: hilo?.criterio ?? "", candidatos: hilo?.candidatos ?? "",
  por: censo?.por_nido ?? "",
};

// Tabla con etiquetas por celda (en el móvil cada fila se lee como una ficha)
const tabla = (t, cls = "") => `<div class="met-tabla-caja"><table class="met-tabla ${cls}">
  <thead><tr>${t.cabecera.map((h) => `<th scope="col">${h}</th>`).join("")}</tr></thead>
  <tbody>${t.filas.map((f) => `<tr>${f.map((x, i) => `<td data-etiqueta="${t.cabecera[i]}">${x}</td>`).join("")}</tr>`).join("")}</tbody>
</table></div>`;

// Pasos del proceso: el script (o scripts) en monoespaciada y la explicación debajo
const paso = (t) => {
  const p = t.match(/^(.*?<\/code>):\s([\s\S]*)$/);
  return p ? `<li><span class="met-script">${p[1]}</span> <span class="met-desc">${p[2]}</span></li>` : `<li>${t}</li>`;
};

const fuentes = (l) => tabla({
  cabecera: [MI.conjunto || "Conjunto", MI.uso || "Para qué se usa"],
  filas: (l || []).map((f) => [f.url ? `<a href="${f.url}">${f.titulo}</a>` : f.titulo, f.uso || ""]),
}, "met-tabla-fuentes");

const carto = [
  relieve && pl(I.carto_relieve, { fuente: relieve.fuente }),
  dens && pl(I.carto_densidad, { nucleo: nf.format(dens.nucleo_m), celda: dens.celda_m }),
  censo && pl(I.carto_censo, { por: censo.por_nido, anio: censo.temporada, municipio: censo.municipio, d0: censo.distancia_m[0], d1: censo.distancia_m[1] }),
  base && pl(I.carto_base, { build: base.build.replace(".pmtiles", ""), version: base.version_esquema }),
  I.carto_limites,
].filter(Boolean);

const fotos = Object.values(img || {}).map((f) => `<li class="met-foto">
  <img src="${f.src}" alt="" width="96" height="72" loading="lazy" decoding="async">
  <span>${f.descripcion_es} ${pl(I.foto_credito, { autor: `<a href="${f.url_pagina}">${f.autor}</a>`,
    licencia: `<a href="${f.url_licencia}">${f.licencia}</a>` })}${f.adaptacion ? `, ${I.foto_adaptada}` : ""}.</span></li>`);

const tam = meta?.ficheros_bytes || {};
const descargas = `<p class="met-pdf"><a href="memoria_tecnica.pdf">${MI.memoria_pdf || "Memoria técnica (PDF)"}</a>
  <span>${MI.pdf_texto || ""}</span></p>` + tabla({
  cabecera: [MI.fichero || "Fichero", MI.tamano || "Tamaño"],
  filas: c.descargas.ficheros.map((f) => {
    const b = tam[f.url.replace(/^data\//, "")];
    return [`<a href="${f.url}" download>${f.nombre}</a> <span class="met-formato">CSV</span>`, b ? kb(b) : ""];
  }),
}, "met-tabla-descargas");

const titulos = { conjuntos: I.conjuntos_odb, fuentes: I.otras_fuentes, cartografia: I.cartografia_titulo,
  fotos: MI.fotos_titulo || I.creditos_fotos, descargas: c.descargas.titulo };
const cuerpo = {
  conjuntos: () => fuentes(cr.conjuntos_odb),
  fuentes: () => fuentes(cr.otras_fuentes),
  cartografia: () => lista(carto),
  fotos: () => (fotos.length ? `<ul class="met-fotos">${fotos.join("")}</ul>` : ""),
  descargas: () => descargas,
};
const secciones = m.secciones.map((s) => ({ ...s, titulo: s.titulo || titulos[s.tipo] }))
  .filter((s) => !s.tipo || cuerpo[s.tipo]);

const seccion = (s) => `<section class="met-seccion" aria-labelledby="${s.id}">
  <h2 id="${s.id}">${s.titulo}</h2>
  ${s.tipo ? cuerpo[s.tipo]() : ""}
  ${(s.parrafos || []).map((p) => `<p>${pl(p, v)}</p>`).join("")}
  ${s.codigo ? `<pre class="met-codigo"><code>${s.codigo.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</code></pre>` : ""}
  ${s.lista ? (s.id === "proceso" ? `<ol class="met-pasos">${s.lista.map(paso).join("")}</ol>` : lista(s.lista, "met-lista")) : ""}
  ${s.tabla ? tabla(s.tabla, s.id === "cifras" ? "met-tabla-cifras" : "") : ""}
</section>`;

// Cabecera
const volver = document.getElementById("met-volver");
volver.href = "index.html" + sufijo;
volver.querySelector("span").textContent = MI.volver || c.meta.titulo;
const accesos = [
  ["memoria_tecnica.pdf", MI.memoria_pdf],
  ["#descargas", MI.datos],
  ["https://github.com/rburgosm/avispa-asiatica-bizkaia", MI.repositorio],
].filter((a) => a[1]);
document.getElementById("met-titulos").innerHTML = `
  <p class="met-antetitulo"><a href="index.html${sufijo}">${c.meta.titulo}</a></p>
  <h1>${m.titulo}</h1>
  ${MI.entradilla ? `<p class="met-entradilla">${MI.entradilla}</p>` : ""}
  <p class="met-firma">${c.meta.autoria} · ${c.meta.fecha}</p>
  <ul class="met-accesos">${accesos.map(([u, t]) => `<li><a href="${u}">${t}</a></li>`).join("")}</ul>`;

// Texto
const art = document.getElementById("metodologia");
art.innerHTML = secciones.map(seccion).join("");

// Índice: desplegable arriba en el móvil; lista fija al lado en el escritorio
const nav = document.getElementById("met-indice");
nav.innerHTML = `<details><summary>${MI.indice || "En esta página"}</summary>
  <ol>${secciones.map((s) => `<li><a href="#${s.id}">${s.titulo}</a></li>`).join("")}</ol></details>`;
const det = nav.querySelector("details");
const ancho = matchMedia("(min-width: 1100px)");
const ajustar = () => { det.open = ancho.matches; };
ajustar();
ancho.addEventListener("change", ajustar);
nav.addEventListener("click", (e) => { if (e.target.closest("a") && !ancho.matches) det.open = false; });

// Apartado en lectura, marcado en el índice (IntersectionObserver, sin escuchar el scroll)
const enlaces = new Map([...nav.querySelectorAll("a")].map((a) => [a.hash.slice(1), a]));
const visibles = new Set();
const io = new IntersectionObserver((entradas) => {
  for (const e of entradas) e.isIntersecting ? visibles.add(e.target.dataset.id) : visibles.delete(e.target.dataset.id);
  const actual = secciones.find((s) => visibles.has(s.id));
  if (!actual) return;
  for (const [id, a] of enlaces) id === actual.id ? a.setAttribute("aria-current", "true") : a.removeAttribute("aria-current");
}, { rootMargin: "-20% 0px -60% 0px" });
art.querySelectorAll(".met-seccion").forEach((s) => { s.dataset.id = s.querySelector("h2").id; io.observe(s); });

// Pie
document.getElementById("met-pie").innerHTML = `<div class="met-pie-dentro">
  ${(m.pie || []).map((p) => `<p>${p}</p>`).join("")}
  <p><a href="index.html${sufijo}">← ${c.meta.titulo}</a></p></div>`;

if (location.hash) document.querySelector(location.hash)?.scrollIntoView();
