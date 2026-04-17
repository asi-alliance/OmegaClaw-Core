# KB-02: ASI:Chain Ecosystem and Shards

**scope:** The ASI:Chain blockchain runtime for decentralized AGI — its architecture (F1R3FLY, MeTTaCycle, consensus mechanisms), and all named shards: Omega, Qwestor, QBRAIN, and BGI Nexus.
**excludes:** Hyperon cognitive algorithms internal to the stack (→ KB-01); tokenomics formulas and economic models (→ KB-03); consciousness theory (→ KB-05).

**confidence:** Medium for ASI:Chain architecture (described in stable hyperon.md reference). Low for individual shard papers — all four shard WPs are marked "initial rough version" and should be treated as design proposals, not deployed systems. All shard-specific claims marked [UNCERTAIN].
**last_updated:** 2026-04-09
**primary_sources:** hyperon.md (ASI:Chain section), Omega-Shard-WP.pdf (Sept 2025, draft), Qwestor-Shard-WP.pdf (Sept 2025, draft), QBRAIN-WP.pdf (Sept 2025, draft), BGI-Nexus-Shard-draft.pdf (Sept 2025, draft)

---

## Core Concepts

**ASI:Chain** is the Layer 1 blockchain runtime environment designed specifically for decentralized AGI deployment. It is not a general-purpose blockchain. Its design goal is to serve as a distributed cognitive substrate — a worldwide supercomputer for AI-native workloads. The core claim is that ASI:Chain is the first blockchain capable of native inference settlement: verifying cognitive state transitions (reasoning steps) rather than merely validating token transfers.

**Two foundational engines** power ASI:Chain. F1R3FLY handles the computational blockchain substrate — concurrency, sharding, consensus, and distributed execution. MeTTaCycle handles the AGI cognitive execution layer — compiling and orchestrating Hyperon cognitive workloads on top of F1R3FLY.

**BlockDAG structure** allows thousands of non-conflicting AI processes to execute in parallel, breaking the sequential bottleneck of legacy blockchains like Ethereum. This makes the architecture suited to the massively parallel, concurrent workloads of AGI.

**Decentralized deployment is one of three pillars** of the path from Hyperon to beneficial AGI. Decentralization prevents monopolistic control of AGI infrastructure, provides auditability of cognitive state transitions, and enables multi-party execution. ASI:Chain is not mandatory for every Hyperon/OmegaClaw deployment — it can also run on a single machine or private network where decentralization is not required.

**The shard model** extends ASI:Chain with purpose-specialized sub-chains. Each shard optimizes for a different workload. Shards interoperate and can delegate tasks across the ecosystem. All current shard papers are initial drafts [UNCERTAIN].

---

## Current State

### F1R3FLY

F1R3FLY is the underlying computational blockchain engine of ASI:Chain. It is grounded in Rholang (Reflective Higher-Order Process Calculus), which models every interaction — financial transactions and AGI inference alike — as concurrent processes communicating over channels. Key architectural properties:

- **Reified RSpaces and MORK PathMaps** treat storage as a programmable living system rather than a static bucket. It can function as a blockchain, a file system, or a vector database simultaneously.
- **LMDB integration** provides durable persistence with low-latency retrieval.
- **Protocol interoperability** [UNCERTAIN]: F1R3FLY nodes are described as eventually speaking RGB/Really Good Bitcoin, Lightning, and Ethereum protocols.
- **Object-capability (Ocaps) security** enforces correct and safe execution before programs run.

### MeTTaCycle

MeTTaCycle is the AGI execution engine for ASI:Chain — the "AI Layer 0." It receives validated instructions from F1R3FLY via the MeTTa-IL mechanism and compiles and executes them across Hyperon subsystems. Responsibilities include:

- Governing the dynamic evolution of Atomspaces — the knowledge and meaning structures of the Hyperon ecosystem.
- Orchestrating fluid topology of thought: synthesizing, merging, and refining semantic concepts across the network.
- Using ChromaDB for embeddings and semantic operations.
- Using PeTTa for reasoning and cognitive calculi.

