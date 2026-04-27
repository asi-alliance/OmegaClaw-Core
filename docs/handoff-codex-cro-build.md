# Handoff brief — Codex / Oma CRO build for SingularityNET

**Audience:** OpenAI Codex (ChatGPT-5.5) joining this workstation to build a
CRO-focused variant of Oma for Esther Galfvalfi at SingularityNET, oriented
around NIST IR 8286-style enterprise risk management with easy dashboards.

**Author:** the Claude session that built the dual-format adapter, the
Telegram + local channels, the TUI, and the dashboard webui. Branch
`feature/dual-format-adapter-and-local-tui` on `hlgreenblatt/OmegaClaw-Core`.
PR open at `asi-alliance/OmegaClaw-Core#108`.

This doc is the single best entry point. Read it before touching code.

## 1. The big picture

**Oma** is an instance of **OmegaClaw** — a neural-symbolic AI agent built on
the Hyperon AGI stack (MeTTa as the substrate, SWI-Prolog as the host runtime,
Python adapters for I/O). The OpenCog Hyperon team at SingularityNET maintains
the upstream `mettaclaw` framework; the SingularityNET-aligned fork
`asi-alliance/OmegaClaw-Core` is what we extend.

The agent runs in a continuous loop. Each turn it:

1. Pulls any pending input from the active channel.
2. Builds a context blob from the system prompt + skills catalog + accumulated
   history.
3. Calls an LLM with that blob as a single user message.
4. Parses the LLM response as MeTTa s-expressions (or, for reasoning models,
   as JSON tool calls translated to MeTTa via the dual-format adapter).
5. Dispatches matched skill calls (send, remember, query, pin, shell,
   read-file, write-file, append-file, search, tavily-search,
   technical-analysis, metta).

The owner-user is **Larry Greenblatt** (founder, InterNetwork Defense). The
CRO-build target is **Esther Galfvalfi** (SingularityNET CRO). Larry's persona
prompt, Maybe Logic / RAW / Leary frame, and griffin/InterNetwork-Defense
context are documented in `memory/prompt.txt`. **Don't push that file** — it's
gitignored as personal config; each owner customizes their own copy.

## 2. Where everything runs

| Host | Role | Notes |
|---|---|---|
| `192.168.122.147` (this WS) | Oma swipl + webui + TUI + Codex now too | 8 GB RAM, 4 vCPU. No GPU. |
| `192.168.86.22` | Ollama in docker (the model serving box) | RTX 3090 24 GB. Sysadmin owns docker. |
| `192.168.86.41` | vLLM (Qwen/Qwen3-8B-Instruct on port 8001) | A4000 16 GB. Too small for Granite. |
| Anthropic API | Cloud fallback (Claude Haiku 4.5, Opus 4.6) | Costs money — used sparingly. |

SSH from this WS to `192.168.86.22` works passwordless as `omaclaw` user
(read-only — no docker, no sudo). SSH to `.41` not currently configured here.

## 3. Available models on `192.168.86.22:11434` (Ollama)

| Model | Tag | Best for | Notes |
|---|---|---|---|
| Gemma 4 | `gemma4:26b` | Daily routine + speed (124 tok/s gen!) | Lowest hallucination rate observed |
| Qwen3 14B | `qwen3:14b` | Chat default — sweet spot of speed + reasoning | Native thinking + native tool calling |
| Mistral Small 3.2 | `mistral-small3.2:24b` | High-stakes drafts (board memos, customer comms) | Tightest executive prose; 8 tok/s |
| Granite 4 H Small | `granite4:32b-a9b-h` | ISO/IEC 42001, regulatory writing, CRO drafts | 32B MoE / 9B active. 5 tok/s. Quality wins on slow prose. |
| GLM-4.7 Flash | `glm-4.7-flash:q4_K_M` | Fallback only | 9.7 tok/s with thinking-mode burn |
| DeepSeek R1 distill | `deepseek-r1:14b` | Pure reasoning experiments | Bad at tool calls — JSON adapter needed |
| Phi-4 | `phi4:14b` | Available, not in active rotation | Microsoft enterprise tone, very restrained |
| Phi-4 reasoning | `phi4-reasoning:14b` | Available, not in active rotation | Reasoning variant with `<think>` tags |
| Qwen 3.6 abliterated 27B/35B | (two huihui_ai variants) | Skip — too slow, abliterated isn't for CRO work | Pre-existing on the box |

