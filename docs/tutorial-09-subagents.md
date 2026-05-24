# Tutorial 09 — Subagent Dispatch

**Goal:** delegate a bounded multi-step task to a specialist
subagent, end-to-end.

## Prerequisites

- A working OmegaClaw deployment (see [Usage](/README.md#usage)).
- An LLM endpoint reachable from the OmegaClaw host that you want
  the subagent to use. This can be a local Ollama instance, a remote
  API, or anything else that speaks the OpenAI chat completions
  protocol.
- The env var holding the API key for that endpoint (Ollama uses any
  value; remote APIs need real keys).

## The anatomy of a subagent

A subagent is three things:

1. A **persona prompt** — short instructions telling the subagent
   what it's for and how to format its output.
2. A **persona config** — JSON file naming the persona prompt and
   binding it to a provider/model/endpoint.
3. A **dispatch call** from the parent — `(delegate goal tools
   persona_key max_turns)`.

The parent emits the dispatch call as one of its skill tuple
entries. The subagent runs its own internal loop in the parent's
Python process, calls only the tools the parent allowed, and
returns a single-string digest into the parent's
`LAST_SKILL_USE_RESULTS` for the next parent turn.

## Example: a "researcher" subagent on a local Ollama

We'll set up a research subagent that does multi-step web search +
synthesis on a local Ollama-served model and returns a one-paragraph
digest.

### Step 1 — Persona prompt

Create `memory/personas-subagent/prompt-researcher.txt`:

```text
You are a focused research subagent. Your job is bounded and short.

PROTOCOL:
- Emit one s-expression per line, each starting with '('.
- Use only the tools listed in TOOLS; no others exist.
- When you have your answer, emit (emit "<digest>") on its own line and stop.
- The digest should be a single sentence or short paragraph, ≤ 1500 chars.
- Do not narrate your reasoning. Do not use <think> blocks. Do not use markdown fences.
- No more than 3 tool calls per turn.

Examples of valid output:

  (search "lithium battery prices 2026")

  (read-file "memory/notes.md")
  (search "site:openai.com pricing changes")

  (emit "Three vendors found: ...")
```

Keep it short (200-400 chars). The persona is included in the
subagent's prompt on every iteration; long personas inflate the
subagent's per-call cost.

### Step 2 — Persona config

Create `memory/personas-subagent/researcher.json`:

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

Adapt `provider`, `model`, `base_url`, and `api_key_env` for your
deployment. The field meanings are documented in
[`reference-skills-subagent.md`](./reference-skills-subagent.md#configuration)
and in `memory/personas-subagent/README.md`.

### Step 3 — Set the env var

```bash
export OLLAMA_API_KEY=ollama
```

(Ollama doesn't authenticate, but the OpenAI client requires an
`api_key` argument, so the env var must be set to some non-empty
value.)

### Step 4 — Dispatch from the parent

Once the parent agent is running with the deployment's normal
configuration, you can dispatch a research sub-task by giving the
parent a prompt that should elicit a `delegate` call. The parent's
skill catalogue includes `delegate` automatically; the parent's
foundation model will pick it when the task fits.

For testing, you can also inject a dispatch directly by adding it to
the parent's `getSkills` example or by prompting:

```text
human: Please dispatch a researcher subagent to summarize the most
recent entries in memory/notes.md.
```

…and the parent should produce a skill tuple including something like:

```metta
(delegate "summarize the most recent entries in memory/notes.md"
          "search,read-file"
          "researcher"
          8)
```

### Step 5 — Read the result

After dispatch, the parent's next turn shows the digest in
`LAST_SKILL_USE_RESULTS` as a `(COMMAND_RETURN: ((delegate ...)
"<digest>"))` line. The digest is a single-line string of at most
2,000 characters.

## Verifying it worked

In the agent's log:

```
(---------iteration N)
... [parent calls delegate] ...
[subagent's per-call tokens land in memory/usage.jsonl with "subagent": true]
... [digest appears in next iteration's LAST_SKILL_USE_RESULTS] ...
```

`memory/usage.jsonl` records each subagent LLM call alongside the
parent's; the records carry `"subagent": true` so you can separate
the two streams during cost analysis.

## Conventions

- Persona configs are per-deployment. Do not commit configs that
  contain real API keys or sensitive endpoint URLs.
- Persona prompts should be short, declarative, and explicit about
  the `emit` protocol.
- Tool subsets should be the minimum the subagent needs. Smaller
  subsets reduce the subagent's prompt size and the parent's
  cognitive load.

## Verification

- The new subagent's tools listed in the catalogue (search,
  read-file, etc.) appear in the subagent's prompt for that
  dispatch only.
- The parent's `LAST_SKILL_USE_RESULTS` contains the digest as a
  single line ≤ 2,000 chars.
- `memory/usage.jsonl` shows the subagent's per-call tokens with
  `"subagent": true`.
- If the subagent's endpoint is unreachable, the digest is a clear
  `"(subagent error: ...)"` string and the parent's loop continues.

## Next steps

- [reference-skills-subagent.md](./reference-skills-subagent.md) —
  precise signature, parameters, configuration, failure modes.
- [subagent-design.md](./subagent-design.md) — architectural
  rationale and the per-component design.
- [reference-internals-extension-points.md](./reference-internals-extension-points.md)
  — where to plug in additional behavior.