### Consensus Mechanisms

Multiple consensus mechanisms appear across the ecosystem. Understanding which applies where matters for evaluating reliability:

**Casper CBC** (current standard): Real-time finality consensus suitable for rapid response validation. Used by Qwestor and other shards as the initial live consensus layer.

**Casanova** [UNCERTAIN — described as "upon maturity"]: Next-generation consensus being developed to replace or supplement Casper in production shards. Multiple shard papers describe transitioning to Casanova once it matures.

**Cordial Miners / Reputation-Enhanced Cordial Miners**: Background consensus for compute providers who do not need real-time finality — intermittent availability is acceptable. Used for deep reasoning tasks, long-running processes, and background compute contribution. Reputation weighting adjusts influence based on demonstrated contribution history.

### Shard Architecture: Omega Shard [UNCERTAIN — initial draft]

**Purpose:** The frontier AGI research shard within ASI:Chain. Designed to host the most advanced AGI R&D systems and to pursue autonomous research toward HLAGI (Human-Level AGI) and ASI.

**Dual-layer architecture:**
- Layer 1 (Real-Time Consensus via Casper CBC, transitioning to Casanova): Handles urgent AGI queries, records intelligence contribution proofs, manages cross-shard interactions, distributes rewards. Requires staked ASI tokens and reliable infrastructure.
- Layer 2 (Background Compute via Reputation-Enhanced Cordial Miners): Deep reasoning without real-time constraints, recursive self-improvement experiments, long-running consciousness simulations, autonomous research generation. No stake required; intermittent availability acceptable.

**Intelligence Contribution Rewards Pool:** A pool that rewards meaningful advances in collective intelligence. The Meta-Predictor Shard assesses contributions for reward distribution.

**Cross-shard integration:** Omega delegates neural-symbolic reasoning subtasks to Qwestor, outsources quantum computing requirements to QBRAIN, and uses Meta-Predictor for intelligence contribution assessment.

**Use cases claimed [UNCERTAIN]:** Resolution of queries exceeding standard AI agents, autonomous research into intelligence/consciousness/reasoning, HLAGI development infrastructure.

### Shard Architecture: Qwestor Shard [UNCERTAIN — initial draft]

**Purpose:** Decentralized backend infrastructure for neural-symbolic AI applications. Supports two end-user products: Qwestor (persistent AI personalities with memory and growth) and Qwello (streamlined research engine).

**Services handled:** Knowledge graph management, symbolic reasoning, neural inference coordination, persistent state management.

**Two-layer design:**
- Consensus layer (Casper CBC, transitioning to Casanova): Real-time response validation. Validators require reliable infrastructure and staked ASI.
- Compute layer (Reputation-Enhanced Cordial Miners): Background thinking, broader participation, no stake required.

**Revenue model [UNCERTAIN]:** Simple percentage of application subscription and API fees.

**Performance specifications [UNCERTAIN]:** Described as targeting sub-second response for simple queries; longer background reasoning jobs handled asynchronously.

### Shard Architecture: QBRAIN Shard [UNCERTAIN — initial draft]

**Purpose:** Decentralized quantum computing network integrated with ASI:Chain. Creates quantum-secure consensus and makes quantum computation available to AI and DeFi applications.

**Unique consensus mechanism — Quantum Proof-of-Useful Work (QPoUW):** Validators generate value through performing useful quantum computations rather than solving arbitrary proof-of-work puzzles.

**Verification via Meta-Predictor:** Classical verification of quantum advantage is fundamentally difficult. QBRAIN bypasses this by using the Meta-Predictor market for verification — a market-based approach to assessing whether quantum computations provide real advantage.

