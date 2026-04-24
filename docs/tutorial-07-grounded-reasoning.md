# Tutorial 07 — Grounded Reasoning

**Goal:** reduce reasoning failure by pulling premises from **verified external sources** instead of the LLM's internal weights.

This is the single most impactful mitigation for the failure modes catalogued in [reference-failure-modes.md](./reference-failure-modes.md).

## Why grounding matters

Left to its own devices, the LLM both **states the fact** and **assigns the confidence** — two independent opportunities for error. Empirically, LLM-originated confidence is overconfident by roughly 15 percentage points and LLM-originated factual claims are accurate about 55% of the time.

The fix is to separate those responsibilities:

- The **external source** provides the fact (SEC filing, PubMed paper, API response, database row).
- The **LLM** reformulates the fact into an atom and picks an `(stv ...)` calibrated to *source quality*, not to its own prior.

## Worked example — Netflix content spend

**Ungrounded chain (LLM prior):**

```
(--> netflix (contentSpend "~$16B"))     (stv 1.0 0.49)   ; LLM guess
... deduction chain ...
→ conclusion confidence: c ≈ 0.49
```

**Externally grounded chain:**

```
Step 1: fetch Netflix 10-K from SEC EDGAR
Step 2: verified content spend = $17B
Step 3: atomize with source-anchored confidence
(--> netflix (contentSpend "$17B"))      (stv 1.0 0.81)   ; SEC 10-K
... same deduction chain ...
→ conclusion confidence: c ≈ 0.81
```

**Impact:** conclusion confidence **nearly doubled** (0.49 → 0.81), and the premise is now cached in long-term memory with provenance.

## The pattern

```
1. Query long-term memory for the fact.
   (query "netflix content spend")

   Hit with provenance?  → use it.
   Miss or stale?        → fetch fresh.

2. Fetch from a verified source.
   (search "netflix 10-K content spend")
   (shell "curl ... SEC EDGAR ...")
   (tavily-search "netflix content spend 2024 10-K")

3. Atomize with source-quality confidence.
   Primary source (SEC, peer-reviewed):    c = 0.9
   Secondary source (major news outlet):   c = 0.7
   Tertiary source (blog, forum):          c = 0.4

4. Store for reuse with provenance in the atom body.
   (remember "SEC 10-K FY2024: netflix content spend $17B (c=0.9)")

5. Reason.
   (metta (|- ...))
```

## Step-by-step — add a grounded fact

Ask the agent, in a running OmegaClaw session:

```
please verify Netflix's 2024 content spend from SEC EDGAR and
add it to memory with provenance before we reason about it
```

The agent should, across a few cycles:

1. `(search "Netflix 2024 10-K content spend SEC EDGAR")` or `(tavily-search ...)`.
2. Optionally `(shell "curl -s <filing url> | grep -A2 'content spend'")` to get raw text.
3. `(remember "SEC 10-K FY2024: netflix content spend $17B (c=0.9)")`.
4. Pin the verified figure for downstream use.
5. Run `(metta (|- ...))` with the new premise.

## Source-quality to confidence mapping

| Source class | Suggested initial `c` |
|---|---|
| Primary / authoritative (SEC, PubMed, official API) | 0.9 |
| Verified secondary (Reuters, AP, peer-reviewed review) | 0.7 |
| General secondary (major news, Wikipedia citation) | 0.55 |
| Tertiary (blog, forum, anonymous claim) | 0.4 |
| LLM prior only, no external check | 0.5 *(and assume it is 15pp too high)* |

Frequency (`f`) stays tied to the actual content of the claim; source quality lives in confidence.

## The flywheel effect

Grounding a single fact **persists across sessions** through `remember`. Every subsequent reasoning chain that touches that fact inherits the verified confidence. Over time, the long-term memory becomes a knowledge graph with explicit provenance — the system's reliability compounds with use.

## Verification

- The fact is present in long-term memory with its source (search logs for `query` for the source string).
- Conclusions that depend on the grounded fact clear the ACT threshold (`f ≥ 0.6, c ≥ 0.5`) — see [reference-orchestration.md](./reference-orchestration.md).
- Re-running the same question produces a stable answer (low variance).

## Longer-term direction

The whitepaper-documented target is **automated retrieval**: the system pulls data directly from verified APIs (SEC EDGAR, PubMed, official data feeds) and maps source quality to confidence programmatically, removing the LLM's subjective numerical judgment from the loop entirely. Today's manual pattern above is the bridge until that automation exists.

## Next steps

- [tutorial-08-reliable-reasoning.md](./tutorial-08-reliable-reasoning.md) — chain depth, revision, thresholds.
- [reference-failure-modes.md](./reference-failure-modes.md) — why grounding matters, in numbers.
- [tutorial-05-reasoning-with-nal-pln.md](./tutorial-05-reasoning-with-nal-pln.md) — the underlying reasoning mechanics.
