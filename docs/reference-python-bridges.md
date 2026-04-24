# Reference — Python and Prolog Bridges

MeTTa handles reasoning and control flow; bridges handle everything that needs a library ecosystem.

## `lib_llm_ext.py`

LLM and embedding bridges.

| Function | Purpose |
|---|---|
| `useClaude(prompt)` | Call an Anthropic Claude model. Used when `provider = Anthropic`. |
| `useMiniMax(prompt)` | Call MiniMax. Used when `provider = ASICloud` (or similar routing). |
| `useAsi1(prompt)` | Call ASI1. Used when `provider = ASIOne`. |
| `useLocalEmbedding(str)` | Compute an embedding with a locally loaded model. Used when `embeddingprovider = Local`. |
| `initLocalEmbedding()` | Load the local embedding model once at startup. |

OpenAI calls go through MeTTa-side helpers (`useGPT`, `useGPTEmbedding`) that are defined elsewhere in the library but use the same LLM call pattern.

## `src/agentverse.py`

Remote agent bridge.

| Function | Purpose |
|---|---|
| `tavily_search(query)` | Forward a query to the remote Tavily search agent. |
| `technical_analysis(ticker)` | Forward a ticker to the remote technical analysis agent. |

Both use a fixed Agentverse address and return the remote agent's reply as a string. Add your own function following the same pattern — see [tutorial-06-remote-agentverse-skills.md](./tutorial-06-remote-agentverse-skills.md).

## `src/helper.py`

String and time utilities used by the loop.

| Function | Purpose |
|---|---|
| `balance_parentheses(str)` | Attempt to repair mismatched parentheses in LLM output before `sread` parses it. |
| `normalize_string(obj)` | Render a skill return value into a string safe to embed in the next prompt. |
| `around_time(ts, n)` | Backs `(episodes ts)` — returns `n` lines of `memory/history.metta` around `ts`. |

## `src/skills.pl`

Prolog helpers imported via `import_prolog_functions_from_file`.

| Predicate | Purpose |
|---|---|
| `shell/2` | Run a shell command and capture stdout. Rejects apostrophes. |
| `first_char/2` | Return the first character of a string — used by the loop to detect whether the LLM produced a valid s-expression. |

## Calling conventions

- MeTTa to Python: `(py-call (module.function arg1 arg2 ...))`.
- MeTTa to Prolog: `(translatePredicate (predicate ...))` for side-effecting predicates, or `!(import_prolog_function name)` to lift a Prolog function into MeTTa.

## See also

- [reference-internals-loop.md](./reference-internals-loop.md) — where these bridges are invoked.
- [reference-internals-extension-points.md](./reference-internals-extension-points.md) — where to add new bridges.
