# OmegaClaw

<p align="center">
  <img src="./omegaclaw-logo-SoD_g_nX.png" alt="OmegaClaw logo" width="220" />
</p>



---

## Documentation & Demo

Full documentation lives in [`docs/`](./docs/README.md): introduction, tutorials, and API reference as a flat set of markdown files.

Preview a live demo of OmegaClaw running in --Coming Soon!--

---

## Overview

OmegaClaw is a **hybrid agentic AI framework** implemented in MeTTa on OpenCog Hyperon. A large language model (LLM) works together with persistant memory in queryable format and formal logic engines — **NAL** and **PLN** — to remember its experiences, reason about the world, track uncertainty, combine evidence, and produce conclusions that are mathematically grounded rather than just plausible-sounding.

The core agent loop is approximately **200 lines of MeTTa**.

>Most AI assistants generate answers that sound right. OmegaClaw-hosted agents generate answers that come with a **mathematical receipt** showing exactly how confident each conclusion is and what evidence supports it. When the agent says it is 72% confident, that number comes from formal inference — not a feeling.

- OmegaClaw operates via a **continuous, stateful execution loop**, rather than a rigid stateless request-response model. By utilizing active memory "pins", the architecture allows the system to maintain a stable internal state and drive long-horizon, interleaved workflows without requiring a human prompt to trigger every step.
- Memory is stored as **knowledge graph that can reason**, not just retrieve. Rather than storing facts as flat text, AtomSpace structures knowledge as typed, relational atoms — meaning OmegaClaw can query its own memory symbolically, not just semantically. This is the difference between operating on a history of compressed context window, and reasoning over a web of meaning.
- Through direct access to its own execution traces and stored memories, OmegaClaw can observe and reflect on its own reasoning processes. This early-stage **metacognition** provides a level of structural transparency and self-auditing rarely found in standard agentic systems.

---

## What OmegaClaw does

- Runs a token-efficient agentic loop that receives messages, selects skills, and acts.
- Maintains a **three-tier memory** architecture (working, long-term, AtomSpace).
- Delegates reasoning to one of two formal engines, orchestrated by the LLM:
  - **NAL** — Non-Axiomatic Logic, symbolic inference under uncertainty.
  - **PLN** — Probabilistic Logic Networks, probabilistic higher-order reasoning.
  - ONA (OpenNARS for Applications) is a planned third engine but is **not installed by default** — see [reference-lib-ona.md](./reference-lib-ona.md) for the current experimental status.
- Exposes an extensible **skill system** covering memory, shell and file I/O, communication channels, web search, remote agents, and formal reasoning.

---

## The hybrid thesis

### Two kinds of reasoning, one pipeline

| Aspect | LLM (neural) | Formal engine (symbolic) |
|---|---|---|
| Natural language understanding | ✅ | ❌ |
| Premise formulation from text | ✅ | ❌ |
| Inference orchestration (which rule when) | ✅ | ❌ |
| Truth-value propagation | ❌ | ✅ |
| Confidence decay through chains | ❌ | ✅ |
| Formal contradiction detection | ❌ | ✅ |
| Auditable conclusion path | ❌ | ✅ |

The LLM turns ambiguous natural language into structured atoms with explicit truth values. The formal engine takes those atoms and applies rules whose truth-value arithmetic is deterministic and auditable.

When the agent outputs a conclusion, you can trace it back through every step: which premises fed into which rule, what truth value each premise carried, and what the math produced.

---

## About

OmegaClaw agentic AI system implemented in MeTTa, guided by the MeTTaClaw proposal from Ben Goertzel, and an agent core inspired by Nanobot.
Beyond basic tool use, it features embedding-based long-term memory represented entirely in MeTTa AtomSpace format.

Long-term memory is deliberately maintained by the agent via `(remember string)` for adding memory items and `(query string)` for querying related memories.
The agent can learn and apply new skills and declarative knowledge through the use of memory items.

In addition, an initial set of OpenClaw-like tools is implemented, including web search, file modification, communication channels, and access to the operating system shell and its associated tools. Additionally two Fetch.ai Agentverse tools, Tavily Search and Technical Research, are featured in its toolset.

