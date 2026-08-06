# Tutorial 09 — Web Browsing

**Goal:** give the agent the ability to read full web page content, navigate
links, and conduct multi-page research — going beyond the snippet-only
`websearch` skill.

## Prerequisites

- A working OmegaClaw installation (see [README installation section](../README.md#installation)).
- `src/webfetch.py` present in your clone (added by this PR).
- Optional: `pip install trafilatura` for higher-quality content extraction.

---

## Background: `websearch` vs. web browsing

The existing `websearch` skill queries DuckDuckGo and returns titles and
snippets — metadata only. The actual page content is never fetched. This is
fast and cheap but insufficient when the agent needs to:

- Read a full article or documentation page.
- Follow links to discover related resources.
- Verify a claim from a primary source.

The `webfetch`, `weblinks`, and `websearch-and-read` skills close this gap.

---

## Step 1 — Install the optional dependency

`webfetch` works with the Python standard library alone, but
[trafilatura](https://trafilatura.readthedocs.io/) provides significantly
better boilerplate removal (navigation bars, cookie banners, ads):

```sh
pip install "trafilatura>=1.12,<2.0"
```

Or add it to `requirements.txt` (already done in this PR) and reinstall:

```sh
pip install -r requirements.txt
```

---

## Step 2 — Verify the skills are registered

Start the agent and ask:

```
what skills do you have for browsing the web?
```

You should see the agent list `webfetch`, `weblinks`, and
`websearch-and-read` in its reply.

---

## Step 3 — Fetch a single page

Ask the agent:

```
read the content of https://en.wikipedia.org/wiki/Hyperon_(software)
```

The agent should emit:

```metta
(webfetch "https://en.wikipedia.org/wiki/Hyperon_(software)")
```

And return the article text (up to 8 000 characters).

---

## Step 4 — Combined search and read

For research tasks, `websearch-and-read` does everything in one call:

```
what is the latest news about Fetch.ai and SingularityNET merger?
```

The agent will emit:

```metta
(websearch-and-read "Fetch.ai SingularityNET merger 2024")
```

This searches DuckDuckGo, fetches the top 3 results, and returns combined
full-text content with source headers.

---

## Step 5 — Multi-step browsing with link navigation

For a deeper research workflow:

```
find the documentation index for SingularityNET and list the main sections
```

The agent might chain:

```metta
(websearch "SingularityNET developer documentation")
(weblinks "https://dev.singularitynet.io/")
```

Then follow up with:

```metta
(webfetch "https://dev.singularitynet.io/docs/concepts/")
```

---

## Step 6 — Saving findings to memory

Web content is not automatically stored. To persist important facts:

```metta
(websearch-and-read "OpenCog Hyperon AtomSpace design")
(remember "Hyperon AtomSpace is a typed metagraph store that supports ...")
```

---

## Content safety

Fetched page text is returned as **plain data** and injected into
`LAST_SKILL_USE_RESULTS`. The agent should treat it as untrusted input —
it may contain misleading text, but it is never executed.

If you are concerned about prompt injection via web content, you can restrict
`webfetch` to a list of trusted domains by wrapping `webfetch.fetch` with a
domain allowlist before registering the skill.

---

## Limitations and when to use `tavily-search` instead

| Situation | Recommended skill |
|---|---|
| Need page full text | `webfetch` |
| Need to explore site structure | `weblinks` |
| Quick research, want content in one call | `websearch-and-read` |
| Need JS-rendered pages (SPAs, Twitter, etc.) | Playwright extension (not included) |
| Need curated, high-quality research results | `tavily-search` (Agentverse) |
| Query rate-limited by DuckDuckGo | `tavily-search` |

---

## Troubleshooting

**`webfetch` returns an empty string**
- The site may be blocking bots. Try a different URL.
- The page may be JS-rendered (no content without a browser).
- Check the logs for `HTTP 403` or `URLError`.

**Content is mostly navigation / boilerplate**
- Install `trafilatura`: `pip install trafilatura`.
- The stdlib fallback `_TextExtractor` is less accurate on heavily templated pages.

**`websearch-and-read` returns fewer pages than expected**
- Some search results may return HTTP errors (paywalls, bot protection).
  Successfully fetched pages are still returned.

---

## Next steps

- [reference-skills-web-browsing.md](./reference-skills-web-browsing.md) — full API reference.
- [tutorial-07-grounded-reasoning.md](./tutorial-07-grounded-reasoning.md) — using web content to ground symbolic reasoning.
- [reference-internals-extension-points.md](./reference-internals-extension-points.md) — adding a Playwright sidecar for JS-rendered pages.
