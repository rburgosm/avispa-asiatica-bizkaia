#!/usr/bin/env bash
# Publica web/ en ionos-03 (sin sudo). Antes: comprobación de cifras, metadatos con el dominio y compresión.
# Uso: deploy/publicar.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-$HOME/Proyectos/observatorio-patinetes/.venv/bin/python}
$PY -I scripts/web_comprobar_cifras.py | tail -1
$PY -I scripts/web_preparar_compartir.py --url-base https://tresmilnidos.eus
# Versión del contenido en la URL de es.json, para que los navegadores no usen una copia vieja
V=$(sha256sum web/content/es.json | cut -c1-8)
sed -i -E "s|content/[$][{]lang[}][.]json([?]v=[0-9a-f]+)?|content/\${lang}.json?v=$V|" web/js/app.js web/js/metodologia.js
$PY -I scripts/web_comprimir.py > /dev/null
rsync -az --delete --exclude 'README.md' web/ ionos-03:/var/www/tresmilnidos.eus/
echo "Publicado en https://tresmilnidos.eus"
