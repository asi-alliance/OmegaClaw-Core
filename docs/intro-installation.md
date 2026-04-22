# Installation

OmegaClaw supports two setups: the recommended Docker one-liner and a manual MeTTa install.

## Option A — Docker (recommended)

Requirements: Docker.

```bash
curl -fsSL https://raw.githubusercontent.com/asi-alliance/OmegaClaw-Core/refs/heads/main/scripts/omegaclaw_setup.sh \
  | bash -s -- singularitynet/omegaclaw:latest
```

The script prompts for:

- an LLM API key (OpenAI by default)
- a unique IRC channel name

and prints a one-time secret used to authenticate the first IRC user. See [tutorial-01-first-run.md](./tutorial-01-first-run.md) for the full first-run walkthrough.

Container management:

| Action | Command |
|---|---|
| Stop | `docker stop omegaclaw` |
| Restart | `docker start omegaclaw` |
| View logs | `docker logs -f omegaclaw` |

Memory persists across restarts because `memory/history.metta` and the ChromaDB store are kept in the container volume.

## Option B — Manual

Requirements: a working MeTTa / Hyperon install, Python 3, and the Python dependencies pulled in by `lib_llm_ext.py`, `src/agentverse.py`, `channels/*.py`, and the ChromaDB bridge.

1. Clone the repository.
2. Export any required API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) depending on the `provider` you choose in `src/loop.metta`.
3. Run:

```bash
metta run.metta
```

Command-line overrides follow `argk` convention (`key=value`), e.g.:

```bash
metta run.metta provider=Anthropic LLM=claude-opus-4-6
```

## Environment variables and API keys

Which variables you need depends on which LLM provider, embedding provider, and channel you select. The default `provider` in `src/loop.metta` is **Anthropic**.

### LLM provider keys

Set one key, matching the `provider` you configure:

| `provider` value | Env var | Notes |
|---|---|---|
| `Anthropic` (default) | `ANTHROPIC_API_KEY` | Claude models via the Anthropic API. |
| `OpenAI` | `OPENAI_API_KEY` | GPT models. Also reused by the OpenAI embedding provider below. |
| `ASICloud` | `ASI_API_KEY` | ASI Alliance inference endpoint (`inference.asicloud.cudos.org`), currently routes to MiniMax models. The variable name is deliberately `ASI_API_KEY` — not `ASI_KEY` or `ASICLOUD_API_KEY`. |
| `ASIOne` | `ASIONE_API_KEY` | Fetch.ai inference endpoint (`https://api.asi1.ai/v1`), currently routes to ASI1 model. The variable name is `ASIONE_API_KEY`. |

Only the variable for your selected `provider` is required; the others can be unset.

### Embedding provider keys

Set via `embeddingprovider` in `src/memory.metta`:

| `embeddingprovider` value | Env var | Notes |
|---|---|---|
| `Local` | *(none)* | Uses `intfloat/e5-large-v2` through `sentence_transformers`. Downloaded on first run. |
| `OpenAI` | `OPENAI_API_KEY` | Reuses the same key as the OpenAI LLM provider. |

### Channel keys

| Channel | Env var | Notes |
|---|---|---|
| IRC | *(none required)* | Connects anonymously to QuakeNet. Optional `OMEGACLAW_AUTH_SECRET` gates who the agent treats as its owner. |
| Mattermost | `MM_BOT_TOKEN` | Set via `configure` or directly in `src/channels.metta`. |

### Docker setup script

`scripts/omegaclaw_setup.sh` (invoked by the Docker one-liner above) asks which provider you want, writes the chosen key into the container's runtime config, and auto-pairs the embedding provider: `Anthropic → Local`, `OpenAI → OpenAI`, `ASICloud → Local`, `ASIOne → Local`. You don't need to set anything manually when using Docker.

All runtime parameters are listed in [reference-configuration.md](./reference-configuration.md).
