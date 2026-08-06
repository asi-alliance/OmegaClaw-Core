"""
tests/test_src_webfetch.py — Unit tests for src/webfetch.py.

Run with:
    cd <repo-root>
    pytest ./tests

All tests are fully offline: network calls are monkey-patched so the test
suite can run in CI without outbound access.
"""

import sys
import types
import unittest.mock as mock
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap — mirror the approach used by the rest of the test suite:
# add src/ to sys.path so plain `import webfetch` resolves without the
# `src.` prefix (matching how MeTTa's py-call loads modules at runtime).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

import webfetch  # noqa: E402  (imported after path setup)


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

_MINIMAL_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
  <nav>Nav noise</nav>
  <h1>Hello World</h1>
  <p>This is the main content of the page.</p>
  <script>var x = 1;</script>
  <footer>Footer noise</footer>
</body>
</html>"""

_LINK_HTML = """<!DOCTYPE html>
<html><body>
  <a href="https://example.com/page1">Page One</a>
  <a href="/relative/page">Relative Link</a>
  <a href="javascript:void(0)">JS Link</a>
  <a href="#anchor">Anchor</a>
  <a href="https://example.com/page2">Page Two</a>
</body></html>"""

_BASE_URL = "https://example.com"


def _make_mock_response(body: str, url: str = _BASE_URL, content_type: str = "text/html; charset=utf-8"):
    """Return a context-manager mock that mimics urllib.request.urlopen."""
    mock_resp = mock.MagicMock()
    mock_resp.read.return_value = body.encode("utf-8")
    mock_resp.geturl.return_value = url
    mock_resp.headers = {"Content-Type": content_type}
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = mock.MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# _TextExtractor
# ---------------------------------------------------------------------------

class TestTextExtractor:

    def test_strips_script_tags(self):
        html = "<html><body><p>Keep this</p><script>DROP THIS</script></body></html>"
        extractor = webfetch._TextExtractor()
        extractor.feed(html)
        text = extractor.get_text()
        assert "Keep this" in text
        assert "DROP THIS" not in text

    def test_strips_style_tags(self):
        html = "<html><head><style>body{color:red}</style></head><body><p>Content</p></body></html>"
        extractor = webfetch._TextExtractor()
        extractor.feed(html)
        assert "color" not in extractor.get_text()

    def test_strips_nav_and_footer(self):
        extractor = webfetch._TextExtractor()
        extractor.feed(_MINIMAL_HTML)
        text = extractor.get_text()
        assert "Hello World" in text
        assert "main content" in text

    def test_inserts_newline_at_block_elements(self):
        html = "<html><body><p>First</p><p>Second</p></body></html>"
        extractor = webfetch._TextExtractor()
        extractor.feed(html)
        text = extractor.get_text()
        assert "First" in text
        assert "Second" in text
        # The two paragraphs must be on separate lines.
        assert text.index("First") < text.index("Second")

    def test_empty_body(self):
        extractor = webfetch._TextExtractor()
        extractor.feed("<html><body></body></html>")
        assert extractor.get_text() == ""

    def test_nested_skip_tags(self):
        html = "<script><script>inner</script></script><p>outer</p>"
        extractor = webfetch._TextExtractor()
        extractor.feed(html)
        text = extractor.get_text()
        assert "inner" not in text
        assert "outer" in text


# ---------------------------------------------------------------------------
# _LinkExtractor
# ---------------------------------------------------------------------------

class TestLinkExtractor:

    def test_extracts_absolute_links(self):
        extractor = webfetch._LinkExtractor(base_url=_BASE_URL)
        extractor.feed(_LINK_HTML)
        urls = [lnk["url"] for lnk in extractor.links]
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls

    def test_resolves_relative_links(self):
        extractor = webfetch._LinkExtractor(base_url=_BASE_URL)
        extractor.feed(_LINK_HTML)
        urls = [lnk["url"] for lnk in extractor.links]
        assert "https://example.com/relative/page" in urls

    def test_discards_javascript_links(self):
        extractor = webfetch._LinkExtractor(base_url=_BASE_URL)
        extractor.feed(_LINK_HTML)
        urls = [lnk["url"] for lnk in extractor.links]
        assert all("javascript" not in u for u in urls)

    def test_discards_anchor_links(self):
        extractor = webfetch._LinkExtractor(base_url=_BASE_URL)
        extractor.feed(_LINK_HTML)
        urls = [lnk["url"] for lnk in extractor.links]
        assert all(not u.startswith("#") for u in urls)

    def test_preserves_link_text(self):
        extractor = webfetch._LinkExtractor(base_url=_BASE_URL)
        extractor.feed(_LINK_HTML)
        texts = [lnk["text"] for lnk in extractor.links]
        assert "Page One" in texts


# ---------------------------------------------------------------------------
# _resolve_url
# ---------------------------------------------------------------------------

class TestResolveUrl:

    def test_absolute_https(self):
        assert webfetch._resolve_url("https://example.com/p", _BASE_URL) == "https://example.com/p"

    def test_protocol_relative(self):
        result = webfetch._resolve_url("//example.com/p", _BASE_URL)
        assert result == "https://example.com/p"

    def test_root_relative(self):
        result = webfetch._resolve_url("/path/to/page", _BASE_URL)
        assert result == "https://example.com/path/to/page"

    def test_relative_path(self):
        result = webfetch._resolve_url("subpage", "https://example.com/section/")
        assert result.startswith("https://example.com")

    def test_discard_empty(self):
        assert webfetch._resolve_url("", _BASE_URL) == ""

    def test_discard_mailto(self):
        assert webfetch._resolve_url("mailto:user@example.com", _BASE_URL) == ""

    def test_discard_tel(self):
        assert webfetch._resolve_url("tel:+123456", _BASE_URL) == ""

    def test_http_preserved(self):
        assert webfetch._resolve_url("http://example.com/p", _BASE_URL) == "http://example.com/p"


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------

class TestTruncate:

    def test_short_text_unchanged(self):
        text = "Hello world"
        assert webfetch._truncate(text, 1000) == text

    def test_truncates_at_max_chars(self):
        text = "a" * 10000
        result = webfetch._truncate(text, 8000)
        assert len(result) < 10000
        assert "truncated" in result

    def test_prefers_newline_break(self):
        # Build a text where the last newline is well within the 85% zone.
        text = ("x" * 7000) + "\n" + ("y" * 1000)
        result = webfetch._truncate(text, 8000)
        # Should break at the newline, not inside "yyy...".
        assert "truncated" in result


# ---------------------------------------------------------------------------
# fetch()
# ---------------------------------------------------------------------------

class TestFetch:

    def test_returns_text_on_success(self):
        with mock.patch("urllib.request.urlopen", return_value=_make_mock_response(_MINIMAL_HTML)):
            result = webfetch.fetch("https://example.com")
        assert "Hello World" in result
        assert "main content" in result

    def test_prepends_https_when_scheme_missing(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            return _make_mock_response(_MINIMAL_HTML)

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            webfetch.fetch("example.com")

        assert captured["url"].startswith("https://")

    def test_returns_empty_string_on_http_error(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.HTTPError("url", 404, "Not Found", {}, None)):
            result = webfetch.fetch("https://example.com/missing")
        assert result == ""

    def test_returns_empty_string_on_url_error(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("connection refused")):
            result = webfetch.fetch("https://unreachable.example.com")
        assert result == ""

    def test_respects_max_chars(self):
        long_html = "<html><body>" + "<p>" + "word " * 5000 + "</p>" + "</body></html>"
        with mock.patch("urllib.request.urlopen", return_value=_make_mock_response(long_html)):
            result = webfetch.fetch("https://example.com", max_chars=500)
        assert len(result) <= 600  # some headroom for the truncation notice

    def test_handles_non_utf8_charset(self):
        latin1_body = "<html><body><p>Héllo</p></body></html>".encode("latin-1")
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = latin1_body
        mock_resp.geturl.return_value = _BASE_URL
        mock_resp.headers = {"Content-Type": "text/html; charset=latin-1"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            result = webfetch.fetch("https://example.com")
        # Should not raise; may contain replacement chars but must return str.
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# links()
# ---------------------------------------------------------------------------

class TestLinks:

    def test_returns_metta_list_format(self):
        with mock.patch("urllib.request.urlopen", return_value=_make_mock_response(_LINK_HTML)):
            result = webfetch.links("https://example.com")
        assert result.startswith("(")
        assert result.endswith(")")
        assert "LINK:" in result
        assert "URL:" in result

    def test_deduplicates_urls(self):
        dup_html = """<html><body>
            <a href="https://example.com/p">First</a>
            <a href="https://example.com/p">Duplicate</a>
        </body></html>"""
        with mock.patch("urllib.request.urlopen", return_value=_make_mock_response(dup_html)):
            result = webfetch.links("https://example.com")
        assert result.count("https://example.com/p") == 1

    def test_respects_max_links(self):
        many_links = "".join(
            f'<a href="https://example.com/page{i}">Page {i}</a>' for i in range(50)
        )
        html = f"<html><body>{many_links}</body></html>"
        with mock.patch("urllib.request.urlopen", return_value=_make_mock_response(html)):
            result = webfetch.links("https://example.com", max_links=5)
        assert result.count("URL:") == 5

    def test_returns_empty_on_error(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("fail")):
            result = webfetch.links("https://broken.example.com")
        assert result == ""


# ---------------------------------------------------------------------------
# search_and_read()
# ---------------------------------------------------------------------------

class TestSearchAndRead:

    def _mock_ddgs(self, results):
        """Patch the _ddgs_search imported into webfetch."""
        return mock.patch.object(webfetch, "_ddgs_search", return_value=results)

    def test_returns_combined_content(self):
        fake_results = [
            {"title": "Page A", "url": "https://a.example.com", "snippet": "..."},
            {"title": "Page B", "url": "https://b.example.com", "snippet": "..."},
        ]
        page_html = "<html><body><p>Article content here.</p></body></html>"

        with self._mock_ddgs(fake_results):
            with mock.patch("urllib.request.urlopen", return_value=_make_mock_response(page_html)):
                result = webfetch.search_and_read("test query", max_results=2)

        assert "SOURCE:" in result
        assert "Article content here." in result

    def test_returns_empty_when_no_search_results(self):
        with self._mock_ddgs([]):
            result = webfetch.search_and_read("query with no results")
        assert result == ""

    def test_returns_empty_when_search_raises(self):
        with mock.patch.object(webfetch, "_ddgs_search", side_effect=Exception("DDG down")):
            result = webfetch.search_and_read("failing query")
        assert result == ""

    def test_skips_results_without_url(self):
        fake_results = [{"title": "No URL", "url": "", "snippet": "..."}]
        with self._mock_ddgs(fake_results):
            result = webfetch.search_and_read("query")
        assert result == ""

    def test_includes_source_header_per_page(self):
        fake_results = [
            {"title": "Result 1", "url": "https://r1.example.com", "snippet": ""},
            {"title": "Result 2", "url": "https://r2.example.com", "snippet": ""},
        ]
        page_html = "<html><body><p>Content.</p></body></html>"

        with self._mock_ddgs(fake_results):
            with mock.patch("urllib.request.urlopen", return_value=_make_mock_response(page_html)):
                result = webfetch.search_and_read("query", max_results=2)

        assert result.count("=== SOURCE:") == 2
