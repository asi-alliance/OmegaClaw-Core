from collections import deque
import json
import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os

try:
    from src.logger import get_logger
except ModuleNotFoundError:  # running this file directly as a script
    from logger import get_logger

logger = get_logger(__name__)

TS_RE = re.compile(r'^\("(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"')
LLM_COMMANDS = {
    "append-file",
    "clear-frame-junk",
    "compact-frame",
    "complete-goals-ltm",
    "complete-goals-stm",
    "ctx-add-hypothesis",
    "ctx-add-result",
    "episodes",
    "metta",
    "new-autonomous-frame",
    "new-frame",
    "pin",
    "query",
    "read-file",
    "remember",
    "websearch",
    "send",
    "send_probe",
    "shell",
    "show-active-framespace",
    "show-completed-framespace",
    "show-current-frame",
    "show-frame-index",
    "show-frame-relation",
    "show-root-frame",
    "switch-frame",
    "switch-mode",
    "tavily-search",
    "technical-analysis",
    "write-file",
    "get-io-policy",
    "write-file-b64",
}
TWO_ARG_COMMANDS = {
    "write-file",
    "append-file",
    "write-file-b64",
    "ctx-add-hypothesis",
    "ctx-add-result",
}

def compact_plain(value, limit=1200):
    """
    Return a compact, single-line summary with a stable digest.
    This does not write files and does not store to LTM.
    MeTTa decides whether to pin/remember the resulting summary.
    """
    text = normalize_string(value)
    compact = re.sub(r"\s+", " ", text).strip()
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

    if len(compact) > int(limit):
        compact = compact[: int(limit) - 3].rstrip() + "..."

    return f"sha256:{digest[:16]} chars:{len(text)} excerpt:{compact}"


def make_id(prefix="id"):
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}-{stamp}"


