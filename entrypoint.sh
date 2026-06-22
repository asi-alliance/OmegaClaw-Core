#!/usr/bin/env bash
set -euo pipefail

cd /PeTTa

su www-data -s /bin/sh -c "sh /opt/nginx/nginx.sh"

GATEWAY_URL="http://localhost:8080"
EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-Local}"

for arg in "$@"; do
  if [[ "$arg" == embeddingprovider=* ]]; then
    export EMBEDDING_PROVIDER="${arg#*=}"
  fi
done

# Optional knowledge-base import
if [[ "${IMPORT_KB_ON_START}" == "1" ]]; then
  su nobody -s /bin/sh -c "${OMEGACLAW_DIR}/scripts/import_knowledge.sh"
fi

# Scrub environment: only allowlisted vars survive.
SAFE_VARS="HOME USER PATH HOSTNAME TERM LANG LC_ALL \
  GATEWAY_URL PYTHONDONTWRITEBYTECODE PYTHONUNBUFFERED \
  HF_HOME SENTENCE_TRANSFORMERS_HOME HF_HUB_OFFLINE TRANSFORMERS_OFFLINE \
  OMEGACLAW_DIR MEMORY_DIR LLM_SERVER_LOCAL_URL TEST_SERVER_IP \
  DC_BOT_TOKEN DC_API_BASE DC_GATEWAY_URL"

env_args=""
for var in $SAFE_VARS; do
  eval val=\${$var:-}
  if [ -n "$val" ]; then
    env_args="$env_args $var=$val"
  fi
done

exec env -i $env_args su nobody -s /bin/sh -c "sh run.sh run.metta $*"