Model selection lives in `models.yaml` at repo root. Each entry maps a model
name to `format: metta | json | either`. Add a new model = one line in YAML.

## 4. The five things this codebase does that aren't obvious

These are documented in detail in `docs/notes-dual-format-llm-2026-04-25.md`.
Scanning before changing code prevents a lot of pain.

1. **`(string-safe ...)` in `src/utils.metta` mangles JSON examples in the
   prompt** by replacing every `"` with `_quote_`. JSON-mode models need
   `_un_string_safe` (in `lib_llm_ext.py`) to reverse that before the prompt
   reaches them. Don't apply un_string_safe to metta-mode models — they
   depend on the placeholder encoding.

2. **`balance_parentheses` in `src/helper.py` is positional-only** by default.
   The fast-path I added detects nested parens (kwarg shape) and passes
   through; otherwise the legacy line-based normalizer runs. **Both branches
   are load-bearing — keep them.**

3. **The `loop.metta:69` safety net check uses `string_length > 1` instead of
   the original `first_char == "("`** because the SWI-Prolog↔MeTTa string-vs-
   atom binding broke `first_char` for Python-string returns. If you tighten
   this back, the JSON path will silently lose every reply.

4. **There is no standalone skill registry.** Skills are MeTTa rewrite rules
   in `src/skills.metta`, `src/channels.metta`, etc. Dispatch *is* the MeTTa
   engine matching `=` rules. Don't try to build a "skill table" object —
   the engine IS the table.

5. **Per-process state resets on every swipl restart.** `_authenticated_user_ids`
   in channels, `_recent_sends` dedup buffers, all `&state` vars in MeTTa.
   Long-term memory (`memory/history.metta` + `chroma_db/`) survives.

## 5. Channels and clients (what talks to Oma)

Adapter pattern: each channel is a Python module in `channels/` that exposes
`start_*`, `getLastMessage`, `send_message`. Wire-in is in `src/channels.metta`
and `lib_omegaclaw.metta`.

