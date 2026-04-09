# ==========================================
# Stage 1: Build Environment (Heavy tools stay here)
# ==========================================
FROM docker.io/library/swipl:latest as build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      build-essential \
      python3 \
      python3-pip \
      python3-dev \
      ca-certificates \
      pkg-config \
      cmake \
      libopenblas-dev \
      libblas-dev \
      liblapack-dev \
      gfortran \
      libgflags-dev \
 && rm -rf /var/lib/apt/lists/*

# Install FAISS (Static Library)
RUN git clone --depth 1 https://github.com/facebookresearch/faiss.git /faiss
WORKDIR /faiss
# --parallel N should match available CPU cores (too high causes OOM on low-memory VPS)
RUN cmake -B build -DFAISS_ENABLE_GPU=OFF -DFAISS_ENABLE_PYTHON=OFF -DBUILD_SHARED_LIBS=OFF \
 && cmake --build build --config Release --parallel 2 \
 && cmake --install build

# Install PeTTa (MeTTa-to-Prolog transpiler)
RUN git clone --depth 1 https://github.com/trueagi-io/PeTTa.git /PeTTa
WORKDIR /PeTTa
RUN sh build.sh

# ==========================================
# Stage 2: Production Environment (Lean & Secure)
# ==========================================
FROM docker.io/library/swipl:latest as final

# Install runtime necessities (gosu for non-root, iptables for firewall)
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 \
      python3-pip \
      python3-dev \
      build-essential \
      iptables \
      gosu \
 && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd -r mettagroup && useradd -r -g mettagroup mettauser

# Install Python dependencies required by MeTTaClaw
RUN pip3 install --no-cache-dir --break-system-packages \
      janus-swi \
      openai \
      # python-telegram-bot \
      aiogram \
      requests \
      websocket-client \
      PyYAML \
      chromadb

# Set up the working directory
WORKDIR /app

# Copy compiled artifacts from the build stage
COPY --from=build /PeTTa /app/PeTTa
COPY --from=build /usr/local/lib/libfaiss.a /usr/local/lib/

# Setup the project structure
# We copy the local mettaclaw code into a stable location
COPY . /app/mettaclaw

# Link MeTTaClaw into PeTTa/repos so it can be imported as a library
RUN mkdir -p /app/PeTTa/repos \
 && ln -s /app/mettaclaw /app/PeTTa/repos/mettaclaw \
 && cp /app/mettaclaw/run.metta /app/PeTTa/run.metta \
 && cp /app/mettaclaw/firewall.sh /firewall.sh \
 && chmod +x /firewall.sh

# Lock down filesystem permissions
# Root ownership for safety, non-root user cannot modify the codebase
RUN chown -R root:root /app \
 && chmod -R 755 /app

# Create a specific isolated data directory for MeTTaClaw's writes (logs, DBs)
RUN mkdir -p /app/data \
 && chown -R mettauser:mettagroup /app/data \
 && chown -R mettauser:mettagroup /app/mettaclaw/memory \
 && touch /app/mettaclaw/telegram_bot.log \
 && chown mettauser:mettagroup /app/mettaclaw/telegram_bot.log

# Environment variables for PeTTa/Janus
ENV PYTHONPATH=/app/mettaclaw:/app/mettaclaw/src:/app/mettaclaw/channels

# Change working directory to PeTTa root to run run.sh
WORKDIR /app/PeTTa

ENTRYPOINT ["/firewall.sh"]

# Use gosu to step down to non-root user
CMD ["gosu", "mettauser", "sh", "run.sh", "run.metta", "default"]
