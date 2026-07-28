#!/usr/bin/env bash
set -euo pipefail

CHROMA_DB_PATH="${CHROMA_DB_PATH:-/PeTTa/chroma_db}"
IMPORT_KB_FORCE="${IMPORT_KB_FORCE:-0}"

normalize_provider() {
  echo "$1" | tr '[:upper:]' '[:lower:]'
}

mkdir -p "${CHROMA_DB_PATH}"

PROVIDER="$(normalize_provider "${EMBEDDING_PROVIDER}")"

case "${PROVIDER}" in
  openai)
    if [[ -z "${OPENAI_API_KEY:-}" ]]; then
      echo "ERROR: OPENAI_API_KEY is required when EMBEDDING_PROVIDER=OpenAI." >&2
      exit 1
    fi

    SENTINEL="${CHROMA_DB_PATH}/.import-kb.openai.done"

    if [[ -f "${SENTINEL}" && "${IMPORT_KB_FORCE}" != "1" ]]; then
      echo "[import-kb] Already initialized with OpenAI embeddings; skipping."
    else
      echo "[import-kb] Running import-knowledge with OpenAI embeddings."
      echo "[import-kb] CHROMA_DB_PATH=${CHROMA_DB_PATH}"
      import-knowledge
      date -Iseconds > "${SENTINEL}"
      echo "[import-kb] Import complete."
    fi
    ;;

  local)
    SENTINEL="${CHROMA_DB_PATH}/.import-kb.local.done"

    if [[ -f "${SENTINEL}" && "${IMPORT_KB_FORCE}" != "1" ]]; then
      echo "[import-kb] Already initialized with local embeddings; skipping."
    else
      echo "[import-kb] Running import-knowledge with local embeddings."
      echo "[import-kb] CHROMA_DB_PATH=${CHROMA_DB_PATH}"
      import-knowledge --local
      date -Iseconds > "${SENTINEL}"
      echo "[import-kb] Import complete."
    fi
    ;;

  *)
    echo "ERROR: Unsupported embeddingprovider='${EMBEDDING_PROVIDER}'." >&2
    echo "Use embeddingprovider=OpenAI or embeddingprovider=Local." >&2
    exit 1
    ;;
esac
