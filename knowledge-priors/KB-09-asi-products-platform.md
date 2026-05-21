# KB-09: ASI Alliance Products — ASI:One, ASI:Create, ASI:Cloud

**scope:** The three primary ASI Alliance joint products: ASI:One (unified AI interface and web app), ASI:Create (AI agent launchpad and creation platform), and ASI:Cloud (decentralized GPU compute infrastructure).
**excludes:** ASI Alliance overview and token merger (→ KB-08); developer tools like Agentverse, uAgents, and ASI Network (→ KB-10); Hyperon/ASI:Chain technical stack (→ KB-01, KB-02).

**confidence:** Medium — all three products are actively developing. ASI:Cloud launched December 2025. ASI:Create is in closed alpha. ASI:One is actively updated. All feature details should be verified with [CHECK LIVE] sources.
**last_updated:** 2026-04-09
**primary_sources:** Web research April 2026, superintelligence.io, ASI Alliance blogs

---

## Core Concepts

These three products represent the consumer-facing and developer-facing output of the ASI Alliance. They form what the Alliance calls the **ASI Innovation Stack**: a layered set of tools enabling anyone to interact with AI agents (ASI:One), create and launch AI agents (ASI:Create), and run AI workloads on decentralized compute (ASI:Cloud).

The products are designed to interoperate: agents built via ASI:Create can be discovered through ASI:One, and compute-intensive workloads can route through ASI:Cloud. The Agentverse platform (→ KB-10) acts as the underlying agent infrastructure connecting these layers.

---

## Current State

### ASI:One

**What it is:** ASI:One is the unified AI interface and portal for the ASI Alliance ecosystem. It is the primary way end users interact with AI agents across the network. The platform is described as users' "digital lifeline for real-world applications" — a place to discover, interact with, and benefit from the autonomous agents deployed across the Agentverse network.

**ASI-1 Mini:** Fetch.ai introduced ASI-1 Mini, described as the world's first Web3 LLM designed for agentic AI. This model is integrated into ASI:One and is the AI engine behind natural language interaction with registered agents. Unlike general-purpose LLMs, ASI-1 Mini is designed specifically for orchestrating autonomous agents and understanding Web3 contexts.

**Key features (as of early 2026):**
- Natural language interaction with registered AI agents: users type requests in plain English and ASI:One routes to the appropriate agent.
- ASI:One Social: companion and collaboration use cases, social interaction features.
- Location awareness: local results based on user location.
- Preferences area: tune tone and behavior of agent interactions.
- Personality presets: pre-made personality templates or custom configurations.
- Website integration: agent profiles can link to external websites.
- Labs tab: advanced/experimental features open to all users.
- Mobile-optimized: redesigned chat and navigation for mobile.

**Integration with Agentverse:** When you interact via ASI:One, the platform uses the ASI-1 Mini LLM to intelligently map your natural language query to the most relevant registered agent on Agentverse and execute the appropriate function.

**Documentation:** https://docs.asi1.ai/documentation [CHECK LIVE — for latest features and agent directory]

### ASI:Create

**What it is:** ASI:Create is the ASI Alliance's AI agent launchpad — a platform for funding, creating, deploying, and monetizing AI agents. It is designed to democratize AI creation, enabling innovators to bring agent ideas to life without high initial costs or technical barriers.

**Current status [CHECK LIVE]:** As of early 2026, ASI:Create is in Closed Alpha phase. Full public launch and feature rollout are planned through 2025-2026.

**Core capabilities:**
- **Agent creation:** Use templates and pre-built tools to spin up new agents without deep technical knowledge.
- **Crowdfunding:** Developers can crowdfund agent ideas directly from the platform. Community members can back projects they believe in.
- **Monetization:** Deploy agents and monetize them directly via the platform — subscription models, per-use fees.
- **Developer Spaces:** Community hubs fostering growth and collaboration around AI projects.
- **LLM aggregation:** [CHECK LIVE — roadmap item] Access to multiple LLMs from within the platform.
- **IDE integration:** [CHECK LIVE — roadmap item] Planned integration with VS Code and other developer IDEs.

