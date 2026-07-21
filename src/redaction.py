"""Best-effort secret redaction (extracted from lib_llm_ext.py for Issue #3/#7 reuse).

Stdlib-only, no third-party imports, so both ``lib_llm_ext`` (raw LLM logging) and
``tracing`` (reasoning traces, Issue #7) can share one redactor without pulling in ``openai``.
It detects common secret/token formats plus long base64-ish runs and replaces them with a
typed ``[REDACTED:<kind>]`` marker. Best-effort: it does not guarantee every secret is caught.
"""

import re

_REDACTION_PATTERNS = [
    # Anthropic keys (check before the generic sk- rule).
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")),
    # OpenAI keys, incl. project keys (sk-, sk-proj-).
    ("openai_key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{16,}")),
    # GitHub tokens: ghp_/gho_/ghu_/ghs_/ghr_ and fine-grained github_pat_.
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    # AWS access key id.
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    # HTTP bearer tokens (redact the token, keep the scheme).
    ("bearer", re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{12,}")),
    # Long high-entropy-ish base64/hex runs (>=40 chars). Conservative: requires a
    # contiguous token of base64 alphabet, so normal prose is not mangled.
    ("secret", re.compile(r"\b[A-Za-z0-9+/_\-]{40,}={0,2}\b")),
]


def redact_secrets(text: str) -> str:
    """Replace secret-looking substrings with a typed ``[REDACTED:<kind>]`` marker.

    Best-effort: detects common secret/token formats (known key/token shapes plus
    long base64-ish runs) and leaves ordinary text intact. It does not guarantee
    that every possible secret is caught.
    """
    if not text:
        return text
    out = text
    for kind, pattern in _REDACTION_PATTERNS:
        if kind == "bearer":
            out = pattern.sub(lambda m: f"{m.group(1)}[REDACTED:bearer]", out)
        else:
            out = pattern.sub(f"[REDACTED:{kind}]", out)
    return out


def _selftest():
    """Lightweight self-tests runnable without pytest/Docker."""
    assert redact_secrets("key sk-ant-abcd1234efgh").endswith("[REDACTED:anthropic_key]")
    assert "[REDACTED:openai_key]" in redact_secrets("use sk-proj-ABCDEFGHIJKLMNOP1234")
    assert "[REDACTED:github_token]" in redact_secrets("tok ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345")
    assert "[REDACTED:aws_key]" in redact_secrets("id AKIAIOSFODNN7EXAMPLE here")
    assert "Bearer [REDACTED:bearer]" in redact_secrets("Authorization: Bearer abcdef123456ghijkl")
    assert redact_secrets("just some ordinary text") == "just some ordinary text"
    assert redact_secrets("") == ""
    print("redaction self-tests passed")


if __name__ == "__main__":
    _selftest()
