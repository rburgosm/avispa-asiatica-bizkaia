// Buscador «Tu municipio» (referente: el buscador del Washington Post «2°C»).
// Selector grande con autocompletado propio (combobox ARIA: dedo y teclado; tolerante a tildes, a
// guiones y a los nombres bilingües, p. ej. «Gernika» → Gernika-Lumo, «Abanto» → Abanto y
// Ciérvana-Abanto Zierbena). Al elegir municipio: gráfico con su tasa anual (circulitos grises huecos),
// su tendencia en tinta, la de Bizkaia sin Bilbao en naranja y la de su comarca (Eustat) en gris
// discontinuo, cada una con su etiqueta y su valor al final; al lado, la ficha: nidos por 1.000
// habitantes, puesto en Bizkaia, días hasta la retirada y comparación con la comarca.
// Bilbao: «sin datos (servicio municipal propio)». Con menos de POCOS nidos al año de media no se
// dibuja la tendencia (con tan pocos nidos, un año suelto la mueve demasiado) y se dice.
// Datos: web/data/municipios_serie.json (tendencias: recta de MCO de scripts/web_preparar_datos.py).
import { duracion, formateador, medidas, plantilla, alRedimensionar, tamano, envolver } from "../util.js";

const POCOS = 10;          // nidos al año de media (2019-2025) por debajo de los cuales no hay tendencia
const INICIAL = "Morga";   // municipio del nido hilo
const MAX_OPCIONES = 8;
// Formas en castellano que no forman parte del nombre oficial (las bilingües ya están en el nombre)
const ALIAS = {
  Barakaldo: "Baracaldo", "Gernika-Lumo": "Guernica Guernica y Luno", Getxo: "Guecho", Leioa: "Lejona",
  Lekeitio: "Lequeitio", "Markina-Xemein": "Marquina Jemein", Mungia: "Munguia", Plentzia: "Plencia",
  Sopela: "Sopelana", Santurtzi: "Santurce", Balmaseda: "Valmaseda", Galdakao: "Galdacano",
  Igorre: "Yurre", Iurreta: "Yurreta", Etxebarri: "Echevarri", "Amorebieta-Etxano": "Amorebieta Echano",
};

