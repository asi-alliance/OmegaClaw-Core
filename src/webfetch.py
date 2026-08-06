#!/usr/bin/env python3
"""
webfetch.py — Web browsing skill for OmegaClaw-Core.

Extends the existing ``websearch`` skill (DuckDuckGo SERP snippets) with full
page content retrieval, link extraction, and a combined search-and-read helper.

Skills to register in skills.metta
───────────────────────────────────
  webfetch url              — fetch and return readable text from a web page
  weblinks url              — extract hyperlinks from a web page
  websearch-and-read query  — DuckDuckGo search + auto-fetch top results

MeTTa bindings (add to skills.metta):
  (= (webfetch $url)
     (py-call (webfetch.fetch $url)))

  (= (weblinks $url)
     (py-call (webfetch.links $url)))

  (= (websearch-and-read $query)
     (py-call (webfetch.search_and_read $query)))

Static skill descriptions (add to getStaticSkills in skills.metta):
  "- Fetch and read the full text content of a web page by URL: webfetch url"
  "- Extract hyperlinks from a web page: weblinks url"
  "- Search the web and read the full content of the top results: websearch-and-read query"

Dependencies
────────────
All stdlib except one optional library:
  stdlib  : urllib.request, urllib.error, urllib.parse, html.parser, re
  optional: trafilatura (pip install trafilatura) — higher-quality content
            extraction; the module degrades gracefully to a stdlib fallback
            when trafilatura is not installed.

Content safety
──────────────
Fetched page text is returned as plain data — it is NOT executed or
interpreted by this module. Callers (the LLM prompt) should treat web
content as untrusted input and should not follow instructions found in it.
"""

import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Optional

try:
    from src.logger import get_logger
except ModuleNotFoundError:  # imported directly with src/ on the path
    from logger import get_logger

# Optional high-quality content extractor — graceful fallback if absent.
try:
    import trafilatura as _trafilatura
    _HAS_TRAFILATURA = True
except ImportError:
    _HAS_TRAFILATURA = False

# Reuse the existing DuckDuckGo search helper for search_and_read.
try:
    from src.websearch import search_ as _ddgs_search
except ModuleNotFoundError:
    from websearch import search_ as _ddgs_search

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MAX_CHARS = 8000          # default character limit for fetch()
_DEFAULT_MAX_LINKS = 20            # default link count limit for links()
_DEFAULT_SEARCH_RESULTS = 3        # pages to fetch in search_and_read()
_DEFAULT_CHARS_PER_PAGE = 4000     # per-page limit in search_and_read()
_REQUEST_TIMEOUT = 15              # seconds

_USER_AGENT = (
    "Mozilla/5.0 (compatible; OmegaClaw/1.0; "
    "+https://github.com/asi-alliance/OmegaClaw-Core)"
)

# HTML tags whose content should be silently discarded during text extraction.
_SKIP_TAGS = frozenset({
    "script", "style", "noscript", "head", "meta", "link",
    "iframe", "object", "embed", "svg", "form", "button",
    "nav", "footer", "aside", "header",
})

# HTML tags that imply a line-break in the extracted text.
_BLOCK_TAGS = frozenset({
    "p", "div", "br", "li", "dt", "dd", "tr", "h1", "h2",
    "h3", "h4", "h5", "h6", "blockquote", "pre",
})


# ---------------------------------------------------------------------------
# Internal HTML parsers
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Convert HTML to plain readable text (stdlib fallback).

    Strips ``<script>``, ``<style>`` and other non-content tags. Inserts
    newlines at block-level elements so the output retains paragraph structure.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth: int = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped + " ")

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse runs of blank lines and normalise whitespace.
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


