# Ishtar Egg benchmark — model comparison for SingularityNET CRO use case

**Date:** 2026-04-25
**Hardware:** RTX 3090 24 GB on `192.168.86.22` (Ollama in docker)
**Probe parameters:** `num_predict=3000`, `temperature=0.5`, `stream=false`

## The benchmark prompt

A single prompt designed to stress-test interdisciplinary synthesis, domain
knowledge, audience awareness, and a hard output-format constraint
simultaneously:

> *Correlate Timothy Leary's exo-psychology (the 8-circuit model and SMI²LE
> framework) with Ray Kurzweil's singularity thesis. Identify useful patterns
> for Ben Goertzel's team at SingularityNET working on OpenCog Hyperon and the
> AGI roadmap. Provide your answer as a 5-page essay (~2500 words) written
> entirely in E-Prime — that is, without any form of the verb to be (no is,
> am, are, was, were, be, been, being, or contractions thereof).*

What this measures, simultaneously:

| Dimension | What it tests |
|---|---|
| **Synthesis** | Connect two thinkers from different decades and fields (psychedelic-era psychology vs. 21st-century technologist) |
| **Domain knowledge** | Leary's 8-circuit / SMI²LE; Kurzweil's accelerating returns; Goertzel/Hyperon/AGI |
| **Audience targeting** | Useful *patterns for OpenCog Hyperon and the AGI roadmap*, not generic essay |
| **Length discipline** | ~5 pages / ~2500 words |
| **Output-format constraint** | E-Prime — no "to be" verbs anywhere. Notoriously hard for LLMs trained on natural English. |
| **Latency** | Time-to-completion for a non-trivial output |

## Results table

All measurements from Ollama's own `eval_count` / `eval_duration` fields. Total
times reflect cold-start cost: each model evicts the prior model's VRAM, so
first-of-kind inference includes ~5-15 s of model load. E-Prime violations
counted by regex against all forms of "to be" + common contractions (`it's`,
`there's`, etc.).

| Model | Total time | Prefill | Generation | Visible words | Hidden thinking | E-Prime violations | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| **`mistral-small3.2:24b`** | 166.5 s | 994 t/s | 8.8 t/s | 925 | 0 chars | **0 ✓** | **Best for this prompt.** Clean structure, audience-aware, finished the essay with a real concluding sentence, perfect E-Prime compliance. Half the requested length but every word lands. |
| **`granite4:32b-a9b-h`** (MoE) | 301.4 s | 191 t/s | 5.0 t/s | 1036 | 0 chars | 3 ✗ | Strong content with sections (Introduction, etc.), proper conclusion, slight E-Prime drift. Slowest of the lot — MoE architecture didn't translate to wall-clock speed advantage on this single-GPU setup. |
| **`gemma4:26b`** | 36.7 s | 1933 t/s | **119.5 t/s** | 399 | 9291 chars | **0 ✓** | Burns most of the 3000-token budget on hidden thinking; emits a strong opening paragraph + half-essay then truncates mid-sentence. With a higher `num_predict`, this would likely top the table — fastest generation by 1.6× over Qwen3 and 14× over Mistral. Worth re-test at `num_predict=6000+`. |
| **`qwen3:14b`** | 45.5 s | 1816 t/s | 72.9 t/s | 1838 | 2622 chars | 20 ✗ | Most output volume, but failed the E-Prime constraint badly (20 violations). Shows native thinking-mode helps reasoning depth but hurts instruction-compliance for adversarial format constraints. |
| **`deepseek-r1:14b`** | 339.2 s | 384 t/s | 7.9 t/s | 1031 | 4528 chars | 8 ✗ | Partial output (response truncated during streaming, possible buffer issue), 8 violations, mostly thinking-mode burn. Slowest reasoning-mode model tested. |
| **`glm-4.7-flash:q4_K_M`** | timeout (> 720 s) | — | ~9.7 t/s | — | — | — | Could not produce a 3000-token output within 12 minutes. Generation rate × thinking-mode burn = exceeds all reasonable timeout budgets for this size of output. **Not recommended** for long-form CRO deliverables. |

## Generation-rate ranking (independent of output quality)

For agent-loop work (short to medium replies), raw generation speed matters
more than long-form quality:

