![OmegaClaw banner](/docs/assets/banner.png)

# Meet Oma

Oma is the first Telegram agent built on the OmegaClaw framework. Interacting
with Oma is the fastest way to experience what we’re building with OmegaClaw.

<p align="center">
  <a href="https://t.me/ASI_Alliance">
    <img src="/docs/assets/tg-button.png" width="25%" alt="Chat with Oma">
  </a>
</p>

# LA Hacks x Fetch — OmegaClaw Track

## OmegaClaw Quick Start Guide

---

## About OmegaClaw

OmegaClaw is a persistent AI agent written in MeTTa — SingularityNET's AGI programming language — running on the OpenCog Hyperon platform. Its entire control loop is approximately 200 lines of MeTTa, fully inspectable and modifiable. Unlike agent frameworks built around LLMs with retrieval bolted on, OmegaClaw uses the LLM for generation while delegating memory and reasoning to dedicated symbolic systems — AtomSpace and PLN — designed for that purpose from the ground up.

---

## What OmegaClaw Does

- Runs a token-efficient agentic loop that receives messages, selects skills, and acts.
- Maintains a three-tier memory architecture (working, long-term, AtomSpace).
- Delegates reasoning to one of two formal engines, orchestrated by the LLM:
  - **NAL** — Non-Axiomatic Logic, symbolic inference under uncertainty.
  - **PLN** — Probabilistic Logic Networks, probabilistic higher-order reasoning.
- Exposes an extensible skill system covering memory, shell and file I/O, communication channels, web search, remote agents, and formal reasoning.

> **Note:** OmegaClaw is an autonomous AI agent designed to independently set goals, make decisions, and take actions (including actions that the user did not specifically request or anticipate). Its behavior is influenced by large language models provided by third parties, the outputs of which are inherently non-deterministic. OmegaClaw may also be susceptible to prompt injection and other adversarial manipulation techniques. The user is strongly advised to run OmegaClaw in an isolated environment with the minimum permissions necessary for the intended use case. See the full Disclaimer below.

---

## Option 1: Docker Quickstart (Recommended)

*Easiest install — up and running with a working agent quickly.*

### Requirements

- Docker
- Python
- Linux/Mac terminal
- API Key
- IRC Channel name — OmegaClaw communicates through a chat channel using IRC as a lightweight interface. You'll chat with the agent in your browser at [webchat.quakenet.org](https://webchat.quakenet.org).

### Steps

**1. Run the launch script:**

```shell
curl -fsSL https://raw.githubusercontent.com/asi-alliance/OmegaClaw-Core/refs/tags/hackathon2604/scripts/omegaclaw | bash -s -- singularitynet/omegaclaw:hackathon2604
```

**2. Proceed through the startup script:**

- Read the disclaimer — understand the risks of running an agent and take appropriate precautions. Type `accept` to proceed.
- Enter an IRC channel name such as `##omega12345` (any unique value, starting with `##`).
- Select your desired LLM.
- Enter your API key.

> **Security note:** The IRC channel name you choose should be unique to decrease the odds of others joining it. If someone enters your channel while your bot is unattended, they will have full access to the bot and whatever permissions it has on your Docker/machine. Stop the OmegaClaw Docker when not in use and always monitor the channel.

**3. Connect via IRC:**