| Channel | File | Status |
|---|---|---|
| **local** (FIFO) | `channels/local.py` | Pairs with `tui.py` and `webui.py`. Two named pipes: `/tmp/oma-in` for input, `/tmp/oma-out` for output. Internet-free. |
| **telegram** | `channels/telegram.py` | Long-polling. Multi-user via shared auth secret (`OMEGACLAW_AUTH_SECRET`). Per-call paraphrase dedup (last 8 sends). Bot: `@AgentGriff_Uma_Bot`. |
| **irc** | `channels/irc.py` | Pre-existing (we didn't touch). QuakeNet by default. |
| **mattermost** | `channels/mattermost.py` | Pre-existing. |

Run command pattern:
```
cd ~/PeTTa && source .venv/bin/activate && \
  OMEGACLAW_AUTH_SECRET="" OLLAMA_MODEL=qwen3:14b \
  sh run.sh run.metta provider=Ollama commchannel=local
```

Single-channel-per-swipl by design. To switch channels: kill swipl, relaunch
with new `commchannel=…`.

User-facing clients on this WS:

* `omatui` (symlink to `tui.py`) — minimal CLI chat REPL
* `omaweb` (symlink to `webui.py`) — http://127.0.0.1:22333 dashboard
  - sidebar pages: Current chat / History / Channels / Settings
  - hero token-per-second tile (background probe every 30 s)
  - model switcher dropdown in header (kills + relaunches swipl with new model)
  - `↻ new` button + `/new` slash command in chat = level-1 memory reset

## 6. The dual-format LLM adapter (the most important thing to understand)

`lib_llm_ext.py` translates between Oma's MeTTa-s-expression world and the
JSON tool-call output most reasoning models emit. Hard constraint preserved:
**zero behavior change** for any model already working in metta-mode.

Pipeline:

```
LLM call → raw text response
        ↓
   _strip_thinking()       (only json/either modes — strips <think>...</think>)
        ↓
   _strip_fences()          (removes ```json ... ``` markdown wrappers)
        ↓
   _find_balanced_block()   (locates first balanced {} or [] past prose preamble)
        ↓
   _normalize_call()        (unifies our shape vs OpenAI tools shape)
        ↓
   _json_call_to_metta()    (synthesizes (skill (kwarg "value") …) string)
        ↓
   sread + MeTTa engine     (UNCHANGED — engine matches kwarg shim rules,
                             which delegate to original positional rules)
```

`models.yaml` config:
```yaml
deepseek-r1:14b:
  format: json
gemma4:26b:
  format: metta
mistral-small3.2:24b:
  format: json     # instruct-tuned but JSON works fine; eats no thinking budget
```

Default for unknown models: `metta` (the conservative protocol).

Adding a new model: ensure the model is on Ollama (or wire a new HTTP base
URL), then add one line to `models.yaml`. No code changes.

## 7. The CRO build target — what Esther needs

NIST IR 8286 ("Integrating Cybersecurity and Enterprise Risk Management") is
the framework. Three-line summary:

* **Line 1** = risk owners doing the work (engineering teams, ops)
* **Line 2** = risk management function (CRO, the GRC team) — synthesizes
  Line-1 inputs into enterprise-risk view
* **Line 3** = audit / board / committee oversight

Esther operates at Line 2. The Oma CRO build should let her:

1. **Ingest** Line-1 inputs at scale — incident reports, control assessments,
   risk-register updates, vendor security questionnaires, audit findings,
   policy exceptions, etc. Probably from email, Slack/Mattermost, file drops,
   or pasted into the chat.
2. **Synthesize** them into NIST IR 8286 risk-register entries with
   likelihood × impact, control mapping (NIST CSF 2.0 / ISO 27001 / ISO 42001
   for AI), residual risk, treatment recommendations.
3. **Dashboard** the rolled-up enterprise risk view — top N risks by
   priority, risks-needing-attention this week, controls failing assessment,
   outstanding remediations, AI-system-specific risks (ISO 42001
   alignment), trend over time.
4. **Draft** Line-3 communications — board memos, audit committee briefs,
   regulator-facing summaries — in the right register and length.

Granite is the right model for #4 (drafting). Qwen3 or Gemma is right for
#1-#3 (interactive triage and synthesis). Routing per task is the pattern
the dual-format adapter already supports.

## 8. Where Codex should add the CRO-specific bits

These are the seams in the codebase the existing architecture invites you
to extend, in increasing order of disruption:

### 8a. New skills (additive, lowest risk)
Add new MeTTa rewrite rules to `src/skills.metta`. Each rule needs:
* A positional form (the original protocol)
* A kwarg shim that delegates to the positional form
* An entry in `_SKILL_ARG_ORDER` in `lib_llm_ext.py`
* A line in `(getSkills)` so the LLM knows the skill exists
* A line in `_JSON_HINT` describing arg names

CRO-relevant skills you'll likely want:
* `risk-register` — append/query/update entries
* `score` — compute likelihood × impact with NIST IR 8286 buckets
* `map-control` — link a risk to NIST CSF / ISO 27001 / ISO 42001 controls
* `dashboard-data` — emit the latest dashboard JSON for the webui
* `notify-line3` — draft a Line-3 brief from the current risk register

### 8b. New channel: email or Slack inbound (additive)
Build `channels/email.py` (IMAP poll for incoming risk reports) or
`channels/slack.py` (webhook receiver) following the existing channel
contract: `start_*`, `getLastMessage`, `send_message`. Wire into
`lib_omegaclaw.metta` import list and `src/channels.metta` dispatch.

### 8c. New CRO dashboard pages in webui
Add to `webui.py`:
* `/risks` endpoint that returns the parsed risk register
* `/heatmap` endpoint returning likelihood × impact matrix data
* New sidebar page (HTML pattern in `INDEX_HTML` already established):
  ```
  <a class="nav-link" data-page="risks">Risks</a>
  <a class="nav-link" data-page="heatmap">Heatmap</a>
  ```
* JS to render heatmap (vanilla canvas or simple HTML table — keep
  stdlib-only philosophy; don't pull in D3 / React / build steps)

### 8d. New persona prompt for Esther (config, not code)
Create `memory/prompt-esther.txt` modeled on `memory/prompt.txt` but with
Esther's frame instead of Larry's. Switch personas at swipl launch by
either symlinking `memory/prompt.txt → memory/prompt-esther.txt` before
start, or by extending `(getPrompt)` in MeTTa to read a configurable file
(needs a small change in `src/skills.metta` or wherever `getPrompt` lives).

### 8e. Storage for risk register
The existing `chroma_db/` is for embedding-based recall. A risk register
needs structured storage (the same risk gets updated, queried by ID,
filtered by status). Recommended: a small `memory/risks.jsonl` or a
SQLite file that the new `risk-register` skill reads/writes via Python.
Don't try to put structured data in `history.metta` — wrong tool.

## 9. Things to NOT do (will break invariants)

* Don't change `src/loop.metta`'s safety-net `string_length > 1` back to
  `first_char == "("`. See gotcha #3 above.
* Don't push `memory/prompt.txt` or `memory/history.metta` to git. Personal.
* Don't add `num_ctx`, `keep_alive`, `num_gpu`, or Modelfile overrides to
  Ollama HTTP requests. Triggers a 60 s model reload. Documented in
  `docs/notes-ollama-server.md`-equivalent (or memory).
* Don't introduce new Python dependencies in `webui.py` or `tui.py`. Both
  are stdlib-only by design — that's why they install with zero ceremony.
* Don't modify the existing positional skill rules. Only ADD kwarg shims
  alongside. Both forms must coexist (the dual-format compatibility story).
* Don't run multiple swipl instances against the same `chroma_db/` — sqlite
  locking will explode.
* Don't change `OMEGACLAW_AUTH_SECRET` while Oma is running — channel auth
  state is captured at swipl start.

## 10. Useful context files in the repo

* `docs/notes-dual-format-llm-2026-04-25.md` — full implementation notes
  for the adapter. Read first.
* `docs/notes-model-evaluation-2026-04-25.md` — first model comparison pass.
* `docs/notes-ishtar-egg-benchmark-2026-04-25.md` — single-prompt benchmark
  combining synthesis, audience awareness, E-Prime constraint. Useful for
  understanding which model does what well.
* `models.yaml` — per-model format config.
* `tui.py` and `webui.py` — both heavily commented; good entry points.
* `channels/local.py` and `channels/telegram.py` — clean reference for
  how a channel adapter is structured.

## 11. Quick start for Codex

```bash
cd /home/omaclaw/PeTTa/repos/OmegaClaw-Core
git checkout feature/dual-format-adapter-and-local-tui   # the work-in-progress branch
git log --oneline -5                                       # see recent history
ls docs/                                                   # browse the notes
omaweb &   # webui on http://127.0.0.1:22333
omatui     # CLI chat REPL (in another terminal)
```

Useful one-liners:

```bash
# what model is Oma using right now?
curl -s http://127.0.0.1:22333/stats | python3 -c "import sys,json;print(json.load(sys.stdin)['model'])"

# what's loaded on the Ollama box?
ssh omaclaw@192.168.86.22 'curl -s http://localhost:11434/api/tags | python3 -m json.tool' | grep '"name"'

# tail Oma's runtime log filtered for human messages and agent sends
tail -f /tmp/omegaclaw.log | grep -E '^\(HUMAN-MSG|^\(RESPONSE: \(\(send'
```

Welcome aboard.
