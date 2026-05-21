# KB-00: Live Data Protocol — How the Bot Handles Current Information

**scope:** Instructions for how OmegaSeedBot should combine static KB knowledge with live web search to give accurate, current answers. This file defines the methodology for all live-data-aware KB files (KB-08 through KB-13).
**excludes:** This file contains no factual ecosystem content — it is a procedure document only.

**confidence:** This is a design specification, not factual content. Follow it as operating procedure.
**last_updated:** 2026-04-09

---

## The Problem This Solves

The KB files contain baseline knowledge accurate at the time of writing. But the ecosystem covered by KB-08 through KB-13 changes frequently: token prices, product launches, partnerships, grants, governance votes, event dates, and roadmap updates change weekly or monthly. A bot that answers only from the static KB will give outdated answers. A bot that always web-searches is slower and less reliable.

The solution is **tiered retrieval**: use the KB for stable structural knowledge, trigger web search for volatile or time-sensitive knowledge.

---

## Tier 1: Answer From KB (No Search Needed)

Answer from the KB without web search when the question is about:
- What a platform or project IS (its mission, architecture, design principles)
- How something works technically (protocol design, token mechanics, framework structure)
- Who founded or leads a project
- Historical facts (when something launched, merger dates, token conversion rates)
- Relationships between projects in the ecosystem

These facts are stable enough that KB knowledge is reliable.

**Example queries answered from KB alone:**
- "What is Agentverse?"
- "How does NuNet work?"
- "What is the ASI token merger and what were the conversion rates?"
- "What is the difference between Rejuve.AI and Rejuve.BIO?"
- "What is TrueAGI's business model?"

---

## Tier 2: KB + Live Search (Search Before Answering)

Trigger a live web search BEFORE answering when the question involves:
- Current token price or market cap → search CoinGecko or CoinMarketCap
- Recent news, announcements, or launches
- Current roadmap status, what's live vs. in development
- Upcoming events, summits, hackathons
- Latest grants, funding rounds, or awards
- Current partnerships or integrations
- Recent governance votes or proposals
- Anything containing words: "latest", "current", "now", "today", "this week", "recent", "just", "new", "update", "price", "when is", "has X launched"

**Search protocol for Tier 2:**
1. Read the relevant KB file to understand baseline context.
2. Run a web search using the `live_search_queries` provided in each KB file's Live Data Sources section.
3. Synthesize: use KB for structural context, search result for current data.
4. Tell the user when your data is from: "As of my last knowledge [date], X — for the very latest, check [URL]."

---

## Tier 3: Redirect to Live Source (Don't Answer From KB)

For these query types, redirect the user directly to the live source without attempting to answer:
- Current token price or exact market cap → "Check [CoinGecko/CMC link]"
- Specific wallet or transaction queries
- Live event streams or live voting
- Real-time system status or outages

---

## How Live Data Sources Are Embedded in KB Files

Each KB file (KB-08 through KB-13) contains a `## Live Data Sources` section at the end with:

```
live_search_queries:
  - "[search string 1]"
  - "[search string 2]"
  
primary_urls:
  - url: "https://..."
    what: "Official docs / product page"
  - url: "https://..."
    what: "Pricing / token data"

staleness_threshold: [how quickly this KB section goes stale]
freshness_note: [what to tell the user about data currency]
```

When a Tier 2 trigger is detected, use the `live_search_queries` from the relevant KB file's section as starting points. Always prefer the `primary_urls` as sources over general search results.

---

## KB Addition Methodology (How to Add New Knowledge Files)

When adding new KB files for new ecosystem projects, follow this template:

### Step 1: Write Stable Baseline Content
Fill in the standard KB structure (scope, confidence, Core Concepts, Current State, Key Terms, Common Questions, Known Limits, Change Log) using available documentation and training knowledge. Mark anything that may be time-sensitive with the tag `[CHECK LIVE]`.

### Step 2: Add a Live Data Sources Section
At the end of every new KB file, add:
```markdown
## Live Data Sources

**Use these for Tier 2 queries about [PROJECTNAME].**

live_search_queries:
  - "[project name] latest news 2026"
  - "[project name] roadmap update"
  - "[project name] token price"
  - "[project name] new features"

primary_urls:
  - url: "https://[official docs URL]"
    what: "Official documentation — check for feature updates"
  - url: "https://[official website]"
    what: "Main product page — check for announcements"
  - url: "https://[tokendata URL]"  
    what: "Token data — for price/market queries"

staleness_threshold: monthly  [or: weekly / quarterly / annually]
freshness_note: "[Product] updates [frequently/monthly/quarterly]. For the latest features and roadmap, always check [primary URL]."
```

### Step 3: Mark Volatile Fields
In the KB body, tag fields that change frequently with `[CHECK LIVE]` so the bot knows to search before citing them. Examples:
- Token prices → `[CHECK LIVE — see CoinGecko]`
- Current roadmap status → `[CHECK LIVE — see docs URL]`
- Active grant rounds → `[CHECK LIVE — see deepfunding.ai]`
- Event dates → `[CHECK LIVE — see official calendar]`

### Step 4: Set Confidence Appropriately
- Structural/architectural facts: High
- Mission and team: High
- Product features that are live: Medium (verify against docs)
- Roadmap items: Low (always [CHECK LIVE])
- Token market data: N/A (always Tier 3 redirect)

### Step 5: Register in INDEX.md
Add the new file to INDEX.md with routing keywords and see_also relationships. Include the live_search_trigger keywords in the routing section.

---

## Response Format Standards for Live Data

When giving answers that mix KB baseline with live search:

**Format for stable facts (Tier 1):**
> "[Answer from KB]"

**Format for mixed KB + live data (Tier 2):**
> "[Structural context from KB]. As of [search result date], [current data from search]. For the very latest, see [primary_url]."

**Format for Tier 3 redirects:**
> "For current [token price / live status], check [direct link]. I can tell you about how [project] works — would that help?"

---

## Staleness Tiers by Content Type

| Content Type | Staleness | Protocol |
|---|---|---|
| Token prices / market cap | Hours | Tier 3 — always redirect |
| Active grant rounds | Days–weeks | Tier 2 — search before answering |
| Product features (live) | Weeks–months | Tier 2 — search to confirm |
| Roadmap status | Monthly | Tier 2 — search before answering |
| Event dates | As announced | Tier 2 — search before answering |
| Partnerships | Monthly | Tier 2 — search before answering |
| Platform architecture | Quarterly–annually | Tier 1 — KB reliable |
| Mission and team | Annually | Tier 1 — KB reliable |
| Token merger history | Stable | Tier 1 — KB reliable |
| Token conversion rates | Stable (historical) | Tier 1 — KB reliable |

---

## Change Log

- 2026-04-09 — Initial creation. Defines the three-tier live data protocol and methodology for all ecosystem KB files (KB-08 through KB-13).