Simplicity of design, ease of prototyping, ease of extension, and transparent implementation in MeTTa were the primary design criteria.

The following example demonstrates learning and decision-making in a textually represented grid-world environment adapted from [NACE](https://github.com/patham9/NACE):

![mettaclaw_in_nace_world](https://github.com/user-attachments/assets/c6c01839-234d-4505-baf6-4f2f3787c7b9)


This project also aims to explore the potential of Agentic Physical AI, a ROS2 package for mobile robots with manipulators is underway.

**Installation**

Prerequisites: Git, Python3, Pip and [venv](https://docs.python.org/3/library/venv.html) library

First, get [SWI-Prolog](https://www.swi-prolog.org/). Then:
```
git clone https://github.com/trueagi-io/PeTTa
cd PeTTa
mkdir -p repos
git clone https://github.com/asi-alliance/OmegaClaw-Core.git repos/OmegaClaw-Core
git clone https://github.com/patham9/petta_lib_chromadb.git repos/petta_lib_chromadb
python3 -m venv ./.venv
source ./.venv/bin/activate
python3 -m pip install -r
cp repos/OmegaClaw-Core/run.metta ./
```

**Usage**

Before running the system you need to choose your LLM API provider and export the API key as the environment variable.
| Provider | Env var name | Notes |
|---|---|---|
| `Anthropic` (default) | `ANTHROPIC_API_KEY` | Claude models via the Anthropic API. |
| `OpenAI` | `OPENAI_API_KEY` | GPT models. Also reused by the OpenAI embedding provider below. |
| `ASICloud` | `ASI_API_KEY` |  MiniMax models via ASI Alliance inference endpoint (`inference.asicloud.cudos.org`). |

Run the system via the following command which ensures the system is started from the root folder of PeTTa:
```
OMEGACLAW_AUTH_SECRET=<channel-secret> sh run.sh run.metta IRC_channel="<irc-channel>"
```
After start go to https://webchat.quakenet.org/ to communicate with the agent. Join `<irc-channel>` and after agent is joined send `auth <channel-secret>` message to authenticate yourself as an agent owner. Please replace `<irc-channel>` and `<channel-secret>` by your own values.

The full list of the `run.metta` optinos
| Option | Value | Description |
|---|---|---|
| `provider` | `Anthropic`, `OpenAI` or `ASICloud` | The name of the LLM API provider. The corresponding API token should be exported as an environment variable (see the table above). Default value is `Anthropic` |
| `IRC_channel` | `"#some_channel_name"` | Name of the channel on [QuakeNet IRC server](https://webchat.quakenet.org/) which agent will connect to. In order to make agent talk only to the owner the `OMEGACLAW_AUTH_SECRET` environment variable is used. After agent is joined to the channel send `auth <secret>` message for the authentication. For example if `OMEGACLAW_AUTH_SECRET=12345` then one need sending `auth 12345`. |
| `embeddingprovider` | `Local` or `OpenAI` | The embedding provider to use for the memory. `Local` uses [sentence-transformers](https://pypi.org/project/sentence-transformers/) library locally. `OpenAI` requires `OPENAI_API_KEY` and uses OpenAI embedding API. |

**Illustrations**

Long-Term Memory Recall:

<img width="638" height="125" alt="image" src="https://github.com/user-attachments/assets/0d4817ed-e743-4e44-8bd4-a10e27ea6380" />

Tool use:

<img width="1323" height="188" alt="image" src="https://github.com/user-attachments/assets/18ef19c4-010a-4c94-84ce-bb49277dccfc" />

Shell output of the actual invocation of the generated MeTTa code:

<img width="416" height="486" alt="image" src="https://github.com/user-attachments/assets/f5b27205-cdb2-47e7-821a-ffd93b3dd7c6" />

System also added it into its Atom Space storage (embedding vector omitted):

<img width="379" height="69" alt="image" src="https://github.com/user-attachments/assets/6aa59deb-33b4-42b9-a535-ae153b4b7a18" />