**Who backs it:** ASI:Create is backed by the ASI Alliance — SingularityNET, Fetch.ai, CUDOS, and (formerly) Ocean Protocol.

**Why it matters:** It positions itself as the primary onramp for new AI agent projects entering the decentralized AI economy. Rather than building from scratch on raw APIs, developers can launch, fund, and monetize agents through a structured platform.

**Documentation:** https://docs.superintelligence.io/artificial-superintelligence-alliance/asi-innovation-stack/asi-less-than-create-greater-than/introducing-asi-less-than-create-greater-than [CHECK LIVE — for current alpha access and feature updates]

### ASI:Cloud

**What it is:** ASI:Cloud is the ASI Alliance's decentralized, permissionless GPU compute platform. Built by SingularityNET and CUDOS, it provides access to high-performance AI inference and compute resources without the restrictions (KYC requirements, geographic limitations, vendor lock-in) of centralized cloud providers.

**Launch status:** ASI:Cloud exited beta in December 2025 and began processing live enterprise workloads.

**Core capabilities:**
- **Permissionless access:** Authenticate using Web3 wallets. No KYC required.
- **AI inference endpoints:** OpenAI-compatible endpoints supporting major open-source models including Llama 3.3 70B, Qwen 3 32B, Gemma 3 27B, and others.
- **Low cost:** Pricing starts at $0.07 per million input tokens — significantly lower than AWS, Google Cloud, or Azure equivalents. [CHECK LIVE — pricing may change]
- **Payment flexibility:** Pay in FET/ASI tokens and stablecoins. Fiat payment options planned. [CHECK LIVE]
- **Transparent pricing:** No surprise fees for bandwidth, storage, or data egress — predictable cost structure.
- **GPU access:** Access to GPU clusters for training and inference workloads.
- **Enterprise-grade:** Positioned for production AI workloads at scale, not just experimentation.

**Who builds it:** Co-developed by SingularityNET and CUDOS (the GPU compute infrastructure contributor to the ASI Alliance). CUDOS previously operated its own decentralized compute network which was integrated into ASI:Cloud.

**Target users:** Developers, enterprises, and Web3 builders who need AI compute without centralized provider constraints. Particularly relevant for teams building on ASI:Chain or the Agentverse who need scalable inference.

**Forum/community:** https://community.superintelligence.io/c/compute/18 [CHECK LIVE — for developer discussion, issues, and announcements]

---

## Key Terms

**ASI:One:** The unified AI interface for the ASI Alliance ecosystem. Primary end-user portal for interacting with AI agents via natural language.
**ASI-1 Mini:** The Web3-native LLM developed by Fetch.ai, designed for agentic AI orchestration and integrated into ASI:One.
**ASI:Create:** The AI agent creation and launchpad platform. Enables creating, funding, deploying, and monetizing agents.
**ASI:Create Closed Alpha:** The current (early 2026) limited-access phase of ASI:Create. [CHECK LIVE for access status]
**Developer Spaces:** Community collaboration hubs within ASI:Create for growing AI projects.
**ASI:Cloud:** Decentralized permissionless GPU compute platform. Built by SingularityNET + CUDOS.
**CUDOS:** GPU infrastructure provider and ASI Alliance contributor responsible for ASI:Cloud compute layer.
**OpenAI-compatible endpoints:** ASI:Cloud inference APIs that match the OpenAI API format, enabling easy migration from OpenAI to decentralized compute.
**ASI Innovation Stack:** The Alliance's name for the layered set of products: ASI:Create (build) → Agentverse (deploy/discover) → ASI:One (interact) → ASI:Cloud (compute).
**Web3 LLM:** An LLM designed to understand and operate within Web3 contexts — wallets, tokens, on-chain data, decentralized services. ASI-1 Mini is the first such model.
**Permissionless compute:** Access to compute without requiring identity verification (KYC), allowing global access including from jurisdictions excluded by centralized providers.

