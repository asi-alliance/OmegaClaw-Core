# Tutorial 06 — Remote Agentverse Skills

**Goal:** understand how OmegaClaw delegates work to remote agents through the Agentverse bridge, and when to use this pattern.

OmegaClaw can use Agentverse-backed skills when it needs to hand a task off to a remote agent. The core idea is simple: a local MeTTa skill calls into the Python bridge, and the bridge sends the request to a fixed Agentverse address.

Two example skills illustrate that pattern:

- `tavily-search` for web research
- `technical-analysis` for market-oriented ticker analysis

## Example skills

### `tavily-search`

`tavily-search` is an example of a remote research skill. OmegaClaw sends a search query to an external search agent and gets back compact search results.

Use it when the agent needs:

- recent web information
- a few relevant links
- short snippets from search results

Example:

```metta
(tavily-search "OpenCog Hyperon")
```

### `technical-analysis`

`technical-analysis` is an example of a remote analysis skill. OmegaClaw sends a ticker symbol to an external technical analysis agent and receives the reply.

Use it when the agent needs:

- chart-oriented stock insight
- a quick view on a ticker
- external market analysis without implementing it locally

Example:

```metta
(technical-analysis "AMZN")
```

## How the bridge works

These example skills follow the same simple pattern:

1. OmegaClaw calls a MeTTa skill.
2. The skill passes the request into the Python Agentverse bridge (`src/agentverse.py`).
3. The bridge sends the request to a fixed remote agent address.
4. OmegaClaw receives the reply and uses it like normal tool output.

The point of this design is to keep OmegaClaw lightweight while letting specialized external agents handle domain-specific work.

## Why this pattern is useful

Using Agentverse-backed skills adds new capabilities without expanding the local core too much. In these examples, OmegaClaw gains:

- web search through a dedicated external search agent
- stock technical analysis through a dedicated external analysis agent

This keeps the local runtime smaller and lets specialized services do the domain-specific work.

## Adding your own remote skill

1. Pick an Agentverse agent address for your target service.
2. Add a function to `src/agentverse.py` that posts the request and awaits the reply.
3. Expose a one-line MeTTa skill in `src/skills.metta`:

   ```metta
   (= (my-remote-skill $arg)
      (py-call (agentverse.my_remote_skill $arg)))
   ```

4. Add a descriptive line to `getSkills` so the LLM knows the skill exists.

## Limits

Because these skills depend on remote agents, they are only as reliable as the external service behind them:

- they need network access
- they depend on the target agent being reachable
- output quality depends on the remote agent, not only on OmegaClaw

## See also

- [reference-skills-remote-agents.md](./reference-skills-remote-agents.md) — precise signatures.
- [reference-python-bridges.md](./reference-python-bridges.md) — `src/agentverse.py` in detail.
