// Pasos de la especie y del sistema, dibujados con D3 sobre fotografías reales (Wikimedia Commons,
// adaptadas por scripts/web_adaptar_imagenes.py; crédito visible al pie de cada foto):
//   llegada  — línea del tiempo grande de la cronología que se dibuja con el scroll; los hitos de
//              estado.hitos aparecen uno a uno al pasar la línea (los demás hitos confirmados, como
//              puntos pequeños). Foto: la avispa.
//   ciclo    — el año de un nido con los datos de Bizkaia: altura típica de los nidos retirados en
//              cada época (eje vertical, metros) y diámetro típico (tamaño del círculo). Fotos: nido
//              primario y nido secundario, que se funden según el progreso del paso.
//   circuito — vecino → ayuntamiento → Basalan, con el porcentaje de nidos que cierra Basalan.
// Nido hilo (data/nido_hilo.json): anillo en el gráfico del ciclo si el paso trae texto «hilo».
// Datos: web/data/esquemas.json, indicadores.json, cronologia.json, imagenes.json.
import { duracion, formateador, porcentaje, medidas, alRedimensionar, plantilla, envolver, tabla, tamano, tramo } from "../util.js";

export function crearEsquema(contenedor, { esquemas, indicadores, cronologia, imagenes, hilo }, textos, capaFotos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const pct = porcentaje(textos.idioma, 0);
  let estado = { vista: "llegada" }, vistaActual = null, prog = 0, hiloTexto = "";

  const svg = d3.select(contenedor).append("svg").attr("role", "img").attr("class", "esquema");
  const raiz = svg.append("g");
  const hito = (fecha) => cronologia.hitos.find((h) => h.fecha === fecha);
  const [desde, hasta] = indicadores.periodo;
  const basalan = indicadores.temporadas.map((t, i) => ({ t, v: indicadores.pct_basalan[i] }))
    .filter((r) => r.t >= desde && r.t <= hasta);

  // ---------------------------------------------------------------- fotografías a sangre
  // <picture> con AVIF y WebP de reserva (srcset con descriptores w; anchuras de 800 px al máximo
  // del recorte del original, generadas por scripts/web_adaptar_imagenes.py). Recorte 16:9 desde
  // 900 px de ancho y 4:5 en el móvil. Nunca se amplía por encima del original: si la caja pide más
  // píxeles CSS de los que tiene la versión mayor, la foto se muestra a su tamaño máximo, centrada
  // sobre su propia versión diminuta y difuminada (data URI, sin filtros CSS). Grano sutil en CSS.
  const FOTOS = { llegada: ["avispa"], ciclo: ["nido_primario", "nido_secundario"], circuito: [] };
  const ESCRITORIO = window.matchMedia("(min-width: 900px)");
  const fotos = {};
  const srcset = (lista, formato) => lista.map((v) => `${v[formato]} ${v.w}w`).join(", ");
  // Ancho que ocupa la foto con object-fit: cover en una caja a pantalla completa
  const SIZES = { ancho: "(max-aspect-ratio: 16/9) 178vh, 100vw", alto: "(max-aspect-ratio: 4/5) 80vh, 100vw" };
  for (const [clave, f] of Object.entries(imagenes)) {
    const v = f.adaptacion && f.adaptacion.variantes;
    if (!v) continue;
    const an = v.ancho.anchuras, al = v.alto.anchuras;
    const mayor = (l) => l[l.length - 1];
    const fig = document.createElement("figure");
    fig.className = "foto";
    fig.style.setProperty("--fondo-ancho", `url("${v.ancho.fondo}")`);
    fig.style.setProperty("--fondo-alto", `url("${v.alto.fondo}")`);
    fig.style.backgroundColor = f.adaptacion.color || "var(--linea)";
    fig.innerHTML = `<picture>
        <source media="(min-width: 900px)" type="image/avif" srcset="${srcset(an, "avif")}" sizes="${SIZES.ancho}" width="${mayor(an).w}" height="${mayor(an).h}">
        <source media="(min-width: 900px)" type="image/webp" srcset="${srcset(an, "webp")}" sizes="${SIZES.ancho}" width="${mayor(an).w}" height="${mayor(an).h}">
        <source type="image/avif" srcset="${srcset(al, "avif")}" sizes="${SIZES.alto}" width="${mayor(al).w}" height="${mayor(al).h}">
        <img src="${al[0].webp}" srcset="${srcset(al, "webp")}" sizes="${SIZES.alto}" width="${mayor(al).w}" height="${mayor(al).h}"
          alt="${f.descripcion_es}" decoding="async" fetchpriority="${clave === "avispa" ? "auto" : "low"}">
      </picture>
      <figcaption class="pie-foto">${f.descripcion_es} ${plantilla(I.foto_credito, {
        autor: `<a href="${f.url_pagina}">${f.autor}</a>`, licencia: `<a href="${f.url_licencia}">${f.licencia}</a>` })}, ${I.foto_adaptada}</figcaption>`;
    capaFotos.appendChild(fig);
    const img = fig.querySelector("img");
    fotos[clave] = { fig, img, maximo: { ancho: mayor(an), alto: mayor(al) }, foco: f.adaptacion.foco };
    // Decodificación fuera del hilo principal antes de mostrarla (la capa se ve con un fundido)
    const lista = () => fig.classList.add("lista");
    img.decode().then(lista, lista);
  }
  // Tamaño en píxeles CSS: cover si la versión mayor da para cubrir la caja; si no, su tamaño
  // máximo centrado (sin estirar) sobre el fondo difuminado.
  function encajarFotos() {
    const W = capaFotos.clientWidth, H = capaFotos.clientHeight;
    if (!W || !H) return;
    const prop = ESCRITORIO.matches ? "ancho" : "alto";
    for (const o of Object.values(fotos)) {
      const m = o.maximo[prop];
      const escala = Math.max(W / m.w, H / m.h);  // píxeles CSS por píxel del original al cubrir
      const limitada = escala > 1;
      o.fig.classList.toggle("limitada", limitada);
      o.img.style.width = limitada ? `${Math.min(W, m.w)}px` : "";
      o.img.style.height = limitada ? `${Math.min(H, m.h)}px` : "";
      o.img.style.objectPosition = `${o.foco[0] * 100}% ${o.foco[1] * 100}%`;
    }
  }
  encajarFotos();
  new ResizeObserver(encajarFotos).observe(capaFotos);
  // Foto y gráfico no a la vez: primero las fotos a sangre (la tarjeta entra un poco después en el
  // móvil) y, desde FIN_FOTOS del progreso del paso, el gráfico con la misma tarjeta.
  const FIN_FOTOS = 0.5, TARJETA = 0.12;
  const progresoGrafico = (p) => ((FOTOS[estado.vista] || []).length ? Math.max(0, (p - FIN_FOTOS) / (1 - FIN_FOTOS)) : p);
  function verFotos() {
    const lista = FOTOS[estado.vista] || [];
    const activa = lista.length && prog < FIN_FOTOS ? lista[Math.min(lista.length - 1, Math.floor((prog / FIN_FOTOS) * lista.length))] : null;
    for (const [k, o] of Object.entries(fotos)) o.fig.classList.toggle("visible", k === activa);
    const parada = contenedor.closest(".parada");
    if (parada) {
      parada.classList.toggle("fase-foto", !!activa);
      parada.classList.toggle("foto-sola", !!activa && prog < TARJETA);
    }
  }

  // ---------------------------------------------------------------- vistas
  let actualizarProgreso = () => {};

  function llegada(g, w, h) {
    const lista = (estado.hitos || []).map(hito).filter(Boolean);
    const fraccion = (hh) => +hh.fecha.slice(0, 4) + (hh.fecha.length > 4 ? (+hh.fecha.slice(5, 7) - 1) / 12 : 0);
    // Posición de cualquier hito: año, mes y día si los tiene; los periodos («2013/2015»), en su inicio
    const fechaNum = (hh) => {
      const m = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?/.exec(hh.fecha);
      return m ? +m[1] + (m[2] ? (+m[2] - 1 + (m[3] ? (+m[3] - 1) / 31 : 0)) / 12 : 0) : null;
    };
    const a0 = Math.min(...lista.map(fraccion)) - 1.5, a1 = Math.max(hasta + 1, 2026);
    const te = tamano("--t-etiqueta"), tf = tamano("--t-fecha");
    // Margen lateral para que las etiquetas de los años del eje (centradas en su marca) quepan
    const borde = Math.max(8, tamano("--t-eje") * 1.4);
    const x = d3.scaleLinear().domain([a0, a1]).range([borde, w - borde]);
    const yl = Math.round(h * 0.55);
    // Móvil: años de referencia cada cinco años y solo dos anotaciones menores (anotarMenores)
    const movil = w < 480;
    const marcas = d3.range(Math.ceil(a0 / 5) * 5, a1 + 0.01, 5);
    const eje = g.append("g").attr("class", "eje").attr("transform", `translate(0,${yl + 14})`)
      .call((movil ? d3.axisBottom(x).tickValues(marcas) : d3.axisBottom(x).ticks(Math.max(3, Math.floor(w / 110))))
        .tickFormat(String).tickSize(0));
    eje.select(".domain").remove();
    g.append("line").attr("x1", x(a0)).attr("x2", x(a1)).attr("y1", yl).attr("y2", yl).attr("stroke", "var(--linea)").attr("stroke-width", 6).attr("stroke-linecap", "round");
    const trazo = g.append("line").attr("x1", x(a0)).attr("y1", yl).attr("y2", yl).attr("x2", x(a0))
      .attr("stroke", "var(--acento)").attr("stroke-width", 6).attr("stroke-linecap", "round");
    // Los demás hitos confirmados de la cronología, como puntos pequeños (también en el móvil)
    const confirmado = new Set(cronologia.estados);
    const enLista = new Set(lista.map((hh) => hh.fecha));
    const otros = cronologia.hitos.filter((hh) => confirmado.has(hh.estado) && !enLista.has(hh.fecha) && fechaNum(hh) !== null);
    const puntos = g.append("g").selectAll("circle").data(otros).join("circle").attr("cx", (hh) => x(fechaNum(hh))).attr("cy", yl)
      .attr("r", 3.5).attr("fill", "var(--fondo)").attr("stroke", "var(--tinta-suave)").attr("stroke-width", 1.2).attr("opacity", 0);
    const ancho = Math.min(220, w / lista.length - 10);
    const grupos = lista.map((hh, i) => {
      const xx = x(fraccion(hh));
      const arriba = i % 2 === 0;
      const gg = g.append("g").attr("opacity", 0);
      gg.append("line").attr("x1", xx).attr("x2", xx).attr("y1", yl).attr("y2", arriba ? yl - tf * 2.4 : yl + tf * 2.6)
        .attr("stroke", "var(--tinta)").attr("stroke-width", 1.2);
      gg.append("circle").attr("cx", xx).attr("cy", yl).attr("r", 9).attr("fill", "var(--acento)").attr("stroke", "var(--fondo)").attr("stroke-width", 3);
      const ancla = xx > w * 0.7 ? "end" : "start";
      const dx = ancla === "end" ? -8 : 8;
      const ty = arriba ? yl - tf * 2.4 : yl + tf * 2.6 + tf * 0.8;
      gg.append("text").attr("class", "enorme").attr("x", xx + dx).attr("y", ty).attr("text-anchor", ancla).text(hh.fecha.slice(0, 4));
      const t = gg.append("text").attr("x", xx + dx).attr("y", ty + te * 1.3).attr("text-anchor", ancla)
        .text(I.llegada[hh.fecha] || hh.titulo).call(envolver, ancho);
      t.selectAll("tspan").attr("text-anchor", ancla);
      if (arriba) {  // el texto va encima del año
        const n = +t.attr("data-lineas");
        t.attr("transform", `translate(0,${-(n * te * 1.15) - tf * 1.15 - te * 0.4})`);
      }
      return { gg, a: fraccion(hh) };
    });
    const notas = anotarMenores(g, w, h, x, yl, fechaNum, grupos.map((q) => q.gg), eje, movil);
    actualizarProgreso = (p, animar) => {
      const a = a0 + (a1 - a0) * Math.min(1, p / 0.85);
      const xa = x(a);
      trazo.interrupt().transition().duration(animar ? duracion(250) : 0).attr("x2", xa);
      // Hitos grandes, anotaciones menores y puntos: fundido al pasar el trazo por su fecha
      // (solo se lanza la transición cuando cambia el objetivo: no se reinicia en cada evento de scroll)
      const fundir = (sel, v, ms) => {
        const n = sel.node();
        if (n.__objetivo === v) return;
        n.__objetivo = v;
        sel.interrupt().transition().duration(animar ? duracion(ms) : 0).attr("opacity", v);
      };
      for (const q of grupos) fundir(q.gg, a >= q.a ? 1 : 0, 450);
      for (const q of notas) fundir(q.gg, a >= q.a ? 1 : 0, 600);
      puntos.each(function (hh) { fundir(d3.select(this), a >= fechaNum(hh) ? 0.9 : 0, 300); });
    };
  }

  // Anotaciones de algunos hitos menores (confirmados): texto corto en tinta suave con flecha curva
  // fina hasta su punto, con menos jerarquía que los hitos grandes. Fecha y texto salen de
  // cronologia.json: cada entrada da la fecha y un fragmento literal del título que se muestra (si el
  // fragmento no está en el título, la anotación no se pone). Se colocan en orden de prioridad,
  // arriba o abajo y a un lado u otro del punto, en la primera posición que no pisa los hitos
  // grandes, el eje, otras anotaciones ni el borde; si no cabe, no se pone. Móvil: solo las dos primeras.
  const MENORES = [
    ["2016-07-01", "Entra en funcionamiento el protocolo foral", "abajo"],
    ["2018-01-06", "Primer aviso del registro de nidos", "arriba"],
    ["2013-08-03", "Catálogo Español de Especies Exóticas Invasoras", "arriba"],
    ["2014-11-14", "Estrategia estatal", "abajo"],
    ["2011-09", "Mesa de Seguimiento de la Vespa velutina", "arriba"],
  ];
  function anotarMenores(g, w, h, x, yl, fechaNum, grandes, eje, movil) {
    const capa = g.append("g").attr("class", "notas-crono");
    const id = "punta-crono";
    if (svg.select(`#${id}`).empty()) {
      svg.append("defs").append("marker").attr("id", id).attr("viewBox", "0 0 10 10").attr("refX", 8).attr("refY", 5)
        .attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto")
        .append("path").attr("d", "M0,1 L9,5 L0,9").attr("fill", "none").attr("stroke", "var(--tinta-suave)").attr("stroke-width", 1.5);
    }
    // Caja de un elemento en las coordenadas de g (con las transformaciones de sus padres)
    const ref = g.node().getCTM().inverse();
    const caja = (n) => {
      const b = n.getBBox(), m = ref.multiply(n.getCTM());
      const pts = [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]]
        .map(([px, py]) => [m.a * px + m.c * py + m.e, m.b * px + m.d * py + m.f]);
      return { x0: d3.min(pts, (q) => q[0]), x1: d3.max(pts, (q) => q[0]), y0: d3.min(pts, (q) => q[1]), y1: d3.max(pts, (q) => q[1]) };
    };
    const choca = (a, b, m = 6) => a.x0 < b.x1 + m && a.x1 > b.x0 - m && a.y0 < b.y1 + m && a.y1 > b.y0 - m;
    // Obstáculos: hitos grandes (rótulo, año y palo), eje con sus años y la propia línea
    // (pieza a pieza: la caja del grupo entero taparía el hueco entre el palo y el rótulo)
    const piezas = grandes.flatMap((gg) => gg.selectChildren().nodes().map(caja));
    const centros = grandes.map((gg) => +gg.select("circle").attr("cx"));
    const etiquetasEje = eje.selectAll("text").nodes().map(caja);
    const ocupado = [...piezas, caja(eje.node()), { x0: x.range()[0] - 6, x1: x.range()[1] + 6, y0: yl - 10, y1: yl + 10 }];
    const lin = 15 * 1.2, anchoMax = Math.min(200, w * (movil ? 0.5 : 0.42));
    const lista = MENORES.slice(0, movil ? 2 : MENORES.length).map(([fecha, fragmento, lado]) => {
      const hh = cronologia.hitos.find((q) => q.fecha === fecha && cronologia.estados.includes(q.estado));
      if (!hh || !hh.titulo.includes(fragmento)) return null;
      return { hh, fragmento, lado, a: fechaNum(hh) };
    }).filter(Boolean);
    // Flecha curva desde el borde del texto del lado del punto, a media altura de la línea más
    // cercana a la línea del tiempo, hasta el borde del punto (como las de los mapas)
    let lineas = 1, alto = 0, radio = 7;
    const flecha = (c, lado, dx, px, py) => {
      // centrada sobre o bajo el punto (dx = 0): desde el centro del borde más cercano a la línea
      const sx = dx === 0 ? (c.x0 + c.x1) / 2 + 6 : dx > 0 ? c.x0 - 4 : c.x1 + 4;
      const sy = dx === 0 ? (lado === "arriba" ? c.y1 + 3 : c.y0 - 3)
        : lado === "arriba" ? c.y1 - (lineas > 1 ? lin * 0.5 : alto / 2) : c.y0 + (lineas > 1 ? lin * 0.5 : alto / 2);
      const ang = Math.atan2(py - sy, px - sx);
      const ex = px - Math.cos(ang) * radio, ey = py - Math.sin(ang) * radio;
      const curva = dx === 0 ? 0.15 : (dx > 0) === (lado === "arriba") ? -0.3 : 0.3;
      return { sx, sy, ex, ey, mx: (sx + ex) / 2 - (ey - sy) * curva, my: (sy + ey) / 2 + (ex - sx) * curva };
    };
    const notas = [];
    for (const n of lista) {
      const px = x(n.a), py = yl;
      // si el punto queda bajo el de un hito grande (protocolo de 2016 y lista de la UE, dos semanas
      // después), la punta se queda en el borde del punto grande
      radio = centros.some((cx) => Math.abs(cx - px) < 8) ? 14 : 7;
      const gg = capa.append("g").attr("opacity", 0);
      const t = gg.append("text").attr("class", "nota-crono").attr("x", 0).attr("y", 0);
      // envolver() reparte por palabras: se escribe el texto completo y se marca el año después
      t.text(`${n.hh.fecha.slice(0, 4)} ${n.fragmento}`).call(envolver, anchoMax, 1.2);
      t.select("tspan").each(function () {
        const s = d3.select(this), [anio, ...resto] = s.text().split(" ");
        s.text(null);
        s.append("tspan").attr("class", "nota-anio").text(anio);
        s.append("tspan").text(` ${resto.join(" ")}`);
      });
      const b0 = t.node().getBBox();
      lineas = +t.attr("data-lineas") || 1;
      alto = b0.height;
      const ancho = b0.width;
      const otro = n.lado === "arriba" ? "abajo" : "arriba";
      let elegida = null;
      for (const lado of [n.lado, otro]) {
        for (const dy of [34, 64, 96, 128, 160, 192]) {
          for (const dx of [18, -18, 60, -60, 110, -110, 0]) {
            const x0 = dx === 0 ? px - ancho / 2 : dx > 0 ? px + dx : px + dx - ancho;
            const y0 = lado === "arriba" ? py - dy - alto : py + dy;
            const c = { x0, y0, x1: x0 + ancho, y1: y0 + alto };
            if (c.x0 < 0 || c.x1 > w || c.y0 < 0 || c.y1 > h) continue;
            if (ocupado.some((o) => choca(c, o))) continue;
            const f = flecha(c, lado, dx, px, py);
            if (Math.hypot(f.ex - f.sx, f.ey - f.sy) > 120) continue;  // sin flechas largas que crucen el gráfico
            // la flecha tampoco cruza hitos grandes ni otras anotaciones (salvo junto a su punto)
            const muestras = d3.range(0.05, 1, 0.05).map((k) => [
              (1 - k) ** 2 * f.sx + 2 * (1 - k) * k * f.mx + k * k * f.ex,
              (1 - k) ** 2 * f.sy + 2 * (1 - k) * k * f.my + k * k * f.ey])
              .filter(([qx, qy]) => Math.hypot(qx - px, qy - py) > radio + 14);
            const tapan = [...piezas, ...etiquetasEje, ...notas.map((q) => q.c)];
            if (muestras.some(([qx, qy]) => tapan.some((o) => qx > o.x0 - 8 && qx < o.x1 + 8 && qy > o.y0 - 8 && qy < o.y1 + 8))) continue;
            // ni se cruza o roza con las flechas ya puestas
            if (muestras.some(([qx, qy]) => notas.some((q) => q.muestras.some(([rx, ry]) => Math.hypot(qx - rx, qy - ry) < 8)))) continue;
            elegida = { c, lado, dx, muestras };
            break;
          }
          if (elegida) break;
        }
        if (elegida) break;
      }
      if (!elegida) { gg.remove(); continue; }
      const { c, lado, dx, muestras } = elegida;
      t.attr("transform", `translate(${c.x0 - b0.x},${c.y0 - b0.y})`);
      const f = flecha(c, lado, dx, px, py);
      gg.insert("path", "text").attr("class", "flecha-crono").attr("marker-end", `url(#${id})`)
        .attr("d", `M${f.sx.toFixed(1)},${f.sy.toFixed(1)} Q${f.mx.toFixed(1)},${f.my.toFixed(1)} ${f.ex.toFixed(1)},${f.ey.toFixed(1)}`);
      ocupado.push(c);
      notas.push({ gg, a: n.a, c, muestras });
    }
    return notas;
  }

  function ciclo(g, w, h) {
    const perfil = esquemas.perfil;
    const columnas = [...perfil.map((p) => p.epoca), "invierno"];
    const x = d3.scalePoint().domain(columnas).range([0, w]).padding(0.5);
    const te = tamano("--t-etiqueta"), lin = te * 1.15;
    const anchoCol = x.step() * 0.95;
    // Rótulos de las épocas arriba: el alto de la franja se mide (líneas reales tras partir)
    const cabeceras = columnas.map((c) => {
      const t = g.append("text").attr("x", x(c)).attr("y", te).attr("text-anchor", "middle").attr("class", "grande")
        .text(I.epocas[c]).call(envolver, anchoCol);
      t.selectAll("tspan").attr("text-anchor", "middle");
      return t;
    });
    const lineasCab = d3.max(cabeceras, (t) => +t.attr("data-lineas") || 1);
    const arriba = te + (lineasCab - 1) * lin + te * 0.6;
    // Dato bajo el suelo, partido por « · » (tamaño, altura, árbol) para no cortar «a 3 m». Si el
    // lienzo es bajo, primero se quita la parte secundaria («en árbol», también en la tabla), nunca
    // se reduce la letra.
    const piezas = (p) => plantilla(I.ciclo_dato, { d: fmt(p.diam_cm), a: fmt(p.altura_m), arbol: pct(p.pct_arbol) }).split(" · ");
    // Agrupación de las piezas en líneas, la misma en todas las columnas: la primera opción en la
    // que todo cabe (todo junto, tamaño y altura juntos, altura y árbol juntos o una por línea)
    const AGRUPAR = [[[0, 1, 2]], [[0, 1], [2]], [[0], [1, 2]], [[0], [1], [2]]];
    let grupos = AGRUPAR[AGRUPAR.length - 1];
    const unir = (lista) => grupos.map((gr) => gr.filter((k) => k < lista.length).map((k) => lista[k]).join(" · ")).filter(Boolean);
    const elegirGrupos = (n) => {
      const prueba = g.append("text").attr("visibility", "hidden");
      const largo = (t) => prueba.text(t).node().getComputedTextLength();
      grupos = AGRUPAR.find((op) => {
        grupos = op;
        return perfil.every((p) => unir(piezas(p).slice(0, n)).every((l) => largo(l) <= anchoCol));
      }) || AGRUPAR[AGRUPAR.length - 1];
      prueba.remove();
    };
    // Cada línea unida se escribe partida al ancho de la columna; devuelve el número de líneas
    const escribirDato = (padre, xx, lista) => unir(lista).reduce((n, linea) => {
      const s = padre.append("text").attr("x", xx).attr("y", suelo0 + te * 1.3 + n * lin).attr("text-anchor", "middle")
        .text(linea).call(envolver, anchoCol);
      s.selectAll("tspan").attr("text-anchor", "middle");
      return n + (+s.attr("data-lineas") || 1);
    }, 0);
    let suelo0 = 0;
    const lineasDato = (lista) => {
      elegirGrupos(lista.length);
      const prueba = g.append("g").attr("visibility", "hidden");
      const n = escribirDato(prueba, 0, lista);
      prueba.remove();
      return n;
    };
    let partes = piezas(perfil[0]).length, lineasAbajo = d3.max(perfil, (p) => lineasDato(piezas(p)));
    const altoAbajo = (n) => te * 1.3 + (n - 1) * lin + te * 0.5;
    const MIN_TRAZADO = te * 7;
    if (h - arriba - altoAbajo(lineasAbajo) < MIN_TRAZADO) {
      partes = 2;
      lineasAbajo = d3.max(perfil, (p) => lineasDato(piezas(p).slice(0, 2)));
    }
    const suelo = h - altoAbajo(lineasAbajo);
    const alto = Math.max(suelo - arriba, 40);
    const rmax = Math.min(x.step() * 0.36, alto * 0.22, 46);
    const r = d3.scaleSqrt().domain([0, Math.max(d3.max(perfil, (p) => p.diam_cm), hilo.nido.diametro_cm)]).range([0, rmax]);
    // El círculo más alto no toca los rótulos: el techo de la escala deja su radio libre
    const altMax = Math.max(d3.max(perfil, (p) => p.altura_m), hilo.nido.altura_m);
    const pMax = perfil.reduce((a, b) => (b.altura_m > a.altura_m ? b : a));
    const ymax = altMax * 1.05;
    const y = d3.scaleLinear().domain([0, ymax]).range([suelo, Math.min(suelo - 10, arriba + r(pMax.diam_cm) + 2)]);
    g.append("line").attr("x1", 0).attr("x2", w).attr("y1", suelo).attr("y2", suelo).attr("stroke", "var(--tinta-suave)").attr("stroke-width", 1.5);
    const eje = g.append("g").attr("class", "eje").call(d3.axisLeft(y).ticks(alto < te * 9 ? 2 : 3).tickFormat((v) => `${fmt(v)} m`).tickSize(-w));
    eje.select(".domain").remove();
    eje.selectAll("text").attr("x", 2).attr("dy", -4).attr("text-anchor", "start");
    eje.lower();
    suelo0 = suelo;
    const cols = columnas.map((c, i) => {
      const xx = x(c);
      const gd = g.append("g").attr("class", "columna").attr("opacity", 0);
      const p = perfil.find((q) => q.epoca === c);
      if (p) {
        const cy = y(p.altura_m);
        gd.append("line").attr("x1", xx).attr("x2", xx).attr("y1", suelo).attr("y2", cy)
          .attr("stroke", "var(--tinta-suave)").attr("stroke-dasharray", "3 3");
        gd.append("circle").attr("cx", xx).attr("cy", cy).attr("r", r(p.diam_cm))
          .attr("fill", "var(--acento)").attr("fill-opacity", 0.85).attr("stroke", "var(--tinta)").attr("stroke-width", 1);
        escribirDato(gd, xx, piezas(p).slice(0, partes));
      } else {
        // Invierno: la columna no tiene círculo; su texto va encima de las reinas (puntos), dentro
        // del trazado, con halo del fondo sobre las líneas de la cuadrícula. Si no cabe encima, los
        // puntos (decorativos) se quitan y el texto baja hasta el suelo.
        const d = gd.append("text").attr("x", xx).attr("y", 0).attr("text-anchor", "middle")
          .attr("paint-order", "stroke").attr("stroke", "var(--fondo)").attr("stroke-width", 4).attr("stroke-linejoin", "round")
          .text(I.ciclo_invierno).call(envolver, anchoCol);
        d.selectAll("tspan").attr("text-anchor", "middle");
        const n = +d.attr("data-lineas") || 1;
        const conPuntos = suelo - 24 - (n - 1) * lin >= arriba + te * 0.8;
        d.attr("y", Math.max(arriba + te * 0.8, suelo - (conPuntos ? 24 : 6) - (n - 1) * lin));
        if (conPuntos) {
          for (let k = 0; k < 5; k++) {
            gd.append("circle").attr("cx", xx - 16 + k * 8).attr("cy", suelo - 8 - (k % 2) * 6).attr("r", 2.5).attr("fill", "var(--tinta)");
          }
        }
      }
      return { gd, i };
    });
    // Nido hilo: anillo a su altura y con su diámetro, en la columna de su época (verano y otoño)
    const nh = hilo.nido;
    const gh = g.append("g").attr("class", "hilo").attr("opacity", 0);
    const xh = x("verano_otono") + Math.min(x.step() * 0.28, 40);
    gh.append("circle").attr("class", "hilo-anillo").attr("cx", xh).attr("cy", y(nh.altura_m)).attr("r", r(nh.diametro_cm) + 4);
    gh.append("text").attr("class", "hilo-texto").attr("x", xh + r(nh.diametro_cm) + 10).attr("y", y(nh.altura_m)).attr("dy", "0.35em");
    let ultimo = null;  // el texto del nido hilo solo se vuelve a partir si cambia (mide texto)
    actualizarProgreso = (p) => {
      // las épocas aparecen una a una con el scroll
      const n = Math.min(cols.length, 1 + Math.floor(Math.min(1, p / 0.8) * cols.length));
      cols.forEach((c) => { const v = c.i < n ? 1 : 0; if (+c.gd.attr("opacity") !== v) c.gd.interrupt().transition().duration(duracion(450)).attr("opacity", v); });
      gh.attr("opacity", hiloTexto && n >= 2 ? 1 : 0);
      if (ultimo !== hiloTexto) {
        ultimo = hiloTexto;
        gh.select("text").text(hiloTexto).call(envolver, Math.max(90, w - xh - r(nh.diametro_cm) - 14));
      }
    };
  }

  function circuito(g, w, h) {
    const nodos = I.circuito_nodos;
    const vertical = w < 420;
    const n = nodos.length;
    const te = tamano("--t-etiqueta"), tp = tamano("--t-eje");
    // Debajo: lo que hace Basalan (dato), los bomberos y el registro público. Se escribe primero
    // para medir su alto; las dos líneas pequeñas son secundarias y se quitan si no cabe todo.
    const lineas = [
      plantilla(I.circuito_basalan, { min: pct(d3.min(basalan, (r) => r.v)), max: pct(d3.max(basalan, (r) => r.v)), desde, hasta }),
      I.circuito_bomberos, I.circuito_registro];
    const gb = g.append("g");
    const altos = lineas.map((l, k) => {
      const t = gb.append("text").attr("x", w / 2).attr("text-anchor", "middle").attr("data-k", k)
        .attr("class", k ? "pequeno" : null).attr("font-weight", k ? 400 : 600).text(l).call(envolver, w - 8);
      t.selectAll("tspan").attr("text-anchor", "middle");
      return (+t.attr("data-lineas") || 1) * (k ? tp : te) * 1.25 + 4;
    });
    const altoBajo = (k) => d3.sum(altos.slice(0, k));  // k = número de líneas que se muestran
    const p16 = hito("2016-07-01");
    const altoDesde = p16 ? tp * 1.9 : 0;
    let caja, pos, verBajo = lineas.length, verDesde = !!p16;
    if (vertical) {
      // Alto disponible: «Desde…», las cajas, las flechas y el texto de abajo. Si no cabe, se
      // reduce por orden: flechas, relleno de las cajas, líneas secundarias, «Desde…» y, al final,
      // flechas mínimas. La letra no cambia.
      const ancho = Math.min(w * 0.8, 280);
      const HUECO = { max: te * 3.2, min: te * 1.5, ultimo: te * 0.9 }, CAJA = { max: te * 3.8, min: te * 2.9 };
      const SEP = te * 1.1;  // de la última caja al texto de abajo
      const fijo = (cajaH, b, d) => (d ? altoDesde : 0) + n * cajaH + SEP + altoBajo(b);
      let cajaH = CAJA.max;
      const hueco = () => (h - fijo(cajaH, verBajo, verDesde)) / (n - 1);
      if (hueco() < HUECO.min) cajaH = Math.max(CAJA.min, CAJA.max - (HUECO.min - hueco()) * (n - 1) / n);
      if (hueco() < HUECO.min) verBajo = 1;
      if (hueco() < HUECO.min) verDesde = false;
      const gap = Math.max(HUECO.ultimo, Math.min(HUECO.max, hueco()));
      caja = { w: ancho, h: cajaH };
      const y0 = (verDesde ? altoDesde : 0) + cajaH / 2;
      pos = nodos.map((_, i) => ({ x: w / 2, y: y0 + i * (cajaH + gap) }));
    } else {
      caja = { w: Math.min((w - 40) / n - 28, 230), h: te * 5 };
      pos = nodos.map((_, i) => ({ x: (i + 0.5) * (w / n), y: Math.max(h * 0.42, 80) }));
    }
    if (p16 && verDesde) {
      g.append("text").attr("x", w / 2).attr("y", pos[0].y - caja.h / 2 - (vertical ? tp * 0.7 : 16)).attr("text-anchor", "middle").attr("class", "pequeno")
        .text(plantilla(I.circuito_desde, { mes: I.meses_largos[+p16.fecha.slice(5, 7) - 1], anio: p16.fecha.slice(0, 4) }));
    }
    // flechas
    g.append("defs").append("marker").attr("id", "flecha").attr("viewBox", "0 0 10 10").attr("refX", 9).attr("refY", 5)
      .attr("markerWidth", 7).attr("markerHeight", 7).attr("orient", "auto-start-reverse")
      .append("path").attr("d", "M0,0 L10,5 L0,10 z").attr("fill", "var(--tinta-suave)");
    for (let i = 0; i < n - 1; i++) {
      const a = pos[i], b = pos[i + 1];
      g.append("line").attr("stroke", "var(--tinta-suave)").attr("stroke-width", 1.5).attr("marker-end", "url(#flecha)")
        .attr("x1", vertical ? a.x : a.x + caja.w / 2 + 2).attr("y1", vertical ? a.y + caja.h / 2 + 2 : a.y)
        .attr("x2", vertical ? b.x : b.x - caja.w / 2 - 4).attr("y2", vertical ? b.y - caja.h / 2 - 4 : b.y);
    }
    nodos.forEach((nd, i) => {
      const gg = g.append("g").attr("transform", `translate(${pos[i].x},${pos[i].y})`).attr("opacity", 0);
      const ultimo = i === n - 1;
      gg.append("rect").attr("x", -caja.w / 2).attr("y", -caja.h / 2).attr("width", caja.w).attr("height", caja.h).attr("rx", 4)
        .attr("fill", ultimo ? "var(--acento-2)" : "var(--fondo)").attr("stroke", ultimo ? "var(--acento-2)" : "var(--tinta-suave)");
      const t = gg.append("text").attr("text-anchor", "middle").attr("y", nd.detalle ? -4 : 5);
      t.append("tspan").attr("class", "grande").attr("x", 0).attr("fill", ultimo ? "var(--blanco)" : "var(--tinta)").text(nd.nombre);
      if (nd.detalle) t.append("tspan").attr("x", 0).attr("dy", "1.3em")
        .attr("fill", ultimo ? "var(--blanco)" : "var(--tinta-suave)").text(nd.detalle);
      gg.transition().delay(i * 300).duration(duracion(500)).attr("opacity", 1);
    });
    // Texto de abajo: primera línea con su base a te * 0.85 del borde superior del bloque
    const ult = pos[n - 1];
    const yb = ult.y + caja.h / 2 + (vertical ? te * 1.1 + te * 0.85 : 24);
    gb.selectAll("text").each(function (_, k) {
      if (k >= verBajo) { this.remove(); return; }
      const t = d3.select(this).attr("y", yb + altoBajo(k));
      t.selectAll("tspan").attr("x", w / 2);
    });
  }

  const VISTAS = { llegada, ciclo, circuito };

  function dibujar(animar = true) {
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: 8, derecha: 8, abajo: 8, izquierda: 8 });
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    const cambia = vistaActual !== estado.vista;
    vistaActual = estado.vista;
    const vieja = raiz.selectAll("g.vista");
    if (cambia && animar && duracion()) vieja.transition().duration(duracion(300)).attr("opacity", 0).remove();
    else vieja.remove();
    actualizarProgreso = () => {};
    const g = raiz.append("g").attr("class", "vista").attr("transform", `translate(${m.izquierda},${m.arriba})`);
    (VISTAS[estado.vista] || llegada)(g, w, h);
    if (cambia && animar && duracion()) g.attr("opacity", 0).transition().delay(150).duration(duracion(400)).attr("opacity", 1);
    actualizarProgreso(progresoGrafico(prog), false);
    verFotos();
  }

  alRedimensionar(contenedor, () => { vistaActual = null; dibujar(false); });
  return {
    nota() { return estado.vista === "ciclo" ? plantilla(I.ciclo_nota, { desde, hasta }) : ""; },
    actualizar(nuevo, animar = true) {
      estado = { vista: "llegada", ...nuevo }; prog = 0;
      // Si el título del gráfico es el mismo titular de la tarjeta, en el móvil se oculta (sin
      // cambiar el alto del lienzo); app.js pone el título antes de llamar a actualizar.
      const panel = contenedor.closest(".panel"), t = panel && panel.querySelector(".titulo-grafico");
      if (t) panel.classList.toggle("titulo-repetido", textos.pasos.some((p) => p.titular && p.titular === t.textContent));
      dibujar(animar);
    },
    progreso(p) { prog = p; actualizarProgreso(progresoGrafico(p), true); verFotos(); },
    hilo(texto) { hiloTexto = texto; actualizarProgreso(progresoGrafico(prog), false); },
    ocultarFotos() {
      Object.values(fotos).forEach((o) => o.fig.classList.remove("visible"));
      document.querySelectorAll(".fase-foto, .foto-sola").forEach((e) => e.classList.remove("fase-foto", "foto-sola"));
    },
    tablaDatos() {
      const caja = document.createElement("div");
      caja.appendChild(tabla([I.epoca, I.nidos_retirados, I.diametro_tipico, I.altura_tipica, I.en_arbol],
        esquemas.perfil.map((p) => [I.epocas[p.epoca], fmt(p.n), `${fmt(p.diam_cm)} cm`, `${fmt(p.altura_m)} m`, pct(p.pct_arbol)]),
        I.tabla_perfil));
      const fechas = textos.pasos.flatMap((p) => (p.estado && p.estado.hitos) || []);
      caja.appendChild(tabla([I.fecha, I.hito, I.fuente], fechas.map(hito).filter(Boolean).map((hh) => [hh.fecha, hh.titulo, hh.url]),
        I.tabla_hitos));
      return caja;
    },
    describir() {
      if (estado.vista === "ciclo") {
        return esquemas.perfil.map((p) => plantilla(I.ciclo_desc, { epoca: I.epocas[p.epoca], n: fmt(p.n), d: fmt(p.diam_cm),
          a: fmt(p.altura_m), arbol: pct(p.pct_arbol) })).join(" ");
      }
      if (estado.vista === "circuito") {
        return plantilla(I.circuito_basalan, { min: pct(d3.min(basalan, (r) => r.v)), max: pct(d3.max(basalan, (r) => r.v)), desde, hasta });
      }
      return "";
    },
  };
}
