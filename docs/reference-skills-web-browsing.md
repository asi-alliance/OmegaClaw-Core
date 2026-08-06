# Reference — Web Browsing Skills

Defined in `src/webfetch.py`. These skills extend the existing `websearch`
skill with full page content retrieval, link extraction, and a combined
search-and-read workflow.

---

## `webfetch`

### Signature
```metta
(webfetch "url")
```

### Purpose
Fetch a web page and return its readable plain-text content. Strips scripts,
styles, navigation, and boilerplate. Uses
[trafilatura](https://trafilatura.readthedocs.io/) when installed; falls back
to a stdlib `html.parser`-based extractor otherwise.

### Parameters
- `url` — full URL of the page. A leading `https://` is added automatically
  if the scheme is missing.

### Returns
Plain text, truncated to 8 000 characters by default. Returns an empty string
on any HTTP or network error (never raises).

### Examples
```metta
(webfetch "https://en.wikipedia.org/wiki/MeTTa_(programming_language)")
```

After a `websearch` returns a URL:
```metta
(websearch "OpenCog Hyperon architecture")
; → (TITLE: "Hyperon Overview" URL: "https://wiki.opencog.org/..." SNIPPET: "...")
(webfetch "https://wiki.opencog.org/...")
; → Full article text
```

### Notes / Limits
- Default character limit: **8 000**. Longer pages are truncated; the last
  line of the result reads `[... content truncated at N chars ...]`.
- JavaScript-rendered pages (SPAs) will return minimal or empty content
  because `webfetch` does not execute JavaScript. For JS-heavy sites consider
  the Playwright-backed extension described in `docs/tutorial-09-web-browsing.md`.
- Respects `Content-Type` charset headers; decodes with replacement on errors.
- Does **not** store fetched content in long-term memory. Use `remember` if
  you want to persist a snippet.

---

## `weblinks`

### Signature
```metta
(weblinks "url")
```

### Purpose
Fetch a web page and extract its hyperlinks. Useful for discovering subpages,
navigating a site, or building a reading list before calling `webfetch`.

### Parameters
- `url` — full URL of the page to inspect.

### Returns
A MeTTa-style list string:
```
((LINK: <anchor text> URL: <href>) (LINK: ...) ...)
```
Returns an empty string on error. Anchor text is capped at 120 characters.

Automatically resolves:
- Protocol-relative URLs (`//example.com/...` → `https://...`)
- Root-relative paths (`/page` → `https://host/page`)
- Relative paths against the final (post-redirect) URL

Discards: `javascript:`, `mailto:`, `tel:`, and fragment-only (`#...`) links.

### Examples
```metta
(weblinks "https://docs.singularitynet.io/")
; → ((LINK: Introduction URL: https://docs.singularitynet.io/intro)
;    (LINK: API Reference URL: https://docs.singularitynet.io/api) ...)
```

### Notes / Limits
- Returns at most **20** unique links by default.
- Does not recurse; only the links on the given page are returned.

---

## `websearch-and-read`

### Signature
```metta
(websearch-and-read "query")
```

### Purpose
Combines DuckDuckGo search (via the existing `websearch` backend) with
`webfetch` to return the **full content** of the top search results in a
single skill call. Saves the agent two or more round-trips when researching
a topic.

### Parameters
- `query` — the search string, same as for `websearch`.

### Returns
A multi-section string. Each section is prefixed with a source header:
```
=== SOURCE: <page title> | URL: <url> ===
<full page text, up to 4 000 chars>

=== SOURCE: ...
```
Returns an empty string if no results were found or none could be fetched.

### Examples
```metta
(websearch-and-read "Hyperon MeTTa getting started")
```

### Notes / Limits
- Fetches the top **3** results by default, 4 000 characters each.
- Individual pages that return HTTP errors are silently skipped; the call
  still returns the successfully fetched pages.
- Count of pages fetched depends on network availability; do not rely on an
  exact number.
- For higher result quality, `tavily-search` (via Agentverse) remains
  available as an alternative.

---

## Python bridge

All three skills delegate to `src/webfetch.py` via `py-call`:

```metta
(= (webfetch $url)             (py-call (webfetch.fetch $url)))
(= (weblinks $url)             (py-call (webfetch.links $url)))
(= (websearch-and-read $query) (py-call (webfetch.search_and_read $query)))
```

The module is pure stdlib + one optional dependency (`trafilatura`). See
`src/webfetch.py` for full API documentation.

---

## See also

- [reference-skills-communication.md](./reference-skills-communication.md) — `websearch`, `send`, `receive`
- [reference-skills-remote-agents.md](./reference-skills-remote-agents.md) — `tavily-search` (Agentverse-backed alternative)
- [tutorial-09-web-browsing.md](./tutorial-09-web-browsing.md) — end-to-end walkthrough
- [reference-python-bridges.md](./reference-python-bridges.md) — how `py-call` works
