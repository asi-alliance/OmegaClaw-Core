"""Deterministic advisory risk classification for intended OmegaClaw actions.

This module does not execute, inspect, or intercept an action.  It classifies
only the skill name and argument supplied by the caller and never includes the
argument in its result or logs.
"""

import re


READ_ONLY_SKILLS = {
    "action-risk-check",
    "episodes",
    "get-io-policy",
    "query",
    "read-file",
    "search",
    "technical-analysis",
    "tavily-search",
    "version",
    "websearch",
}

STATE_CHANGING_SKILLS = {
    "append-file",
    "metta",
    "pin",
    "remember",
    "send",
    "shell",
    "write-file",
    "write-file-b64",
}

DESTRUCTIVE_PATTERNS = (
    re.compile(r"(?:^|[;&|]\s*|\bsudo\s+)rm\s+(?:[^;&|]*\s)?-(?:[a-z]*r[a-z]*f|[a-z]*f[a-z]*r)\b", re.I),
    re.compile(r"\b(?:docker\s+)?volume\s+(?:rm|remove|prune)\b", re.I),
    re.compile(r"\bdocker\s+(?:system|container)\s+prune\b", re.I),
    re.compile(r"\b(?:drop|truncate)\s+(?:table|database|schema)\b", re.I),
    re.compile(r"\bgit\s+push\b[^\n;&|]*(?:--force(?:-with-lease)?\b|-f(?:\s|$))", re.I),
    re.compile(r"\b(?:delete|destroy|erase|purge)\b[^\n]*(?:persistent\s+data|database|docker\s+volume)\b", re.I),
)

SENSITIVE_PATTERNS = (
    re.compile(r"(?:^|[/\\])\.env(?:\.[^/\\\s]+)?(?:$|[/\\\s])", re.I),
    re.compile(r"(?:^|[/\\])\.ssh(?:$|[/\\\s])", re.I),
    re.compile(r"(?:^|[/\\])id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?(?:$|[/\\\s])", re.I),
    re.compile(r"(?:^|[/\\])(?:credentials?|secrets?)(?:\.[^/\\\s]+)?(?:$|[/\\\s])", re.I),
    re.compile(r"(?:^|[/\\])(?:shadow|passwd)(?:$|[/\\\s])", re.I),
    re.compile(r"\b(?:telegram|openrouter)[_-]?(?:token|api[_-]?key)\b", re.I),
    re.compile(r"\b(?:api[_-]?key|access[_-]?token|private[_-]?key)\s*[=:]", re.I),
)


def _normalize(value):
    return " ".join(str(value).strip().lower().split())


def _matches(patterns, text):
    return any(pattern.search(text) for pattern in patterns)


def check(skill_name, target_or_argument):
    """Return a stable advisory classification without echoing caller input."""
    skill = _normalize(skill_name).replace("_", "-")
    target = _normalize(target_or_argument)

    # Ordered deliberately: a lower-risk category must never weaken a match.
    if _matches(DESTRUCTIVE_PATTERNS, target):
        return "decision=block, risk=critical, reason=destructive-action"
    if _matches(SENSITIVE_PATTERNS, target):
        return "decision=review, risk=high, reason=sensitive-target"
    if skill in STATE_CHANGING_SKILLS:
        return "decision=review, risk=medium, reason=state-changing"
    if skill in READ_ONLY_SKILLS:
        return "decision=allow, risk=low, reason=read-only"
    return "decision=review, risk=medium, reason=unknown-action"
