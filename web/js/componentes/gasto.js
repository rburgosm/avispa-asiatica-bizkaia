// Gasto identificable en la retirada de nidos, 2017-2025 (paso 11). Barras azules (acción
// pública) con el importe de las líneas propias de 2017-2019 y su coste por nido; 2020
// «mezclado con otros trabajos» y 2021-2025 «sin desglose», como columnas rayadas en gris sin
// altura de dato (no hay importe que dibujar), con el encargo anual a Basalan como contexto.
// Datos: web/data/gasto.json (outputs/avispa_gasto_anual.csv y avispa_gasto_coste_nido.csv).
import { duracion, formateador, medidas, rayado, tabla, alRedimensionar, plantilla, envolver } from "../util.js";

export function crearGasto(contenedor, datos, textos) {
  const d3 = window.d3;
  const I = textos.interfaz;
  const fmt = formateador(textos.idioma, 0);
  const fmtM = formateador(textos.idioma, 1);
  const anios = datos.anios;
  const millones = (v) => `${fmtM(v / 1e6)} M€`;
  const miles = (v) => `${fmt(Math.round(v / 1000))} mil €`;

  const svg = d3.select(contenedor).append("svg").attr("role", "img");
  const patron = rayado(svg);
  const g = svg.append("g");
  const gEjeX = g.append("g").attr("class", "eje");
  const gEjeY = g.append("g").attr("class", "eje");
  const gBarras = g.append("g");
  const gEtiq = g.append("g");
  const gGrupos = g.append("g");

  function grupos() {
    // Tramos seguidos con el mismo estado (para una sola etiqueta por tramo)
    const out = [];
    for (const a of anios) {
      const u = out[out.length - 1];
      if (u && u.estado === a.estado) u.lista.push(a); else out.push({ estado: a.estado, lista: [a] });
    }
    return out;
  }

  function dibujar(animar = true) {
    const { ancho, alto, w, h, m } = medidas(contenedor, { arriba: 22, derecha: 8, abajo: 26, izquierda: 50 });
    const dur = animar ? duracion(700) : 0;
    svg.attr("viewBox", `0 0 ${ancho} ${alto}`);
    g.attr("transform", `translate(${m.izquierda},${m.arriba})`);
    const x = d3.scaleBand().domain(anios.map((a) => a.anio)).range([0, w]).padding(0.18);
    const maxImp = d3.max(anios, (a) => a.retirada_eur || 0);
    const y = d3.scaleLinear().domain([0, maxImp * 1.25]).nice().range([h, 0]);
    gEjeX.attr("transform", `translate(0,${h})`)
      .call(d3.axisBottom(x).tickSizeOuter(0).tickFormat((t) => (w < 360 ? `'${String(t).slice(2)}` : t)));
    gEjeY.call(d3.axisLeft(y).ticks(4).tickFormat((v) => (v === 0 ? "0" : miles(v))).tickSize(-w))
      .call((s) => s.select(".domain").remove());

    const conImporte = anios.filter((a) => a.estado === "importe");
    gBarras.selectAll("rect.imp").data(conImporte, (a) => a.anio).join(
      (e) => e.append("rect").attr("class", "imp").attr("y", h).attr("height", 0))
      .attr("x", (a) => x(a.anio)).attr("width", x.bandwidth()).attr("fill", "var(--acento-2)")
      .transition().duration(dur).attr("y", (a) => y(a.retirada_eur)).attr("height", (a) => h - y(a.retirada_eur));
    // Columnas sin dato: rayadas a toda la altura, con borde discontinuo
    const sinDato = anios.filter((a) => a.estado !== "importe");
    gBarras.selectAll("rect.sin").data(sinDato, (a) => a.anio).join("rect").attr("class", "sin")
      .attr("x", (a) => x(a.anio)).attr("width", x.bandwidth()).attr("y", 0).attr("height", h)
      .attr("fill", patron).attr("stroke", "var(--gris-dato)").attr("stroke-dasharray", "3 2")
      .attr("opacity", 0).transition().duration(dur).attr("opacity", 0.8);

    // Importe y coste por nido sobre cada barra con importe
    const estrecho = x.bandwidth() < 48;
    const et = gEtiq.selectAll("text.imp").data(conImporte, (a) => a.anio).join("text").attr("class", "imp etiqueta-valor")
      .attr("text-anchor", "middle").attr("font-size", estrecho ? 10 : 12);
    et.attr("x", (a) => x(a.anio) + x.bandwidth() / 2).attr("y", (a) => y(a.retirada_eur) - (datos.coste_nido[a.anio] ? (estrecho ? 44 : 30) : 6))
      .each(function (a) {
        const t = d3.select(this).text(null);
        t.append("tspan").attr("x", x(a.anio) + x.bandwidth() / 2).text(miles(a.retirada_eur));
        const c = datos.coste_nido[a.anio];
        if (c) {
          const v = c.min === c.max ? fmt(c.min) : `${fmt(c.min)}-${fmt(c.max)}`;
          const lineas = estrecho ? [v, I.eur_nido_corto] : [plantilla(I.eur_nido, { v })];
          lineas.forEach((l) => t.append("tspan").attr("x", x(a.anio) + x.bandwidth() / 2).attr("dy", "1.15em")
            .attr("font-weight", 400).attr("fill", "var(--tinta-suave)").text(l));
        }
      });

    // Etiqueta de cada tramo sin dato, dentro de la zona rayada, sobre un fondo para que se lea
    const gr = grupos().filter((gg) => gg.estado !== "importe").map((gg) => {
      const a0 = gg.lista[0].anio, a1 = gg.lista[gg.lista.length - 1].anio;
      const enc = gg.lista.map((a) => a.encargo_eur).filter((v) => v != null);
      const texto = gg.estado === "mezclado"
        ? I.gasto_mezclado
        : plantilla(I.gasto_sin_desglose, { min: millones(d3.min(enc)), max: millones(d3.max(enc)) });
      return { k: gg.estado, x0: x(a0), x1: x(a1) + x.bandwidth(), texto };
    });
    const eg = gGrupos.selectAll("g").data(gr, (d) => d.k).join((e) => {
      const gg = e.append("g");
      gg.append("rect").attr("fill", "var(--fondo)").attr("stroke", "var(--gris-dato)");
      gg.append("text").attr("class", "etiqueta-valor").attr("font-size", 12);
      return gg;
    });
    eg.each(function (d) {
      const gg = d3.select(this);
      const anchoTexto = d.k === "mezclado" ? Math.max(d.x1 - d.x0 - 8, 30) : d.x1 - d.x0 - 12;
      const t = gg.select("text").attr("x", 0).attr("y", 0).attr("data-texto", null).text(d.texto);
      if (d.k === "mezclado" && d.x1 - d.x0 < 70) {
        // Columna estrecha: texto vertical
        t.attr("transform", `translate(${(d.x0 + d.x1) / 2 - 4},8) rotate(90)`).text(d.texto);
        gg.select("rect").attr("width", 0).attr("height", 0);
        return;
      }
      t.attr("transform", null).call(envolver, anchoTexto);
      const bb = t.node().getBBox();
      const tx = d.x0 + (d.x1 - d.x0 - bb.width) / 2, ty = h * 0.35;
      t.attr("transform", `translate(${tx - bb.x},${ty - bb.y})`);
      gg.select("rect").attr("x", tx - 5).attr("y", ty - 4).attr("width", bb.width + 10).attr("height", bb.height + 8);
    });
  }

  function tablaDatos() {
    return tabla([I.anio, I.retirada_nidos, I.eur_por_nido, I.encargo_basalan, I.detalle],
      anios.map((a) => {
        const c = datos.coste_nido[a.anio];
        return [a.anio, a.retirada_eur != null ? `${fmt(a.retirada_eur)} €` : (a.estado === "mezclado" ? I.gasto_mezclado_corto : I.sin_desglose),
          c ? (c.min === c.max ? `${fmt(c.min)} €` : `${fmt(c.min)}-${fmt(c.max)} €`) : "–",
          a.encargo_eur != null ? `${fmt(a.encargo_eur)} €` : "–", a.detalle];
      }));
  }

  alRedimensionar(contenedor, () => dibujar(false));
  return {
    actualizar(_, animar = true) { dibujar(animar); },
    tablaDatos,
    describir() {
      const sd = anios.filter((a) => a.estado === "sin_desglose");
      const enc = sd.map((a) => a.encargo_eur);
      return plantilla(I.gasto_desc, { desde: sd[0].anio, hasta: sd[sd.length - 1].anio,
        min: millones(d3.min(enc)), max: millones(d3.max(enc)) });
    },
  };
}
