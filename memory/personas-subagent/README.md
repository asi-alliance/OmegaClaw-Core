# personas-subagent/ — subagent persona configs

This directory holds **per-deployment** JSON config files that bind a
persona prompt to a provider/model/endpoint. The directory ships
empty upstream (only `.gitkeep`); each deployment provides its own
configs.

Each subagent persona is two files:

- `<key>.json` — provider/model/endpoint binding + tool defaults
- `<persona_file>` — the persona prompt text (referenced by the JSON's
  `persona_file` field)

The directory path is configurable via the
`OMEGACLAW_SUBAGENT_PERSONA_DIR` environment variable. Default:
`memory/personas-subagent/` relative to the OmegaClaw repo root.

## JSON schema

```json
{
  "persona_file":       "prompt-researcher.txt",
  "provider":           "Ollama-local",
  "model":              "qwen2.5-coder:14b",
  "base_url":           "http://localhost:11434/v1",
  "api_key_env":        "OLLAMA_API_KEY",
  "max_output_tokens":  1500,
  "default_tool_subset": ["search", "read-file"],
  "notes": "Researcher subagent — local fast model for fetch/digest."
}
```

| Field | Required | Meaning |
|---|---|---|
| `persona_file` | yes | Path to the persona prompt text. Relative to this directory unless absolute. |
| `provider` | yes | Provider name. Any string the deployment recognizes; e.g. `Anthropic`, `OpenAI`, `Ollama-local`, `DeepSeek`, `OpenRouter`. The dispatcher constructs an OpenAI-compatible client per call; provider name is informational + reused for upstream's `_provider_registry` lookup when applicable. |
| `model` | yes | Model identifier passed to the chat completion call. |
| `base_url` | optional | Endpoint URL override. When present, takes precedence. Lets a deployment point at a specific local Ollama / vLLM / private endpoint without disturbing the parent's provider config. |
| `api_key_env` | yes | Name of the env var that carries the API key. **Never embed key material here** — the dispatcher reads `os.environ[api_key_env]` at dispatch time. |
| `max_output_tokens` | optional, default 1500 | Per-subagent-call output cap. |
| `default_tool_subset` | optional | Tool subset to use when the dispatch call omits the tools argument. The dispatch call's explicit tools argument always overrides. |
| `notes` | optional | Free-form human-readable description. Not consumed by the dispatcher. |

## Security

- Do not commit persona configs that contain real API key material.
  Always reference an env var by name; let the deployment populate
  the env (via `.env`, systemd unit, docker `--env-file`, etc.).
- Do not commit persona prompts containing identifying or private
  information unless your deployment policy permits it.
- The `.gitignore` for this directory should be configured per
  deployment — typically `*.json` and `prompt-*.txt` ignored except
  for example files.

## Example: deploying the bundled researcher persona

The bundled example (`prompt-researcher.txt` + the schema above) is
designed for a local Ollama endpoint. Adapt `provider`, `model`,
`base_url`, and `api_key_env` for your deployment, then:

```bash
export OLLAMA_API_KEY=ollama  # placeholder; Ollama itself doesn't auth
# (the env var must be set even for unauthenticated endpoints, since
# the OpenAI client requires an api_key argument)
```

…then the parent agent can dispatch via:

```metta
(delegate "do thing X" "search,read-file" "researcher" 8)
```

## Available tools in v1

See `docs/subagent-design.md` §4.5.2 for the full taxonomy. v1
registered tools:

- `search` — web search via DuckDuckGo (`channels/websearch.py`)
- `read-file`, `write-file`, `append-file` — file I/O
- `shell` — restricted subprocess (no apostrophes, 30s timeout,
  output capped at 4 KB)
- `tavily-search` — Tavily via Agentverse (if `uagents` installed)
- `technical-analysis` — technical-analysis agent via Agentverse

v1 deliberately excludes `query`, `episodes`, `remember`, `pin`,
`metta`, `send`, `delegate` — see §4.5.2 for reasoning. The
dispatcher rejects v1-excluded tools at parse time with a clear
error string.
