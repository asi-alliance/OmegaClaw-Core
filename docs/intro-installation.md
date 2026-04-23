# Installation

OmegaClaw supports two setups: the recommended Docker one-liner and a manual MeTTa install.

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

All runtime parameters are listed in [reference-configuration.md](./reference-configuration.md).