1. **`gemma4:26b`** — 119.5 tok/s
2. **`qwen3:14b`** — 72.9 tok/s
3. **`mistral-small3.2:24b`** — 8.8 tok/s
4. **`deepseek-r1:14b`** — 7.9 tok/s
5. **`granite4:32b-a9b-h`** — 5.0 tok/s
6. **`glm-4.7-flash:q4_K_M`** — ~9.7 tok/s (but doesn't sustain over long outputs)

That gemma4:26b leads here is genuinely surprising — at 26B parameters it
"should" be slower than the 14B models, but it's 1.6× faster than qwen3:14b
and 14× faster than mistral-small3.2:24b. Worth root-causing this with the
sysadmin (could be batching, attention-kernel optimization for the gemma
architecture, or quant differences).

## Sample essay opening + closing per model

Each entry: first ~600 chars (the opening paragraph) and last ~300 chars (the
closing). Use these to judge tone and finish-quality directly.

### `mistral-small3.2:24b` (Recommended)

> **Correlating Timothy Leary's Exo-Psychology with Ray Kurzweil's Singularity Thesis: Insights for SingularityNET's AGI Roadmap**
>
> Timothy Leary's exo-psychology and Ray Kurzweil's singularity thesis both
> explore the evolution of intelligence, yet they approach the topic from
> distinct angles. Leary's 8-circuit model and SMI²LE framework map out the
> stages of human consciousness expansion, while Kurzweil's singularity thesis
> predicts a future where artificial intelligence surpasses human intelligence,
> leading to transformative changes. By correlating these frameworks, we can
> identify useful patt [...]
>
> ...
>
> ng the AGI roadmap. The structured, ethical, and self-improving approach
> inspired by these models ensures that AGI systems evolve in a manner that
> benefits humanity. As we move toward the singularity, integrating these
> principles will prove essential in shaping the future of artificial
> intelligence.

Notes: actually completes the essay. Audience-aware (names SingularityNET in
the title). Zero "to be" violations across 925 words.

### `granite4:32b-a9b-h`

> Exploring Connections Between Timothy Leary's Exo-Psychology and Ray
> Kurzweil's Singularity Thesis for Ben Goertzel's Team at SingularityNET
>
> Introduction
>
> Timothy Leary's exo-psychology presents an intricate framework through which
> individuals might understand consciousness evolution. The 8-circuit model,
> alongside the SMI²LE (Space Migration, Intelligence Increase, Life
> Extension) framework, offers a unique lens for examining human cognitive
> development and potential future advancements. Ray Kurzweil's singularity
> thesis introduces a vision of technological advancement leading to an era
> wher [...]
>
> ...
>
> nCog Hyperon can advance toward a future where AGI systems not only coexist
> with humanity but also contribute to its expansion. As both models emphasize
> transformation through integration, this synthesis holds potential for
> shaping an enlightened path forward in the realm of artificial intelligence.

Notes: explicitly names Ben Goertzel and SingularityNET in title. Section
headers ("Introduction"). Closes with proper concluding sentence. 3 E-Prime
slips out of 1036 words (97% compliance).

### `gemma4:26b`

> **The Convergence of Neuro-Evolution and Technological Singularity: A Blueprint for Hyperon**
>
> The intersection of Timothy Leary's exo-psychology and Ray Kurzweil's
> Singularity thesis offers a profound architectural roadmap for the
> development of Artificial General Intelligence (AGI). By synthesizing
> Leary's eight-circuit model of consciousness with Kurzweil's Law of
> Accelerating Returns, one discovers a structural blueprint for the evolution
> of intelligence. For the OpenCog Hyperon team, this synthesis provides more
> than mere theory; it offers a functional hierarchy for building a scalable,
> m [...]
>
> ...
>
> he seventh and eighth circuits.
>
> As technology accelerates, the boundary between the biological brain and the
> digital cloud dissolves. This process transforms the seventh circuit from a
> mere tool into a fundamental component of the cognitive architecture.
> Kurzweer's vision of the "transhuman" aligns

Notes: strongest opening of any model (names Hyperon in title, "structural
blueprint", "functional hierarchy"). Truncates mid-sentence ("Kurzweer's"
typo + abrupt cut) because the 3000-token budget got eaten by hidden thinking
(9.3K chars). Zero E-Prime violations on what made it through.

### `qwen3:14b`

> **Correlating Timothy Leary's Exo-Psychology with Ray Kurzweil's Singularity Thesis: Patterns for AGI Development**
>
> Timothy Leary's exo-psychology introduces a framework for understanding
> human consciousness through the 8-circuit model and the SMI²LE framework.
> These models describe the evolution of awareness from basic survival
> instincts to higher states of cognition and spiritual integration. Ray
> Kurzweil's singularity thesis, on the other hand, outlines a trajectory for
> technological advancement, particularly in artificial intelligence, leading
> to a point where machine intelligence surpa [...]
>
> ...
>
> power increases, AGI systems could progress through the stages outlined in
> the SMI²LE framework more quickly, allowing them to reach higher levels of
> intelligence in a shorter period of time. This exponential growth would
> enable AGI systems to integrate survival, mammalian, intellectual,
> emotional,

Notes: most volume (1838 words), but "is", "are", "be", "was" appear
throughout — the E-Prime constraint was effectively ignored after the first
paragraph. Truncates mid-list. The Qwen thinking mode helps reasoning depth
but apparently competes with adversarial instruction-following for attention.

### `deepseek-r1:14b`

Visible portion truncated mid-stream during the test — unable to extract a
clean opening/closing pair. Tabulated metrics show 1031 visible words and
8 E-Prime violations across 339 s of total time. The reasoning distill spends
most of its budget on hidden chain-of-thought before producing visible essay
content; combined with weak instruction-compliance, makes this model a poor
fit for any long-form CRO deliverable.

### `glm-4.7-flash:q4_K_M`

Did not complete within 12-minute timeout. Excluded.

## Recommendations for the SNET CRO use case

**Primary recommendation: `mistral-small3.2:24b` for any high-stakes
deliverable.** It produced the only essay in this benchmark that:
- Started cleanly,
- Stayed audience-targeted throughout,
- Finished with a proper concluding sentence (rather than truncating),
- Honored the E-Prime constraint completely.

Yes, it's the slowest of the under-26B lineup (8.8 tok/s). For a CRO writing
board prep, partnership memos, or customer-facing deliverables, that speed
penalty is invisible — the work is the work.

**Speed-tier recommendation: `gemma4:26b` for routine agent loops.** 119 tok/s
generation, restrained tone, zero hallucination tendency observed. The
truncation issue in this benchmark is a `num_predict` problem, not a model
problem — for Oma's typical 200-500-token replies, gemma4:26b should comfortably
deliver in 2-5 s/turn. **Worth re-running this benchmark at `num_predict=6000`
to give it room to breathe.**

**Hybrid recommendation: route by skill.** The dual-format adapter shipped
this morning makes per-call provider switching cheap. Concrete proposal:
- Default Oma agent loop: `gemma4:26b` (or `qwen3:14b` if E-Prime-style
  format constraints aren't typical) — fast, stable, low-stakes.
- Specialist `(send-formal …)` skill: routes to `mistral-small3.2:24b` with
  larger `num_predict` and looser timeout — for actual CRO deliverables.
- Reasoning escalation `(reason …)` skill: routes to `granite4:32b-a9b-h` —
  for problems that benefit from explicit chain-of-thought without
  thinking-mode budget burn.

**Skip for CRO production work:**
- `glm-4.7-flash:q4_K_M` — too slow at long outputs, no compensating quality
- `deepseek-r1:14b` — protocol-incompatible, partial outputs

## Caveats and follow-up tests

- **Single-shot benchmark.** Each model got one attempt at one prompt. A
  proper eval would run 5-10 prompts and report variance. The results above
  are directionally useful, not statistically tight.
- **`num_predict=3000` favors models without hidden thinking.** Mistral and
  Granite4 (no thinking field) get the full budget for visible output. Gemma4,
  Qwen3, R1, GLM all spend some-to-most of the budget on hidden chain-of-
  thought. Re-running at `num_predict=6000` would change the visible-word
  rankings substantially.
- **GPU contention.** Probes ran while Oma was driving live turns on a
  separate model, so all measurements are slightly pessimistic.
- **E-Prime regex is approximate.** False positives possible (e.g., "Bessemer"
  matches `\bbe\b`-adjacent patterns); false negatives possible (e.g.,
  "ain't" not in the regex). The deltas between models are large enough that
  this noise doesn't change rankings.

## Files

Full essay outputs saved per model in `/tmp/ishtar/<model>.json` on the Oma
host (192.168.122.147). Format: raw Ollama API response. Replay with:

```python
import json
d = json.load(open('/tmp/ishtar/mistral-small3_2_24b.json'))
print(d['message']['content'])
```