**Initial hardware [UNCERTAIN — 2026–2028 roadmap]:**
- Entry level: Dirac3 photonic processors (~$300,000/unit or ~$1,000/hour cloud access).
- Advanced: NISQ (Noisy Intermediate-Scale Quantum) devices.
- Hardware pooling options for shared access.

**Year 1 tasks (2026–2027) [UNCERTAIN]:** Quantum machine learning kernels, quantum random number generation, small Variational Quantum Eigensolvers (VQE).
**Year 2 tasks (2027–2028) [UNCERTAIN]:** QAOA optimization, quantum neural network training, quantum sampling.

**MeTTa-Q [UNCERTAIN — 2028 target]:** A quantum-optimized type system for MeTTa. Initial quantum AI libraries use standard MeTTa with a planned transition to MeTTa-Q.

### Shard Architecture: BGI Nexus Shard [UNCERTAIN — initial draft]

**Purpose:** Democratic compute coordination shard for collectively beneficial purposes. Combines NuNet's decentralized compute framework with reputation-weighted Cordial Miners consensus.

**Key innovation:** Democratic task selection. Network members vote on computational priorities based on earned reputation — not stake or token weight. The system is designed to evolve toward computations that demonstrably benefit humanity.

**Reputation components:**
- Compute Contribution (Rc): Based on verified compute provided.
- Voting Participation (Rv): Based on active participation in governance.
- Proposal Quality (Rp): Based on quality of task proposals.
- Impact Verification (Ri): Based on verified real-world impact of completed tasks.

**Task selection algorithm:** Benefit scoring weights tasks by collective beneficial impact, available resources, and reputation-weighted votes. Dynamic reallocation shifts resources as impact assessments update.

**Design goal:** Create emergent alignment between individual contribution and collective progress — participants benefit personally precisely when they contribute to collectively beneficial outcomes.

**Byzantine fault tolerance:** Maintained across heterogeneous hardware with intermittent connectivity, enabling global participation.

---

## Key Terms

**ASI:Chain:** Layer 1 blockchain runtime designed for decentralized AGI deployment. Capable of native inference settlement.
**F1R3FLY:** Concurrent sharded blockchain engine powering ASI:Chain, grounded in Rholang process calculus.
**MeTTaCycle:** AGI execution engine on ASI:Chain. Compiles and runs Hyperon cognitive workloads.
**Rholang:** Reflective Higher-Order Process Calculus underlying F1R3FLY's concurrency model.
**BlockDAG:** Directed Acyclic Graph of blocks enabling thousands of parallel non-conflicting processes.
**Casper CBC:** Current real-time consensus mechanism for shard validators.
**Casanova:** [UNCERTAIN] Next-generation consensus to replace Casper in mature shards.
**Cordial Miners:** Background consensus for compute providers; reputation-weighted variant used in most shards.
**Omega Shard:** [UNCERTAIN draft] AGI frontier research shard targeting HLAGI and ASI development.
**Qwestor Shard:** [UNCERTAIN draft] Neural-symbolic DePIN shard supporting Qwestor and Qwello applications.
**Qwestor (app):** Persistent AI personality with memory, growth, and symbolic reasoning.
**Qwello (app):** Streamlined research engine built on Qwestor Shard infrastructure.
**QBRAIN:** [UNCERTAIN draft] Quantum computing shard with Quantum Proof-of-Useful Work.
**QPoUW:** Quantum Proof-of-Useful Work — QBRAIN consensus mechanism generating value via quantum computation.
**Dirac3:** Photonic quantum processor used as entry-level QBRAIN hardware.
**MeTTa-Q:** [UNCERTAIN — 2028] Quantum-optimized type system for MeTTa.
**BGI Nexus:** [UNCERTAIN draft] Democratic compute coordination shard for collectively beneficial computation.
**NuNet:** Decentralized compute framework that BGI Nexus builds upon.
**Meta-Predictor:** Market-based shard used to verify intelligence contributions and quantum computations.
**HLAGI:** Human-Level AGI — the development milestone Omega Shard is specifically designed to support.
**DePIN:** Decentralized Physical Infrastructure Network — the model used by Qwestor for hardware participation.
**Intelligence settlement:** ASI:Chain's claimed capability to verify cognitive state transitions natively on-chain.
**Inference settlement:** Synonym for intelligence settlement.

