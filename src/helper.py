from collections import deque
import re
from datetime import datetime

TS_RE = re.compile(r'^\("(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"')

def extract_timestamp(line):
    m = TS_RE.search(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

def around_time(needle_time_str, k):
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

def _parse_sexpr_end(s, i):
    """Given s[i] == '(', return index just past the matching ')',
       respecting double-quoted strings. Returns -1 on imbalance."""
    if i >= len(s) or s[i] != "(":
        return -1
    depth = 0
    in_str = False
    esc = False
    while i < len(s):
        c = s[i]
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"':
            in_str = not in_str
        elif not in_str:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return -1


def _try_parse_sexprs(s):
    """Try to parse s as a whitespace-separated sequence of balanced
       s-expressions (each starting with '('). Returns the list of
       expression substrings, or None if the input isn't cleanly s-expr
       shaped (e.g., bare tokens, malformed parens)."""
    s = s.strip()
    if not s:
        return None
    exprs = []
    i = 0
    n = len(s)
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        if s[i] != "(":
            return None
        end = _parse_sexpr_end(s, i)
        if end < 0:
            return None
        exprs.append(s[i:end])
        i = end
    return exprs if exprs else None


def _has_nested_paren(s):
    """True if s contains a '(' nested at depth >= 2 (outside strings),
       i.e. a sub-expression like a kwarg `(name value)` or a nested call.
       Flat positional forms like `(send "hi")` return False and continue
       to the legacy normalization path that quotes bare tokens."""
    in_str = False
    esc = False
    depth = 0
    for c in s:
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"':
            in_str = not in_str
        elif not in_str:
            if c == "(":
                depth += 1
                if depth >= 2:
                    return True
            elif c == ")":
                depth -= 1
    return False


def balance_parentheses(s):
    s = s.replace("_quote_", '"').replace("_newline_", "\n")
    # Fast path: kwarg-shape or otherwise already-structured s-expressions
    # (from lib_llm_ext's JSON→MeTTa adapter, or any model emitting nested
    # forms). Pass through, only adding the outer list wrap. We require a
    # nested '(' so plain positional inputs like `(send "hi")` still flow
    # to the legacy normalizer below for bare-token quoting.
    if _has_nested_paren(s):
        parsed = _try_parse_sexprs(s)
        if parsed is not None:
            return "(" + " ".join(parsed) + ")"
    sexprs = []
    special_two_arg_cmds = {"write-file", "append-file"}
    for line in s.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("(-"):
            line = "(pin -" + line[2:]
        elif line.startswith("-"):
            line = "pin " + line
        # remove one outer (...) if present
        if line.startswith("(") and line.endswith(")"):
            line = line[1:-1].strip()
        parts = line.split(maxsplit=1)
        cmd = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""
        if cmd in special_two_arg_cmds:
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
                    filename = '"' + rest[1:].replace('"', '\\"') + '"'
                    content = ""
            else:
                split_rest = rest.split(maxsplit=1)
                filename = '"' + split_rest[0].replace('"', '\\"') + '"'
                content = split_rest[1].strip() if len(split_rest) > 1 else ""
            if content:
                if content.startswith('"') and content.endswith('"'):
                    sexprs.append(f"({cmd} {filename} {content})")
                else:
                    content = content.replace('"', '\\"')
                    sexprs.append(f'({cmd} {filename} "{content}")')
            else:
                sexprs.append(f"({cmd} {filename})")
            continue
        if rest:
            if rest.startswith('"') and rest.endswith('"'):
                sexprs.append(f"({cmd} {rest})")
            else:
                rest = rest.replace('"', '\\"')
                sexprs.append(f'({cmd} "{rest}")')
        else:
            sexprs.append(f"({cmd})")
    ret = " ".join(sexprs)
    return "(" + ret + ")"

def normalize_string(x):
    try:
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="ignore")
        return str(x).encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        return str(x)

def test_balance_parenthesis():
	assert balance_parentheses('(write-file test.txt hello world)') == '((write-file "test.txt" "hello world"))'
	assert balance_parentheses('(append-file test.txt hello world)') == '((append-file "test.txt" "hello world"))'
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

if __name__ == "__main__":
    test_balance_parenthesis()
