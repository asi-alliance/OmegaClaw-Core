# Model evaluation for Oma — local under-26B candidates

**Date:** 2026-04-25
**Hardware:** RTX 3090 24 GB on `192.168.86.22` (Ollama in docker container)
**Pipeline:** Oma running with the dual-format LLM adapter shipped earlier today
(`docs/notes-dual-format-llm-2026-04-25.md`). All models tagged
`format: json` in `models.yaml`.
**Use case:** OmegaClaw "Oma" persona acting as Line-2 risk owner / strategic
synthesis assistant for the SingularityNET CRO. ~12k-token prompts (persona +
Maybe Logic frame + skills catalog + history) per turn.

## Throughput measurements

Single controlled probe per model: 200-300 token output ceiling, fixed user
prompt *"Write a 200-word paragraph about the role of a Chief Revenue Officer."*
Numbers come from Ollama's own `eval_count`/`eval_duration` fields, so they
include any thinking-mode token burn for models that default to it.

| Model | Size / quant | Prefill (tok/s) | Generation (tok/s) | Total round-trip | Visible content? |
|---|---|---:|---:|---:|---|
| `gemma4:26b` | 26B Q4 | 731 | **124.1** | 9.9 s | ✗ thinking-mode burn (default-on) |
| `qwen3:14b` | 14B Q4 | 349 | **77.1** | 2.8 s | ✗ thinking-mode burn |
| `glm-4.7-flash:q4_K_M` | ~14B Q4 | 55 | 9.7 | 30.5 s | ✗ thinking-mode burn |
| `deepseek-r1:14b` | 14B Q4 (R1 distill on Qwen) | 83 | 8.9 | 39.1 s | ✗ pure reasoning model |
| `mistral-small3.2:24b` | 24B Q4 | **939** | 8.6 | 42.1 s | ✓ clean executive prose |

**Caveats:**
- Probes ran on a shared GPU while Oma was driving live turns — measured speeds
  are pessimistic, not best-case.
- "Visible content" notes whether the 200-token output budget produced human-
  readable text in `message.content`. Models with default-on thinking mode burn
  the budget on hidden reasoning before emitting `content`. Larger
  `num_predict` resolves this for them.
- gemma4:26b's 124 tok/s sustained generation on a 3090 is genuinely
  surprising and worth verifying with a follow-up at higher token budgets — if
  reproducible, it's the speed leader by a wide margin.

## Live agent-loop behavior on Oma

These come from passive observation in the Oma loop, where each "iter" is one
full turn through `loop.metta`: build context, call LLM, parse response,
dispatch any skill calls, sleep 1s.

| Model | Cold-start iter | Steady-state iter (real reply) | Idle iter (model emits `[]`) |
|---|---:|---:|---:|
| `qwen3:14b` | ~24 s | **4–10 s** | 2 s |
| `glm-4.7-flash:q4_K_M` | ~60 s | 20–24 s | n/a (kept inventing replies until anti-repeat patch) |
| `deepseek-r1:14b` | ~30 s | 17–24 s | 1–2 s |

The KV-cache hit on follow-up turns (same persona block, same skills catalog,
small delta in history) explains why steady-state iter time is dramatically
lower than cold-prefill measurements imply. For Oma specifically, prefill speed
matters most for the *first* turn of a session and after long idle gaps; after
that, it's all generation speed.

## Reasoning quality assessment

Subjective, based on how the model behaves inside the Oma loop with the
production prompt (persona + Maybe Logic frame + skills + history).

