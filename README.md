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
- `(episodes time)` for retrieving episodes around a point in time

Additionally the agent has an episodic trace for observations, tool usage record, and self-created working working memory items:

- `(pin string)` for adding a message to itself to its episodic trace

The agent can follow multistep operations effectively by pinning, and learn and apply **new skills** and **knowledge** through the use of memory items.

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

Requirement: Docker

OmegaClaw can be installed and started with:
```bash
curl -fsSL https://raw.githubusercontent.com/asi-alliance/OmegaClaw-Core/refs/heads/main/scripts/omegaclaw_setup.sh | bash -s -- singularitynet/omegaclaw:latest
```
When prompted, enter your OpenAI API key and a unique IRC channel name, then interact with your OmegaClaw at [webchat.quakenet.org](https://webchat.quakenet.org) or any IRC portal. 

### Channel authentication

At startup, the setup script prints a **one-time secret**.

To activate message handling, send this command in your channel exactly once:

```text
auth <one-time-secret>
```

The first user who sends the correct secret becomes the authenticated user.
All messages from other users are silently ignored.

When done interacting with your OmegaClaw, please use these commands as needed:

| Action | Command |
|--------|---------|
| Stop OmegaClaw | `docker stop omegaclaw` |
| Restart OmegaClaw | `docker start omegaclaw` |
| View logs | `docker logs -f omegaclaw` |

Your OmegaClaw will retain its memory for subsequent restarts.
