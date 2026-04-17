# KB-01: Hyperon Technical Stack

**scope:** Everything about the Hyperon AGI platform — MeTTa language, Atomspace/MORK/DAS knowledge representations, cognitive algorithms (PLN, ECAN, MOSES, MetaMo, SubRep, TransWeave), PRIMUS architecture, and the OmegaClaw agent profile.
**excludes:** ASI:Chain / shard deployment architecture (→ KB-02); ethical and motivational philosophy (→ KB-06); tokenomics and economics (→ KB-03).

**confidence:** High for documented components. Medium for roadmap items and prototype-stage systems. Items marked [UNCERTAIN] are explicitly under development or not yet validated.
**last_updated:** 2026-04-09
**primary_sources:** hyperon.md (merged from Hyperon Master Index '26 and Hyperon for AGI→ASI Technical Whitepaper 2025), Action-Ontology.pdf, AGI-25-METAMO-Two.pdf (partial draft)

---

## Core Concepts

**Hyperon** is SingularityNET's AGI technology stack. It provides a unified platform where neural, symbolic, and evolutionary cognitive processes operate on a shared knowledge substrate. The central design principle is that diverse AI modes — reasoning, learning, attention, motivation, self-modification — must interact directly on shared memory rather than through narrow translation APIs.

**The Atomspace** is the universal cognitive substrate. Every piece of information — facts, rules, neural weights, goals, control signals, executable programs — exists as an Atom inside it. Code and data are interchangeable. Pattern matching, inference, learning, and self-modification happen simultaneously on the same structures. The Atomspace is typed and content-addressed: every Atom has a unique content-derived ID (CID) enabling automatic deduplication and cryptographic provenance.

**MeTTa (Meta-Type Talk)** is the native programming language for Hyperon AGI. It is simultaneously a cognitive calculus, a logic programming language, and a self-modifying inference engine. Programs are themselves Atoms inside the Atomspace — this homoiconic property enables deep self-reference. MeTTa acts as a lingua franca allowing neural networks, probabilistic reasoners, and evolutionary systems to interoperate. It runs as a non-deterministic inference engine enabling parallel search over the metagraph.

**MORK (MeTTa Optimized Reduction Kernel)** is the high-performance in-memory hypergraph engine underlying the Atomspace. It organizes data as trie-map (radix tree) structures, enabling near-instant pattern matching and logic operations — speedups of thousands to millions of times over previous implementations. Current scale: 500M+ atoms in RAM. Writers submit changes as atomic deltas; readers always see consistent state. Weighted Atom Sweeps (WAS) provide probabilistic sampling for attention scheduling.

**DAS (Distributed AtomSpace)** is the large-scale distributed counterpart to MORK. It operates as a distributed knowledge management system over massive mutable hypergraphs stored in MongoDB/Redis backends. DAS separates Long-Term Importance (persistent distributed storage) from Short-Term Importance (high-speed RAM attention), governed by an Attention Broker that prevents combinatorial explosion during inference.

**OmegaClaw Agent** is an agent evolving toward AGI through dynamic orchestration of the Hyperon stack. OmegaClaw is not a separate theory from Hyperon — it is a specific agent-driven deployment that uses MeTTa as orchestration language, Atomspace/MORK/DAS as cognitive memory, ECAN/PLN/MOSES/MetaMo as cognitive functionality, and ASI:Chain for auditable decentralized runtime where needed.

---

## Current State

### MeTTa Implementations

Three active implementations exist at different maturity levels:

**Hyperon-Experimental** is the original reference implementation, built in Rust with deep Python integration. It prioritizes flexibility and semantic correctness over raw execution speed. It is appropriate for R&D but not yet production-grade. 2026 roadmap includes Prolog VM integration, Python packages for Windows, and improved variable binding representation.

**PeTTa** is a high-performance compiler-runtime for MeTTa. It translates MeTTa into optimized Prolog via a Smart Dispatch compiler that resolves at compile time whether code is a function or data. Achieves execution speeds comparable to handwritten Prolog. Fully adheres to Hyperon-Experimental semantics. Suitable for production symbolic reasoning workloads (robotics, large-scale inference).

**MeTTaTron** is the F1R3FLY-native MeTTa compiler. It compiles MeTTa to MeTTa-IL for execution on the ASI:Chain stack. It is the bridge from MeTTa source programs to distributed blockchain-native execution. [UNCERTAIN — maturity level not fully specified in available sources]

**MeTTa-IL** is the compiler intermediate representation based on Graph-Structured Lambda Theory (GSLT). It makes program semantics explicit and typed when crossing system boundaries. Logic for local reasoning is lowered into MORK; logic requiring global consensus is lowered into F1R3FLY's distributed path.

**PyMeTTa** [UNCERTAIN — under development] is a Python-compatible dialect that transpiles to MeTTa-IL. Intended to enable notebook-based development with full semantic guarantees.

### Knowledge Representation Architecture

The MORK architecture has four layers. The Graph DB Layer uses in-memory hypergraph triemaps for efficient expression matching. MORKL is the declarative query language for MORK, using S-expression syntax optimized for trie structures. MM2 (Minimal MeTTa 2) is the low-level dataflow language for performance-critical components, using the Gather-Process-Scatter paradigm with explicit control flow. The Zipper Abstract Machine (ZAM) is the multi-threaded runtime executing MM2 dataflows using cursor-based (zipper) navigation.

The Space API defines a universal interface so cognitive processes see all backends (MORK Spaces, DAS, Neural Spaces, Rholang Spaces) as uniform.

### Cognitive Algorithms

**ECAN (Economic Attention Networks)** manages which Atoms are actively considered during reasoning. Each Atom carries Short-Term Importance (STI, immediate context-relevance) and Long-Term Importance (LTI, historical utility). STI propagates through Hebbian-weighted associative links. A recent enhancement [UNCERTAIN — whitepaper framing] models attention as an incompressible fluid optimally controlled toward goal-relevant regions, with Weighted Atom Sweeps implementing this on MORK.

**PLN (Probabilistic Logic Networks)** is the primary symbolic reasoning system. It represents beliefs with graded confidence and supports deductive, inductive, and abductive reasoning under uncertainty. PLN operates over Atomspace via forward- and backward-chaining inference, calling ECAN to filter to high-salience working memory. The 2025 incarnation uses [UNCERTAIN] quantale-annotated factor graphs where logical structure and uncertainty travel together as messages, with geodesic control guiding chaining.

**MeTTa-NARS (Non-Axiomatic Reasoning System)** handles open-ended reasoning under the Assumption of Insufficient Knowledge and Resources (AIKR). Uses two-dimensional evidence values (frequency and confidence) rather than binary truth. Designed for open-world scenarios with scarce, inconsistent data.

**NACE (Non-Axiomatic Causal Explorer)** is a causal learning agent that overcomes data inefficiency of deep reinforcement learning. It builds a logic-based environment model by observing direct consequences of actions, using curiosity-driven exploration with intrinsic uncertainty-reduction rewards.

**MOSES / GEO-EVO** is the evolutionary program generation engine. It breeds compact, interpretable symbolic programs. It uses Elegant Normal Form (ENF) to collapse functionally equivalent programs to canonical form. GEO-EVO adds bidirectional guidance (forward from current capabilities, backward from desired outcomes). Programs live in Atomspace as typed structures other components can inspect and modify. The weakness prior [UNCERTAIN — see GLOSSARY] biases toward simpler programs.

**MetaMo** is the motivational framework for open-ended intelligent agents. It models motivation as a dynamical system coupling appraisal processes (evaluating situations for salience, risk, opportunity) with decision processes (selecting actions, allocating resources). Motivational state is represented as goal intensities plus modulatory variables (valence, arousal, risk sensitivity). A pseudo-bimonad structure [UNCERTAIN — formal development ongoing] couples appraisal (comonad, OpenPsi) and decision (monad, MAGUS). Stability enforced via contractive update dynamics. Every decision has an associated audit trail.

**SubRep (Subgoal Representation)** [UNCERTAIN — research-stage] provides certified subgoal learning. It enables safe decomposition of high-level goals into verifiable subgoals, with formal guarantees about what can be learned.

**TransWeave** [UNCERTAIN — research-stage] enables compositional knowledge transfer with formal bounds on transfer degradation. It measures retargeting difficulty — how hard it is to move an intelligent system from one goal trajectory to another. Programs successful in one domain transfer across domains with bounded degradation, using a weakness-geometry framework to identify compatible semantic structure.

**Semantic Parsing** is the neural-symbolic bridge between natural language and Atomspace. It converts language inputs into grounded atoms via SENF (Semantic Elegant Normal Form), which collapses varied phrasings of the same fact into a canonical graph representation.

**AI-DSL (AI Domain Specific Language)** assembles complex AI workflows from discrete services on SingularityNET/ASI marketplaces. It uses a MeTTa-based backward chainer treating user requests as theorems and available AI services as axioms. Uses combinatory logic (Bluebird, Phoenix combinators) for tractability.

### PRIMUS Cognitive Architecture

PRIMUS is Hyperon's proposed configuration of layers viewed as likely to give rise to AGI. It uses three representational regimes with different dynamics: fast perceptual encoding, slower symbolic manipulation, and long-horizon planning. Spaces decomposition separates working cognitive spaces. Evidence anchoring ties abstract representations to grounded observations. Bridging operators connect symbolic and subsymbolic representations. Multi-rate dynamics run different cognitive loops at different timescales.

The Action-Ontology supplement clarifies PRIMUS world modeling through Turchin's framework: state is treated as an affordance distribution (not a point), objects are defined as invariants under cognitive action (not intrinsic properties), and modeling schemes R and {Ma} describe hierarchical memory and time.

### QuantiMORK

[UNCERTAIN — proposed architecture] QuantiMORK enables native neural computation within the metagraph itself by representing tensors and neural weights as atoms. This reduces the boundary between symbolic and neural processing, enabling the metagraph to serve simultaneously as symbolic reasoning substrate and neural parameter store.

---

## Key Terms

**Atom:** The fundamental unit of the Atomspace. Can represent a concept, relation, neural weight, goal, rule, or program.
**Atomspace:** The shared typed metagraph where all Hyperon cognitive processes operate. Code and data are interchangeable.
**MORK:** High-performance in-memory trie-based hypergraph engine. Supports 500M+ atoms in RAM.
**DAS:** Distributed AtomSpace for large-scale distributed hypergraph storage with attention brokering.
**MeTTa:** Native AGI programming language for Hyperon. Homoiconic, non-deterministic, reflective.
**PeTTa:** High-performance MeTTa compiler targeting Prolog for production symbolic reasoning.
**MeTTaTron:** F1R3FLY-native MeTTa compiler for ASI:Chain-aligned execution.
**MeTTa-IL:** Compiler intermediate representation; bridge between MeTTa source and runtime execution paths.
**ECAN:** Attention allocation system using STI/LTI to focus cognitive resources.
**PLN:** Probabilistic Logic Networks — graded-confidence reasoning over Atomspace.
**NARS / MeTTa-NARS:** Non-Axiomatic Reasoning System for open-world reasoning under incomplete knowledge.
**NACE:** Non-Axiomatic Causal Explorer — causal environment modeling agent.
**MOSES / GEO-EVO:** Evolutionary program synthesis with bidirectional search guidance.
**MetaMo:** Motivational framework treating goal-updating as a stable dynamical system.
**OpenPsi:** Appraisal comonad implementing the appraisal side of MetaMo.
**MAGUS:** Decision monad implementing the decision side of MetaMo.
**SubRep:** [UNCERTAIN] Certified subgoal learning with formal decomposition guarantees.
**TransWeave:** [UNCERTAIN] Knowledge transfer framework with bounded degradation guarantees.
**PRIMUS:** Proposed cognitive architecture configuration for AGI.
**QuantiMORK:** [UNCERTAIN] Native neural-symbolic computation within the metagraph.
**OmegaClaw:** The AGI agent built atop the Hyperon stack.
**SENF:** Semantic Elegant Normal Form — canonical representation for language parsed into Atomspace.
**Weakness prior:** Bias toward simpler, more general programs — see GLOSSARY for quantale formalization.
**ENF:** Elegant Normal Form — MOSES's canonical program representation to collapse equivalent programs.
**ZAM:** Zipper Abstract Machine — MORK's multi-threaded concurrent runtime for MM2 execution.
**STI / LTI:** Short-Term and Long-Term Importance — ECAN's attention scalars on each Atom.

---

## Common Questions

**What is Hyperon?** Hyperon is SingularityNET's AGI technology platform. It integrates symbolic reasoning, probabilistic inference, neural learning, and evolutionary search on a shared knowledge substrate called the Atomspace. Unlike systems built by scaling neural networks alone, Hyperon is designed for general intelligence through neurosymbolic integration.

**What is MeTTa?** MeTTa is a programming language designed specifically for AGI. Programs written in MeTTa are themselves stored inside the Atomspace (homoiconic), enabling the system to inspect and rewrite its own code at runtime. MeTTa acts as a lingua franca for diverse AI subsystems to communicate and collaborate.

**What is the Atomspace?** The Atomspace is the shared knowledge substrate where all cognitive activity in Hyperon occurs. Every fact, rule, neural weight, goal, and program is an Atom inside it. Code and data are the same type of object, making the system's own logic queryable and improvable.

**What is MORK?** MORK is the high-performance in-memory database powering the Atomspace. It organizes information as trie-maps (radix trees), enabling extremely fast pattern matching. It currently supports over 500 million atoms in RAM.

**What is PLN?** PLN (Probabilistic Logic Networks) is Hyperon's reasoning system. Unlike classical logic, PLN assigns graded confidence to beliefs and supports deductive, inductive, and abductive reasoning under uncertainty. It lets Hyperon draw conclusions even when information is incomplete or noisy.

**What is ECAN?** ECAN is Hyperon's attention system. Since reasoning over the full Atomspace at once is computationally intractable, ECAN tracks which atoms are most relevant right now (STI) and historically useful (LTI), and focuses cognitive resources on a manageable relevant subset.

**What is MetaMo?** MetaMo is Hyperon's motivational framework. It models how an AGI agent's goals and priorities can evolve over time while remaining stable, coherent, and interpretable. Rather than fixed reward functions, it treats motivation as a dynamical system with formal stability guarantees.

**What is TransWeave?** TransWeave is a framework [UNCERTAIN — research stage] for measuring and enabling knowledge transfer between domains. It provides formal bounds on how much performance degrades when a learned capability is applied in a new context.

**What is OmegaClaw?** OmegaClaw is an AGI agent under development that orchestrates the Hyperon stack — MeTTa for cognitive calculus, Atomspace for memory, ECAN/PLN/MOSES/MetaMo for cognition, ASI:Chain for auditable runtime.

**What is SubRep?** SubRep [UNCERTAIN — research stage] is a system for learning subgoals with formal certification. It lets the agent safely decompose complex goals into achievable intermediate steps with verifiable guarantees.

**What is PRIMUS?** PRIMUS is Hyperon's proposed cognitive architecture — a specific configuration of the stack (perception, symbolic manipulation, planning, attention, motivation) believed capable of giving rise to AGI.

**How does OmegaClaw relate to Hyperon?** OmegaClaw is not separate from Hyperon — it is an agent-driven deployment of the Hyperon stack. Where Hyperon describes the platform and components, OmegaClaw describes a specific agent-oriented orchestration of those components.

---

## Known Limits

This file does not cover: ASI:Chain shard architecture and deployment (→ KB-02). Tokenomics and economic models (→ KB-03). AGI societal strategy and timelines (→ KB-04). Consciousness theory and wu-wei frameworks (→ KB-05). MeTTaSoul ethical ontology and moral reasoning (→ KB-06). Human-AI design patterns (→ KB-07). Technical depths of F1R3FLY and MeTTaCycle (→ KB-02). Quantum computing applications (→ KB-02, QBRAIN section).

Roadmap items (QuantiMORK, PyMeTTa, SubRep full implementation, TransWeave validation) are [UNCERTAIN] — implementation maturity is uneven. Do not present these as deployed capabilities.

---

## Change Log

- 2026-04-09 — Initial creation. Sources: hyperon.md (merged Hyperon Master Index '26 + Hyperon for AGI→ASI WP 2025), Action-Ontology.pdf (2026, Goertzel), AGI-25-METAMO-Two.pdf (2025 draft, Lian & Goertzel).