---

## Common Questions

**What is ASI:Chain?** ASI:Chain is a blockchain designed specifically for AGI. Unlike Ethereum or Bitcoin, it is built to handle the massively parallel, graph-based workloads of artificial general intelligence. It verifies AI reasoning steps (cognitive state transitions) natively on-chain, not just token transfers.

**What is F1R3FLY?** F1R3FLY is the computational engine underneath ASI:Chain. It uses a formal mathematical model (Rholang process calculus) to enable thousands of AI processes to run in parallel without bottleneck. Think of it as the execution fabric that makes ASI:Chain an AI supercomputer rather than a financial ledger.

**What is MeTTaCycle?** MeTTaCycle is the AGI-specific execution layer on ASI:Chain. It takes validated instructions from F1R3FLY and runs Hyperon cognitive workloads — managing knowledge synthesis, semantic operations, and reasoning across the network.

**Does OmegaClaw require ASI:Chain?** No. ASI:Chain can run on a single machine, a private network, or the public chain. ASI:Chain deployment is required when auditability, multi-party execution, or decentralized governance is needed — but not for all local or private deployments.

**What is the Omega Shard?** [UNCERTAIN — initial draft] The Omega Shard is a specialized section of ASI:Chain reserved for the most advanced AGI research. It runs both fast real-time consensus (for urgent queries) and slow deep-compute background processing (for autonomous research and self-improvement experiments). It targets development of human-level AGI.

**What is Qwestor?** Qwestor is a product running on the Qwestor Shard — a persistent AI personality with memory and growth capability. The shard it runs on handles the neural-symbolic reasoning infrastructure behind it.

**What is QBRAIN?** [UNCERTAIN — initial draft] QBRAIN is a shard that brings quantum computing into the ASI:Chain ecosystem. It lets quantum hardware providers contribute computation and get rewarded, while AI and DeFi applications access quantum capabilities via the network.

**What is the BGI Nexus Shard?** [UNCERTAIN — initial draft] BGI Nexus coordinates distributed computation for collectively beneficial purposes. Unlike most networks where token weight determines governance, BGI Nexus uses reputation earned through beneficial contribution to govern which computational tasks the network prioritizes.

**What consensus mechanism does ASI:Chain use?** Different parts of the ecosystem use different mechanisms: Casper CBC for real-time validation by staked validators, and Cordial Miners for background compute providers. A transition to Casanova is described as planned [UNCERTAIN] when Casanova matures.

**How do shards connect to each other?** Shards interoperate: Omega delegates subtasks to Qwestor and QBRAIN; QBRAIN uses Meta-Predictor for verification; BGI Nexus integrates NuNet's compute framework. Cross-shard task delegation is built into the architecture.

---

## Known Limits

This file does not cover: Hyperon cognitive algorithms (→ KB-01). Tokenomics and shard economics (→ KB-03). AGI timelines and societal strategy (→ KB-04). Consciousness theory (→ KB-05). Ethical ontology (→ KB-06). Human-AI design patterns (→ KB-07).

All four shard papers are initial rough drafts. Treat shard-specific tokenomics, hardware specifications, consensus transitions, and timelines as design proposals subject to significant revision. Do not present as deployed systems.

---

## Change Log

- 2026-04-09 — Initial creation. Sources: hyperon.md (ASI:Chain section, 2025–2026), Omega-Shard-WP.pdf (Sept 2025 draft), Qwestor-Shard-WP.pdf (Sept 2025 draft), QBRAIN-WP.pdf (Sept 2025 draft), BGI-Nexus-Shard-draft.pdf (Sept 2025 draft). All shard WPs explicitly marked "initial rough version" in source documents.
