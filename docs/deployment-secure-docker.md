# Secure Docker Compose Deployment

This guide deploys OmegaClaw with security layers that prevent the
autonomous agent from directly accessing API keys, with an optional
restricted network mode for full isolation.

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
│  │   Internet: direct (default) or        │                  │
│  │             proxied-only (restricted)   │                  │
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

**Layer 3 — Network isolation (restricted mode only).** In restricted mode,
the agent container sits on a Docker internal network with no route to the
internet. It can only reach `llm-proxy` and `irc-proxy`, both of which bridge
internal and external networks.

## Prerequisites

- Docker Engine 24+ with Compose V2
- An API key for your chosen LLM provider (Anthropic, OpenAI, or ASI Cloud)

## Quick Start (default — full network)

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

API keys are held by the proxy — the agent container never receives them.
The agent has full outbound internet access for web search, RAG, and
Agentverse integrations.

### Verify key isolation

```bash
# Should show LLM_PROXY_URL and OMEGACLAW_AUTH_SECRET only — no API keys
docker compose exec omegaclaw env

# Double-check /proc/self/environ
docker compose exec omegaclaw sh -c "cat /proc/self/environ | tr '\0' '\n' | sort"
```

## Restricted Mode (no direct internet)

To run the agent with no direct internet access — only able to reach the
LLM and IRC proxies:

```bash
docker compose -f docker-compose.restricted.yml up -d
```

In this mode, features like DuckDuckGo search, Tavily agents, Agentverse
integrations, and web scraping are not available unless their endpoints are
explicitly allowlisted (see below).

## Network Allowlist (restricted mode)

In restricted mode the agent can only reach services on the Docker internal
network. To grant access to specific external domains, add them as proxy
pass-throughs. There are two approaches depending on whether you need HTTP(S)
or raw TCP.

### Option A — Add an nginx location (HTTP/HTTPS endpoints)

Edit `proxy/nginx.conf.template` and add a `location` block inside the
`server` section:

```nginx
location /tavily/ {
    proxy_pass https://api.tavily.com/;
    proxy_set_header Host api.tavily.com;
    proxy_ssl_server_name on;
    proxy_ssl_protocols TLSv1.2 TLSv1.3;
    proxy_http_version 1.1;
}
```

If the endpoint requires an API key, add the key variable to
`proxy/entrypoint.sh` and pass it as an environment variable to `llm-proxy`
in `docker-compose.restricted.yml`:

```yaml
# in docker-compose.restricted.yml, under llm-proxy.environment:
- TAVILY_API_KEY=${TAVILY_API_KEY:-}
```

```nginx
# in the nginx location block:
proxy_set_header Authorization "Bearer ${TAVILY_API_KEY}";
```

Then rebuild the proxy:

```bash
docker compose -f docker-compose.restricted.yml up -d --build llm-proxy
```

The agent reaches the endpoint via `http://llm-proxy:8080/tavily/...` — no
direct internet required.

### Option B — Add a socat service (raw TCP endpoints)

For non-HTTP services, add a new socat relay service in
`docker-compose.restricted.yml`:

```yaml
services:
  custom-proxy:
    build:
      context: ./proxy
      dockerfile: Dockerfile.socat
    environment:
      - IRC_UPSTREAM_HOST=example.com
      - IRC_UPSTREAM_PORT=443
    networks:
      - internal
      - external
    restart: unless-stopped
```

Add `custom-proxy` to the omegaclaw service's `depends_on` list, then
configure the agent to connect to `custom-proxy:<port>` instead of the
external host directly.

### Verifying the allowlist

```bash
# From inside the agent container, confirm the proxy is reachable:
docker compose -f docker-compose.restricted.yml exec omegaclaw \
  wget -qO- http://llm-proxy:8080/tavily/

# Confirm direct internet is still blocked:
docker compose -f docker-compose.restricted.yml exec omegaclaw \
  wget -qO- http://example.com   # should fail with "network unreachable"
```

## Feature Availability by Mode

| Feature              | Default | Restricted |
|----------------------|:-------:|:----------:|
| IRC chat             | yes     | yes        |
| LLM inference        | yes     | yes        |
| API keys hidden      | yes     | yes        |
| DuckDuckGo search    | yes     | allowlist  |
| Tavily agent search  | yes     | allowlist  |
| Agentverse agents    | yes     | allowlist  |
| Web scraping / RAG   | yes     | allowlist  |

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
   this. For `provider=OpenAI`, the default full-network mode handles this
   naturally. In restricted mode, add `OPENAI_API_KEY` to the agent's
   environment in a compose override.

2. **Mattermost**: Connects directly to `chat.singularitynet.io` over
   HTTPS/WSS. Works in default mode. In restricted mode, add a proxy entry
   for `chat.singularitynet.io`.

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

# For restricted mode:
docker compose -f docker-compose.restricted.yml down
```

## Backward Compatibility

The existing `scripts/omegaclaw` single-container deployment still works. When
`LLM_PROXY_URL` is not set, `lib_llm_ext.py` falls back to reading API keys
from environment variables (and clears them after reading via
`os.environ.pop`).
