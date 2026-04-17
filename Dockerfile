# syntax=docker/dockerfile:1.7

# For maximum integrity, set this to an immutable digest in CI/CD.
ARG SWIPL_IMAGE=docker.io/library/swipl:9.2.4

FROM ${SWIPL_IMAGE} AS builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/opt/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/opt/sentence_transformers

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      build-essential \
      cmake \
      pkg-config \
      python3 \
      python3-dev \
      python3-pip \
      libopenblas-dev \
      libblas-dev \
      liblapack-dev \
      gfortran \
      libgflags-dev \
 && rm -rf /var/lib/apt/lists/*

# Build dependencies from source. Pin refs at build time for reproducibility.
ARG PETTA_REPO=https://github.com/patham9/PeTTa.git
ARG PETTA_REF=main
ARG FAISS_REPO=https://github.com/facebookresearch/faiss.git
ARG FAISS_REF=v1.8.0
ARG CHROMADB_REPO=https://github.com/patham9/petta_lib_chromadb.git
ARG CHROMADB_REF=master

# Embedding model to pre-download at build time.
ARG EMBEDDING_MODEL=intfloat/e5-large-v2

RUN git clone --depth 1 --branch "${PETTA_REF}" "${PETTA_REPO}" /PeTTa
RUN git clone --depth 1 --branch "${FAISS_REF}" "${FAISS_REPO}" /faiss

WORKDIR /faiss
RUN cmake -B build -DFAISS_ENABLE_GPU=OFF -DFAISS_ENABLE_PYTHON=OFF -DBUILD_SHARED_LIBS=OFF \
 && cmake --build build --config Release --parallel \
 && cmake --install build

WORKDIR /PeTTa
RUN sh build.sh
RUN mkdir -p /PeTTa/repos \
 && git clone --depth 1 --branch "${CHROMADB_REF}" "${CHROMADB_REPO}" /PeTTa/repos/petta_lib_chromadb

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    --index-url https://download.pytorch.org/whl/cpu \
    torch \
 && python3 -m pip install --no-cache-dir --break-system-packages \
    chromadb \
    janus-swi \
    openai \
    uagents \
    sentence-transformers \
    aiogram \
    requests \
    websocket-client \
    PyYAML

# Pre-download the sentence-transformers model so runtime does not need network access.
RUN mkdir -p "${HF_HOME}" "${SENTENCE_TRANSFORMERS_HOME}" \
 && python3 - <<PY
from sentence_transformers import SentenceTransformer
model_name = "${EMBEDDING_MODEL}"
print(f"Downloading embedding model: {model_name}")
SentenceTransformer(model_name)
print("Model download complete.")
PY

# ===========================================================================
# Runtime stage
# ===========================================================================
FROM ${SWIPL_IMAGE} AS runtime

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/opt/sentence_transformers

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      python3 \
      libopenblas-dev \
      libblas-dev \
      liblapack-dev \
      gfortran \
      libgflags-dev \
      git \
      gosu \
      iptables \
 && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd -r omegagroup && useradd -r -g omegagroup omegauser

WORKDIR /PeTTa

COPY --from=builder /usr/local /usr/local
COPY --from=builder /PeTTa /PeTTa
COPY --from=builder /opt/huggingface /opt/huggingface
COPY --from=builder /opt/sentence_transformers /opt/sentence_transformers

# Bring in only local OmegaClaw source (filtered by .dockerignore).
COPY . /PeTTa/repos/OmegaClaw-Core

RUN cp /PeTTa/repos/OmegaClaw-Core/run.metta /PeTTa/run.metta \
 && cp /PeTTa/repos/OmegaClaw-Core/firewall.sh /firewall.sh \
 && chmod +x /firewall.sh \
 && mkdir -p ./chroma_db \
 && mkdir -p /app/data \
 && chown -R omegauser:omegagroup ./chroma_db \
 && chown -R omegauser:omegagroup /PeTTa/repos/OmegaClaw-Core/memory \
 && chown -R omegauser:omegagroup /app/data \
 && chown -R omegauser:omegagroup /opt/huggingface /opt/sentence_transformers

# Declare persistent volumes
VOLUME ["/PeTTa/repos/OmegaClaw-Core/memory", "/PeTTa/chroma_db", "/app/data"]

# Python module search path
ENV PYTHONPATH=/PeTTa/repos/OmegaClaw-Core:/PeTTa/repos/OmegaClaw-Core/src:/PeTTa/repos/OmegaClaw-Core/channels

ENTRYPOINT ["/firewall.sh"]

# Use gosu to step down to non-root user
CMD ["gosu", "omegauser", "sh", "run.sh", "run.metta", "default"]
