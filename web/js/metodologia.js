// Pinta la página de metodología desde content/<idioma>.json.
import { json, listaFuentes } from "./util.js";

const lang = new URLSearchParams(location.search).get("lang") === "eu" ? "eu" : "es";
const c = await json(`content/${lang}.json`);
const m = c.metodologia, cr = c.creditos, I = c.interfaz;
const lista = (l) => `<ul>${l.map((x) => `<li>${x}</li>`).join("")}</ul>`;
document.documentElement.lang = c.idioma;
document.title = `${m.titulo} · ${c.meta.titulo}`;
const [primera, ...resto] = m.secciones;
const seccion = (s) => `<h2 id="${s.id}">${s.titulo}</h2>${(s.parrafos || []).map((p) => `<p>${p}</p>`).join("")}${s.lista ? lista(s.lista) : ""}`;
document.getElementById("metodologia").innerHTML = `
  <p><a href="index.html${lang === "es" ? "" : "?lang=" + lang}">← ${c.meta.titulo}</a></p>
  <h1>${m.titulo}</h1>
  ${seccion(primera)}
  <h2 id="conjuntos">${I.conjuntos_odb}</h2><ul>${listaFuentes(cr.conjuntos_odb)}</ul>
  <h2 id="fuentes">${I.otras_fuentes}</h2><ul>${listaFuentes(cr.otras_fuentes)}</ul>
  ${resto.map(seccion).join("")}
  <h2 id="descargas">${c.descargas.titulo}</h2>
  <ul>${c.descargas.ficheros.map((f) => `<li><a href="${f.url}" download>${f.nombre}</a> (CSV)</li>`).join("")}</ul>`;
if (location.hash) document.querySelector(location.hash)?.scrollIntoView();
