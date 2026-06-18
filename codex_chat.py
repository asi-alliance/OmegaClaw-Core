#!/usr/bin/env python3
"""Interactive chat against your ChatGPT/Codex subscription (the provider=Codex backend).

  python3 codex_chat.py [MODEL]      # interactive REPL (default: gpt-5.4)
  python3 codex_chat.py --selftest   # non-interactive 2-turn memory check

In the REPL:  exit / quit  to leave  ·  /reset  clears history  ·  /model NAME  switches model.
Replies stream live; conversation history is kept so it's a real multi-turn chat.
"""
import sys, json, uuid, urllib.request, urllib.error
from lib_codex_auth import _access_token, CODEX_RESPONSES_URL, CODEX_DEFAULT_MODEL

SYSTEM = "You are a helpful, concise assistant."


def ask(history, model, stream_to=None):
    token, account_id = _access_token()
    body = json.dumps({
        "model": model, "instructions": SYSTEM, "input": history,
        "reasoning": {"effort": "medium"}, "stream": True, "store": False,
    }).encode()
    req = urllib.request.Request(CODEX_RESPONSES_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}", "chatgpt-account-id": account_id,
        "openai-beta": "responses=experimental", "originator": "codex_cli_rs",
        "Content-Type": "application/json", "Accept": "text/event-stream",
        "User-Agent": "codex_cli_rs/0.139.0", "session_id": str(uuid.uuid4()),
    })
    out = []
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                d = line[5:].strip()
                if d == "[DONE]":
                    break
                try:
                    ev = json.loads(d)
                except ValueError:
                    continue
                if ev.get("type") == "response.output_text.delta":
                    delta = ev.get("delta", "")
                    out.append(delta)
                    if stream_to:
                        stream_to.write(delta); stream_to.flush()
    except urllib.error.HTTPError as e:
        msg = e.read()[:300].decode("utf-8", "replace")
        if stream_to:
            stream_to.write(f"[HTTP {e.code}: {msg}]")
        return f"[HTTP {e.code}: {msg}]"
    return "".join(out)


def umsg(t): return {"type": "message", "role": "user",      "content": [{"type": "input_text",  "text": t}]}
def amsg(t): return {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": t}]}


def selftest(model):
    h = []
    h.append(umsg("Remember this number: 42. Reply just 'ok'.")); r1 = ask(h, model); h.append(amsg(r1))
    h.append(umsg("What number did I ask you to remember? Reply with only the number."))
    r2 = ask(h, model)
    print("turn1:", repr(r1)); print("turn2:", repr(r2))
    print("MULTI-TURN MEMORY:", "PASS" if "42" in r2 else "FAIL")


def repl(model):
    print(f"Codex chat — model={model}.  exit/quit · /reset · /model NAME\n")
    h = []
    while True:
        try:
            u = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if u in ("exit", "quit"):
            break
        if not u:
            continue
        if u == "/reset":
            h = []; print("(history cleared)\n"); continue
        if u.startswith("/model "):
            model = u.split(None, 1)[1].strip(); print(f"(model -> {model})\n"); continue
        h.append(umsg(u))
        sys.stdout.write("gpt> ")
        r = ask(h, model, stream_to=sys.stdout); print("\n")
        h.append(amsg(r))


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        rest = [a for a in args if a != "--selftest"]
        selftest(rest[0] if rest else CODEX_DEFAULT_MODEL)
    else:
        repl(args[0] if args else CODEX_DEFAULT_MODEL)
