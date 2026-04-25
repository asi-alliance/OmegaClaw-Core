# Secure Docker Compose Deployment

This guide deploys OmegaClaw with a reverse proxy that hides API keys from
the agent container. An optional restricted mode adds full network isolation.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    external network (internet)               │
│                                                              │
│  ┌───────────┐              ┌──────────────┐  HTTPS          │
│  │ irc-proxy │  TCP         │  llm-proxy   │──TLS────────▸   │
│  │ (socat)   │──────────▸   │  (nginx)     │  LLM + other    │
│  └─────┬─────┘              └──────┬───────┘  APIs            │
└────────┼───────────────────────────┼─────────────────────────┘
┌────────┼───────────────────────────┼─────────────────────────┐
│        │    internal network       │                         │
│  ┌─────┴───────────────────────────┴──────┐                  │
│  │            omegaclaw                   │                  │
│  │   NO API keys in environment           │                  │
│  │   Default: full internet access        │                  │
│  │   Restricted: proxy-only access        │                  │
│  └────────────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

**Layer 1 — Reverse proxy.** An nginx reverse proxy holds all API keys.
The agent sends requests to `http://llm-proxy:8080/<path>` without
credentials. The proxy injects the real key and forwards over TLS. The
agent process never sees API keys.

**Layer 2 — Environment variable clearing.** As defense in depth, Python
channel code uses `os.environ.pop()` to read the owner secret once and
immediately remove it from the process environment.

**Layer 3 — Network isolation (restricted mode only).** The agent container
sits on a Docker internal network with no route to the internet. It can
only reach proxy services that bridge internal and external networks.

## Prerequisites

- Docker Engine 24+ with Compose V2
- An API key for your chosen LLM provider (Anthropic, OpenAI, or ASI Cloud)

## Quick Start (default — full network)

```bash
cd OmegaClaw-Core

# 1. Create your .env from the template
cp .env.example .env

# 2. Edit .env — set your API key, channel config, and owner secret
#    Generate a secret:  openssl rand -base64 24
nano .env

# 3. Build and start
docker compose up -d

# 4. Check logs
docker compose logs -f omegaclaw
```

The agent has full outbound internet access for web search, RAG, and
third-party integrations. API keys are still hidden in the proxy.

### Verify key isolation

```bash
# Should show LLM_PROXY_URL and OMEGACLAW_OWNER_SECRET only — no API keys
docker compose exec omegaclaw env

# Double-check /proc/self/environ
docker compose exec omegaclaw sh -c "cat /proc/self/environ | tr '\0' '\n' | sort"
```

## Restricted Mode (no direct internet)

To run the agent with no direct internet access:

```bash
# In .env, set IRC_SERVER=irc-proxy so the agent routes through the proxy
docker compose -f docker-compose.restricted.yml up -d
```

In this mode the agent can only reach services on the Docker internal
network (llm-proxy, irc-proxy). IRC works via irc-proxy once `IRC_SERVER`
is pointed at it in `.env`. Other channels and external services require
allowlisting (see below).

All three compose files share service definitions via `extends` from
`docker-compose.base.yml`, so configuration changes only need to be made
in one place.

## Network Allowlist (restricted mode)

In restricted mode the agent has no internet. To grant access to specific
external endpoints, add them as proxy pass-throughs.

### Option A — Add an nginx location (HTTP/HTTPS endpoints)

This works for any REST API: Telegram, Tavily, Agentverse, Mattermost, etc.

1. Add a `location` block in `proxy/nginx.conf.template`:

```nginx
location /telegram/ {
    proxy_pass https://api.telegram.org/;
    proxy_set_header Host api.telegram.org;
    proxy_ssl_server_name on;
    proxy_ssl_protocols TLSv1.2 TLSv1.3;
    proxy_http_version 1.1;
}
```

If the endpoint needs an API key, add the variable to
`docker-compose.restricted.yml` under `llm-proxy.environment`:

```yaml
- TAVILY_API_KEY=${TAVILY_API_KEY:-}
```

Then use it in the nginx location:

```nginx
proxy_set_header Authorization "Bearer ${TAVILY_API_KEY}";
```

The proxy entrypoint auto-detects new `${VAR}` references in the template —
no changes to `entrypoint.sh` are needed.

2. Rebuild the proxy:

```bash
docker compose -f docker-compose.restricted.yml up -d --build llm-proxy
```

### Option B — Add a socat service (raw TCP endpoints)

For non-HTTP protocols (IRC, raw WebSocket, etc.), add a socat relay
service in `docker-compose.restricted.yml`:

```yaml
services:
  mm-proxy:
    build:
      context: ./proxy
      dockerfile: Dockerfile.socat
    environment:
      - IRC_UPSTREAM_HOST=chat.singularitynet.io
      - IRC_UPSTREAM_PORT=443
    networks:
      - internal
      - external
    restart: unless-stopped
```

Add the new service to omegaclaw's `depends_on`, then point the agent at
the proxy hostname instead of the real server.

### Verifying the allowlist

```bash
# Confirm the proxy endpoint is reachable from the agent:
docker compose -f docker-compose.restricted.yml exec omegaclaw \
  wget -qO- http://llm-proxy:8080/health

# Confirm direct internet is still blocked:
docker compose -f docker-compose.restricted.yml exec omegaclaw \
  wget -qO- http://example.com   # should fail
```

