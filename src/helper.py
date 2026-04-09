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
    filename = "repos/mettaclaw/memory/history.metta"
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
    s = s.replace("_quote_", '"').strip()
    # Find first "((" which should begin the command block
    cmd_start = s.find("((")
    if cmd_start == -1:
        # No command block at all: treat whole thing as narrative
        narrative = s.strip()
        if narrative:
            return f'((pin "{narrative}"))'
        return "(())"
    narrative = s[:cmd_start].strip()
    cmd_part = s[cmd_start:].strip()
    # Normalize outer parentheses of command part
    left = 0
    while left < len(cmd_part) and cmd_part[left] == '(':
        left += 1
    right = 0
    while right < len(cmd_part) and cmd_part[len(cmd_part) - 1 - right] == ')':
        right += 1
    core = cmd_part[left:len(cmd_part) - right if right else len(cmd_part)].strip()
    if narrative:
        narrative = narrative.replace('"', '\\"')
        return f'((pin "{narrative}") {core})'
    else:
        return f"(({core}))"

def normalize_string(x):
    try:
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="ignore")
        return str(x).encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        return str(x)
