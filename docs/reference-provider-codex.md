# Reference — `Codex` provider (ChatGPT subscription auth)

Run OmegaClaw's LLM off a **ChatGPT Plus/Pro/Team subscription** instead of a pay-per-token API key, by reusing a logged-in Codex CLI session. No `*_API_KEY` required.

---

## Enable

```bash
codex login                 # one-time: sign in with your ChatGPT account
metta run.metta provider=Codex
```

That's it — the loop calls `callProvider((provider) …)`, so `provider=Codex` routes to the provider with no other change.

---

## How it works

`lib_codex_auth.py` (registered by `lib_llm_ext.py` as provider `Codex`) is self-contained (Python stdlib only, no `openai` SDK):

1. **Token** — reads `~/.codex/auth.json` written by `codex login`: `tokens.access_token` (Bearer), `tokens.account_id`, `tokens.refresh_token`. When the access-token JWT is within 60s of expiry it refreshes via the public Codex OAuth client at `https://auth.openai.com/oauth/token` and writes the file back.
2. **Inference** — `POST https://chatgpt.com/backend-api/codex/responses` using the **Responses API** schema (`input` is a list; `stream` must be `true`), with headers `Authorization: Bearer …`, `chatgpt-account-id: …` (required), `openai-beta: responses=experimental`, `originator: codex_cli_rs`. The SSE `response.output_text.delta` events are aggregated into the reply.

## Configuration

| Setting | Default | Notes |
|---|---|---|
| `provider=Codex` | — | selects this provider |
| `CODEX_MODEL` (env) | `gpt-5.4` | model slug; subscription slugs drift (e.g. `gpt-5.5`, `gpt-5.4-mini`, `gpt-5-codex`) |
| `CODEX_AUTH_PATH` (env) | `~/.codex/auth.json` | alternate token location (e.g. copied to a CI runner) |

`reasoningMode` maps to the Responses `reasoning.effort`. `maxOutputToken` is **ignored** — the Codex backend rejects `max_output_tokens`.

## Self-test

```bash
python3 lib_codex_auth.py     # prints: is_available: True | model: gpt-5.4  /  reply: 'codex-provider-works'
```

---

## Notes

- The `chatgpt.com/backend-api/codex` endpoint is internal, so model slugs and request details can change over time.
- Usage counts against your ChatGPT/Codex rate limits (rolling 5-hour + weekly).
- Treat `~/.codex/auth.json` as a credential — don't commit or share it.
