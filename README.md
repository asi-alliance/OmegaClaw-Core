# OmegaClaw

<p align="center">
  <img src="./omegaclaw-logo-SoD_g_nX.png" alt="OmegaClaw logo" width="220" />
</p>



---

## Overview

OmegaClaw is an agentic AI system implemented in **MeTTa**.

Beyond basic tool use, it features **embedding-based long-term memory** represented entirely in **MeTTa AtomSpace** format.

Long-term memory is deliberately maintained by the agent through:

- `(remember string)` for adding memory items
- `(query string)` for querying related memories

The agent can learn and apply **new skills** and **declarative knowledge** through the use of memory items.

In addition, an initial set of **OpenClaw-like tools** is implemented, including:

- web search
- file modification
- communication channels
- access to the operating system shell and its associated tools

Simplicity of design, ease of prototyping, ease of extension, and transparent implementation in MeTTa were the primary design criteria.

The lean agent core comprises approximately **200 lines of code**.

---

## Special Features

### Token-efficient agentic loop

OmegaClaw uses a **token-efficient agentic loop**, enabling low-cost long-term operation and embodiment in domains that require real-time learning and decision-making.

### Flexible memory representation

The agent can learn to represent its memories in different ways, including forms that allow other Hyperon components to operate on the same memories within the same AtomSpace. Each memory item is stored as a triplet (timestamp, atom, embedding) yet the agent remains flexible in choosing the specific representation. Consequently, the agent is not hardcoded to any particular memory representation, and different formats can co-exist in the same atom space.

Each memory item is stored as a triplet:

`(timestamp, atom, embedding)`

---

## Quick Start - IRC Channel

Create a Docker container to run your own OmegaClaw on an IRC channel you specify.

Requirement: Docker

OmegaClaw can be installed and started with:
```bash
curl -fsSL https://raw.githubusercontent.com/asi-alliance/OmegaClaw-Core/refs/heads/main/scripts/omegaclaw_setup.sh | bash -s -- omegaclaw:<version>
```
When prompted, enter your OpenAI API key and a unique IRC channel name, then interact with your OmegaClaw at [webchat.quakenet.org](https://webchat.quakenet.org) or any IRC portal. 

When done interacting with your OmegaClaw, please use these commands as needed:

| Action | Command |
|--------|---------|
| Stop OmegaClaw | `docker stop omegaclaw` |
| Restart OmegaClaw | `docker start omegaclaw` |
| View logs | `docker logs -f omegaclaw` |

Your OmegaClaw will retain its memory for subsequent restarts.

---

## Full Installation


First, get [SWI-Prolog](https://www.swi-prolog.org/Download.html). Then:

```
git clone https://github.com/trueagi-io/PeTTa
cd PeTTa
mkdir -p repos && git clone https://github.com/asi-alliance/OmegaClaw-Core.git repos/mettaclaw
```

**Usage**

Run the system via the following command which ensures the system is started from the root folder of PeTTa:

```
cp repos/mettaclaw/run.metta ./
OPENAI_API_KEY=... sh run.sh run.metta
```