---

## Common Questions

**What is ASI:One?** ASI:One is the main interface for interacting with AI agents in the ASI Alliance ecosystem. Think of it as a smart assistant app that understands natural language and routes your request to the best available AI agent across the network.

**What is ASI-1 Mini?** ASI-1 Mini is the world's first Web3-native LLM, created by Fetch.ai and integrated into ASI:One. Unlike GPT-4 or Claude, it is specifically designed for understanding agentic tasks and Web3 contexts. It powers the natural language understanding inside ASI:One.

**What is ASI:Create?** ASI:Create is a platform for building, funding, and launching AI agents. It provides templates, tools, crowdfunding, and monetization in one place. It is currently in closed alpha [CHECK LIVE for access]. Think of it as a cross between a developer IDE, an app store, and a Kickstarter for AI agents.

**What is ASI:Cloud?** ASI:Cloud is the ASI Alliance's decentralized GPU cloud. It launched in December 2025 and offers AI inference at prices significantly lower than AWS or Google Cloud, with no KYC required and payment in crypto or stablecoins. It uses OpenAI-compatible API endpoints so migration from existing providers is straightforward.

**How do ASI:One, ASI:Create, and ASI:Cloud connect?** ASI:Create is where you build agents. Agentverse is where they are hosted and registered. ASI:One is where users discover and interact with those agents in natural language. ASI:Cloud provides the GPU compute that powers inference for agents running on the network.

**Can I use ASI:Cloud without ASI tokens?** Yes — ASI:Cloud accepts stablecoins as well as ASI/FET tokens. Fiat payment options are planned. [CHECK LIVE for current payment options]

**Is ASI:Create free to use?** [CHECK LIVE — alpha access details]. The announced model includes free agent creation tools with monetization options. Check https://docs.superintelligence.io for current access and pricing.

**What models does ASI:Cloud support?** As of December 2025: Llama 3.3 70B, Qwen 3 32B, Gemma 3 27B, and others. [CHECK LIVE — model catalog expands regularly]

---

## Known Limits

This file does not cover: ASI Alliance overview and token (→ KB-08). Developer tools like Agentverse and uAgents (→ KB-10). SingularityNET-specific projects (→ KB-11, KB-12). Community programs (→ KB-13). ASI:Chain blockchain architecture (→ KB-02).

All three products are actively developing. Feature details, pricing, and availability should always be verified with live sources before citing to users. ASI:Create is in closed alpha — access and features change frequently [CHECK LIVE].

---

## Live Data Sources

**Use these for Tier 2 queries about ASI:One, ASI:Create, and ASI:Cloud.**

live_search_queries:
  - "ASI:One latest update features 2026"
  - "ASI:Create alpha access launch date 2026"
  - "ASI:Cloud pricing models inference 2026"
  - "ASI-1 Mini LLM capabilities update"
  - "Artificial Superintelligence Alliance product update"

primary_urls:
  - url: "https://docs.asi1.ai/documentation"
    what: "ASI:One official documentation — latest features and agent directory"
  - url: "https://docs.superintelligence.io/artificial-superintelligence-alliance/asi-innovation-stack/asi-less-than-create-greater-than/introducing-asi-less-than-create-greater-than"
    what: "ASI:Create official documentation"
  - url: "https://superintelligence.io/products/asi-cloud/"
    what: "ASI:Cloud product page and pricing"
  - url: "https://community.superintelligence.io/c/compute/18"
    what: "ASI:Cloud developer community forum"
  - url: "https://fetch.ai/blog"
    what: "Fetch.ai blog — ASI:One and product release notes"

staleness_threshold: weekly
freshness_note: "ASI:One, ASI:Create, and ASI:Cloud are all in active development with frequent updates. For the most current feature list, availability, and pricing, always check the official docs and product pages above."

---

## Change Log

- 2026-04-09 — Initial creation. Sources: web research April 2026 including ASI Alliance official sites, Fetch.ai blog, Chainwire, The Defiant (ASI:Cloud launch Dec 2025).
