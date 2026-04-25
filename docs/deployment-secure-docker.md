# Secure Docker Compose Deployment

This guide deploys OmegaClaw with three security layers that prevent the
autonomous agent from accessing or exfiltrating API keys.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    external network (internet)               │
│                                                              │
│  ┌───────────┐  IRC         ┌──────────────┐  HTTPS          │
│  │ irc-proxy │──TCP──────▸  │  llm-proxy   │──TLS────────▸   │
│  │ (socat)   │  server      │  (nginx)     │  LLM APIs       │
│  └─────┬─────┘              └──────┬───────┘                 │
└────────┼───────────────────────────┼─────────────────────────┘
┌────────┼───────────────────────────┼─────────────────────────┐
│        │    internal network       │                         │
│  ┌─────┴───────────────────────────┴──────┐                  │
│  │            omegaclaw                   │                  │
│  │   NO API keys in environment           │                  │
│  │   NO direct internet access            │                  │
│  └────────────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

**Layer 1 — LLM proxy sidecar.** An nginx reverse proxy holds all API keys.
The agent sends LLM requests to `http://llm-proxy:8080` with a dummy
credential. The proxy strips it, injects the real key, and forwards over TLS
to the upstream provider. The agent process never sees the real key.

**Layer 2 — Environment variable clearing.** As defense in depth (and for
backward-compatible direct-run mode), Python code uses `os.environ.pop()` to
read secrets once and immediately remove them from the process environment.

**Layer 3 — Network isolation.** The agent container sits on a Docker internal
network with no route to the internet. It can only reach `llm-proxy` and
`irc-proxy`, both of which bridge internal and external networks.

## Prerequisites

- Docker Engine 24+ with Compose V2
- An API key for your chosen LLM provider (Anthropic, OpenAI, or ASI Cloud)

## Quick Start (restricted mode)

```bash
cd OmegaClaw-Core

# 1. Create your .env from the template
cp .env.example .env

# 2. Edit .env — set your API key, IRC channel, and auth secret
#    Generate a secret:  openssl rand -base64 24
nano .env

# 3. Build and start
docker compose up -d

# 4. Check logs
docker compose logs -f omegaclaw
```

The agent will connect to your IRC channel via the proxy. Authenticate with
`auth <your-secret>` in the channel as usual.

### Verify key isolation

```bash
# Should show LLM_PROXY_URL and OMEGACLAW_AUTH_SECRET only — no API keys
docker compose exec omegaclaw env

# Double-check /proc/self/environ
docker compose exec omegaclaw sh -c "cat /proc/self/environ | tr '\0' '\n' | sort"
```

## Full-Network Mode (web search, RAG, Agentverse)

To give the agent direct internet access (required for DuckDuckGo search,
Tavily agents, and Agentverse integrations):

```bash
docker compose -f docker-compose.yml -f docker-compose.full-network.yml up -d
```

API keys remain hidden in the proxy even in full-network mode — this only
opens outbound networking from the agent container.

## Feature Availability by Mode

| Feature              | Restricted | Full-network |
|----------------------|:----------:|:------------:|
| IRC chat             | yes        | yes          |
| LLM inference        | yes        | yes          |
| API keys hidden      | yes        | yes          |
| DuckDuckGo search    | —          | yes          |
| Tavily agent search  | —          | yes          |
| Agentverse agents    | —          | yes          |
| Web scraping / RAG   | —          | yes          |

## Configuration Reference

All settings are in `.env`. See `.env.example` for the full list.

| Variable              | Required | Description |
|-----------------------|----------|-------------|
| `ANTHROPIC_API_KEY`   | *        | Anthropic API key (set for `provider=Anthropic`) |
| `ASI_API_KEY`         | *        | ASI Cloud API key (set for `provider=ASICloud`) |
| `OPENAI_API_KEY`      | *        | OpenAI API key (set for `provider=OpenAI`) |
| `PROVIDER`            |          | LLM provider: `Anthropic`, `OpenAI`, `ASICloud` (default: `Anthropic`) |
| `EMBEDDING_PROVIDER`  |          | `Local` or `OpenAI` (default: `Local`) |
| `IRC_CHANNEL`         |          | IRC channel name (default: `##omegaclaw`) |
| `IRC_SERVER`          |          | Upstream IRC server for the proxy (default: `irc.quakenet.org`) |
| `IRC_PORT`            |          | Upstream IRC port (default: `6667`) |
| `OMEGACLAW_AUTH_SECRET` |        | Channel auth secret (generate with `openssl rand -base64 24`) |

\* Set the key for your chosen provider. Others can be left blank.

## Known Limitations

1. **OpenAI provider**: The `useGPT` function in PeTTa's `lib_llm` (outside
   this repo) reads `OPENAI_API_KEY` directly. The proxy cannot intercept
   this. For `provider=OpenAI`, use full-network mode and add
   `OPENAI_API_KEY` to the agent's environment in a compose override.

2. **Mattermost**: Connects directly to `chat.singularitynet.io` over
   HTTPS/WSS. Requires full-network mode.

3. **`git-import!` at startup**: `run.metta` calls `git-import!` for repos
   already present in the Docker image. PeTTa skips cloning when the
   directory exists. If it attempts a `git fetch`, this will fail harmlessly
   in restricted mode.

## Stopping and Cleaning Up

```bash
# Stop all services
docker compose down

# Stop and remove volumes (deletes agent memory)
docker compose down -v
```

## Backward Compatibility

The existing `scripts/omegaclaw` single-container deployment still works. When
`LLM_PROXY_URL` is not set, `lib_llm_ext.py` falls back to reading API keys
from environment variables (and clears them after reading via
`os.environ.pop`).
