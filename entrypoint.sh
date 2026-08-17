#!/usr/bin/env bash
set -euo pipefail

# Adds slash at the end which is critical to Nginx configuration work properly
nginx_url() {
    text=$1
    [[ ${text} != */ ]] && text="${text}/"
    echo "${text}"
}

cd /PeTTa

EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-Local}"
OPENAIAPI_URL="http://localhost:8080/" # dummy value
MM_URL="http://localhost:8080/" # dummy value
OPENCLAW_URL="http://localhost:8080/" # dummy value
for arg in "$@"; do
  if [[ "$arg" == embeddingprovider=* ]]; then
    EMBEDDING_PROVIDER="${arg#*=}"
  fi
  # URL to redirect OpenAIAPI provider requests
  if [[ "$arg" == openaiapi_url=* ]]; then
    OPENAIAPI_URL=$(nginx_url "${arg#*=}")
  fi
  # URL to redirect Mattermost communication channel requests
  if [[ "$arg" == MM_URL=* ]]; then
    MM_URL=$(nginx_url "${arg#*=}")
  fi
  # URL to redirect OpenClaw Gateway requests
  if [[ "$arg" == openclaw_url=* ]]; then
    OPENCLAW_URL=$(nginx_url "${arg#*=}")
  fi
done
export EMBEDDING_PROVIDER OPENAIAPI_URL MM_URL OPENCLAW_URL

su www-data -s /bin/sh -c "sh /opt/nginx/nginx.sh"

# Optional knowledge-base import
if [[ "${IMPORT_KB_ON_START}" == "1" ]]; then
  su nobody -s /bin/sh -c "${OMEGACLAW_DIR}/scripts/import_knowledge.sh"
fi

# Verify that the agent user can write the mounted transfer directory.
if [[ "${MEMORY_TRANSFER_MOUNTED:-0}" == "1" ]]; then
  su nobody -s /bin/sh -c 'test -d /memory-transfer && test -w /memory-transfer' \
    || { echo "Memory transfer directory is not writable by the agent user." >&2; exit 1; }
fi

# Recover an interrupted import before starting the agent.
su nobody -s /bin/sh -c 'cd "$1" && exec python3 -m src.memory_transfer recover' \
  sh "$OMEGACLAW_DIR" \
  || { echo "Memory import recovery failed. Aborting startup." >&2; exit 1; }

# Validate the archive filename again at the container boundary.
if [[ -n "${MEMORY_IMPORT_FILE:-}" ]]; then
  if [[ ! "${MEMORY_IMPORT_FILE}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*\.tar\.gz$ ]]; then
    echo "MEMORY_IMPORT_FILE must be a plain filename, not a path: ${MEMORY_IMPORT_FILE}" >&2
    exit 1
  fi
  case "${MEMORY_IMPORT_MODE:-overwrite}" in
    overwrite|append) ;;
    *) echo "MEMORY_IMPORT_MODE must be overwrite or append" >&2; exit 1 ;;
  esac
  import_args=("/memory-transfer/${MEMORY_IMPORT_FILE}" --mode "${MEMORY_IMPORT_MODE:-overwrite}")
  [[ "${MEMORY_IMPORT_NO_HISTORY:-0}" == "1" ]] && import_args+=(--no-history)
  [[ "${MEMORY_IMPORT_NO_VECTOR:-0}" == "1" ]] && import_args+=(--no-vector)
  [[ "${MEMORY_IMPORT_ONLY_HISTORY:-0}" == "1" ]] && import_args+=(--only-history)
  echo "memory_transfer: importing ${MEMORY_IMPORT_FILE}"
  su nobody -s /bin/sh -c 'cd "$1" && shift && exec python3 -m src.memory_transfer import "$@"' \
    -- sh "$OMEGACLAW_DIR" "${import_args[@]}" \
    || { echo "Memory import failed. Aborting startup." >&2; exit 1; }
  echo "memory_transfer: import complete"
fi

# Scrub environment: only allowlisted vars survive.
SAFE_VARS="HOME USER PATH HOSTNAME TERM LANG LC_ALL \
  PYTHONDONTWRITEBYTECODE PYTHONUNBUFFERED \
  HF_HOME SENTENCE_TRANSFORMERS_HOME HF_HUB_OFFLINE TRANSFORMERS_OFFLINE \
  EMBEDDING_PROVIDER \
  OMEGACLAW_memoryExportEnabled \
  OMEGACLAW_DIR MEMORY_DIR TEST_SERVER_IP"

env_args=""
for var in $SAFE_VARS; do
  eval val=\${$var:-}
  if [ -n "$val" ]; then
    env_args="$env_args $var=$val"
  fi
done

exec env -i $env_args su nobody -s /bin/sh -c "sh run.sh run.metta GATEWAY_URL="http://localhost:8080" $*"
