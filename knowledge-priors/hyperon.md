# Hyperon Reference

## Note

This document is a merge of **Hyperon for AGI → ASI: Technical Whitepaper 2025 by Ben Goertzel and **Hyperon Master Index ’26 from Khellar Crawford\*\*\*\*.

Several frontier components named below are at different levels of maturity. Nothing in this document should be read as flattening the distinction between current capabilities, active prototypes, and research directions.

---

## Table of Contents

1. [Hyperon Overview](#1-hyperon-overview)
2. [MeTTa Programming Language](#2-metta-programming-language)
3. [ASI:Chain Runtime Environment](#3-asi-chain-runtime-environment)
4. [Knowledge Representations](#4-knowledge-representations)
5. [Hyperon AI Algorithms](#5-hyperon-ai-algorithms)
6. [Cognitive Architecture & Research](#6-cognitive-architecture--research)
7. [Self-Modification, Safety, and Governance](#7-self-modification-safety-and-governance)
8. [Application Domains and Beneficial Grounding](#8-application-domains-and-beneficial-grounding)
9. [Implementation Status and Near-Term Roadmap](#9-implementation-status-and-near-term-roadmap)
10. [OmegaClaw Agent Reference Profile](#10-omegaclaw-agent-reference-profile)
11. [Source Basis](#11-source-basis)

---

## 1. Hyperon Overview

Welcome to the Hyperon Index, a curated technical document designed to provide an intuitive and demystified understanding of our AGI frameworks and their constituent parts. Hyperon is SingularityNET’s Artificial General Intelligence (AGI) technology stack building on decades of research from the legacy OpenCog project. Hyperon provides a unified platform for integrating diverse machine cognitive processes — from symbolic reasoning and probabilistic inference to neural learning and evolutionary search.

Much of the significance of the present Hyperon effort lies in the deliberate rebuilding of infrastructure so that these modes of cognition can interact at far greater scale, concurrency, and semantic fidelity than prior generations allowed.

This document serves as the primary reference for our internal R&D initiatives, offering high-level, current descriptions of each component alongside links to demos, peer-reviewed publications, repositories, and technical documentation for those seeking deeper immersion. The result is not merely a taxonomy of components, but the emergence of a common cognitive medium in which learning, reasoning, attention, motivation, and program synthesis can enter into recurrent, auditable loops.

Hyperon is also a unified neurosymbolic AGI platform designed to progress from current AI capabilities through human-level AGI to beneficial ASI. Unlike approaches that rely solely on scaling neural networks or stitching together disparate AI components, Hyperon provides an integrated foundation where multiple cognitive processes — neural, symbolic, evolutionary — operate over a shared knowledge metagraph.

The core innovation lies in the Atomspace, a typed, content-addressed metagraph that serves as a universal substrate for all cognitive activity. Implemented on MORK, a high-performance prefix-tree database, the Atomspace co-locates symbols, tensors, truth values, motives, and operations in one computational substrate. This design enables unprecedented synergy between reasoning, learning, and self-modification processes that would be impossible in traditional architectures where these components communicate only through narrow APIs.

Since the 2023 whitepaper, several critical advances have been identified as moving Hyperon from promising architecture to practical implementation. The MORK infrastructure now supports over 500 million atoms in RAM. Quantale-based weakness theory is introduced as a unified mathematical framework for simplicity across cognitive algorithms. TransWeave adds compositional knowledge transfer with formal guarantees about what will transfer successfully. MetaMo and SubRep provide auditable goal management and certified subgoal learning. QuantiMORK proposes native neural computation within the metagraph itself, reducing the boundary between symbolic and neural processing. Implementation maturity remains uneven across these methods, but the architectural direction is coherent.

The path from Hyperon to AGI and ultimately ASI is framed through three pillars: reflective self-modification with mathematical goal stability guarantees, decentralized deployment on blockchain infrastructure preventing monopolistic control, and grounding in beneficial applications including medicine, education, robotics, and mathematics. These are not presented as safety layers bolted onto the system after the fact; they are part of how cognition is intended to operate within Hyperon.

### 1.1 TL;DR Structure of the Stack

The index is organized into the following key sections:

- **MeTTa Programming Language**: MeTTa is the native “language of thought” — a fundamentally AGI-specific programming language. This section covers its primary implementations, specifically PeTTa, a high-performance interpreter/compiler-runtime path, and Hyperon Experimental, the original reference implementation that established the framework’s core principles.
- **ASI:Chain Runtime Environment**: The ASI:Chain functions as the “blockchain of thought,” providing a decentralized substrate for secure computation and cognitive state updates. Critically, this environment is not limited to public networks; it can be deployed on a single machine or a private network of machines for localized usage, ensuring high-integrity, auditable records of cognitive transformations and transactions.
- **Knowledge Representations**: This section details Atomspace technologies, the symbolic foundation of the Hyperon neural-symbolic approach. In this context, “Atoms” represent symbolic data and formal categories that allow the system to store not just raw data, but the relationships and logic behind it. Systems such as DAS and MORK enable a dynamic knowledge metagraph where code and data are interchangeable.
- **Hyperon AI Algorithms**: Here we describe the core cognitive algorithms authored in MeTTa and executed on the Hyperon substrate. These algorithms represent the functional “modules” of intelligence: PLN for reasoning under uncertainty, ECAN for managing limited computational resources, MOSES for creative problem-solving and evolutionary methods, and related systems that deepen motivation, transfer, compression, and causal learning.
- **Cognitive Architecture & Research**: This section provides an overview of the PRIMUS cognitive architecture, a carefully considered configuration of the layers and components outlined above that is viewed as likely to give rise to artificial general intelligence.

### 1.2 OmegaClaw Agent in Context

For present purposes, the **OmegaClaw Agent** is best understood as an agent evolving toward AGI by making use of components and infrastructure from the Hyperon technology stack:

- MeTTa serves as a useful cognitive calculus and orchestration language.
- Atomspace, implemented through DAS and/or MORK, provides shared cognitive memory and transformation substrate.
- ECAN, PLN, MOSES/GEO-EVO, MetaMo, SubRep, semantic parsing, and related subsystems provide cognitive functionality.
- ASI:Chain / F1R3FLY / MeTTaCycle will provide an auditable decentralized runtime where local, private-network, or public-network deployment semantics are needed.

This reference therefore treats OmegaClaw not as a separate theory from Hyperon, but as an agent-driven dynamic orchestration of the Hyperon stack.

---

## 2. MeTTa Programming Language

### 2.1 Canonical Description

MeTTa (Meta-Type Talk) is a programming language designed to be the native “language of thought” for AGI. It was designed to serve as the central cognitive calculus for the Hyperon AGI framework — a universal glue that allows diverse AI components (e.g. neural networks, probabilistic reasoners, evolutionary models, etc.) to communicate, collaborate, and synergistically integrate their capabilities.

Rooted in principles of both neural networks and symbolic reasoning, MeTTa unifies elements of functional programming (drawing inspiration from languages like Haskell, Idris, and Prolog), logic programming, and dependent typing.

Unlike general-purpose languages, MeTTa was designed to operate natively over cognitive structures — atoms (symbolic data representations), types (formal categories), and transformations — which are stored in a dynamic knowledge metagraph known as an Atomspace. Within this framework, code and data are interchangeable.

This design enables:

- **Interoperability**: MeTTa acts as a shared medium and translator for diverse AI systems — a lingua franca for them to not just “plug in” but seamlessly interoperate. It is a substrate for heterogeneous AI subsystems and paradigms to flow together and combine, allowing their unique capabilities to be expressed, executed, and coherently orchestrated across distributed, interoperable networks.
- **Concurrency**: It leverages a higher-order rho-calculus foundation to treat programs as asynchronous processes that intelligently execute in parallel without blocking. Its systems utilize parallelized backtracking to scale these computations across multi-core and distributed architectures with near-linear performance.
- **Security and Auditability**: It employs a by-construction security model to ensure access rights are unforgeable and mathematically verifiable. Within decentralized networks, all state updates are fully transactional and atomic, maintaining a high-integrity, auditable record of cognitive transformations.
- **Reflective Self-Modification**: Programs can inspect, analyze, and rewrite themselves at runtime. This reflection is critical for an AGI to learn, adapt, and evolve its own cognitive processes.
- **Flexible Reasoning**: The language’s structure allows for dynamic type introspection and the programmatic manipulation of its own knowledge and logic.
- **Nondeterminism / Determinism**: MeTTa operates inherently as a non-deterministic inference engine, enabling massive-scale parallel search and lazy incremental answer discovery across the metagraph. Efficiency is achieved through smart compilers that resolve symbolic data versus executable functions, while low-level kernels allow explicit deterministic control-flow in compute-intensive tasks.

### 2.2 Additional Language-Stack Framing

The whitepaper deepens this picture by describing a language stack in which each layer serves a specific role while maintaining semantic consistency:

- **MeTTa** provides the high-level interface where developers write cognitive code as graph transformations. Its homoiconic pattern-rewrite semantics mean programs are themselves part of the Atomspace, enabling deep self-reference critical for AGI.
- **MeTTa-IL** serves as the compiler’s intermediate representation, based on Graph-Structured Lambda Theory (GSLT). It is intended to make program semantics explicit and typed when crossing system boundaries.
- **MM2** operates at the lowest level, implementing performance-critical operations directly on MORK structures. Factor-graph message passing, weighted sweeps, and proof verification are envisioned to run at near-database speed while maintaining semantic guarantees.
- **PyMeTTa** (under development) provides a Python-compatible dialect that transpiles cleanly to MeTTa-IL, enabling notebook-based development and integration with the Python ecosystem while preserving the semantic guarantees of the core system. The associated `metta-magic` library is described as a batteries-included path to PLN inference, evolutionary algorithms, pattern mining, and more.

### 2.3 Various Implementations of MeTTa

MeTTa is not a monolithic entity but a living specification with several specialized implementations, or flavors. Each is optimized for different performance characteristics, environments, and roles within the Hyperon framework, all stemming from the original reference implementation.

#### 2.3.1 Hyperon Experimental

**GitHub / demos / code**

- <https://github.com/trueagi-io/hyperon-experimental/>
- <https://metta-lang.dev/docs/playground/playground.html>
- <https://metta-lang.dev/docs/learn/learn.html>

**Papers**

- Potapov A., Bogdanov V. _Univalent foundations of AGI are (not) all you need_. Springer: LNCS, V.13154 (proc. AGI’21). 2022. P. 184–195.
- Warrell J., Potapov A., Vandervorst A., Goertzel B. _A Meta-Probabilistic-Programming Language for Bisimulation of Probabilistic and Non-Well-Founded Type Systems_. Springer: LNCS, V.13539 (proc. AGI’22). 2023. P. 434–451.

**Description**

Hyperon-Experimental is the original reference implementation of MeTTa, serving as the master blueprint for the language and the primary engine for R&D. Built in Rust, it is designed for maximum extensibility.

A notable characteristic is its deep Python integration, which enables a hybrid development model where MeTTa and Python code can interoperate seamlessly within the same application. This provides the leverage of the entire Python ecosystem, including its vast AI, data science, and machine learning libraries, directly within MeTTa’s symbolic reasoning framework.

Furthermore, Hyperon-Experimental is engineered as an extensible library with a C API, allowing it to be integrated with programs written in other languages like C or C++. While this architecture is robust and forward-looking, it intentionally prioritizes flexibility and semantic correctness over raw execution speed. As a result, it has merit for conducting small experiments but does not, at present, provide production-grade performance.

**Roadmap (2026)**

- Add the capability to integrate various expression evaluation mechanisms into hyperon-experimental, for example:
  - traditional interpretation of expressions from the AtomSpace, as it currently happens;
  - storing expressions inside the Prolog interpreter and invoking Prolog for expression evaluation;
  - invoking compiled expressions.
- Integration of Prolog VM-based modules for interpreting Meta expressions within the Prolog VM; modernization of the module mechanism so that it allows such seamless integration.
- Release Python packages for Windows.
- Address the issue of inefficient representation of variable bindings, which should significantly improve performance, although the exact path remains under refinement.

#### 2.3.2 PeTTa

**GitHub / docs / docker**

- <https://github.com/patham9/PeTTa/>
- <https://github.com/patham9/PeTTa/wiki/>
- <https://github.com/trueagi-io/metta-wam>

**Description**

PeTTa is a high-performance compiler and runtime for the MeTTa language, designed to execute complex symbolic AI code at speeds required for real-time applications like robotics and large-scale reasoning. It achieves this by translating MeTTa source code directly into highly optimized Prolog.

Its core innovation is a Smart Dispatch compiler, which intelligently solves the key challenge of deciding whether a piece of MeTTa code is a function to be executed or a piece of data to be structured. By eliminating slow check-at-runtime methods used by typical interpreters, PeTTa generates code that achieves execution speeds comparable to handwritten, idiomatic Prolog.

Crucially, it fully adheres to the Hyperon-Experimental semantics, ensuring a correct and compatible implementation while providing a major performance boost. It is also fully interoperable with high-performance backends, capable of manipulating MORK spaces and executing MM2 expressions directly from MeTTa code.

This makes PeTTa an essential component for running computationally intensive symbolic architectures — like MeTTa-NARS and PLN — in production, bridging the gap from research-grade interpretation to real-world high-speed deployment.

#### 2.3.3 MeTTaTron

**GitHub / documentation**

- <https://github.com/F1R3FLY-io/MeTTa-Compiler>

**Description**

MeTTaTron is the F1R3FLY-native MeTTa compiler, providing a path from MeTTa into MeTTa-IL and serving as the MeTTa implementation most closely aligned with the F1R3FLY / ASI:Chain execution stack. Within the broader Hyperon ecosystem, it represents an important route by which MeTTa programs can move toward lower-level runtime environments designed for concurrency, distributed execution, and blockchain-native settlement.

Where Hyperon Experimental functions as the reference implementation and PeTTa emphasizes high-performance symbolic execution, MeTTaTron is best understood as a compiler-oriented bridge between MeTTa source programs and the F1R3FLY-side execution model. This makes it especially relevant wherever MeTTa code must interoperate with MeTTa-IL, Rholang-adjacent infrastructure, or ASI:Chain-facing runtime components.

### 2.4 Relevance to OmegaClaw Agent

For a OmegaClaw agent, MeTTa is not merely a convenience language. It is the medium in which symbolic control, orchestration, reflective rewriting, and cross-component coordination become uniform. In practice, OmegaClaw should be read as inheriting MeTTa’s role as shared cognitive calculus, with high-level agent logic remaining MeTTa-facing even when lower-level performance paths are delegated to PeTTa/MeTTaTron, MM2, MORK, or ASI:Chain-aligned execution routes.

---

## 3. ASI:Chain Runtime Environment

**GitHub / docs**

- <https://github.com/asi-alliance/asi-chain>
- <https://github.com/F1R3FLY-io>
- <https://docs.asichain.io/>

### 3.1 Description

ASI:Chain is the dedicated blockchain runtime environment for decentralized AGI, serving as the Layer 1 execution fabric where the Hyperon cognitive stack operates. While traditional blockchains like Ethereum function as sequential global settlement engines, ASI:Chain is an AI-native worldwide supercomputer architected to handle the massive, concurrent, and graph-based workloads of AGI.

Under the hood, this performance is driven by two foundational engines: **F1R3FLY**, which renders flawless process calculi to ensure exponential scalability, and **MeTTaCycle**, which compiles and orchestrates AGI workloads. This dual-engine architecture utilizes BlockDAG data structures to allow thousands of non-conflicting AI processes to execute in parallel, breaking the single-file bottleneck of legacy networks.

Functionally, ASI:Chain serves as a distributed cognitive substrate — a living medium that connects disparate servers into a single, cohesive network of mind. Historically, it is described as the first blockchain capable of native inference settlement, meaning it verifies cognitive state transitions (reasoning steps) rather than merely validating token transfers. Whether running on a private cluster or the public open network, it provides the secure, immutable fabric where agents, tools, and microservices interact, ensuring that the calculi of consciousness can be composed and executed with cryptographic fidelity.

The whitepaper complements this by framing decentralized deployment as one of the pillars on the path from Hyperon to beneficial AGI and ASI: not only for scaling and auditability, but also for avoiding monopolistic control.

### 3.2 Architecture

#### 3.2.1 F1R3FLY

F1R3FLY is the underlying computational blockchain engine powering ASI:Chain, serving as a concurrent, sharded execution layer designed to overcome the sequential bottlenecks of legacy networks. Grounded in the rigorous mathematics of Rholang (Reflective Higher-Order Process Calculus), the engine models every interaction — whether a financial transaction or an AGI inference — as concurrent processes communicating over channels. By ensuring that the outer world of network events and the inner world of smart contracts speak the exact same language, F1R3FLY eliminates friction of translation, enabling a system that is natively reactive and highly scalable.

Its data architecture is equally advanced. F1R3FLY utilizes reified RSpaces and MORK PathMaps (specialized Merkle tries) to treat storage as a programmable, living system rather than a static bucket. This allows for high-efficiency structure sharing and polymorphic data handling — functioning simultaneously as a blockchain, file system, or vector database. For durable persistence, knowledge states are anchored in integrated LMDB, maintaining the low-latency retrieval speeds required for real-time cognitive processing.

F1R3FLY nodes are designed to speak multiple protocols natively, including RGB/Really Good Bitcoin, Lightning, and eventually Ethereum, acting as a high-performance accelerator for the broader Web3 landscape.

#### 3.2.2 MeTTa-IL

A key mechanism in this execution stack is **MeTTa-IL (MeTTa Intermediate Layer)**, the high-performance bridge between developer intent and machine reality. MeTTa-IL performs deep semantic analysis on MeTTa programs, reifying them into a mathematically precise operational form before determining their execution path.

Logic intended for local, low-latency reasoning is lowered directly into MORK for in-memory execution, while logic requiring global synchronization or consensus is lowered into F1R3FLY’s distributed execution path. Formally grounded in reflective higher-order pi-calculus and object-capability (Ocaps) security, MeTTa-IL is intended to enforce correctness and safety prior to execution, allowing cognitive agents to scale from local devices to the global chain without semantic drift.

**Related repositories**

- <https://github.com/F1R3FLY-io/MeTTaIL>
- <https://github.com/F1R3FLY-io/MeTTa-Compiler>

#### 3.2.3 MeTTaCycle

MeTTaCycle is the AGI execution engine for ASI:Chain. It functions as an AI Layer 0, transforming the raw computational power of ASI:Chain into a global cognitive reactor. While F1R3FLY handles deterministic physical computations of the network — consensus, state, and concurrency — MeTTaCycle is the core hosting AGI cognitive processes.

It receives precise, validated instructions via F1R3FLY’s MeTTa-IL mechanism, taking the mathematically lowered instructions and compiling/executing them across lower-level Hyperon subsystems.

MeTTaCycle also governs the dynamic evolution of Atomspaces — the fundamental structures of knowledge and meaning in the Hyperon ecosystem. Transcending the rigid arithmetic of financial ledgers, it orchestrates the fluid topology of thought, enabling the network to synthesize, merge, and refine semantic concepts. It uses ChromaDB to facilitate embeddings and semantic operations as well as PeTTa for reasoning and versatile cognitive calculi, contributing to the claim that ASI:Chain is an AGI inference-native blockchain.

### 3.3 Runtime Relevance to OmegaClaw Agent

For the OmegaClaw agent, ASI:Chain is not mandatory in every deployment; the index is explicit that the runtime can operate on a single machine or a private network of machines. But where auditability, transactional cognition, multi-party execution, or decentralized governance matter, ASI:Chain provides the execution semantics by which cognitive state transitions can be recorded, validated, and reasoned over.

---

## 4. Knowledge Representations

### 4.1 Atomspace Foundation

Traditional AI systems suffer from a fundamental architectural problem: different components — knowledge bases, neural networks, reasoning engines, planners — exist in separate silos, communicating only through narrow interfaces. This creates massive inefficiencies as data gets copied repeatedly, caches become inconsistent, and opportunities for synergy are lost in translation. Each component speaks its own language with only crude inter-translation possible.

The Atomspace eliminates these barriers by providing a universal substrate where all cognitive activity occurs. Every piece of information — whether it is a fact, a rule, a neural weight, a goal, or a control signal — exists as an Atom that cognitive processes can directly access and manipulate. This is not merely a shared database; it is a living computational space where pattern matching, inference, learning, and self-modification happen simultaneously on the same structures.

**Key properties**

- **Content-addressed**: Every atom has a unique identifier (CID), enabling automatic deduplication and cryptographic provenance tracking.
- **Typed metagraph**: A rich type system supports diverse cognitive representations while maintaining consistency.
- **Unified operations**: Pattern matching, unification, and rewriting work uniformly across all atom types, whether symbolic or neural.

The Atomspace is fundamental for the OmegaClaw agent as a shared cognitive medium in which memory, code, motives, belief states, and self-modifying procedures become queryable and transformable.

### 4.2 DAS (Distributed AtomSpace)

**GitHub**

- <https://github.com/singnet/das>

**Description**

DAS is a high-speed, dynamic memory fabric for the Hyperon AGI framework. It operates as a distributed knowledge management system and repository for massive, mutable hypergraphs. Unlike conventional relational databases that silo data into static tables, DAS is architected as a generalized hypergraph — a dynamic web where information is atomized into nodes (concepts) and links (relations). Crucially, this structure allows links to connect not just nodes but other links, enabling the representation of higher-order logic and nested relationships directly in graph topology.

DAS therefore serves not merely as memory, but as a medium of re-entry: perceptions, inferred relations, learned abstractions, goals, and executable structures can all be deposited into a shared metagraph and made available to one another.

To emulate the efficiency of the human mind, DAS decouples the vast persistence of knowledge (Long-Term Importance stored in distributed backends) from the immediate dynamics of attention (Short-Term Importance managed in high-speed RAM). This separation is governed by the Attention Broker, which mitigates combinatorial explosions inherent in graph traversal. Before an inference query is executed, the system performs an activation spreading cycle, distributing tokens to heat up only the contextually relevant atoms. This dynamically constrains the search space to the most relevant atoms, functionally replicating limited working-memory efficiencies seen in biological cognition.

### 4.3 MORK (MeTTa Optimized Reduction Kernel)

**GitHub / demos / code**

- <https://github.com/trueagi-io/MORK/wiki>

**Papers / references named in the index**

- _Triemaps that Match_ (Simon Peyton Jones et al.)
- _CZ2 Scaling Experiments_ (internal Scala prototype)
- _Interacting Trie-Maps_ (internal Scala proof-of-concept)

**Description**

MORK is an ultra-high-performance hypergraph engine for Hyperon. Designed as a specialized in-RAM processing kernel, it executes the heavy lifting of symbolic AI — pattern matching and logic — with speedups ranging from thousands to millions of times compared to previous implementations. This represents a qualitative jump in capability, providing the raw computational velocity required to scale cognitive algorithms from academic experiments to complex real-world applications.

The secret to this speed lies in how MORK physically organizes data. While a standard graph database scatters nodes and links across memory like a tangled ball of yarn, MORK organizes them into a highly optimized Trie-Map (Radix Tree) structure. Shared patterns and nested relationships are compressed into a structured hierarchy. This allows its zipper-based multi-threaded virtual machine to navigate up and down complex reasoning paths with near-instant access, eliminating the slow pointer chasing that plagues traditional graph databases.

Crucially, MORK is built for interoperability through a mechanism known as **sinking**. It uses WebAssembly (WASM) to treat external code — whether Python data libraries or C++ numerical routines — as native operations. This allows the engine to delegate tasks it is not specialized for, such as heavy matrix multiplication, to external optimized libraries.

The whitepaper adds additional architectural clarification:

- MORK is framed as a carefully designed **lock-free, content-addressed prefix tree structure (PathMap / Merkle-DAG)**.
- Writers prepare changes as compact **deltas** that get merged atomically, while readers always see consistent data even during updates.
- **Weighted Atom Sweeps (WAS)** provide probabilistic sampling for attention-based scheduling.
- Current performance framing includes **500M+ atoms in RAM** on modern hardware, contrasted with roughly 50M in traditional approaches.
- For dense computation, two complementary paths are named as under development:
  - **ByteFlow**, which repacks frequently accessed subtrees into contiguous blocks that can be fed directly to GPU/TPU kernels;
  - **ShardZipper**, which enables deterministic batch processing by extracting shards, processing them in isolation, and zipping them back with full Merkle integrity.

### 4.4 Architecture (Bottom-Up)

#### 4.4.1 Graph DB Layer (Triemaps)

At its base is an in-memory hypergraph database built around high-performance triemap data structures. This specialized structure is critical for enabling massive-scale efficient expression matching and unification — core operations in logic programming that are often prohibitively slow. The layer natively supports relational algebra for performing asymptotically superior, space-wide bulk operations on the knowledge store.

#### 4.4.2 MORKL (The Query Language)

MORKL is the declarative query language purpose-built to interface with MORK’s specialized trie-map data structures. While high-level languages like MeTTa handle abstract reasoning, MORKL provides the bare-metal access required for structural manipulation, allowing the system to query hypergraph geometry directly without the overhead of semantic interpretation.

Technically, MORKL uses a declarative S-expression syntax that is strictly operational rather than logical. Its primitives are trie-optimized, engineered to exploit the branching patterns of MORK’s radix trees for maximum efficiency. By limiting its scope to foundational operations — pattern matching, indexing, direct retrieval — MORKL offloads query-planning complexity to the engine, preserving deterministic, high-velocity data access.

#### 4.4.3 Minimal MeTTa 2 (MM2)

MM2 is the low-level dataflow and runtime language used to define computation within MORK. It is not intended for general programming; it is specifically designed for performance-critical components of Hyperon’s cognitive algorithms. In the MORK architecture, MM2 uses MORKL to execute data retrieval and storage steps, then defines the subsequent data-processing pipelines executed by the ZAM.

The core design principle is to provide a highly optimized layer for computationally intensive tasks. In the hybrid execution model, high-level MeTTa code compiles down to invoke specialized MM2 procedures for demanding operations, much as a Python program calls a C or CUDA library. This is estimated to yield at least a two-order-of-magnitude speedup over a pure high-level implementation.

MM2 makes use of the **Gather–Process–Scatter** paradigm that separates data pipelines into retrieving data, processing it, and writing the results. Unlike the automatic branching of some MeTTa versions, MM2 is naturally pruned: the programmer explicitly defines control flow, which is essential for efficient search and inference algorithms.

#### 4.4.4 Zipper Abstract Machine (ZAM)

Built on top of the Graph DB, the ZAM is a concurrency-friendly multi-threaded runtime inspired by Prolog’s Warren Abstract Machine. Its role is to execute the dataflows and instructions defined in MM2, using cursor-based navigation (zippers) for efficient parallel logical inference. This is a key contributor to MORK’s near-linear performance scaling across multiple CPU cores.

### 4.5 Space API

While the Atomspace provides conceptual unity, practical systems need to integrate diverse computational resources. The **Space API** defines a universal interface that allows different backends to appear uniform to cognitive processes. A Space might be an in-RAM knowledge graph, a distributed database shard, a connection to a neural network service, or even a blockchain-based smart contract executor. The point is that MeTTa code need not know these implementation details.

**Current Space implementations named in the whitepaper**

- **MORK Spaces** provide high-performance local processing with the optimizations described above.
- **DAS (Distributed Atomspace)** extends across clusters via MongoDB/Redis for web-scale storage.
- **Neural Spaces** wrap external neural networks, making their embeddings queryable as atoms.
- **Rholang Spaces** enable capability-secured, blockchain-verified execution for multi-party scenarios.

### 4.6 Roadmap Notes

The index lists the following MORK roadmap directions:

- Native MeTTa-to-machine-code compiler
- Multi-machine distributed processing
- Specialized many-core or accelerator support
- WASM and edge deployment optimizations
- Community and third-party package ecosystem

### 4.7 Relevance to OmegaClaw Agent

For OmegaClaw, DAS and MORK should be read as alternative or complementary memory/execution substrates depending on the deployment profile: DAS where large mutable distributed hypergraphs and attention-brokered persistence dominate, MORK where maximal local performance, concurrency, and direct cognitive-kernel execution are paramount. The deeper claim preserved across both documents is that code and data remain interchangeable inside a queryable metagraph, so that the agent’s own logic becomes inspectable and improvable.

---

## 5. Hyperon AI Algorithms

Within this section, we review the mechanisms that compose the dynamics of thought itself. Each Hyperon algorithm functions as a specialized cognitive process that animates the system, elevating static knowledge into active intelligence. Expressed in MeTTa and executed across the distributed substrate, each algorithm addresses a fundamental requirement of general intelligence: handling reasoning under uncertainty, managing attention and economic resource allocation, driving evolutionary learning and program synthesis, supporting motivation, transfer, and causal adaptation.

Crucially, these are not isolated programs but interoperable modules of a unified cognitive cycle. By enabling distinct modes of cognition to interact concurrently on shared memory (Atomspace), Hyperon enables a form of cognitive synergy. What matters most is not the isolated strength of any one algorithm, but the recurrent traffic among them: the dynamics by which perceptual embeddings, attentional signals, rewrite processes, symbolic references, and learned structures continually transform one another through shared state.

### 5.1 Attention / ECAN (Economic Attention Networks)

**GitHub**

- <https://github.com/icog-labs-dev/attention>
- <https://github.com/iCog-Labs-Dev/metta-attention>

**Description**

ECAN is the attention-allocation and resource-regulation subsystem of the Hyperon architecture, designed to support cognitive efficiency under conditions of bounded computation and memory. In principle, a Hyperon agent knows everything stored in an Atomspace; in practice, attempting to reason over all stored knowledge simultaneously would be computationally intractable. ECAN addresses this by continuously regulating which Atoms are actively considered, ensuring that cognitive effort is concentrated on a tractable, context-relevant subset of the knowledge graph at any moment.

This regulation is achieved through two dynamically updated scalar values assigned to each Atom: **Short-Term Importance (STI)** and **Long-Term Importance (LTI)**. STI captures immediate, context-dependent relevance and is propagated through Hebbian-weighted associative links, enabling attention to shift dynamically as situations, goals, or perceptions change. LTI reflects longer-horizon expected utility — encoding how consistently an Atom has contributed to successful inference, learning, or goal-directed behavior over time.

At a systems level, ECAN implements an attention protocol that balances short-term responsiveness with long-term coherence. Atoms compete for limited working-memory and processing capacity based on their importance profiles and current context, with those that fail to demonstrate relevance gradually losing activation.

The whitepaper adds that recent fluid-dynamics-inspired enhancement models attention as an incompressible fluid whose flow is optimally controlled toward goal-relevant regions, providing principled credit assignment along causal chains. Weighted Atom Sweeps implement this efficiently on MORK, with aggregate weights bubbling up the trie for probabilistic sampling.

### 5.2 Motivation: MetaMo

**GitHub**

- <https://github.com/iCog-Labs-Dev/hyperon-openpsi>

**Papers**

- Lian, R., Goertzel, B. _MetaMo: A Robust Motivational Framework for Open-Ended AGI_. AGI 2025.
- Lian, R., Goertzel, B. _Embodying Abstract Motivational Principles in Concrete AGI Systems: From MetaMo to Open-Ended OpenPsi_. AGI 2025.

**Description**

MetaMo is a framework for modeling motivation in open-ended intelligent agents, concerned with how goals, priorities, and evaluative signals can be updated over time while preserving coherence, stability, and interpretability. Rather than relying on scalar reward functions or manually engineered drive hierarchies, MetaMo treats motivation itself as a dynamical system, explicitly coupling appraisal processes — which evaluate situations in terms of salience, risk, and opportunity — with decision processes — which select actions and allocate computational and behavioral resources.

MetaMo represents motivational state as a structured interaction between goal intensities and modulatory variables. Appraisal updates modulators such as valence, arousal, and risk sensitivity in response to contextual novelty and task relevance, while decision mechanisms score candidate actions relative to active goals under the current modulatory configuration. These processes are designed to commute up to bounded error, ensuring consistency between “appraise-then-decide” and “decide-then-appraise” cycles. System stability is enforced via contractive update dynamics that draw motivational state away from pathological extremes, while goal evolution proceeds incrementally to maintain continuity of self-model during learning and self-modification.

Within the Hyperon ecosystem, MetaMo serves as the motivational backbone linking inference, learning, and attention allocation. It shapes control dynamics in Probabilistic Logic Networks by biasing search and inference toward contextually appropriate goals, regulates exploration–exploitation tradeoffs, and embeds safety and ethical constraints directly within motivational dynamics rather than as externally imposed rules.

The whitepaper extends this with stronger formal language: MetaMo is described through a pseudo-bimonad structure where appraisal and decision functions are coupled through a lax distributive law; hierarchical invariants constrain how goals can change; motives evolve while remaining within bounded regions; and every decision is associated with an audit trail explaining not just what was chosen but why.

**Roadmap**

- Foundations: formalize pseudo-bimonad structure and five design principles; prove stability via contractive updates.
- Prototyping: implement OpenPsi (appraisal comonad) and MAGUS (decision monad) with dual overgoals; test in toy simulations.
- Integration: embed MetaMo into Hyperon Atomspace and PLN for motivation-guided inference.
- Prototypes: build a research assistant demo, validate inference allocation, and test multi-agent coordination.
- Scaling: refine blending dynamics, tune overgoals, develop verification methods, and benchmark against other AI approaches.
- Continuous evolution: refine overgoals, add formal safety guarantees, and establish MetaMo as a core motivational framework for scalable open-ended AGI-ready systems.

### 5.3 Semantic Parsing (LLM / NLP)

**GitHub / demos / code**

- <https://github.com/singnet/semantic-parsing>
- <https://github.com/rTreutlein/nl2pln_demo/tree/main>

**Description**

Semantic Parsing is a neural-symbolic bridge designed to interpret the ambiguity of human language into executable logic within AGI. While natural language is fluid and context-dependent, the Atomspace requires rigorous deterministic structures to perform reasoning. This subsystem bridges that gap, functioning as a translator that ingests language inputs and converts them into a structured knowledge graph of distinct queryable facts.

A key mechanism enabling this is **SENF (Semantic Elegant Normal Form)**. This framework addresses the many-to-one complexity of language, where the same fact can be phrased in multiple ways. SENF collapses idiomatic variations into a canonical graph structure, ensuring that diverse inputs map to a unique minimal representation. By combining the semantic intuition of LLMs with formal rewrite rules, the system strips away linguistic noise to reveal essential logical relationships.

The result is the creation of grounded atoms: verified logical expressions that serve as fundamental knowledge representations for the Hyperon ecosystem. Once parsed, a textbook can become a dynamic database where facts are cross-referenced, contradictions are flagged, and Hyperon algorithms can cogitate directly on meaning.

**Roadmap**

- Implement fuzzy semantic elegant normal forms
- Derive an initial commonsense knowledge base

### 5.4 PLN (Probabilistic Logic Networks)

**GitHub / demos / code**

- <https://github.com/trueagi-io/PLN>
- <https://github.com/trueagi-io/pln-experimental>
- <https://github.com/trueagi-io/chaining>

**Description**

PLN is Hyperon’s primary symbolic reasoning system designed to operate under uncertainty, enabling real-time inference when information is incomplete, noisy, or probabilistic. Unlike classical logic systems that assume binary truth values, PLN represents beliefs with graded confidence and updates them continuously as new evidence arrives. It supports deductive, inductive, and abductive reasoning within a single formal framework, allowing the system not only to apply known rules, but also to generalize from experience, form hypotheses, and revise beliefs over time.

Technically, PLN operates over an Atomspace, a graph-structured knowledge representation in which concepts, relations, and experiences are linked together with probabilistic truth values. Reasoning proceeds by transforming and combining these links using principled inference rules grounded in probability theory. This allows PLN to perform causal reasoning, analogical inference, and abstraction, while maintaining transparency about why a conclusion was reached and how confident the system is in it.

To ensure tractability within large Atomspaces, PLN leverages forward- and backward-chaining inference control and can call on ECAN to dynamically filter the knowledge graph into a temporary working memory of high-salience facts.

The whitepaper reframes the 2025 incarnation of PLN as operating through **quantale-annotated factor graphs** where logical structure and uncertainty measures travel together as messages. Each atom carries both what is believed and how strongly it is believed, with evidence counts and confidence intervals. Geodesic control guides chaining so the system pursues inferences that advance both from premises and toward goals. Pattern matching leverages MORK’s prefix structure for near-instant neighbor lookups, while the factor-graph formulation enables massive parallelism.

**Roadmap**

- Enhancements in inference control to support ECAN integration
- Improve truth functions to more accurately estimate simple truth values of conclusions
- Introduce temporal and procedural reasoning for robust prediction and decision-making
- Create reasoning benchmarks for evaluating capabilities
- Engineer effective resource and attention allocation control, from simpler NARS-inspired forms to ECAN

### 5.5 MeTTa-NARS (Non-Axiomatic Reasoning System)

**GitHub / demos / code**

- <https://github.com/patham9/metta-nars>

**Description**

MeTTa-NARS is an open-ended uncertainty reasoning engine designed to operate under the Assumption of Insufficient Knowledge and Resources (AIKR). Unlike traditional logical systems that require complete, clean data to function, MeTTa-NARS is built for the open world where information is scarce, inconsistent, and constantly changing.

The system distinguishes itself through Non-Axiomatic Logic (NAL), which replaces binary truth with a two-dimensional evidence value (frequency and confidence). This allows the agent to distinguish between statements supported by extensive observation and tentative beliefs supported only lightly. It manages this knowledge via concept-centric memory and a rigorous inference control mechanism that treats reasoning as a resource allocation problem.

**Roadmap**

- Further improved attention allocation
- Improvement of temporal reasoning by enlarging data structures
- More effective handling of procedural information for robust decision-making

### 5.6 NACE (Non-Axiomatic Causal Explorer)

**GitHub / demos / code**

- <https://github.com/patham9/NACE>

**Description**

NACE is an experiential learning agent designed to overcome the extreme data inefficiency of deep reinforcement learning. While standard DRL agents require millions of trial-and-error samples to approximate correlations, NACE functions as a causal reasoner: it actively constructs a logic-based model of its environment by observing the direct consequences of its interactions.

Functionally, the agent operates on a cycle of curiosity-driven exploration. NACE generates causal rules from local changes in the environment and prioritizes actions based on an intrinsic reward signal geared toward uncertainty reduction. Rather than merely chasing an external score, it plans paths to states where its internal model is incomplete, systematically filling knowledge gaps. Grounded in NAL, the system tracks evidential weight for every rule and remains robust under noise.

**Roadmap**

- Extension into continuous-state domains

### 5.7 AI-DSL (AI Domain Specific Language)

**GitHub / technical reports**

- <https://github.com/singnet/ai-dsl>
- <https://github.com/singnet/ai-dsl/tree/master/docs/technical-reports>

**Description**

AI-DSL is the protocol and tooling layer designed to automatically assemble complex AI workflows from discrete services available on the SingularityNET and ASI marketplaces. It fulfills the vision of a network of intelligences by treating individual AI services not as isolated applications, but as composable functions that can be chained to solve problems no single service could handle alone.

Functionally, AI-DSL operates as a type-driven program synthesizer. It employs a backward chainer implemented in MeTTa that treats a user request as a theorem to be proven and available AI services as axioms. To bridge the gap between abstract requirements and concrete code, it uses a rich ontology of dependent types. This semantic precision prevents absurd compositions and allows the planner to enforce logical compatibility.

To remain tractable, AI-DSL leverages combinatory logic — especially Bluebird (sequential) and Phoenix (parallel) combinators — plus aggressive pruning to shrink the search space.

**Roadmap**

- Scale for larger networks
- Enrich the ontology
- Support modeling resource requirements such as temporal, financial, and computational cost, as well as evaluating performance characteristics
- Support uncertainty in specifications, likely by replacing a crisp dependent type system with PLN or a related framework

### 5.8 MOSES (Meta-Optimizing Semantic Evolutionary Search) and GEO-EVO

**GitHub**

- <https://github.com/iCog-Labs-Dev/metta-moses/>
- <https://github.com/opencog/moses>

**Description**

MOSES is an evolutionary program generation engine designed to breed compact, interpretable computer programs that solve complex problems. Unlike deep neural networks that function as black boxes of opaque weights, MOSES evolves transparent symbolic code capable of logical generalization. It treats the search for solutions as a meta-optimization problem, maintaining diverse subpopulations of programs (demes) to avoid local optima while iteratively refining candidates.

Functionally, MOSES combines probabilistic model-building with evolutionary search. It operates via two nested loops: an outer loop that explores structural variations and an inner loop that tunes numeric parameters. A defining characteristic of MOSES is its use of **Elegant Normal Form (ENF)** to constrain the search space by collapsing functionally equivalent programs to canonical representation.

The whitepaper extends this line through **MOSES/GEO-EVO**, emphasizing bidirectional guidance: searching forward from current capabilities and backward from desired outcomes. Programs live directly in Atomspace as typed structures that other components can inspect, modify, and reason about. Estimation-of-distribution methods learn which program parameters co-vary, focusing exploration on promising regions of program space. The weakness prior biases toward simpler and more general programs, while TransWeave is intended to enable successful programs to transfer across domains with bounded degradation.

**Roadmap**

- Add multi-deme support
- Implement feature selection and sampling
- Scale to handle continuous data
- Integrate more deeply with other Hyperon components
- Explore integration with MORK

### 5.10 AIRIS

**GitHub / demos / code**

- <https://github.com/singnet/AIRIS-scripts/tree/master>

**Description**

AIRIS is a causal machine learning system designed to overcome the opacity and data inefficiency of traditional deep reinforcement learning. Rather than ingesting massive datasets to approximate statistical correlations, AIRIS functions as a causal reasoner. It actively constructs a deterministic model of its environment through direct interaction.

The system has demonstrated this in voxel-based environments like Minecraft, where it operates without pre-training. By observing the direct consequences of its actions, AIRIS builds a dynamic knowledge base of causal rewrite rules. It uses these rules to run internal simulations in its world model, plan complex paths, and achieve arbitrary goals. When prediction fails, AIRIS isolates the error and updates its rule set, applying a scientific-method-like loop to autonomous navigation.

Within Hyperon, AIRIS serves as a mechanism for causal learning. It translates raw sensory data into structured symbolic knowledge in Atomspace, providing grounded material for higher-level systems like PLN and MOSES.

**Roadmap**

- Develop a generalized AIRIS that can accept any type of data from any domain
- Build public API infrastructure for the generalized AIRIS
- Create demos of AIRIS operating in various domains

### 5.11 SubRep: Certified Subgoal Learning

The whitepaper introduces **SubRep** as a principled answer to the question of which subgoals to learn. Two complementary admission tests are named:

- **CDS (Cone-Dominant Subtasks)** admit options that improve value for all weight vectors within a learned motive cone.
- **PDS (Pareto-Dominant Subtasks)** admit options that improve some objectives without unacceptably harming others.

The **Motive Decomposition Network (MDN)** co-learns the geometry of what the system cares about from experience. Every admitted option carries a certificate — a mathematical proof of utility that remains valid even when options are composed into complex plans.

### 5.12 WILLIAM-on-MORK: Adaptive Compression

The whitepaper also elevates **WILLIAM** as a cross-cutting principle: patterns worth remembering are those that compress experience most effectively. Integrated into MORK’s trie infrastructure, WILLIAM exposes weighted iterators that return the most important patterns from any point in the graph without requiring global scans.

This allows:

- PLN to prioritize inference on high-value subgraphs;
- backward chaining to follow heavy edges likely to succeed;
- neural systems to use compression metrics to guide attention and pruning;
- the broader stack to identify which patterns, tokens, heads, features, or subgraphs carry the most information-theoretic value.

### 5.13 Relevance to OmegaClaw Agent

Taken together, these algorithms imply that the OmegaClaw agent is not restricted to being organized around a single monolithic planner. It can organize itself around recurrent interaction among attention, motivation, reasoning, transfer, causal learning, compression, and program synthesis over shared memory.

---

## 6. Cognitive Architecture & Research

### 6.1 PRIMUS (formerly CogPrime)

**Papers and publications**

- _OpenCog Hyperon: A Framework for AGI at the Human Level and Beyond..._

**Canonical Description**

In effect, Hyperon provides the raw Lego bricks of AGI; **PRIMUS** is the architectural recipe that configures and orchestrates them into a unified AGI engine — fully autonomous, self-evolving, and characterized by emergent cognitive synergy. PRIMUS is a meta-architecture specification implemented in MeTTa: a high-level orchestration layer and accompanying configuration library that defines how Hyperon’s modular engines fit together into a cohesive AGI system.

**PRIMUS elements highlighted in the index**

- **Module Topology**: Specifies which Hyperon components to invoke, in what order, and how data flows between them.
- **Goal & Motivation Loops**: Templates for curiosity-driven search, goal decomposition, reward signals, and learning triggers that animate continuous self-directed cognition.
- **Attention & Resource Policies**: Prescriptive rules for ECAN/ActPC to allocate CPU, memory, and inference budget across competing kernels.
- **Integration Contracts**: Standardized MeTTa interfaces and API bindings ensuring each kernel — symbolic, probabilistic, evolutionary, neural — can be hot-swapped or scaled independently.
- **Cognitive Synergy Patterns**: Reusable coordination motifs such as evolution → inference → attention cycles that underlie emergent generalization and robust decision-making.

### 6.2 PRIMUS Dual Processing Loops

The whitepaper expands PRIMUS by describing two interleaved loops operating over shared Atomspace.

#### 6.2.1 Goal-Directed Loop

The goal-directed loop embodies deliberate purposeful cognition. MetaMo maintains a small set of top-level motives — not merely scalar rewards, but structured objectives with formal stability guarantees. These motives guide the system in assembling and executing plans by combining multiple methods:

- PLN provides uncertain reasoning chains connecting actions to expected outcomes.
- MOSES/GEO-EVO evolves new programs when existing skills prove insufficient.
- SubRep ensures that any subgoal or option admitted to the system provably serves the larger purpose.

Throughout this process, **geodesic control** seeks efficient cognitive pathways by selecting actions that maximize progress per unit effort.

#### 6.2.2 Ambient Background Loop

The ambient background loop represents continuous exploratory activity — pattern recognition, concept formation, and belief refinement that continue even when the system is not narrowly problem-solving. ECAN diffuses attention across the knowledge graph according to importance and relevance, creating pools of activation where cognitive resources naturally concentrate. Within these regions, pattern mining discovers recurring structures, concept blending creates novel combinations, factor-graph PLN quietly tightens beliefs and propagates evidence, and WILLIAM continuously assesses which patterns provide the most compression.

The important claim is that discoveries in one loop immediately benefit the other. Patterns found during ambient exploration become templates for goal-directed reasoning. Subgoals certified during problem-solving become reusable skills for future tasks.

### 6.3 Unified Control Principles

The whitepaper highlights two mathematical principles intended to unify cognition across PRIMUS.

#### 6.3.1 Geodesic Control

Geodesic control treats cognition as an optimal-transport-like problem. Every cognitive step — whether inference, learning update, or planning decision — is evaluated by how much it increases both forward reachability and backward usefulness per unit computational cost. This provides a uniform criterion for efficient reasoning, planning, and self-modification.

A linked notion of **evidence conservation** is used to prevent both hallucination and information loss.

#### 6.3.2 Weakness-Based Simplicity

Weakness-based simplicity provides a general form of Occam’s razor across cognitive paradigms. Logical proofs, neural models, and evolutionary programs each have different native notions of simplicity; quantale theory is proposed as the way to formalize these diverse simplicity notions within a unified framework. A hypothesis is weaker, and thus simpler, when it rules out less or adds less structure.

This is meant to create consistent pressure toward robust, generalizable solutions regardless of which cognitive method discovers them.

### 6.4 Core Components in the White Paper Framing

The whitepaper specifically re-articulates several longstanding PRIMUS components for the Hyperon era:

- **PLN** becomes a factor-graph uncertain reasoner with geodesic control and MORK-accelerated pattern access.
- **MOSES/GEO-EVO** becomes a bidirectionally guided search over typed Atomspace-resident programs, regularized by weakness priors.
- **ECAN** becomes an attention economy implemented efficiently over MORK, with fluid-style control enhancements and weighted probabilistic sweeps.

### 6.5 PRIMUS Roadmap Notes from the Index

- Integrated PRIMUS modules in Hyperon Alpha release and beyond
- Implement cognitive kernels such as ActPC-Chem for experiential learning
- Incorporated LLM-based enhancements across subsystems
- Developed and reused supercompilation techniques for reasoning engines
- Further R&D for motivation, goal generation, and concept formation modules
- Validate and benchmark initial use-case implementations

### 6.6 Cross-Stack Research Directions

This section covers cross-stack research directions that shape how Hyperon’s modules learn, transfer, and cohere over time. These are theoretical and practical approaches to governing the flow of learning, inference, memory, and self-revision across the system.

#### 6.6.1 Predictive and Causal Coding

Predictive coding is a neural learning framework in which hierarchical layers continually generate predictions and update themselves through local prediction-error dynamics. Learning is not treated as a single monolithic end-to-end adjustment, but as an iterative inferential process in which latent states and parameters are refined through structured exchanges of top-down prediction and bottom-up error.

Predictive and causal coding work with information-geometric principles and commutator relationships to shape how learning propagates through the system: local influence estimates, mixed-curvature structure, and small-commutator dynamics help determine where updates should go, where they should not go, and how modular competence can be preserved under continual adaptation.

Causal coding extends this framework by introducing interventional influence into learning so that updates are directed toward modules actually causally implicated in a given context, while clarity and pruning pressures suppress redundant or merely correlational pathways. Recent formulations describe a two-level architecture in which Bayesian routing governs which columns or modules should be active, reused, or forked, while predictive-coding microstructures within those modules are kept coherent through pruning, inhibition, and shell-based consolidation.

The whitepaper’s neural sections complement this with the idea that predictive coding networks permit local updates to begin as soon as prediction errors are detected, without requiring global backpropagation. Commutativity regularization is invoked to ensure different update streams do not interfere destructively.

#### 6.6.2 TransWeave

TransWeave is a framework for carrying useful structure forward when a system moves from one task, environment, or regime into another. The core idea is that an intelligent system should not have to either cling rigidly to an old solution or start over from scratch. It should preserve what is still true, adapt what has changed, and do so in a disciplined way.

In formal terms, TransWeave studies transfer maps that preserve the deep organization of a task while allowing local adaptation. In reinforcement learning this is framed through Bellman–Darboux intertwining: a transfer is good when “transfer then learn” comes out nearly the same as “learn in the new setting.”

The whitepaper extends this substantially:

- transfer is treated as finding **structure-preserving mappings** between task spaces rather than copying solutions;
- the system can compute lower bounds on value degradation when transfer succeeds;
- **H-ICA** is used to detect when solution components fundamentally cannot align across domains;
- transfer operations compose algebraically, supporting a “braiding” property in which learn-then-transfer and transfer-then-learn remain boundedly close.

Within Hyperon, TransWeave is therefore best understood as a cross-stack continuity principle by which intelligence becomes cumulative rather than repeatedly rebuilt.

### 6.7 Neural-Symbolic Integration Modes

The whitepaper lays out two complementary neural-symbolic modes.

#### 6.7.1 Outside Mode

Outside Mode provides pragmatic integration of existing neural models without requiring those models to be natively stored in Atomspace. Large language models, vision models, and other pre-trained systems continue running in their own frameworks but expose internal representations — embeddings, hidden states, attention patterns — as queryable atoms. This makes neural representations inspectable by symbolic processes.

#### 6.7.2 Inside Mode / QuantiMORK

Inside Mode represents a more radical fusion through **QuantiMORK**. Instead of tensors living outside the metagraph and syncing across a boundary, they are envisioned as multiresolution DAGs stored directly in MORK’s PathMap. Wavelet transforms are used because their hierarchical structure maps naturally to prefix trees. Neural computations such as attention, convolution, and gradient updates are then intended to operate on the same memory structures that store symbolic knowledge.

This remains a frontier research direction rather than a flattened statement of current production maturity.

#### 6.7.3 Symbolic Heads for Transformers

The whitepaper proposes symbolic heads as augmentations to transformer layers with structured memory that preserves discrete relationships and logical constraints. Frequent subgraphs mined from training data become retrievable templates. Each transformer layer aligns continuous representations with this discrete library, blending symbolic and neural information in parallel with standard self-attention.

#### 6.7.4 WILLIAM-Guided Efficiency

Compression-guided selection is extended into neural computation. The system tracks which attention heads, tokens, features, and computational paths contribute most to accurate prediction. Dynamic sparsity can then be guided by information-theoretic value rather than ad hoc pruning.

---

## 7. Self-Modification, Safety, and Governance

### 7.1 Goal Stability Framework

The whitepaper treats the transition from AGI to ASI as hinging on self-improvement without value drift. Hyperon’s answer is to represent goals not as monolithic scalar objectives but as **hierarchical invariants** where each level constrains how lower levels can evolve.

Strong stability is described as emerging when modification operators are contractive in appropriate metrics; weak stability applies when stable regions exist without contraction and must be monitored more carefully. This is presented as a mathematically grounded alternative to external “bolt-on” safety mechanisms.

### 7.2 Self-Modification Pipeline

Self-improvement in Hyperon is described through a five-stage pipeline:

1. **Proposal**: candidate changes are formalized as typed metamorphisms with preconditions, postconditions, expected improvements, and effects on weakness metrics.
2. **Analysis**: an influence graph is constructed to show affected components; structural composition laws are checked.
3. **Simulation**: the modification runs in a controlled twin environment with representative reduced workloads.
4. **Certification**: the modification must satisfy safety criteria regarding invariant bands, behavioral drift, weakness, and evidence conservation.
5. **Deployment**: staged rollout proceeds through shadow mode, dual-run comparison, and then primary elevation if stability holds.

All artifacts are content-addressed, enabling rollback when needed.

### 7.3 Decentralized Governance

The whitepaper frames governance as inseparable from safety. Every modification, proof, decision, and certificate is treated as a content-addressed object with cryptographic provenance. Capability security through RSpace / Rholang ensures that each process can access only what it needs.

The economic layer is intended to create positive incentives for safety: communities may require publication of safety certificates before granting compute resources; validators may simulate proposed modifications against public twins; markets can reward transparent safe improvements and penalize opaque risky ones.

### 7.4 Relevance to OmegaClaw Agent

For the OmegaClaw agent, this section establishes the proper reading of reflective capability. Reflection is not merely “the agent can rewrite itself.” It is supposed to occur under typed, auditable, staged, and certifiable conditions. That distinction matters.

---

## 8. Application Domains and Beneficial Grounding

The whitepaper argues that Hyperon should not be developed in isolation and only later aimed at beneficial use. Instead, beneficial applications are used as training grounds that shape the system’s priors and validate the architecture under meaningful constraints.

### 8.1 Game AI (Minecraft / Sophiaverse / Neoterics)

Games provide structured but open-ended environments in which perception, planning, social interaction, and skill transfer can be tested with rapid iteration and safe failure. The whitepaper specifically highlights Minecraft and Sophiaverse, with the specialized Neoterics micro-world offering a constrained but richly instrumented environment for rapid baby-AGI development.

This aligns naturally with AIRIS and related experiential learning work.

### 8.2 Social Robotics

Humanoid robots operating in education and performance settings require the integration of perception, dialogue, motor control, and social reasoning. Pattern mining discovers conversational templates and social scripts; MetaMo is described as throttling novelty when emotional risk is high; interactions are intended to remain auditable both in what was done and why.

### 8.3 Bioinformatics

Biology is described as fundamentally graph-structured — genes, proteins, pathways, diseases — making it a natural fit for Hyperon’s metagraph approach. Pattern mining can discover motifs, PLN can propagate uncertainty through biological networks, and MOSES/GEO-EVO can evolve predictive models for treatment response and biomarker discovery.

### 8.4 Mathematics

Hyperon is also aimed not only at theorem proving but at automated conjecturing: proposing new definitions, lemmas, and theorems worth proving. Pattern mining over proofs, geodesic search over candidate statements, and a proof kernel implemented directly on MORK are all part of this framing.

### 8.5 Why This Matters for OmegaClaw

For the OmegaClaw agent, these domains matter because they shape what the agent is for. They promise cognition in settings where evidence, testability, reproducibility, social appropriateness, and cumulative learning are not optional embellishments but native constraints.

### 8.6 Technical Advantages Over Pure Scaling

The whitepaper is explicit that Hyperon’s path is not framed as mere parameter scaling. The claimed advantages come from selectivity and compositionality: local predictive-coding-style updates operate where uncertainty is high; symbolic heads retrieve structure rather than recomputing it; WILLIAM prunes low-value computational paths; PLN caches and reuses intermediate structure; and TransWeave aims to reuse certified components across tasks rather than relearning from scratch.

A related claim is **cumulative learning**. Because cognitive components share a common substrate, improvements in pattern mining can immediately benefit attention allocation; improved attention can support better inference; improved inference can guide better program evolution; and evolved programs can become templates for later learning. This is one of the central architectural arguments for Hyperon over narrow API-mediated hybrids.

The whitepaper also stresses **reduced technical debt**: typed edits, twin simulation, certification, rollback, and provenance are all intended to make the system’s growth inspectable rather than opaque.

### 8.7 Beneficial by Construction

The merged Hyperon framing does not treat benefit as something imposed from outside a completed intelligence. Instead, beneficial behavior is argued to arise from the same mathematics and structure that make the system capable. Geodesic control is meant to guide efficient progress in both ordinary cognition and self-modification. Weakness regularization is meant to prevent brittleness in both learned models and system changes. Evidence conservation is meant to protect both reasoning quality and reflective revision.

MetaMo contributes by keeping goals and trade-offs explicit rather than hidden in opaque weights. Decentralized deployment contributes by reducing the plausibility of silent centralized objective tampering. Application grounding contributes by repeatedly training the system in domains where evidence, rigor, social sensitivity, and reproducibility matter intrinsically.

### 8.8 Measurable Progress Toward Benefit

The whitepaper proposes that progress toward beneficial AGI should be monitored through concrete metrics rather than through vague reassurance. Examples named include invariant stability, transfer success rates, evidence conservation, deployment transparency, and domain-specific benefit metrics such as hypothesis validation rates, learning outcomes, and proof elegance.

---

## 9. Implementation Status and Near-Term Roadmap

### 9.1 Current Capability Framing

The whitepaper states that the Hyperon platform has reached a level of maturity where several core components are operational and demonstrating architectural benefits:

- MORK handling 500M+ atoms in RAM with efficient pattern matching at scale
- MeTTa providing a functional compiler path with multiple backend targets including MORK, Rholang, and native code generation paths
- PLN operating through factor-graph implementations with geodesic control
- MOSES demonstrating program evolution across multiple domains
- pattern mining achieving real-time operation through streaming I-surprisingness ranking

This should still be read alongside the explicit note that many newer methods remain at varying levels of maturity.

### 9.2 Near-Term Roadmap

The whitepaper identifies the following platform-level targets for the next horizon:

- QuantiMORK demonstrating waveformer integration with predictive coding updates
- TransWeave validated through cross-paradigm transfer demonstrations
- full MetaMo/SubRep integration with safety certificates
- ByteFlow GPU acceleration for dense computations while maintaining the unified substrate
- PyMeTTa launching with the complete `metta-magic` library

### 9.3 Performance Targets

Concrete targets named in the whitepaper include:

- 25–50% FLOP efficiency gains over pure neural approaches on mixed reasoning/perception tasks
- 70% or higher positive transfer rate on related tasks with explicit failure detection for incompatible domains
- self-modification rollback completing in under 2 minutes
- sub-second decision latency for real-time applications

---

### Closing notes

- Claw-specific wording is future-facing representing our intentions for the OmegaClaw roadmap.
- Do not attempt to flatten research-stage material into production claims.
- Not every named component in this profile is equally mature. Some are current operating parts of the stack; others are near-term engineering targets; others remain active research directions. The reference value of this document lies in preserving the intended architecture and careful relationships among components without overstating uniform implementation maturity.