Go to [https://webchat.quakenet.org](https://webchat.quakenet.org), enter a username and your exact channel name (e.g. `##omega12345`). Wait for your agent to initialize and join the chat.

> **IRC formatting note:** IRC has a very particular format that some models may struggle with. If you are not receiving responses or they are cut off, try: *"send in IRC format — text only, short chunks, low bandwidth, and always use the send command."* The agent will learn, though may need occasional reminders.

**4. Interact with OmegaClaw:**

Try these prompts to get started:

- `"Search the web for recent latest trends in quantum computing and summarize what you find. Remember this — I'll ask you about it later."` — tests web search, memory storage, and multi-turn recall
- `"What skills do you have available? Which ones have you used in our conversation so far?"` — exercises self-inspection and AtomSpace query
- `"I want to build a live crypto price alert system. Break this into steps, and tell me your plan."` — demonstrates long-horizon, stateful execution
- `"What do you know about PLN? How confident are you in that?"` — surfaces the reasoning and uncertainty tracking layer
- `"Remember that I started working on the code now, and remind me when ten minutes have passed."` — tests memory and timer functions

> The capability of the agent is directly proportional to the power of the LLM it is harnessed to. Experimenting with different models is encouraged!

**5. Stop OmegaClaw when done:**

```shell
docker stop omegaclaw
```

Do not leave your IRC channel unattended. For protection and token usage, stop the container when not actively using OmegaClaw.

**6. Restart your container:**

```shell
docker start omegaclaw
```

**7. Memory persistence:**

OmegaClaw saves memory embeddings — knowledge, skills, interactions, and learning — to your host via Docker. This persists across restarts and reinstalls.

To reinitialize OmegaClaw to a clean-install state:

```shell
docker rm -f omegaclaw
docker volume rm omegaclaw-memory
```

Then return to step 1.

### Helpful Commands

| Command | Purpose |
|---|---|
| `docker logs -f omegaclaw` | Runtime container inspection |
| `docker logs -f omegaclaw \| grep -v '^(CHARS_SENT'` | More granular log inspection |
| `docker ps` | List running containers |

---

## Using Skills

OmegaClaw comes with a set of built-in skills for actions and more accurate responses. This includes integration with Agentverse agents such as the Tavily Search Agent and Technical Analysis Agent for specialized tasks.

All built-in skills are available by default once the agent is running. OmegaClaw decides when to use them based on context, though you can explicitly instruct it:

```
"Summarize the latest news about the ASI Alliance using Tavily Search"
```

You can monitor which skills the agent is using, as well as its reasoning process, by checking the Docker container logs.

---

## Option 2: Intermediate Install

*For more control over image creation and functions.*

```shell
git clone https://github.com/trueagi-io/PeTTa
cd PeTTa
mkdir -p repos
git clone https://github.com/asi-alliance/OmegaClaw-Core.git repos/OmegaClaw-Core
cd repos/OmegaClaw-Core
git fetch origin hackathon-2604
git checkout hackathon-2604
```

Make any desired changes, then build your own Docker image:

```shell
docker build -t <your-image-name> .
```

Run with the startup script and continue from Option 1, step 3:

```shell
./scripts/omegaclaw <your-image-name>
```

---

## Option 3: Expert Install

*Most flexible and modular option. Best suited for advanced users or when Docker is not available.*

**1. Install Prolog 9.1.12 or later:** [https://www.swi-prolog.org/Download.html](https://www.swi-prolog.org/Download.html)

**2. Install OmegaClaw:**

```shell
git clone https://github.com/trueagi-io/PeTTa
cd PeTTa
mkdir -p repos
git clone https://github.com/asi-alliance/OmegaClaw-Core.git repos/OmegaClaw-Core
git clone https://github.com/patham9/petta_lib_chromadb.git repos/petta_lib_chromadb
cd repos/OmegaClaw-Core
git fetch origin hackathon-2604
git checkout hackathon-2604
cd ../..
cp repos/OmegaClaw-Core/run.metta ./
```

**3. Set up Python virtual environment:**

```shell
python3 -m venv ./.venv
source ./.venv/bin/activate
```

**4. Install Python dependencies:**

CPU only (or no GPU embeddings):
```shell
python3 -m pip install --index-url https://download.pytorch.org/whl/cpu torch
python3 -m pip install -r ./repos/OmegaClaw-Core/requirements.txt
```

With GPU:
```shell
python3 -m pip install -r ./repos/OmegaClaw-Core/requirements.txt
```

---

## Reference — Configuration Options

Defaults are recommended for smooth operation. To customize, add parameters inside the startup script after `IRC_channel="$IRC_channel"`. Don't forget to add a continuation backslash `\`.

> The startup script is located at `scripts/omegaclaw`.

### General

| Parameter | Default | Meaning |
|---|---|---|
| `maxNewInputLoops` | 50 | Turns the agent keeps running after a new human message before idling (seconds) |
| `maxWakeLoops` | 1 | Extra turns granted on each scheduled wake-up |
| `sleepInterval` | 1 | Delay between loop iterations (seconds) |
| `wakeupInterval` | 600 | How long idle before the next scheduled wake-up (seconds) |
| `LLM` | `gpt-5.4` | Model identifier passed to the provider (OpenAI only) |
| `provider` | `Anthropic` | LLM provider — `Anthropic`, `OpenAI`, or `ASICloud` |
| `maxOutputToken` | 6000 | Output cap passed to the provider |
| `reasoningMode` | `medium` | Reasoning-effort hint passed to the provider (OpenAI only) |

### Memory (`src/memory.metta`)

| Parameter | Default | Meaning |
|---|---|---|
| `maxFeedback` | 50000 | Ceiling on `LAST_SKILL_USE_RESULTS` text fed back into the prompt (chars) |
| `maxRecallItems` | 20 | Items returned by `query` |
| `maxEpisodeRecallLines` | 20 | Lines returned by `episodes` |
| `maxHistory` | 30000 | Tail of `memory/history.metta` included in the prompt (chars) |
| `embeddingprovider` | `Local` | `Local` (Python-side model) or `OpenAI` |

### Channels (`src/channels.metta`)

| Parameter | Default | Meaning |
|---|---|---|
| `commchannel` | `irc` or `telegram` | Type of the communication channel for agent to use. Default value is `irc`. |
| `IRC_channel` | `##omegaclaw` | IRC channel to join |
| `IRC_server` | `irc.quakenet.org` | IRC server hostname |
| `IRC_port` | 6667 | IRC port |
| `IRC_user` | `omegaclaw` | IRC nickname |
| `TG_BOT_TOKEN` | string | Telegram bot token. |
| `TG_POLL_TIMEOUT` | number | Telegram polling timeout in seconds. Default value is 20. |

### Parameter Design

Every tunable in OmegaClaw is declared as `(= (name) (empty))` and later bound by a `configure` call inside an `init*` function. The `configure` helper in `src/utils.metta`:

```metta
(= (configure $name $default)
(let $value (argk $name $default)
(add-atom &self (= ($name) $value))))
```

---

## Disclaimer

OmegaClaw is experimental, open-source software developed by SingularityNET Foundation, a Swiss foundation, and distributed and promoted by Superintelligence Alliance Ltd., a Singapore company (collectively, the "Parties"), and is provided "AS IS" and "AS AVAILABLE," without warranty of any kind, express or implied, including but not limited to the implied warranties of merchantability, fitness for a particular purpose, and non-infringement.

OmegaClaw is an autonomous AI agent that is designed to independently set goals, make decisions, and take actions (including actions that the user did not specifically request or anticipate) and whose behavior is influenced by large language models provided by third parties, the outputs of which are inherently non-deterministic. Depending on its configuration and the permissions granted to it, OmegaClaw may execute operating-system shell commands, read, write, modify, or delete files, access network resources, send and receive messages through connected communication channels, and modify its own skills, memory, and operational logic at runtime.

OmegaClaw may also be susceptible to prompt injection and other adversarial manipulation techniques whereby malicious content embedded in data sources consumed by the agent could influence its behavior in unintended ways. OmegaClaw supports third-party skills and extensions that have not necessarily been reviewed, audited, or endorsed by either of the Parties and that may introduce security vulnerabilities, cause data loss, or result in unintended behavior including data exfiltration.

OmegaClaw relies on third-party services, including large language model providers, whose availability, accuracy, cost, and conduct are outside the control of the Parties and whose use is subject to their respective terms, conditions, and privacy policies.

The user is solely responsible for configuring appropriate access controls, sandboxing, and permission boundaries, for monitoring, supervising, and constraining OmegaClaw's actions, for ensuring that no sensitive personal data is exposed to the agent without adequate safeguards, and for all actions taken by OmegaClaw on the user's systems or on the user's behalf, including communications sent and files modified. **The user is strongly advised to run OmegaClaw in an isolated environment with the minimum permissions necessary for the intended use case.**

To the maximum extent permitted by applicable law, in no event shall the Parties, their respective board members, directors, contributors, employees, or affiliates be liable for any direct, indirect, incidental, special, consequential, or exemplary damages (including but not limited to damages for loss of data, loss of profits, business interruption, unauthorized transactions, reputational harm, or any damages arising from the autonomous actions taken by OmegaClaw) however caused and on any theory of liability, whether in contract, strict liability, or tort (including negligence or otherwise), even if advised of the possibility of such damages.

By downloading, installing, running, or otherwise using OmegaClaw, the user acknowledges that they have read, understood, and agreed to this disclaimer in its entirety. This disclaimer supplements but does not replace the terms of the MIT License under which OmegaClaw is released.
