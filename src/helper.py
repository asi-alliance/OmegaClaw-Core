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

def balance_parentheses(s):
    s = s.replace("_quote_", '"')
    sexprs = []
    for line in s.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("(") and line.endswith(")"):
            inner = line[1:-1].strip()
            parts = inner.split(maxsplit=1)
            cmd = parts[0]
            arg = parts[1] if len(parts) > 1 else ""
            if arg:
                arg = arg.strip()
                if not (arg.startswith('"') and arg.endswith('"')): 
                    arg = arg.replace('"', '\\"')
                    line = f'({cmd} "{arg}")'
                else:
                    line = f'({cmd} {arg})'
            else:
                line = f'({cmd})'
            sexprs.append(line)
            continue
        parts = line.split(maxsplit=1)
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else ""
        if arg:
            arg = arg.strip()
            if arg.startswith('"') and arg.endswith('"'):
                sexprs.append(f'({cmd} {arg})')
            else:
                arg = arg.replace('"', '\\"')
                sexprs.append(f'({cmd} "{arg}")')
        else:
            sexprs.append(f'({cmd})')
    ret = " ".join(sexprs)
    return "(" + ret + ")"

def normalize_string(x):
    try:
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="ignore")
        return str(x).encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        return str(x)