| Model | Tool-call protocol fidelity | Reasoning depth | Verbosity / discipline | Verdict for Oma + CRO |
|---|---|---|---|---|
| `qwen3:14b` | High — emits clean JSON tool calls; respects empty-`[]` no-op rule | Strong (native thinking mode) | Some chattiness; needs prompt to enforce executive register | **Recommended primary.** Best balance of speed + reasoning + protocol compliance. |
| `mistral-small3.2:24b` | High (instruction-tuned, native tool calling) | Solid; less depth than Qwen3 thinking mode | Tightest, most business-formal output of any model tested. Writes like an MBA. | **Recommended for high-stakes drafting** (board prep, partnership memos, deal review). 8.6 tok/s makes it slow for routine agent turns. |
| `glm-4.7-flash:q4_K_M` | High after our adapter patches — initial test had a repetition loop, fixed with explicit "emit `[]` for no-op" hint in the JSON output spec | Decent; thinking mode helps | Tendency to repeat itself if not explicitly told to emit `[]` for silence | Workable; better at synthesis than R1, slower than Qwen3. Useful as a fallback. |
| `gemma4:26b` | High in metta-mode (the original Oma protocol). Untested in JSON mode for this run. | Solid reasoning, well-aligned, lowest hallucination rate observed | Restrained, corporate tone | Strong incumbent. The original Oma battle-tested this for hours yesterday. Worth a JSON-mode A/B. |
| `deepseek-r1:14b` | Low without our JSON adapter (emits prose); workable with adapter | Strong on benchmarks, weaker in agent loops | Verbose, drifts off-task | **Not recommended** for production Oma; useful only for offline reasoning experiments. |

## Specific recommendations for the SNET team

1. **Set `qwen3:14b` as Oma's default model.** Speed (4-10 s/iter), tool-call
   discipline, and reasoning depth all check out. `OLLAMA_MODEL=qwen3:14b` in
   the run command, `models.yaml` already configured `format: json`.

2. **Keep `mistral-small3.2:24b` warm for high-stakes tasks.** When the CRO
   asks Oma for a deliverable that will leave the agent (board memo, customer
   email, partnership proposal), swap to Mistral. Slower but the output is
   genuinely closer to professional finished work. Could be wired as a
   per-skill provider override — e.g. `(send-formal …)` routes to Mistral
   while `(send …)` stays on Qwen3.

3. **Re-test `gemma4:26b` in JSON mode.** It already had the highest reasoning
   reliability observed yesterday in metta-mode and the throughput probe today
   suggests it might also be the fastest generator at this size. If JSON-mode
   compliance holds, it could displace Qwen3:14b at the top of the stack.

4. **Skip GLM-4.7-Flash and R1:14b for production.** GLM works but is 5× slower
   than Qwen3 with no quality advantage. R1's reasoning-distill design fights
   the tool-calling protocol; we made it work via the JSON adapter, but Qwen3
   does the same job better and faster.

5. **Anti-repeat instruction is now load-bearing in the JSON hint.** Any future
   reasoning-y model added will benefit. Located in
   `lib_llm_ext.py:_JSON_HINT` — the explicit "emit `[]` if there is no new
   HUMAN_MESSAGE" block. Don't remove it.

## What we measured but didn't yet integrate

- **vLLM `Qwen/Qwen3-8B-Instruct` on `192.168.86.41:8001`.** FP8 quant, 24,576
  ctx. Direct probe returned in 66 ms (small prompt). Lighter than the 14B
  Ollama variant; would be the obvious pick for high-throughput sub-agents
  where Oma delegates routine work. Wiring this in is ~30 lines: new client +
  new dispatch branch in `loop.metta:61-67` + new `useQwen3Vllm()` helper.

- **`huihui_ai/Qwen3.6-abliterated:35b-Claude-4.7-q4_K`** (already on .22).
  35B is over the practical cap — user reported it was visibly slow even when
  driven directly via OpenWebUI. Skipped.

## Code changes that made this evaluation possible

- `lib_llm_ext.py` — JSON tool-call adapter, anti-repeat hint, format-aware
  prompt assembly, per-model `models.yaml` lookup.
- `src/skills.metta` — kwarg shim rules for every skill so
  `(send (text "hi"))` from JSON path delegates to `(send "hi")` from metta
  path. Both shapes coexist.
- `src/loop.metta` — replaced inline OUTPUT_FORMAT with
  `(py-call (lib_llm_ext.get_output_format_hint (provider)))`; loosened the
  safety-net check from `first_char == "("` to `string_length > 1`.
- `src/helper.py` — `balance_parentheses` now fast-paths already-balanced
  s-expressions (kwarg form) instead of mangling them.
- `models.yaml` — per-model `format: metta | json | either` config.

Full implementation notes in `docs/notes-dual-format-llm-2026-04-25.md`.
