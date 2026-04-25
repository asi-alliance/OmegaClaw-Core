# Dual-format LLM adapter — implementation notes

**Date:** 2026-04-25
**Status:** working live on `deepseek-r1:14b` via Telegram channel; Gemma/Qwen MeTTa path preserved.
**Scope:** add JSON tool-call output support to `lib_llm_ext` so reasoning models (DeepSeek R1, future QwQ-style distills) can drive Oma without breaking the existing positional-MeTTa pipeline used by Gemma, Qwen3.6, and Claude.

## The original problem

Reasoning-heavy distills like `deepseek-r1:14b` lack tool-call SFT. When asked to follow OmegaClaw's "emit `(send "hi")`-shaped MeTTa" output convention, R1 emits English chat instead. `sread` parses that prose into garbage like `(How "...")` or `(I "...")`, which doesn't match any skill rule, so `(send ...)` is never invoked and no Telegram reply goes out.

Switching every reasoning model away from local Ollama is unacceptable on cost grounds. The model has to drive Oma using the output format it actually trained on: JSON tool calls.

## Architecture chosen — option (B-tolerant)

The handoff sketched two parallel parsers (sread + JSON dispatcher) feeding a shared "skill registry." Reading the codebase showed there is no standalone registry — skills are MeTTa rewrite rules and `py-call` adapters, dispatched directly by the MeTTa engine. So the cleanest implementation collapses the two parsers into one: translate JSON to MeTTa kwarg-form s-expressions inside `lib_llm_ext`, then the existing sread/eval path handles dispatch unchanged.

```
Model output (raw text)
        │
        ▼
useGemma / useClaude / useMiniMax    (LLM call returns text)
        │
        ▼
_adapt_response(model, text)         (NEW — formats per models.yaml)
    metta  → pass through
    json   → strip fences, find balanced {…}, parse, synthesize MeTTa kwargs
    either → try metta first, fall back to json
    fallback → wrap as (send (text "<raw>"))
        │
        ▼
helper.balance_parentheses (UPDATED — fast-path for already-balanced input)
        │
        ▼
loop.metta line 70: sread → eval
        │
        ▼
Kwarg shim rules in src/skills.metta:
    (= (send (text $x))                         (send $x))
    (= (write-file (filename $f) (content $s))  (write-file $f $s))
    ...etc — delegate to the existing positional rules
        │
        ▼
Existing positional skill bodies — Telegram delivery, file I/O, NAL/PLN, etc.
```

The hard constraint **"zero behavior change for Gemma4:26b and Qwen3.6 27B abliterated"** is honored: those models are tagged `format: metta` in `models.yaml`, so `_adapt_response` returns their output unchanged, and the only MeTTa rules they ever match are the original positional ones.

## Files changed

### 1. `models.yaml` (new)
Per-model output-format config: `metta` | `json` | `either`. Unknown models default to `metta`. Adding a new reasoning model is a one-line yaml entry, no code change.

### 2. `lib_llm_ext.py` (rewritten)
- Loads `models.yaml` at module import.
- `_SKILL_ARG_ORDER` table — per-skill canonical kwarg order. Must stay in sync with the kwarg shim heads in `skills.metta`.
- `_strip_fences` — removes ` ```json … ``` ` wrappers.
- `_find_balanced_block` — scans past prose preamble to the first balanced `{…}`/`[…]` outside double-quoted strings. Handles models that emit explanation before JSON.
- `_normalize_call` — accepts both `{"skill": …, "args": …}` and OpenAI-tools `{"function": {"name": …, "arguments": …}}` shapes (including string-encoded `arguments`).
- `_json_call_to_metta` — synthesizes `(skill (kwarg "value") …)` strings.
- `_adapt_response` — the format-detector entry point.
- `_un_string_safe` — reverses the MeTTa-side `(string-safe …)` encoding (`_quote_` → `"`, `_apostrophe_` → `'`, `_newline_` → `\n`) before sending to a JSON-mode model. Without this, JSON examples in the prompt arrive as `{_quote_skill_quote_: …}` and the model mimics that garbage.
- `get_output_format_hint(provider)` — called from `loop.metta` to inject the model-appropriate `OUTPUT_FORMAT` teaching block (positional MeTTa or JSON tool-call schema).

### 3. `src/skills.metta` (appended)
Kwarg shim rules at the end of the file. Each shim matches `(skill (kwarg_name $val) …)` and delegates to the original positional rule. Both forms coexist; no positional rule was modified or removed.

### 4. `src/loop.metta` (two surgical edits)
- Replaced the inline `OUTPUT_FORMAT: …` literal block with `(py-call (lib_llm_ext.get_output_format_hint (provider)))`. This makes the prompt format-aware without forking `getContext`.
- Loosened the safety-net check at line 69 from `(if (== "(" (first_char $resp)) …)` to `(if (> (string_length $resp) 2) …)`. The `first_char == "("` check was rejecting valid Python-string returns from `py-call` even when they obviously started with `(` — likely a String-vs-atom type mismatch in the SWI-Prolog↔MeTTa binding. The length-based check is permissive enough to let well-formed adapter output through and still gates against the empty-string failure mode.

### 5. `src/helper.py` (`balance_parentheses` updated)
Added a "fast path" that detects already-balanced s-expressions containing nested `(` (kwarg form or nested calls) and passes them through with only the outer list wrap. The original line-based normalization (which quotes bare tokens, e.g., `(write-file test.txt hello world)` → `((write-file "test.txt" "hello world"))`) still runs for everything that doesn't have nested parens — so Gemma's positional output is untouched. Both behaviors are unit-tested in the existing `test_balance_parenthesis` plus new kwarg-shape cases.

