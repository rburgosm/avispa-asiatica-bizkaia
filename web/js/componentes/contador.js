// Contador de tiempo de los mapas con evolución temporal: fecha grande (mes y año), nidos
// acumulados (cifra interpolada con D3, sin saltos) y barra de tiempo de la primera a la última
// temporada con una marca por año, el relleno hasta la posición actual, la temporada en curso
// resaltada y una marca de los meses de primavera (abril-junio) en cada año.
// Con prefers-reduced-motion, la cifra cambia sin animación.
import { duracion, formateador, plantilla } from "../util.js";

export function crearContador(el, { temporadas, meses }, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const nT = temporadas.length, nM = meses.length, N = nT * nM;
  el.innerHTML = `<div class="contador-fila"><span class="contador-fecha"></span>
    <span class="contador-nidos"></span></div><svg class="barra-tiempo" role="presentation"></svg>
    <p class="contador-nota">${I.contador_nota || ""}</p>`;
  const fecha = el.querySelector(".contador-fecha");
  const nidos = d3.select(el.querySelector(".contador-nidos"));
  const svg = d3.select(el.querySelector(".barra-tiempo"));
  let valor = 0, frame = -1, ancho = 0;

  function dibujarBarra() {
    ancho = el.querySelector(".barra-tiempo").clientWidth || 300;
    const h = parseFloat(getComputedStyle(svg.node()).height) || 34;
    svg.attr("viewBox", `0 0 ${ancho} ${h}`).selectAll("*").remove();
    const x = d3.scaleLinear().domain([0, N]).range([6, ancho - 6]);
    const yb = 8;
    const g = svg.append("g");
    g.append("rect").attr("class", "temporada-actual").attr("y", 0).attr("height", yb + 6).attr("rx", 2)
      .attr("fill", "var(--sombra-zona)");
    // primavera de cada año (abril-junio): marca fina en ámbar claro
    const iniPrim = meses.indexOf(4), finPrim = meses.indexOf(6);
    g.append("line").attr("x1", x(0)).attr("x2", x(N)).attr("y1", yb).attr("y2", yb)
      .attr("stroke", "var(--linea)").attr("stroke-width", 6);
    // primavera de cada año (abril-junio): tramo en ámbar claro sobre la pista
    temporadas.forEach((t, k) => {
      if (iniPrim >= 0) {
        g.append("rect").attr("x", x(k * nM + iniPrim)).attr("width", x(k * nM + finPrim + 1) - x(k * nM + iniPrim))
          .attr("y", yb - 3).attr("height", 6).attr("fill", "var(--rampa-1)");
      }
    });
    g.append("line").attr("class", "relleno").attr("x1", x(0)).attr("y1", yb).attr("y2", yb)
      .attr("stroke", "var(--acento)").attr("stroke-width", 6).attr("stroke-opacity", 0.85);
    const paso = ancho < 300 ? 2 : 1;
    temporadas.forEach((t, k) => {
      const gg = g.append("g").attr("class", "anio").attr("data-k", k);
      if (k) gg.append("line").attr("x1", x(k * nM)).attr("x2", x(k * nM)).attr("y1", yb - 4).attr("y2", yb + 4)
        .attr("stroke", "var(--fondo)").attr("stroke-width", 2);
      if (k % paso === 0 || k === nT - 1) {
        gg.append("text").attr("x", x(k * nM + nM / 2)).attr("y", h - 2).attr("text-anchor", "middle")
          .text(ancho < 340 ? `'${String(t).slice(2)}` : t);
      }
    });
    g.append("circle").attr("class", "indicador").attr("cy", yb).attr("r", 6)
      .attr("fill", "var(--acento)").attr("stroke", "var(--fondo)").attr("stroke-width", 2);
    svg.node().__x = x;
    if (frame >= 0) colocar(frame);
  }

  function colocar(f) {
    const x = svg.node().__x;
    if (!x) return;
    const k = Math.floor(f / nM);
    svg.select(".relleno").attr("x2", x(f + 1));
    svg.select(".indicador").attr("cx", x(f + 1));
    svg.select(".temporada-actual").attr("x", x(k * nM)).attr("width", x((k + 1) * nM) - x(k * nM));
    svg.selectAll(".anio").classed("actual", function () { return +this.dataset.k === k; });
  }

  // f: índice de mes (0 = primer mes de la primera temporada); n: nidos acumulados.
  // soloAnio: la fecha visible cambia solo de año en año (los nidos siguen apareciendo mes a mes).
  function poner(f, n, { animar = true, soloAnio = false } = {}) {
    f = Math.max(0, Math.min(N - 1, f));
    const t = temporadas[Math.floor(f / nM)], m = meses[f % nM];
    const texto = soloAnio ? String(t) : plantilla(I.contador_fecha, { mes: I.meses_largos[m - 1], anio: t });
    if (fecha.textContent !== texto) {
      fecha.textContent = texto;
      // cambio de año: el número entra con un fundido y un pequeño desplazamiento
      fecha.classList.remove("cambia");
      if (animar && duracion()) { void fecha.offsetWidth; fecha.classList.add("cambia"); }
    }
    if (frame !== f) { frame = f; colocar(f); }
    const desde = valor;
    valor = n;
    const dur = animar ? duracion(350) : 0;
    const pintar = (v) => nidos.html(plantilla(I.contador_nidos, { n: `<strong>${fmt(v)}</strong>` }));
    nidos.interrupt();
    if (!dur) pintar(n);
    else nidos.transition().duration(dur).ease(d3.easeCubicOut)
      .tween("n", () => { const i = d3.interpolateRound(desde, n); return (q) => pintar(i(q)); });
    el.setAttribute("aria-label", plantilla(I.contador_aria, { fecha: fecha.textContent, n: fmt(n), desde: temporadas[0] }));
  }

  function mostrar(si) {
    el.classList.toggle("oculto", !si);
    if (si && !ancho) dibujarBarra();
  }

  new ResizeObserver(() => { if ((el.querySelector(".barra-tiempo").clientWidth || 0) !== ancho) dibujarBarra(); }).observe(el);
  return { poner, mostrar, total: N };
}
