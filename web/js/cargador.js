// Carga las librerías desde vendor/ (scripts/web_descargar_librerias.py) y, si faltan, desde
// jsDelivr con la misma versión exacta. Al principio solo D3 y Scrollama; MapLibre, pmtiles y
// @protomaps/basemaps (el mapa de detalle) se cargan cuando hacen falta: window.__cargarMapLibre().
// Después arranca la aplicación (módulo ES). Si algo falla, un mensaje claro y «Reintentar».
(function () {
  "use strict";
  var CDN = "https://cdn.jsdelivr.net/npm/";
  var BASICAS = [
    { local: "vendor/d3.min.js", cdn: "d3@7.9.0/dist/d3.min.js", global: "d3" },
    { local: "vendor/scrollama.min.js", cdn: "scrollama@3.2.0/build/scrollama.min.js", global: "scrollama" }
  ];
  var MAPLIBRE = [
    { local: "vendor/maplibre-gl.js", cdn: "maplibre-gl@4.7.1/dist/maplibre-gl.js", global: "maplibregl",
      css: "vendor/maplibre-gl.css", cssCdn: "maplibre-gl@4.7.1/dist/maplibre-gl.css" },
    { local: "vendor/pmtiles.js", cdn: "pmtiles@4.4.1/dist/pmtiles.js", global: "pmtiles" },
    { local: "vendor/basemaps.js", cdn: "@protomaps/basemaps@5.7.2/dist/basemaps.js", global: "basemaps" }
  ];

  function script(src) {
    return new Promise(function (ok, mal) {
      var s = document.createElement("script");
      s.src = src;
      s.onload = ok;
      s.onerror = function () { s.remove(); mal(new Error(src)); };
      document.head.appendChild(s);
    });
  }
  function hoja(href) {
    var l = document.createElement("link");
    l.rel = "stylesheet";
    l.href = href;
    document.head.appendChild(l);
  }

  function cargar(lib) {
    if (window[lib.global]) return Promise.resolve();
    if (lib.css) hoja(lib.css);
    return script(lib.local).catch(function () {
      if (lib.cssCdn) hoja(CDN + lib.cssCdn);
      return script(CDN + lib.cdn);
    }).then(function () {
      if (!window[lib.global]) throw new Error("No se ha cargado " + lib.global);
    });
  }

  var promesaMapLibre = null;
  window.__cargarMapLibre = function () {
    // en orden: pmtiles y basemaps no dependen de MapLibre, pero así se cargan de una vez
    if (!promesaMapLibre) promesaMapLibre = Promise.all(MAPLIBRE.map(cargar)).catch(function (e) { promesaMapLibre = null; throw e; });
    return promesaMapLibre;
  };

  window.__avisoCarga = function (texto, reintentar) {
    var p = document.getElementById("aviso-carga") || document.createElement("p");
    p.id = "aviso-carga";
    p.className = "aviso aviso-carga";
    p.setAttribute("role", "alert");
    p.textContent = texto + " ";
    var b = document.createElement("button");
    b.type = "button";
    b.className = "boton";
    b.textContent = "Reintentar";
    b.onclick = reintentar || function () { location.reload(); };
    p.appendChild(b);
    document.body.insertBefore(p, document.querySelector(".portada").nextSibling);
  };

  Promise.all(BASICAS.map(cargar))
    .then(function () { return import("./app.js"); })
    .then(function (m) { return m.iniciar(); })
    .catch(function (e) {
      console.error(e);
      window.__avisoCarga("No se han podido cargar los datos o las librerías de la página. Comprueba la conexión.");
    });
})();
