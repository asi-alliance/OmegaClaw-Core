#!/bin/sh
set -eu

envsubst '${ANTHROPIC_API_KEY} ${ASI_API_KEY} ${OPENAI_API_KEY}' \
    < /etc/nginx/nginx.conf.template \
    > /etc/nginx/nginx.conf

exec "$@"
