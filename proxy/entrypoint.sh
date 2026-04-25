#!/bin/sh
set -eu

SUBST_VARS=$(grep -o '\${[A-Z_0-9]*}' /etc/nginx/nginx.conf.template | sort -u | tr '\n' ' ')
envsubst "$SUBST_VARS" \
    < /etc/nginx/nginx.conf.template \
    > /etc/nginx/nginx.conf

exec "$@"
