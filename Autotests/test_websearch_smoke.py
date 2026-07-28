"""
Smoke (OMEGA-140): the web search skill actually returns results.

Runs the real `websearch.search_` inside the container against live
DuckDuckGo (via ddgs), so it catches the OMEGA-138 failure mode where
DuckDuckGo changed its response format and search silently returned an
empty list.
"""
from helpers import dexec


def test_websearch_returns_results():
    code = (
        "import os, sys;"
        "sys.path.insert(0, os.path.join(os.environ['OMEGACLAW_DIR'], 'src'));"
        "import websearch;"
        "print('COUNT', len(websearch.search_('test')))"
    )
    res = dexec("python3", "-c", code)
    assert res.returncode == 0, f"search failed: {res.stderr!r}"
    count = next((int(l.split()[1]) for l in res.stdout.splitlines()
                  if l.startswith("COUNT")), 0)
    assert count > 0, f"search_('test') returned {count}; out={res.stdout!r} err={res.stderr!r}"
