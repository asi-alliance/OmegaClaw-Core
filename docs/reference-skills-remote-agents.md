# Reference — Remote Agent Skills

Defined in `src/skills.metta`; bridge code lives in `src/agentverse.py`.

Both skills delegate to a fixed Agentverse address. They depend on network access and the remote agent being reachable.

---

## `tavily-search`

### Signature
```metta
(tavily-search "query")
```

### Purpose
Send a research query to a dedicated Tavily-backed search agent on Agentverse and return its reply.

### Parameters
- `query` — the search string.

### Returns
A compact string of web search results: a few links with short snippets.

### Examples
```metta
(tavily-search "OpenCog Hyperon")
(tavily-search "recent papers on Non-Axiomatic Logic")
```

### Notes / Limits
- Output quality depends on the remote agent, not on OmegaClaw itself.
- For a lighter-weight, direct-backend search, see `search` in [reference-skills-communication.md](./reference-skills-communication.md).

---

## `technical-analysis`

### Signature
```metta
(technical-analysis "TICKER")
```

### Purpose
Send a ticker symbol to a remote technical-analysis agent and return its chart-oriented summary.

### Parameters
- `TICKER` — a stock ticker symbol, quoted.

### Returns
A string containing the remote analysis.

### Examples
```metta
(technical-analysis "AMZN")
(technical-analysis "NVDA")
```

### Notes / Limits
- Remote-only — requires network and a reachable Agentverse target.
- The bridge implementation is in `src/agentverse.py::technical_analysis`.

---

## Adding your own

See [tutorial-06-remote-agentverse-skills.md](./tutorial-06-remote-agentverse-skills.md) for the pattern, and [reference-python-bridges.md](./reference-python-bridges.md) for the bridge surface.
