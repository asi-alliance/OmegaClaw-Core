"""Best-effort secret scrubbing for trace bodies.

Self-contained (stdlib only). ``redact_secrets(text)`` replaces the secret-bearing
portion of common credential shapes with ``[REDACTED]`` while leaving the surrounding
text intact, so an operator who opts into body capture
(``OMEGACLAW_TRACE_BODIES`` / ``OMEGACLAW_DEBUG_LLM_RAW``) still gets a readable trace
without leaking tokens, API keys, or ``Authorization`` headers into the durable JSONL.

Scope is deliberately conservative: only structured, high-signal shapes are matched, so
ordinary prose/code is not mangled. It is a safety net, not a guarantee — never rely on it
to make bodies safe to share publicly.
"""

import re

_PLACEHOLDER = "[REDACTED]"

# Each entry redacts a capture group (group 1 by default, or the named group ``secret``)
# so the label/prefix stays visible and only the sensitive value is removed.
_PATTERNS = (
    # Authorization: Bearer <token>  /  bearer <token>
    re.compile(r"(?i)\b(bearer\s+)(?P<secret>[A-Za-z0-9._~+/=\-]{8,})"),
    # Authorization: <scheme> <token>  and  Authorization= <token>
    re.compile(r"(?i)\b(authorization\s*[:=]\s*)(?P<secret>\S+)"),
    # OpenAI / Anthropic style keys: sk-..., sk-ant-..., sk-proj-...
    re.compile(r"\b(?P<secret>sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{16,})"),
    # AWS access key id
    re.compile(r"\b(?P<secret>AKIA[0-9A-Z]{16})\b"),
    # Google API key
    re.compile(r"\b(?P<secret>AIza[0-9A-Za-z_\-]{35})\b"),
    # Slack tokens
    re.compile(r"\b(?P<secret>xox[baprs]-[A-Za-z0-9\-]{10,})"),
    # GitHub tokens
    re.compile(r"\b(?P<secret>gh[pousr]_[A-Za-z0-9]{20,})"),
    # JSON Web Tokens
    re.compile(r"\b(?P<secret>eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)"),
    # key=value / "key": "value" for common secret-ish names
    re.compile(
        r"(?i)\b(api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|secret|"
        r"client[_-]?secret|password|passwd|pwd|token)\b(\s*[:=]\s*\"?)"
        r"(?P<secret>[^\s\"']{6,})"
    ),
)

# PEM private-key blocks: drop the whole body between the BEGIN/END markers.
_PEM = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----)(.*?)(-----END [A-Z ]*PRIVATE KEY-----)",
    re.DOTALL,
)


def _mask(match):
    span = match.span("secret")
    return match.string[match.start():span[0]] + _PLACEHOLDER + match.string[span[1]:match.end()]


def redact_secrets(text):
    """Return ``text`` with recognizable secrets replaced by ``[REDACTED]``.

    Non-string / falsy input is returned unchanged. Best-effort: any regex failure
    degrades to returning the original text rather than raising.
    """
    if not text or not isinstance(text, str):
        return text
    try:
        redacted = _PEM.sub(r"\1" + _PLACEHOLDER + r"\3", text)
        for pattern in _PATTERNS:
            redacted = pattern.sub(_mask, redacted)
        return redacted
    except Exception:
        return text


if __name__ == "__main__":
    _cases = [
        ("Authorization: Bearer abcdef123456ghijkl", "abcdef123456ghijkl"),
        ("tok Bearer abcdef123456ghijkl", "abcdef123456ghijkl"),
        ("key sk-ant-api03-AAAABBBBCCCCDDDD1234", "sk-ant-api03"),
        ("api_key=supersecretvalue123", "supersecretvalue123"),
        ("password: hunter2hunter2", "hunter2hunter2"),
    ]
    for _text, _leak in _cases:
        _out = redact_secrets(_text)
        assert _PLACEHOLDER in _out, _out
        assert _leak not in _out, _out
    # ordinary prose is untouched
    assert redact_secrets("the quick brown fox jumps over 12 lazy dogs") == \
        "the quick brown fox jumps over 12 lazy dogs"
    print("redaction self-tests passed")
