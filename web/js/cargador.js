// Carga las librerías desde vendor/ (scripts/web_descargar_librerias.py) y, si faltan,
// desde jsDelivr con la misma versión exacta. Después arranca la aplicación (módulo ES).
(function () {
  "use strict";
  var CDN = "https://cdn.jsdelivr.net/npm/";
  var LIBRERIAS = [
    { local: "vendor/d3.min.js", cdn: "d3@7.9.0/dist/d3.min.js", global: "d3" },
    { local: "vendor/scrollama.min.js", cdn: "scrollama@3.2.0/build/scrollama.min.js", global: "scrollama" },
    { local: "vendor/maplibre-gl.js", cdn: "maplibre-gl@4.7.1/dist/maplibre-gl.js", global: "maplibregl",
      css: "maplibre-gl@4.7.1/dist/maplibre-gl.css" }
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

  function cargar(lib) {
    return script(lib.local).catch(function () {
      if (lib.css) {
        var l = document.createElement("link");
        l.rel = "stylesheet";
        l.href = CDN + lib.css;
        document.head.appendChild(l);
      }
      return script(CDN + lib.cdn);
    }).then(function () {
      if (!window[lib.global]) throw new Error("No se ha cargado " + lib.global);
    });
  }

  Promise.all(LIBRERIAS.map(cargar))
    .then(function () { return import("./app.js"); })
    .then(function (m) { return m.iniciar(); })
    .catch(function (e) {
      console.error(e);
      var p = document.createElement("p");
      p.className = "aviso";
      p.textContent = "No se ha podido cargar la página: " + e.message;
      document.body.insertBefore(p, document.getElementById("historia"));
    });
})();
