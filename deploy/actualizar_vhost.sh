#!/usr/bin/env bash
# Actualiza solo el vhost (necesita sudo): copia, nginx -t y recarga; si falla, restaura.
set -euo pipefail
VH=/etc/nginx/sites-available/tresmilnidos.eus.conf
cp $VH $VH.bak
install -m 644 /tmp/tresmilnidos-deploy/nginx/tresmilnidos.eus.conf $VH
if nginx -t; then systemctl reload nginx; echo "vhost actualizado"; else mv $VH.bak $VH; nginx -t && systemctl reload nginx; echo "nginx -t falla: restaurado"; exit 1; fi
