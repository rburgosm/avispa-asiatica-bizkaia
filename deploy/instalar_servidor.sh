#!/usr/bin/env bash
# Instalación única en ionos-03 (necesita sudo). Uso, desde el ordenador del autor:
#   scp -r deploy ionos-03:/tmp/tresmilnidos-deploy && ssh -t ionos-03 'sudo bash /tmp/tresmilnidos-deploy/instalar_servidor.sh'
# Pasos: webroot → vhost solo HTTP (para el reto de ACME) → certificado (certbot certonly --nginx, sin instalador)
#        → vhost completo con HTTPS → contraseña de vista previa → nginx -t y recarga. Si nginx -t falla, restaura.
set -euo pipefail
D=/tmp/tresmilnidos-deploy
DOM=tresmilnidos.eus
NOMBRES=(tresmilnidos.eus www.tresmilnidos.eus avispabizkaia.eus www.avispabizkaia.eus avispa-asiatica-bizkaia.eus www.avispa-asiatica-bizkaia.eus)
VH=/etc/nginx/sites-available/$DOM.conf

install -d -o roberto -g www-data -m 2755 /var/www/$DOM
[ -f /etc/nginx/snippets/cloudflare-real-ip.conf ] || install -m 644 $D/nginx/cloudflare-real-ip.conf /etc/nginx/snippets/

probar() { if ! nginx -t; then echo "nginx -t falla: restauro"; rm -f /etc/nginx/sites-enabled/$DOM.conf; [ -f $VH.bak ] && mv $VH.bak $VH; nginx -t && systemctl reload nginx; exit 1; fi; systemctl reload nginx; }

# 1) Solo HTTP, para que certbot pueda validar a través de Cloudflare
[ -f $VH ] && cp $VH $VH.bak
awk '/^# HTTPS/{exit} {print}' $D/nginx/$DOM.conf > $VH
ln -sf $VH /etc/nginx/sites-enabled/$DOM.conf
probar

# 2) Certificado para los seis nombres
ARGS=(); for n in "${NOMBRES[@]}"; do ARGS+=(-d "$n"); done
certbot certonly --nginx --non-interactive --agree-tos --keep-until-expiring --deploy-hook "systemctl reload nginx" --cert-name $DOM "${ARGS[@]}"

# 3) Contraseña de vista previa (usuario «vista»); la contraseña la genera el autor y la pasa en la variable CLAVE
if [ -n "${CLAVE:-}" ]; then printf 'vista:%s\n' "$(openssl passwd -apr1 "$CLAVE")" > /etc/nginx/tresmilnidos.htpasswd; chmod 640 /etc/nginx/tresmilnidos.htpasswd; chown root:www-data /etc/nginx/tresmilnidos.htpasswd; fi
[ -f /etc/nginx/tresmilnidos.htpasswd ] || { echo "Falta CLAVE para la vista previa"; exit 1; }

# 4) Vhost completo
install -m 644 $D/nginx/$DOM.conf $VH
probar
echo "Listo: https://$DOM"
