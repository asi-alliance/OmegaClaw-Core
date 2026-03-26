# Dockerfile to spin up MeTTaclaw 
#
# Includes:  PeTTa, MORK, PathMap

FROM docker.io/library/swipl:latest as os

# Install system build tools, Python, etc
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git \
      nano \
      build-essential \
      procps \
      curl \
      python3 \
      python3-pip \
      python3-dev \
      ca-certificates \
      pkg-config \
      cmake \
 && rm -rf /var/lib/apt/lists/*

FROM os as build

# 👇 RUST INSTALL
# -----------------------------------------
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain nightly-2026-03-19
ENV PATH="/root/.cargo/bin:${PATH}"

# 👇 PATHMAP INSTALL
RUN git clone --depth 1 https://github.com/Adam-Vandervorst/PathMap.git /PathMap
WORKDIR /PathMap
RUN RUSTFLAGS="-C target-cpu=native" cargo build --release

# 👇 MORK INSTALL
RUN git clone --depth 1 https://github.com/trueagi-io/MORK.git /MORK
WORKDIR /MORK/kernel
RUN RUSTFLAGS="-C target-cpu=native" cargo build --release

# 👇 PETTA INSTALL
#    Clone PeTTa repository directly into /PeTTa
RUN git clone --depth 1 https://github.com/patham9/PeTTa.git /PeTTa

# 👇 Install facebook research Faiss, contains several methods for similarity search.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libopenblas-dev \
      libblas-dev \
      liblapack-dev \
      gfortran \
      libgflags-dev \
 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://github.com/facebookresearch/faiss.git /faiss
WORKDIR /faiss
RUN cmake -B build -DFAISS_ENABLE_GPU=OFF -DFAISS_ENABLE_PYTHON=OFF -DBUILD_SHARED_LIBS=OFF
RUN cmake --build build --config Release --parallel
RUN cmake --install build

# Build foreign function interfaces for PeTTa to utilize MORK and FAISS
WORKDIR /PeTTa
RUN sh build.sh

FROM os

# 👇 Copy artifacts from build stage
COPY --from=build /PeTTa /PeTTa

# 👇 Install janus-swi system-wide
RUN pip3 install --no-cache-dir --break-system-packages janus-swi

# 👇 METTACLAW INSTALL
WORKDIR /PeTTa
RUN mkdir -p repos
RUN git clone --depth 1 https://github.com/patham9/mettaclaw repos/mettaclaw
RUN python3 -m pip install --no-cache-dir --break-system-packages openai

# 👇 Pytorch install
RUN pip install torch --no-cache-dir --break-system-package \
     --index-url https://download.pytorch.org/whl/cpu


WORKDIR /PeTTa

CMD ["/bin/bash"]
