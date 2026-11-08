// Anotaciones sobre los mapas: etiqueta HTML y flecha curva SVG hasta un punto [lon, lat].
// Se recolocan cada vez que la cámara se mueve (recolocar()) con la función de proyección del
// mapa visible (D3 en la narración o MapLibre en el detalle).
import { duracion } from "../util.js";

export function crearAnotador(svgEl, capaEl) {
  const d3 = window.d3;
  const svg = d3.select(svgEl);
  svg.append("defs").append("marker").attr("id", "punta-flecha").attr("viewBox", "0 0 10 10").attr("refX", 8).attr("refY", 5)
    .attr("markerWidth", 7).attr("markerHeight", 7).attr("orient", "auto")
    .append("path").attr("d", "M0,1 L9,5 L0,9").attr("fill", "none").attr("stroke", "var(--tinta)").attr("stroke-width", 1.6);
  let lista = [], proyectar = null;
  // Obstáculos: las cajas visibles de la cabecera del mapa (contador y leyenda; no el hueco del
  // contador oculto) y la tarjeta activa
  const obstaculos = () => [...document.querySelectorAll(".cabeza-mapa > :not(.oculto):not([hidden])"), document.querySelector(".paso-mapa.activo .tarjeta")]
    .filter(Boolean).map((e) => e.getBoundingClientRect()).filter((r) => r.width && r.bottom > 0 && r.top < innerHeight);

  function recolocar() {
    if (!proyectar) return;
    const W = capaEl.clientWidth, H = capaEl.clientHeight;
    const caminos = [];
    for (const a of lista) {
      const [px, py] = proyectar(a.lnglat);
      const dist = a.dist || 70;
      const ew = a.el.offsetWidth, eh = a.el.offsetHeight;
      // Prueba las cuatro posiciones (la preferida primero) y se queda con la que no tapa la
      // cabecera del mapa ni la tarjeta activa
      const pref = [a.lado ? a.lado === "izquierda" : px > W * 0.55, a.vertical ? a.vertical === "arriba" : py > H * 0.4];
      const opciones = [pref, [!pref[0], pref[1]], [pref[0], !pref[1]], [!pref[0], !pref[1]]];
      const obst = obstaculos();
      let izq, arriba, lx, ly;
      for (const [i0, a0] of opciones) {
        let x = px + (i0 ? -dist - ew : dist), y = py + (a0 ? -dist * 0.8 - eh : dist * 0.8);
        x = Math.max(8, Math.min(W - ew - 8, x));
        y = Math.max(8, Math.min(H - eh - 8, y));
        if (izq === undefined) { izq = i0; arriba = a0; lx = x; ly = y; }
        if (!obst.some((o) => x < o.right && x + ew > o.left && y < o.bottom && y + eh > o.top)) { izq = i0; arriba = a0; lx = x; ly = y; break; }
      }
      a.el.style.transform = `translate(${Math.round(lx)}px, ${Math.round(ly)}px)`;
      const sx = izq ? lx + ew + 4 : lx - 4, sy = arriba ? ly + eh : ly;
      const ang = Math.atan2(py - sy, px - sx), r = a.radio || 6;
      const ex = px - Math.cos(ang) * r, ey = py - Math.sin(ang) * r;
      const curva = (izq === arriba ? 1 : -1) * 0.25;
      const mx = (sx + ex) / 2 - (ey - sy) * curva, my = (sy + ey) / 2 + (ex - sx) * curva;
      caminos.push(`M${sx.toFixed(1)},${sy.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${ex.toFixed(1)},${ey.toFixed(1)}`);
    }
    svg.selectAll("path.flecha").data(caminos).join(
      (e) => e.append("path").attr("class", "flecha").attr("marker-end", "url(#punta-flecha)").attr("opacity", 0)
        .call((s) => s.transition().duration(duracion(500)).attr("opacity", 1)))
      .attr("d", (d) => d);
  }

  function poner(nueva, proy) {
    if (proy) proyectar = proy;
    const viejas = [...capaEl.querySelectorAll(".anotacion")];
    viejas.forEach((e) => e.classList.remove("visible"));
    setTimeout(() => viejas.forEach((e) => e.remove()), duracion(600));
    svg.selectAll("path.flecha").remove();
    lista = nueva.map((a) => {
      const el = document.createElement("div");
      el.className = `anotacion${a.clase ? ` ${a.clase}` : ""}`;
      el.innerHTML = a.html;
      capaEl.appendChild(el);
      return { ...a, el };
    });
    recolocar();
    requestAnimationFrame(() => lista.forEach((a) => a.el.classList.add("visible")));
  }
  const tiene = (html) => lista.some((a) => a.html === html);
  // Rectángulos de pantalla de las anotaciones vigentes (obstáculos para los rótulos del mapa)
  const cajas = () => lista.map((a) => a.el.getBoundingClientRect());
  return { poner, recolocar, tiene, cajas, proyector: (p) => { proyectar = p; } };
}
