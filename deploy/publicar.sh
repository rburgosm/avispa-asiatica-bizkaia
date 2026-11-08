#!/usr/bin/env bash
# Publica web/ en ionos-03 (sin sudo). Antes: comprobación de cifras, metadatos con el dominio y compresión.
# Uso: deploy/publicar.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-$HOME/Proyectos/observatorio-patinetes/.venv/bin/python}
$PY -I scripts/web_comprobar_cifras.py | tail -1
$PY -I scripts/web_preparar_compartir.py --url-base https://tresmilnidos.eus
$PY -I scripts/web_comprimir.py > /dev/null
rsync -az --delete --exclude 'README.md' web/ ionos-03:/var/www/tresmilnidos.eus/
echo "Publicado en https://tresmilnidos.eus"