def extract_timestamp(line):
    m = TS_RE.search(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        logger.error(f"Line does not carry a parsable timestamp: {e}")
        return None

def around_time(needle_time_str, k):
    needle_time_str = needle_time_str.replace(r'\"', '').replace('"', '').strip()
    filename = "repos/OmegaClaw-Core/memory/history.metta"
    target = datetime.strptime(needle_time_str, "%Y-%m-%d %H:%M:%S")
    best_lineno = None
    best_line = None
    best_diff = None
    buffer = []
    best_idx = None
    with open(filename, "r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            buffer.append((lineno, line))
            ts = extract_timestamp(line)
            if ts is None:
                continue
            diff = abs((ts - target).total_seconds())
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best_lineno = lineno
                best_line = line
                best_idx = len(buffer) - 1
    if best_lineno is None:
        return
    start = max(0, best_idx - k)
    end = min(len(buffer), best_idx + k + 1)
    ret = ""
    for lineno, line in buffer[start:end]:
        ret += f"{lineno}:{line}"
    return ret

def quote_arg(x):
    if x.startswith('"') and x.endswith('"') and "\n" not in x:
        return x
    else:
        return json.dumps(x, ensure_ascii=False)

def starts_command_line(line):
    s = line.lstrip()
    if not s:
        return False
    # allow "(send ...)" as command start too
    if s.startswith("("):
        s = s[1:].lstrip()
    if not s:
        return False
    first = s.split(maxsplit=1)[0].rstrip(")")
    return first in LLM_COMMANDS

def split_command_blocks(s):
    blocks = []
    cur = []
    for raw in s.splitlines():
        if not raw.strip():
            if cur:
                cur.append(raw)
            continue
        if starts_command_line(raw) and cur:
            blocks.append("\n".join(cur).strip())
            cur = [raw]
        else:
            cur.append(raw)
    if cur:
        blocks.append("\n".join(cur).strip())
    return blocks

def balance_parentheses(s):
    s = s.replace("_quote_", '"').replace("_newline_", "\n")
    sexprs = []
    for line in split_command_blocks(s):
        line = line.strip()
        if not line:
            continue
        if line.startswith("(-"):
            line = "(pin " + line[2:]
        elif line.startswith("-"):
            line = "pin " + line[1:]
        # remove one outer (...) if present
        if line.startswith("(") and line.endswith(")"):
            line = line[1:-1].strip()
        elif line.startswith("("):
            line = line[1:].strip()
        parts = line.split(maxsplit=1)
        if not parts:
            continue
        cmd = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""
        if cmd in TWO_ARG_COMMANDS:
            if not rest:
                sexprs.append(f"({cmd})")
                continue
            # filename is first token unless already quoted
            if rest.startswith('"'):
                end = 1
                escaped = False
                while end < len(rest):
                    ch = rest[end]
                    if ch == '"' and not escaped:
                        break
                    escaped = (ch == '\\' and not escaped)
                    if ch != '\\':
                        escaped = False
                    end += 1
                if end < len(rest) and rest[end] == '"':
                    filename = rest[:end+1]
                    content = rest[end+1:].strip()
                else:
                    filename = quote_arg(rest[1:])
                    content = ""
            else:
                split_rest = rest.split(maxsplit=1)
                filename = quote_arg(split_rest[0])
                content = split_rest[1].strip() if len(split_rest) > 1 else ""
            if content:
                sexprs.append(f"({cmd} {filename} {quote_arg(content)})")
            else:
                sexprs.append(f"({cmd} {filename})")
            continue
        if rest:
            sexprs.append(f"({cmd} {quote_arg(rest)})")
        else:
            sexprs.append(f"({cmd})")
    ret = " ".join(sexprs)
    return "(" + ret + ")"

def normalize_string(x):
    try:
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="ignore")
        return str(x).encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    except Exception as e:
        logger.debug(f"Could not normalize value, using its plain string form: {e}")
        return str(x)

def joinPath(parts):
    return os.path.join(*parts)

def projectRootDirectory():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- HyperClaw Context Frames V2 helper additions ----

def cfv2_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _unescape_repr_id(value: str) -> str:
    value = str(value).strip()
    value = value.replace("'", "").replace('"', "")
    value = value.replace("[", "").replace("]", "")
    return value.strip()


def _balanced_exprs(text: str, head: str) -> List[str]:
    """Extract top-level balanced s-expressions whose head is `head`.

    This is a pragmatic parser for scorer/runtime helper use. It is not a full MeTTa parser,
    but it handles strings and nested parentheses well enough for Frame/FrameRef atoms.
    """
    text = str(text)
    starts = []
    token = f"({head}"
    i = 0
    while True:
        idx = text.find(token, i)
        if idx < 0:
            break
        starts.append(idx)
        i = idx + len(token)

    out = []
    for start in starts:
        depth = 0
        in_str = False
        escaped = False
        for j in range(start, len(text)):
            ch = text[j]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    out.append(text[start : j + 1])
                    break
    return out


def _field(expr: str, field_name: str) -> Optional[str]:
    """Return the raw value of a first-level-ish `(field value)` form.

    This intentionally works on the stable constructor format emitted by the MeTTa code.
    """
    pattern = f"({field_name}"
    idx = expr.find(pattern)
    if idx < 0:
        return None
    start = idx + len(pattern)
    # Skip whitespace.
    while start < len(expr) and expr[start].isspace():
        start += 1
    if start >= len(expr):
        return None
    if expr[start] == "(":
        depth = 0
        in_str = False
        escaped = False
        for j in range(start, len(expr)):
            ch = expr[j]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return expr[start : j + 1]
        return None
    if expr[start] == '"':
        escaped = False
        for j in range(start + 1, len(expr)):
            ch = expr[j]
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                return expr[start : j + 1]
        return None
    # Atom/number until whitespace or close paren.
    end = start
    while end < len(expr) and not expr[end].isspace() and expr[end] != ")":
        end += 1
    return expr[start:end]

def cfv2_refs_completed_after(index_repr, date_prefix) -> str:
    """Return completed FrameRefs whose completed-timestamp starts with or compares after date_prefix.

    date_prefix can be YYYY-MM-DD or a longer timestamp prefix. This is intentionally simple.
    """
    prefix = _unescape_repr_id(date_prefix)
    refs = []
    for ref in _balanced_exprs(str(index_repr), "FrameRef"):
        status = _unescape_repr_id(_field(ref, "status") or "")
        t = _unescape_repr_id(_field(ref, "completed-timestamp") or "")
        if status == "Completed" and t and t >= prefix:
            refs.append(ref)
    return "(" + " ".join(refs) + ")"


def cfv2_select_next_frame_id(index_repr, root_mode="Fast") -> str:
    """Select highest-priority active frame matching root mode from FrameRef space.

    If multiple FrameRefs exist for a frame, the last one wins. This supports append-only refs.
    """
    mode = _unescape_repr_id(root_mode)
    latest: Dict[str, Tuple[float, str, str, str]] = {}
    for ref in _balanced_exprs(str(index_repr), "FrameRef"):
        fid = _unescape_repr_id(_field(ref, "frameID") or "")
        status = _unescape_repr_id(_field(ref, "status") or "")
        frame_mode = _unescape_repr_id(_field(ref, "frame-mode") or "")
        space = _unescape_repr_id(_field(ref, "space") or "")
        priority_raw = _unescape_repr_id(_field(ref, "priority") or "0")
        try:
            priority = float(priority_raw)
        except Exception:
            priority = 0.0
        if fid:
            latest[fid] = (priority, status, frame_mode, space)

    best_id = "NON"
    best_priority = float("-inf")
    for fid, (priority, status, frame_mode, space) in latest.items():
        if space == "Active" and status in {"Active", "Focused"} and frame_mode == mode:
            if priority > best_priority:
                best_priority = priority
                best_id = fid
    return best_id

def test_balance_parenthesis():
    assert balance_parentheses('(write-file test.txt hello world)') == '((write-file "test.txt" "hello world"))'
    assert balance_parentheses('(append-file test.txt hello world)') == '((append-file "test.txt" "hello world"))'
    assert balance_parentheses('(write-file-b64 test.txt aGVsbG8=)') == '((write-file-b64 "test.txt" "aGVsbG8="))'
    assert balance_parentheses('write-file-b64 test.txt aGVsbG8=') == '((write-file-b64 "test.txt" "aGVsbG8="))'
    assert balance_parentheses('(write-file "test.txt" hello world)') == '((write-file "test.txt" "hello world"))'
    assert balance_parentheses('(write-file "test.txt" "hello world")') == '((write-file "test.txt" "hello world"))'
    assert balance_parentheses('(write-file test.txt "hello world")') == '((write-file "test.txt" "hello world"))'
    assert balance_parentheses('(send test.xt hello world)') == '((send "test.xt hello world"))'
    assert balance_parentheses('write-file test.txt hello world') == '((write-file "test.txt" "hello world"))'
    assert balance_parentheses('append-file test.txt hello world') == '((append-file "test.txt" "hello world"))'
    assert balance_parentheses('write-file "test.txt" hello world') == '((write-file "test.txt" "hello world"))'
    assert balance_parentheses('write-file "test.txt" "hello world"') == '((write-file "test.txt" "hello world"))'
    assert balance_parentheses('write-file test.txt "hello world"') == '((write-file "test.txt" "hello world"))'
    assert balance_parentheses('send test.xt hello world') == '((send "test.xt hello world"))'
    assert balance_parentheses('send Here are the planets:\n1. Mercury\n2. Venus') == '((send "Here are the planets:\\n1. Mercury\\n2. Venus"))'
    assert balance_parentheses('send Here are the options:\n- MacBook Air\n- ThinkPad X1\npin done') == '((send "Here are the options:\\n- MacBook Air\\n- ThinkPad X1") (pin "done"))'
    assert balance_parentheses('send "Plain text version:"\n**Mars** - red planet\nNote: Pluto is a dwarf planet') == '((send "\\\"Plain text version:\\\"\\n**Mars** - red planet\\nNote: Pluto is a dwarf planet"))'
    assert balance_parentheses('(send Here are the planets:\n1. Mercury\n2. Venus)') == '((send "Here are the planets:\\n1. Mercury\\n2. Venus"))'
    assert balance_parentheses('send "hello" world') == '((send "\\"hello\\" world"))'
    assert balance_parentheses('send "Hello"\nHow are you?') == '((send "\\"Hello\\"\\nHow are you?"))'
    # bare "()" lines yield no tokens after _strip_outer_parens and must be skipped, not crash
    assert balance_parentheses('()') == '()'
    assert balance_parentheses('') == '()'
    assert balance_parentheses('   ') == '()'
    assert balance_parentheses('()\nsend hello') == '((send "hello"))'
    assert balance_parentheses('write-file "test.txt" hello\nworld') == '((write-file "test.txt" "hello\\nworld"))'
    assert balance_parentheses('- Found a bug') == '((pin "Found a bug"))'
    assert balance_parentheses('(- Found a bug)') == '((pin "Found a bug"))'
    assert balance_parentheses('- Found\na\nbug') == '((pin "Found\\na\\nbug"))'
    assert balance_parentheses('(- Found a bug') == '((pin "Found a bug"))'

if __name__ == "__main__":
    test_balance_parenthesis()
