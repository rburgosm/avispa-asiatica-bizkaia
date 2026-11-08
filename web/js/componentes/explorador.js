// Buscador «Tu municipio» (paso 13): nidos avisados por temporada (abril-diciembre; 2018 rayada,
// registro incompleto), nidos al año por cada 1.000 habitantes, puesto en Bizkaia y días que se
// tarda en retirarlos (la mitad de los nidos, en ese número de días o menos).
// Bilbao: «sin datos (servicio municipal propio)».
// Datos: web/data/municipios_serie.json.
import { duracion, formateador, medidas, rayado, plantilla, alRedimensionar } from "../util.js";

export function crearExplorador(raiz, datos, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const fmt1 = formateador(textos.idioma, 1);
  const T = datos.temporadas;
  const inc = new Set(datos.incompletas);
  const lista = [...datos.municipios].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  const normal = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase().trim();

  raiz.innerHTML = `
    <label for="buscar-municipio">${I.buscar_municipio}</label>
    <input id="buscar-municipio" type="search" list="lista-municipios" autocomplete="off" spellcheck="false"
      placeholder="${I.buscar_ejemplo}">
    <datalist id="lista-municipios">${lista.map((m) => `<option value="${m.nombre}">`).join("")}</datalist>
    <p class="resumen-municipio" id="resumen-municipio" aria-live="polite"></p>
    <div class="lienzo lienzo-explorador" id="lienzo-explorador"></div>`;
  const entrada = raiz.querySelector("input");
  const resumen = raiz.querySelector("#resumen-municipio");
  const contenedor = raiz.querySelector("#lienzo-explorador");

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const patron = rayado(svg);
  const g = svg.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const gBarras = g.append("g");
  const gEtiq = g.append("g");
  const aviso = g.append("text").attr("class", "etiqueta-serie").attr("text-anchor", "middle");
  let actual = null;

  function dibujar(animar = true) {
    if (!actual) return;
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: 20, derecha: 8, abajo: 24, izquierda: 40 });
    const dur = animar ? duracion(500) : 0;
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const sd = actual.sin_datos;
    const filas = T.map((t, i) => ({ t, v: sd ? 0 : actual.nidos[i], inc: inc.has(t) }));
    const x = d3.scaleBand().domain(T).range([0, w]).padding(0.25);
    const y = d3.scaleLinear().domain([0, Math.max(5, d3.max(filas, (f) => f.v))]).nice().range([h, 0]);
    gEjeX.attr("transform", `translate(0,${h})`)
      .call(d3.axisBottom(x).tickSizeOuter(0).tickFormat((t) => (w < 330 ? `'${String(t).slice(2)}` : t)));
    gEjeY.call(d3.axisLeft(y).ticks(4).tickFormat(fmt).tickSize(-w)).call((s) => s.select(".domain").remove());
    gBarras.selectAll("rect").data(filas, (f) => f.t).join(
      (e) => e.append("rect").attr("x", (f) => x(f.t)).attr("y", h).attr("height", 0))
      .attr("width", x.bandwidth()).attr("fill", (f) => (f.inc ? patron : "var(--acento)"))
      .attr("stroke", (f) => (f.inc ? "var(--gris-dato)" : "none"))
      .transition().duration(dur).attr("x", (f) => x(f.t)).attr("y", (f) => y(f.v)).attr("height", (f) => h - y(f.v));
    gEtiq.selectAll("text").data(sd ? [] : filas, (f) => f.t).join("text").attr("class", "etiqueta-valor")
      .attr("text-anchor", "middle").attr("font-size", w < 330 ? 10 : 12)
      .attr("fill", (f) => (f.inc ? "var(--tinta-suave)" : "var(--tinta)"))
      .text((f) => fmt(f.v)).transition().duration(dur)
      .attr("x", (f) => x(f.t) + x.bandwidth() / 2).attr("y", (f) => y(f.v) - 4);
    gEjeX.attr("opacity", sd ? 0 : 1);
    gEjeY.attr("opacity", sd ? 0 : 1);
    aviso.attr("x", w / 2).attr("y", h / 2).attr("fill", "var(--tinta-suave)").text(sd ? I.sin_datos_explorador : "");
    svg.attr("aria-label", plantilla(I.explorador_aria, { municipio: actual.nombre }));
  }

  function mostrar(m, animar = true) {
    actual = m;
    entrada.value = m.nombre;
    if (m.sin_datos) {
      resumen.textContent = plantilla(I.sin_datos_municipio, { municipio: m.nombre });
    } else {
      resumen.innerHTML = plantilla(I.resumen_municipio, {
        municipio: m.nombre, tasa: fmt1(m.tasa), puesto: m.puesto, total: datos.con_puesto,
        desde: datos.periodo[0], hasta: datos.periodo[1],
        dias: m.dias_mediana == null ? I.sin_dato : fmt1(m.dias_mediana),
      }) + ` <span class="notas">${plantilla(I.nota_explorador, { anio: [...inc].join(", ") })}</span>`;
    }
    dibujar(animar);
  }

  entrada.addEventListener("change", () => {
    const q = normal(entrada.value);
    if (!q) return;
    const m = lista.find((x) => normal(x.nombre) === q) || lista.find((x) => normal(x.nombre).includes(q));
    if (m) mostrar(m);
    else resumen.textContent = I.municipio_no_encontrado;
  });
  alRedimensionar(contenedor, () => dibujar(false));
  // Por defecto, el municipio con más nidos por habitante
  mostrar(lista.find((x) => x.puesto === 1) || lista[0], false);
  return { mostrar };
}