export function crearExplorador(raiz, datos, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const t = (k, defecto) => I[k] ?? defecto;   // textos nuevos: ver el resumen del encargo
  const fmt = formateador(textos.idioma, 0);
  const fmt1 = formateador(textos.idioma, 1);
  const TT = datos.temporadas_tasa;
  const [desde, hasta] = datos.periodo;
  const lista = [...datos.municipios].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  // Clave de búsqueda con la misma longitud que el nombre (para resaltar lo que coincide):
  // sin tildes, en minúsculas y con guiones y barras como espacios.
  const clave = (s) => s.normalize("NFC").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/[-/]/g, " ");
  lista.forEach((m) => { m._clave = clave(m.nombre); m._alias = ALIAS[m.nombre] ? clave(ALIAS[m.nombre]) : ""; });

  raiz.innerHTML = `
    <div class="bus-selector">
      <label for="buscar-municipio" class="bus-etiqueta">${I.buscar_municipio}</label>
      <div class="bus-campo">
        <input id="buscar-municipio" type="text" role="combobox" aria-autocomplete="list" aria-expanded="false"
          aria-controls="opciones-municipio" autocomplete="off" autocapitalize="words" spellcheck="false"
          enterkeyhint="search" placeholder="${I.buscar_ejemplo}">
        <button type="button" class="bus-borrar" aria-label="${t("borrar_busqueda", "Borrar")}" hidden>×</button>
        <ul id="opciones-municipio" class="bus-opciones" role="listbox" aria-label="${I.buscar_municipio}" hidden></ul>
      </div>
      <p class="bus-error" aria-live="polite"></p>
    </div>
    <div class="bus-cuerpo">
      <div class="bus-ficha" id="resumen-municipio" aria-live="polite"></div>
      <figure class="bus-grafico">
        <div class="lienzo lienzo-explorador" id="lienzo-explorador"></div>
        <figcaption class="bus-clave"></figcaption>
      </figure>
    </div>`;
  const entrada = raiz.querySelector("input");
  const borrar = raiz.querySelector(".bus-borrar");
  const caja = raiz.querySelector(".bus-opciones");
  const error = raiz.querySelector(".bus-error");
  const ficha = raiz.querySelector(".bus-ficha");
  const clavePie = raiz.querySelector(".bus-clave");
  const contenedor = raiz.querySelector("#lienzo-explorador");

  // ------------------------------------------------------------ autocompletado
  function buscar(texto) {
    const q = clave(texto).trim().replace(/\s+/g, " ");
    if (!q) return lista.map((m) => ({ m, i: -1, n: 0 }));
    const trozos = q.split(" ");
    const res = [];
    for (const m of lista) {
      const i = m._clave.indexOf(q);
      let p;
      if (i === 0) p = 0;
      else if (i > 0 && m._clave[i - 1] === " ") p = 1;
      else if (i > 0) p = 3;
      else if (m._alias && (m._alias.startsWith(q) || m._alias.includes(` ${q}`))) p = 2;
      else if (trozos.length > 1 && trozos.every((x) => m._clave.includes(x))) p = 4;
      else continue;
      res.push({ m, i: p <= 3 ? i : -1, n: q.length, p });
    }
    return res.sort((a, b) => a.p - b.p || a.m.nombre.localeCompare(b.m.nombre, "es"));
  }
  let opciones = [], activa = -1;
  const resaltar = (o) => {
    const s = o.m.nombre;
    if (o.i < 0) return esc(s);
    return `${esc(s.slice(0, o.i))}<mark>${esc(s.slice(o.i, o.i + o.n))}</mark>${esc(s.slice(o.i + o.n))}`;
  };
  function abrir(texto) {
    opciones = buscar(texto).slice(0, texto.trim() ? MAX_OPCIONES : lista.length);
    activa = opciones.length && texto.trim() ? 0 : -1;
    caja.innerHTML = opciones.length
      ? opciones.map((o, k) => `<li role="option" id="op-mun-${k}" aria-selected="${k === activa}" data-k="${k}"><span>${resaltar(o)}</span>${o.m.sin_datos ? ` <span class="bus-op-nota">${t("sin_datos_corto", "sin datos")}</span>` : ""}</li>`).join("")
      : `<li class="bus-vacia" role="presentation">${I.municipio_no_encontrado}</li>`;
    caja.hidden = false;
    entrada.setAttribute("aria-expanded", "true");
    marcar();
  }
  function cerrar() {
    caja.hidden = true;
    entrada.setAttribute("aria-expanded", "false");
    entrada.removeAttribute("aria-activedescendant");
    activa = -1;
  }
  function marcar() {
    caja.querySelectorAll("[role=option]").forEach((li, k) => li.setAttribute("aria-selected", k === activa));
    if (activa >= 0) {
      entrada.setAttribute("aria-activedescendant", `op-mun-${activa}`);
      caja.querySelector(`#op-mun-${activa}`)?.scrollIntoView({ block: "nearest" });
    } else entrada.removeAttribute("aria-activedescendant");
  }
  function elegir(m) {
    cerrar();
    error.textContent = "";
    if (m !== actual) mostrar(m);
    else entrada.value = m.nombre;
    borrar.hidden = !entrada.value;
  }
  // Resuelve un texto escrito sin elegir de la lista (Enter o cambio): exacto o la mejor coincidencia
  function resolver(texto) {
    const r = buscar(texto);
    if (!texto.trim()) return null;
    return (r.find((o) => o.m._clave === clave(texto).trim()) || r[0])?.m ?? null;
  }

  entrada.addEventListener("input", () => { borrar.hidden = !entrada.value; abrir(entrada.value); });
  entrada.addEventListener("focus", () => entrada.select());
  entrada.addEventListener("click", () => { if (caja.hidden) abrir(entrada.value === actual?.nombre ? "" : entrada.value); });
  entrada.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (caja.hidden) { abrir(entrada.value === actual?.nombre ? "" : entrada.value); return; }
      if (!opciones.length) return;
      activa = e.key === "ArrowDown" ? (activa + 1) % opciones.length : (activa <= 0 ? opciones.length - 1 : activa - 1);
      marcar();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const m = !caja.hidden && activa >= 0 ? opciones[activa].m : resolver(entrada.value);
      if (m) elegir(m);
      else error.textContent = I.municipio_no_encontrado;
    } else if (e.key === "Escape") {
      if (!caja.hidden) { e.preventDefault(); cerrar(); }
      else if (actual) entrada.value = actual.nombre;
    } else if (e.key === "Tab") cerrar();
  });
  // Compatibilidad con el cambio directo (scripts/web_probar.py rellena y lanza «change»)
  // (solo con nombre exacto o una única coincidencia: tocar fuera no elige un municipio por sorpresa)
  entrada.addEventListener("change", () => {
    const r = buscar(entrada.value);
    const m = entrada.value.trim() && (r.find((o) => o.m._clave === clave(entrada.value).trim()) || (r.length === 1 && r[0]))?.m;
    if (m) elegir(m);
    else if (entrada.value.trim()) error.textContent = I.municipio_no_encontrado;
  });
  entrada.addEventListener("blur", () => setTimeout(() => {
    if (raiz.contains(document.activeElement)) return;
    cerrar();
    if (actual && entrada.value !== actual.nombre && !error.textContent) entrada.value = actual.nombre;
    borrar.hidden = !entrada.value;
  }, 150));
  // Con el dedo o el ratón: se elige al soltar; mousedown no quita el foco al campo
  caja.addEventListener("mousedown", (e) => e.preventDefault());
  caja.addEventListener("click", (e) => {
    const li = e.target.closest("[role=option]");
    if (!li) return;
    elegir(opciones[+li.dataset.k].m);
    if (matchMedia("(pointer: coarse)").matches) entrada.blur();  // baja el teclado del móvil
  });
  borrar.addEventListener("click", () => {
    entrada.value = ""; error.textContent = ""; borrar.hidden = true;
    entrada.focus(); abrir("");
  });

  // ------------------------------------------------------------ ficha
  ficha.innerHTML = `
    <h3 class="bus-nombre"></h3>
    <p class="bus-sindatos" hidden></p>
    <dl class="bus-datos">
      <div class="bus-dato bus-dato-principal"><dt data-t="tasa"></dt>
        <dd class="bus-cifra" data-c="tasa"></dd><dd class="bus-nota" data-n="nidos"></dd></div>
      <div class="bus-dato"><dt>${t("puesto_bizkaia", "Puesto en Bizkaia")}</dt>
        <dd class="bus-cifra"><span data-c="puesto"></span> <span class="bus-de"></span></dd>
        <dd class="bus-nota">${t("puesto_nota", "1 = más nidos por habitante")}</dd></div>
      <div class="bus-dato"><dt>${t("dias_retirada", "Días hasta la retirada")}</dt>
        <dd class="bus-cifra" data-c="dias"></dd><dd class="bus-nota" data-n="dias"></dd></div>
      <div class="bus-dato bus-dato-comarca"><dt>${t("comarca_eustat", "Comarca (Eustat)")}</dt>
        <dd class="bus-comarca-nombre"></dd><dd class="bus-nota" data-n="comarca"></dd></div>
    </dl>
    <p class="bus-aviso" hidden></p>`;
  const F = (s) => ficha.querySelector(s);
  const previo = { tasa: 0, puesto: 0, dias: 0 };
  function cifra(sel, clave_, v, f) {
    const el = F(sel);
    if (v == null) { el.textContent = I.sin_dato; previo[clave_] = 0; return; }
    const desde_ = previo[clave_] ?? 0;
    previo[clave_] = v;
    const dur = duracion(700);
    const s = d3.select(el).interrupt();
    if (!dur) { el.textContent = f(v); return; }
    s.transition().duration(dur).ease(d3.easeCubicInOut).textTween(() => { const i = d3.interpolateNumber(desde_, v); return (q) => f(q === 1 ? v : i(q)); });
  }
  const sumaPeriodo = (m) => datos.temporadas.reduce((s, a, k) => s + (a >= desde && a <= hasta ? m.nidos[k] : 0), 0);
  const anios = (m) => (m.tasa_anual || []).filter((v) => v != null).length;
  const pocos = (m) => !m.sin_datos && (m.tendencia?.[0] == null || sumaPeriodo(m) / anios(m) < POCOS);

  function rellenarFicha(m) {
    ficha.classList.remove("bus-fundido");
    void ficha.offsetWidth;  // reinicia el fundido de las notas
    ficha.classList.add("bus-fundido");
    F(".bus-nombre").textContent = m.nombre;
    F(".bus-sindatos").hidden = !m.sin_datos;
    F(".bus-sindatos").textContent = "";
    F(".bus-datos").hidden = m.sin_datos;
    if (m.sin_datos) {
      F(".bus-sindatos").textContent = I.sin_datos_leyenda;
      F(".bus-aviso").hidden = false;
      F(".bus-aviso").textContent = t("sin_datos_buscador", "Los nidos de Bilbao los retira su propio servicio municipal y no están en el registro de la Diputación. El gráfico muestra solo la tendencia de Bizkaia.");
      return;
    }
    const n = sumaPeriodo(m), na = anios(m);
    const d0 = TT[TT.length - anios(m)];  // primera temporada con datos (Usansolo, desde 2024)
    F("[data-t=tasa]").textContent = plantilla(I.tasa_columna, { desde: d0, hasta });
    cifra("[data-c=tasa]", "tasa", m.tasa, fmt1);
    F("[data-n=nidos]").textContent = plantilla(t("nidos_periodo", "{n} nidos avisados en {desde}-{hasta}"), { n: fmt(n), desde: d0, hasta });
    cifra("[data-c=puesto]", "puesto", m.puesto, (v) => fmt(Math.round(v)));
    F(".bus-de").textContent = plantilla(t("puesto_de", "de {total}"), { total: datos.con_puesto });
    cifra("[data-c=dias]", "dias", m.dias_mediana, fmt1);
    F("[data-n=dias]").textContent = m.dias_mediana == null ? "" :
      plantilla(m.dias_mediana === 1 ? t("dias_nota_uno", "La mitad de sus nidos se retira en 1 día o menos")
        : t("dias_nota", "La mitad de sus nidos se retira en {dias} días o menos"), { dias: fmt1(m.dias_mediana) });
    const com = m.comarca && datos.comarcas_tasa_anual[m.comarca];
    F(".bus-comarca-nombre").textContent = m.comarca || I.sin_dato;
    if (com) {
      const vm = m.tasa_anual[m.tasa_anual.length - 1], vc = com[com.length - 1], r = vm / vc;
      const cmp = r > 1.1 ? t("comarca_mas", "más que su comarca") : r < 0.9 ? t("comarca_menos", "menos que su comarca") : t("comarca_igual", "parecido a su comarca");
      F("[data-n=comarca]").textContent = plantilla(t("comarca_compara", "En {anio}: {vm} nidos por 1.000 habitantes, {cmp} ({vc})."), { anio: hasta, vm: fmt1(vm), vc: fmt1(vc), cmp });
    } else F("[data-n=comarca]").textContent = "";
    const aviso = F(".bus-aviso");
    aviso.hidden = !pocos(m);
    if (pocos(m)) {
      aviso.textContent = m.tendencia?.[0] == null
        ? plantilla(t("pocas_temporadas", "Solo hay datos de {n} temporadas: no se puede calcular una tendencia."), { n: na })
        : plantilla(t("pocos_nidos", "Con tan pocos nidos (menos de {pocos} al año de media) un solo año cambia mucho la tasa: no se dibuja tendencia, solo los valores de cada año."), { pocos: POCOS });
    }
  }

  // ------------------------------------------------------------ gráfico
  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const recorte = `rec-bus-${Math.random().toString(36).slice(2, 7)}`;
  svg.append("defs").append("clipPath").attr("id", recorte).append("rect");
  const g = svg.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const tituloY = g.append("text").attr("class", "titulo-eje");
  const gLineas = g.append("g").attr("clip-path", `url(#${recorte})`);
  const gPuntos = g.append("g");
  const gEtiq = g.append("g");
  const avisoSvg = g.append("text").attr("class", "etiqueta-serie bus-aviso-svg").attr("text-anchor", "middle");
  let actual = null;

  function dibujar(animar = true) {
    if (!actual) return;
    const te = tamano("--t-etiqueta"), tj = tamano("--t-eje");
    const anchoC = contenedor.clientWidth || 320;
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: te * 2, derecha: Math.min(170, anchoC * 0.34), abajo: tj * 2.2, izquierda: tj * 2.6 });
    const dur = animar ? duracion(800) : 0;
    const tr = () => d3.transition().duration(dur).ease(d3.easeCubicInOut);
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    svg.select(`#${recorte} rect`).attr("x", -4).attr("y", 0).attr("width", w + 8).attr("height", h);
    const sd = actual.sin_datos;
    const conTend = !sd && !pocos(actual);
    const com = !sd && actual.comarca && datos.comarcas_tasa_anual[actual.comarca];
    const serie = sd ? [] : actual.tasa_anual.map((v, i) => ({ t: TT[i], v })).filter((q) => q.v != null);
    const vmax = d3.max([...serie.map((q) => q.v), ...datos.bizkaia_tasa_anual, ...(com || []),
      ...(conTend ? actual.tendencia : [])]) || 1;
    const x = d3.scaleLinear().domain([TT[0], TT[TT.length - 1]]).range([0, w]);
    const y = d3.scaleLinear().domain([0, vmax * 1.08]).nice().range([h, 0]);
    gEjeX.attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).ticks(TT.length).tickFormat((a) => (w < 300 ? `'${String(a).slice(2)}` : a)).tickSizeOuter(0));
    gEjeY.transition(tr()).call(d3.axisLeft(y).ticks(4).tickFormat(fmt).tickSize(-w));
    gEjeY.select(".domain").remove();
    tituloY.attr("x", -m.izquierda).attr("y", -te * 1.1).text(I.eje_tasa);

    const lineas = [{ k: "biz", nombre: I.bizkaia_sin_bilbao, a: datos.bizkaia_tendencia, color: "var(--acento)" }];
    if (conTend) lineas.push({ k: "mun", nombre: actual.nombre, a: actual.tendencia, color: "var(--tinta)" });
    const recta = (l) => d3.line()([[x(TT[0]), y(l.a[0])], [x(TT[TT.length - 1]), y(l.a[1])]]);
    gLineas.selectAll("path.bus-tend").data(lineas, (l) => l.k).join(
      (e) => e.append("path").attr("class", "bus-tend").attr("fill", "none").attr("stroke-width", 3)
        .attr("stroke-linecap", "round").attr("stroke", (l) => l.color).attr("opacity", 0).attr("d", recta),
      (u) => u,
      (q) => q.transition(tr()).attr("opacity", 0).remove())
      .transition(tr()).attr("opacity", 1).attr("d", recta);
    // comarca: tasa anual, gris discontinuo (debajo de las tendencias)
    const lc = d3.line().x((q, i) => x(TT[i])).y((q) => y(q));
    gLineas.selectAll("path.bus-comarca").data(com ? [com] : []).join(
      (e) => e.append("path").attr("class", "bus-comarca").attr("fill", "none").attr("stroke", "var(--gris-dato)")
        .attr("stroke-width", 2).attr("stroke-dasharray", "5 4").attr("opacity", 0).attr("d", lc).lower(),
      (u) => u, (q) => q.transition(tr()).attr("opacity", 0).remove())
      .transition(tr()).attr("opacity", 1).attr("d", lc);
    gPuntos.selectAll("circle").data(serie, (q) => q.t).join(
      (e) => e.append("circle").attr("r", 5).attr("fill", "var(--fondo)").attr("stroke", "var(--tinta-suave)").attr("stroke-width", 1.6)
        .attr("cx", (q) => x(q.t)).attr("cy", h).attr("opacity", 0),
      (u) => u, (q) => q.transition(tr()).attr("opacity", 0).remove())
      .transition(tr()).attr("opacity", 1).attr("cx", (q) => x(q.t)).attr("cy", (q) => y(q.v));

    // etiquetas al final de cada línea con su valor (separadas si se pisan)
    const etiq = lineas.map((l) => ({ k: l.k, y: y(l.a[1]), texto: `${l.nombre}: ${fmt1(l.a[1])}`, color: l.color, clase: "" }));
    if (!sd && !conTend && serie.length) {
      const u = serie[serie.length - 1];
      etiq.push({ k: "mun", y: y(u.v), texto: `${actual.nombre} (${u.t}): ${fmt1(u.v)}`, color: "var(--tinta)", clase: "" });
    }
    if (com) etiq.push({ k: "com", y: y(com[com.length - 1]), texto: `${actual.comarca}: ${fmt1(com[com.length - 1])}`, color: "var(--tinta-suave)", clase: " bus-etiq-comarca" });
    // altura de cada etiqueta según sus líneas (se mide antes de separar)
    const sel = gEtiq.selectAll("text").data(etiq, (e) => e.k).join(
      (e) => e.append("text").attr("opacity", 0).attr("y", (d) => d.y),
      (u) => u, (q) => q.transition(tr()).attr("opacity", 0).remove())
      .attr("class", (e) => `etiqueta-serie${e.clase}`).attr("dy", "0.35em").attr("fill", (e) => e.color).attr("x", w + 12)
      .attr("data-texto", null).text((e) => e.texto).call(envolver, m.derecha - 16);
    sel.each(function (e) { e.lineas = +this.getAttribute("data-lineas") || 1; });
    // se separan con el alto real de cada etiqueta (las de dos líneas ocupan más)
    const orden = [...etiq].sort((a, b) => a.y - b.y);
    for (let i = 1; i < orden.length; i++) {
      const min = orden[i - 1].y + te * 1.15 * (orden[i - 1].lineas - 1) + te * 1.3;
      if (orden[i].y < min) orden[i].y = min;
    }
    const ult = orden[orden.length - 1];
    if (ult) {
      const exceso = ult.y + te * 1.15 * (ult.lineas - 1) - h;
      if (exceso > 0) orden.forEach((e) => { e.y -= exceso; });
    }
    sel.each(function () { d3.select(this).selectAll("tspan").attr("x", w + 12); });
    sel.transition(tr()).attr("opacity", 1).attr("y", (e) => e.y);
    avisoSvg.attr("x", w / 2).attr("y", h / 2).attr("fill", "var(--tinta-suave)").text(sd ? I.sin_datos_explorador : "");
    svg.attr("aria-label", plantilla(I.explorador_aria, { municipio: actual.nombre }));
    clavePie.textContent = sd ? "" : conTend
      ? plantilla(t("clave_explorador", "Rectas: tendencia {desde}-{hasta}. Círculos: valor de cada año en {municipio}. Discontinua: su comarca, año a año."), { desde, hasta, municipio: actual.nombre })
      : plantilla(t("clave_explorador_pocos", "Círculos: valor de cada año en {municipio} (sin tendencia). Recta naranja: tendencia de Bizkaia. Discontinua: su comarca."), { municipio: actual.nombre });
  }

  function mostrar(m, animar = true) {
    actual = m;
    entrada.value = m.nombre;
    borrar.hidden = !entrada.value;
    rellenarFicha(m);
    dibujar(animar);
  }

  alRedimensionar(contenedor, () => dibujar(false));
  // Por defecto, el municipio del nido hilo (para que el buscador no aparezca vacío)
  mostrar(lista.find((x) => x.nombre === INICIAL) || lista.find((x) => x.puesto === 1) || lista[0], false);
  return { mostrar };
}

function esc(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}