class _LinkExtractor(HTMLParser):
    """Extract ``(text, href)`` pairs from ``<a>`` elements."""

    def __init__(self, base_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self._in_a: bool = False
        self._current_href: Optional[str] = None
        self._current_text: list[str] = []
        self.links: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() == "a":
            self._in_a = True
            self._current_href = dict(attrs).get("href", "") or ""
            self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._in_a:
            href = (self._current_href or "").strip()
            text = " ".join("".join(self._current_text).split())
            href = _resolve_url(href, self._base_url)
            if href:
                self.links.append({"text": text or href, "url": href})
            self._in_a = False
            self._current_href = None
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._current_text.append(data)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_url(href: str, base_url: str) -> str:
    """Resolve *href* against *base_url*; return empty string for non-HTTP URLs."""
    if not href:
        return ""
    # Discard anchors, javascript: and mailto: links.
    if href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return ""
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/") and base_url:
        parsed = urllib.parse.urlparse(base_url)
        href = f"{parsed.scheme}://{parsed.netloc}{href}"
    elif not href.startswith(("http://", "https://")):
        # Relative path — resolve against base_url if available.
        if base_url:
            href = urllib.parse.urljoin(base_url, href)
        else:
            return ""
    return href if href.startswith(("http://", "https://")) else ""


def _fetch_raw(url: str, timeout: int = _REQUEST_TIMEOUT) -> tuple[str, str]:
    """
    Perform an HTTP GET request and return ``(body_text, final_url)``.

    Decodes the response body using the charset declared in Content-Type, or
    UTF-8 with replacement on errors. Follows redirects automatically.

    Raises ``urllib.error.URLError`` / ``urllib.error.HTTPError`` on failure.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type", "")
        charset = "utf-8"
        for part in content_type.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                charset = part.split("=", 1)[1].strip().strip('"\'')
                break
        final_url: str = resp.geturl()
        raw: bytes = resp.read()

    return raw.decode(charset, errors="replace"), final_url


def _html_to_text(html: str) -> str:
    """
    Convert HTML to clean plain text.

    Uses *trafilatura* when available (better boilerplate removal), otherwise
    falls back to the stdlib ``_TextExtractor`` parser.
    """
    if _HAS_TRAFILATURA:
        result = _trafilatura.extract(
            html,
            include_links=False,
            include_images=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=False,
        )
        if result:
            return result.strip()

    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def _truncate(text: str, max_chars: int) -> str:
    """Truncate *text* to *max_chars*, preferring to break on a newline."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Try to avoid cutting mid-sentence.
    last_nl = truncated.rfind("\n")
    if last_nl > max_chars * 0.85:
        truncated = truncated[:last_nl]
    return truncated + f"\n\n[... content truncated at {max_chars} chars ...]"


# ---------------------------------------------------------------------------
# Public skill functions (called via py-call from MeTTa)
# ---------------------------------------------------------------------------

def fetch(url: str, max_chars: int = _DEFAULT_MAX_CHARS) -> str:
    """
    Fetch a web page and return its readable text content.

    MeTTa skill: ``webfetch url``

    Parameters
    ----------
    url : str
        Full URL of the page to fetch. A leading ``https://`` is added
        automatically if the scheme is missing.
    max_chars : int, optional
        Maximum number of characters to return (default 8 000).

    Returns
    -------
    str
        Extracted plain text, truncated to *max_chars*; empty string on error.
    """
    try:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        html, final_url = _fetch_raw(url)
        text = _html_to_text(html)

        if not text:
            logger.warning("webfetch: empty content extracted from %r", url)
            return ""

        result = _truncate(text, max_chars)
        logger.info(
            "webfetch: fetched %d chars from %r, returning %d",
            len(text), final_url, len(result),
        )
        return result

    except urllib.error.HTTPError as exc:
        logger.exception("webfetch: HTTP %s for %r: %s", exc.code, url, exc)
        return ""
    except urllib.error.URLError as exc:
        logger.exception("webfetch: URL error for %r: %s", url, exc)
        return ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("webfetch: unexpected error for %r: %s", url, exc)
        return ""


def links(url: str, max_links: int = _DEFAULT_MAX_LINKS) -> str:
    """
    Extract hyperlinks from a web page and return them as a formatted string.

    MeTTa skill: ``weblinks url``

    Parameters
    ----------
    url : str
        Full URL of the page to inspect.
    max_links : int, optional
        Maximum number of unique links to return (default 20).

    Returns
    -------
    str
        MeTTa-style list: ``(LINK: <text> URL: <href>) ...``; empty string on error.
    """
    try:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        html, final_url = _fetch_raw(url)
        extractor = _LinkExtractor(base_url=final_url)
        extractor.feed(html)

        seen: set[str] = set()
        unique: list[dict] = []
        for lnk in extractor.links:
            href = lnk["url"]
            if href not in seen:
                seen.add(href)
                unique.append(lnk)
            if len(unique) >= max_links:
                break

        if not unique:
            logger.info("weblinks: no links found on %r", url)
            return ""

        logger.info("weblinks: found %d unique links on %r", len(unique), final_url)
        parts = [
            f"(LINK: {lnk['text'][:120]} URL: {lnk['url']})"
            for lnk in unique
        ]
        return "(" + " ".join(parts) + ")"

    except Exception as exc:  # noqa: BLE001
        logger.exception("weblinks: failed for %r: %s", url, exc)
        return ""


def search_and_read(
    query: str,
    max_results: int = _DEFAULT_SEARCH_RESULTS,
    max_chars_per_page: int = _DEFAULT_CHARS_PER_PAGE,
) -> str:
    """
    Search the web with DuckDuckGo and return the full text of the top pages.

    MeTTa skill: ``websearch-and-read query``

    This function combines the existing ``websearch`` skill (SERP metadata)
    with ``fetch`` to provide the LLM with the actual page content, not just
    snippets. Each result is prefixed with a source header.

    Parameters
    ----------
    query : str
        Search query string.
    max_results : int, optional
        Number of search results to fetch (default 3).
    max_chars_per_page : int, optional
        Character limit applied to each individual page (default 4 000).

    Returns
    -------
    str
        Combined page texts separated by source headers; empty string on error.
    """
    try:
        results = _ddgs_search(query, max_results=max_results)
    except Exception as exc:  # noqa: BLE001
        logger.exception("search_and_read: search failed for %r: %s", query, exc)
        return ""

    if not results:
        logger.info("search_and_read: no search results for %r", query)
        return ""

    parts: list[str] = []
    for r in results:
        url = r.get("url", "").strip()
        title = r.get("title", url)
        if not url:
            continue

        logger.info("search_and_read: fetching %r", url)
        content = fetch(url, max_chars=max_chars_per_page)
        if content:
            parts.append(f"=== SOURCE: {title} | URL: {url} ===\n{content}")

    if not parts:
        logger.warning("search_and_read: could not read any pages for %r", query)
        return ""

    return "\n\n".join(parts)
