#!/bin/sh
set -eu

SUBST_VARS=$(grep -o '\${[A-Z_0-9]*}' /opt/nginx/nginx.conf.template | sort -u | tr '\n' ' ')
NGINX_CONFIG=/opt/nginx/nginx.conf
touch "${NGINX_CONFIG}"
chmod 0600 "${NGINX_CONFIG}"
envsubst "$SUBST_VARS" \
    < /opt/nginx/nginx.conf.template \
    > "${NGINX_CONFIG}"

nginx -c "${NGINX_CONFIG}"