## Non-obvious gotchas we hit

These each cost real time and would have bitten anyone implementing this clean from the spec.

1. **`string-safe` mangles JSON examples in the prompt.** `(string-safe …)` in `src/utils.metta` replaces every literal `"` with `_quote_` so the prompt can be passed through MeTTa string handling without double-escape headaches. This is invisible during normal positional-MeTTa operation because the agent's positional output also follows the `_quote_` convention. But the moment you inject a JSON example like `{"skill": "send"}` into the prompt, the model sees `{_quote_skill_quote_: _quote_send_quote_}` and emits matching garbage. Fix: `_un_string_safe` in `useGemma` for json/either-mode models only. **Do not apply this to metta-mode models**; their output convention depends on the placeholder encoding.

2. **`balance_parentheses` is positional-only.** It line-strips the outer `()`, splits by space, treats everything after the head as a single string arg, and re-quotes. Hand it `(send (text "hi"))` and it produces `((send "(text \"hi\")"))` — a single-arg call with the kwarg expression as a quoted string. Nothing dispatches. Fix: detect nested parens via `_has_nested_paren` heuristic and pass through.

3. **The `loop.metta:69` safety net check `(== "(" (first_char $resp))` doesn't fire reliably for `py-call` string returns.** For inputs that obviously start with `(`, the comparison evaluates false — the SWI-Prolog `first_char/2` (defined as `sub_string(Str, 0, 1, _, C)`) seems to return something MeTTa's `==` won't match against the string literal `"("`. Likely a String vs atom-list type mismatch when MeTTa wraps Python str returns. Worked around with the length-based check; root-causing the binding behavior is left as future work.

4. **There is no skill registry as a standalone object.** The handoff diagram showed two parsers feeding a shared registry. In reality, dispatch *is* the MeTTa engine matching against `=` rewrite rules. Trying to add a "second dispatcher" alongside MeTTa would be over-engineering. Translation in Python → existing engine handles dispatch.

5. **Auth state is per-process.** `_authenticated_user_ids` is reset on every Telegram adapter restart (`_set_auth_secret` clears the set). After any swipl restart, the owner has to re-DM `auth vulcan42` to re-claim ownership. Worth documenting prominently for whoever takes over operations.

## What was deliberately left out

- **Streaming.** `useGemma` already uses `stream:false`. Token-by-token format detection isn't needed today. If we ever turn on streaming, the format detector needs a buffering mode that holds back until the first balanced brace block or end-of-turn.
- **Migration of registry from positional to keyword args (B-strict).** Considered, rejected as v1 because it breaks every line of accumulated `history.metta` and `chroma_db` and provides no visible benefit beyond what B-tolerant gives us. Revisit if/when we want to clean up the historical encoding for other reasons.
- **Free-text fallback richness.** Currently wraps the whole non-parseable response as `(send (text "<raw>"))`. Good enough — the user at least sees what the model was trying to say instead of silent dead air. A smarter fallback could parse natural-language intent, but that's a model problem, not a plumbing problem.
- **Per-skill arg-order-map kept in Python (option A).** B-tolerant uses MeTTa shims AND a Python arg-order map (`_SKILL_ARG_ORDER`). The map exists because JSON arg order is unspecified; we need a canonical order to synthesize the MeTTa expression. This map is the only piece of duplicated knowledge between Python and MeTTa — keep them in sync when adding new skills.

## How to add a new reasoning model

1. Add the model name to `models.yaml` with `format: json`.
2. Restart Oma. Done.

If the model uses a tool-call shape we haven't seen (e.g., a function-calling format different from OpenAI tools or `{"skill":…, "args":…}`), extend `_normalize_call` to handle it.

## How to add a new skill

1. Add the positional `(= (skill $a $b …) <body>)` rule to `skills.metta` or `channels.metta` as before.
2. Add a kwarg shim: `(= (skill (arg_a $a) (arg_b $b)) (skill $a $b))` at the bottom of `skills.metta`.
3. Add `"skill": ["arg_a", "arg_b"]` to `_SKILL_ARG_ORDER` in `lib_llm_ext.py`.
4. Update `getSkills` (the LLM-facing skill catalog) and the JSON `_JSON_HINT` block in `lib_llm_ext.py` if you want explicit per-skill arg-name guidance.

## Operational notes (testing this run)

- Bot: `@AgentGriff_Uma_Bot` on Telegram, owner-auth via `auth <secret>`.
- Telegram adapter (`channels/telegram.py`) supports multi-user via `_authenticated_user_ids` set; owner can share the auth secret to add collaborators.
- Run command:
  ```
  cd ~/PeTTa && source .venv/bin/activate && export OMEGACLAW_AUTH_SECRET=<secret> \
    OLLAMA_MODEL=deepseek-r1:14b && \
    sh run.sh run.metta provider=Ollama commchannel=telegram TG_BOT_TOKEN=<token>
  ```
- Local Ollama endpoint: `http://192.168.86.22:11434`, native `/api/chat`. **Do not** send `num_ctx`, `keep_alive`, `num_gpu`, or Modelfile overrides in the request — any of them triggers a ~60s model reload on the server. The current `useGemma` is already compliant.
- Per-iteration cost: R1 prefill on a 50k-char prompt is the slow part (~15-25s/turn vs ~7s for Gemma); per-call cost is zero (local).