## Communication Channels

OmegaClaw supports multiple communication channels. Set `COMM_CHANNEL` in
`.env` to your choice and fill in the corresponding config.

| Channel      | `COMM_CHANNEL` | Required config                                        | Restricted mode                          |
|--------------|----------------|--------------------------------------------------------|------------------------------------------|
| IRC          | `irc`          | `IRC_CHANNEL`                                          | Works via irc-proxy (included)           |
| Telegram     | `telegram`     | `TG_BOT_TOKEN`                                         | Needs proxy for `api.telegram.org`       |
| Mattermost   | `mattermost`   | `MM_URL`, `MM_CHANNEL_ID`, `MM_BOT_TOKEN`              | Needs proxy for your Mattermost server   |

Future channels (Discord, Signal, Slack, etc.) follow the same pattern:
add the channel's config vars to `.env`, pass them through in the compose
`command` section, and — for restricted mode — add a proxy entry.

### Owner authentication

When `OMEGACLAW_OWNER_SECRET` is set, the agent requires the owner to send
`auth <secret>` as their first message. The first user who authenticates
becomes the sole accepted sender. This works identically across all channels.

## Feature Availability by Mode

| Feature              | Default | Restricted  |
|----------------------|---------|-------------|
| Chat (any channel)   | yes     | allowlist   |
| LLM inference        | yes     | yes         |
| API keys hidden      | yes     | yes         |
| DuckDuckGo search    | yes     | allowlist   |
| Tavily agent search  | yes     | allowlist   |
| Agentverse agents    | yes     | allowlist   |
| Web scraping / RAG   | yes     | allowlist   |

"allowlist" = works after adding a proxy entry (see above). IRC is
pre-configured via irc-proxy in the restricted compose file.

## Configuration Reference

All settings are in `.env`. See `.env.example` for the full list.

| Variable               | Required | Description                                              |
|------------------------|----------|----------------------------------------------------------|
| `ANTHROPIC_API_KEY`    | *        | Anthropic API key (set for `provider=Anthropic`)         |
| `ASI_API_KEY`          | *        | ASI Cloud API key (set for `provider=ASICloud`)          |
| `OPENAI_API_KEY`       | *        | OpenAI API key (set for `provider=OpenAI`)               |
| `PROVIDER`             |          | LLM provider (default: `Anthropic`)                      |
| `EMBEDDING_PROVIDER`   |          | `Local` or `OpenAI` (default: `Local`)                   |
| `COMM_CHANNEL`         |          | `irc`, `telegram`, or `mattermost` (default: `irc`)      |
| `OMEGACLAW_OWNER_SECRET` |       | Owner auth secret (`openssl rand -base64 24`)            |
| `IRC_CHANNEL`          |          | IRC channel name                                         |
| `IRC_SERVER`           |          | Upstream IRC server (default: `irc.quakenet.org`)        |
| `IRC_PORT`             |          | Upstream IRC port (default: `6667`)                      |
| `TG_BOT_TOKEN`         |          | Telegram bot token                                       |
| `TG_POLL_TIMEOUT`      |          | Telegram polling timeout in seconds (default: `20`)      |
| `MM_URL`               |          | Mattermost server URL                                    |
| `MM_CHANNEL_ID`        |          | Mattermost channel ID                                    |
| `MM_BOT_TOKEN`         |          | Mattermost bot token                                     |

\* Set the key for your chosen provider. Others can be left blank.

## Adding a New API Key to the Proxy

To route a new external API through the proxy (hiding its key from the agent):

1. Add the key to `.env`
2. Add a `location` block in `proxy/nginx.conf.template` using `${YOUR_KEY}`
3. Pass the variable to `llm-proxy` in the compose `environment` section
4. Rebuild: `docker compose up -d --build llm-proxy`

The proxy entrypoint auto-detects `${VAR}` references in the nginx
template, so no changes to `proxy/entrypoint.sh` are needed.

## Known Limitations

1. **OpenAI provider**: The `useGPT` function in PeTTa's `lib_llm` reads
   `OPENAI_API_KEY` directly. The proxy cannot intercept this. In default
   mode this works naturally. In restricted mode, add `OPENAI_API_KEY` to
   the agent's environment in a compose override.

2. **Mattermost WebSocket**: Mattermost uses HTTPS and WSS. In default mode
   this works directly. In restricted mode, add a proxy entry for your
   Mattermost server.

3. **`git-import!` at startup**: `run.metta` calls `git-import!` for repos
   present in the Docker image. PeTTa skips cloning when the directory
   exists. If it attempts a `git fetch`, this fails harmlessly in restricted
   mode.

## Stopping and Cleaning Up

```bash
# Default mode
docker compose down
docker compose down -v          # also removes volumes (agent memory)

# Restricted mode
docker compose -f docker-compose.restricted.yml down
docker compose -f docker-compose.restricted.yml down -v
```

## Backward Compatibility

The `scripts/omegaclaw` and `scripts/omegaclaw_hackathon` single-container
deployments still work. When `LLM_PROXY_URL` is not set, `lib_llm_ext.py`
falls back to reading API keys from environment variables (and clears them
after reading via `os.environ.pop`).
