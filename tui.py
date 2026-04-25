#!/usr/bin/env python3
"""Minimal terminal UI for Oma — internet-free, no external deps.

Pairs with channels/local.py. Two named pipes carry chat I/O:
  /tmp/oma-in   ← user input typed at this terminal
  /tmp/oma-out  → outbound messages from Oma

Run order doesn't strictly matter — the fifos are created by whichever side
gets there first. Typical workflow:

  # terminal A: launch Oma in local-channel mode
  cd ~/PeTTa && source .venv/bin/activate
  OMEGACLAW_AUTH_SECRET= sh run.sh run.metta provider=Ollama \\
      commchannel=local OLLAMA_MODEL=qwen3:14b

  # terminal B: launch this TUI
  python3 ~/PeTTa/repos/OmegaClaw-Core/tui.py

Slash commands at the prompt:
  /quit            — exit the TUI (Oma keeps running in the other terminal)
  /clear           — clear the screen
  /pid             — show currently running swipl PID + iter count
  anything else    — sent to Oma as a user message

If Oma's prompt.txt or OMEGACLAW_AUTH_SECRET requires an auth handshake, type
`auth <secret>` first; otherwise input is allowed by default.
"""
import os
import sys
import threading
import time
import errno
import subprocess

IN_PATH = "/tmp/oma-in"
OUT_PATH = "/tmp/oma-out"


def ensure_fifo(path):
    if not os.path.exists(path):
        try:
            os.mkfifo(path, 0o600)
        except FileExistsError:
            pass


def reader_loop(stop_event):
    """Tail /tmp/oma-out and print each delimited message to the terminal."""
    while not stop_event.is_set():
        try:
            with open(OUT_PATH, "r") as f:
                buf = []
                for line in f:
                    if stop_event.is_set():
                        return
                    line = line.rstrip("\n")
                    if line == "---":
                        if buf:
                            text = "\n".join(buf).strip()
                            if text:
                                _print_oma(text)
                            buf = []
                    else:
                        buf.append(line)
                if buf:
                    text = "\n".join(buf).strip()
                    if text:
                        _print_oma(text)
        except OSError as e:
            if e.errno in (errno.ENOENT,):
                time.sleep(0.5)
                continue
            time.sleep(0.5)
        except Exception:
            time.sleep(0.5)


def _print_oma(text):
    """Print Oma's reply with a prefix; use ANSI carriage-return so we don't
       trample the in-progress input prompt too badly."""
    sys.stdout.write("\r\033[K")  # clear current line
    sys.stdout.write(f"\033[1;36mOma:\033[0m {text}\n")
    sys.stdout.write("\033[1;32mYou>\033[0m ")
    sys.stdout.flush()


def show_pid_status():
    try:
        out = subprocess.check_output(
            ["pgrep", "-af", "[s]wipl.*main.pl"], text=True
        ).strip()
        if not out:
            print("(no Oma swipl process found — start one in another terminal)")
            return
        line = out.splitlines()[0]
        pid = line.split()[0]
        try:
            with open(f"/proc/{pid}/status") as f:
                rss_kb = next(
                    (int(l.split()[1]) for l in f if l.startswith("VmRSS")), 0
                )
        except Exception:
            rss_kb = 0
        try:
            with open("/tmp/omegaclaw.log") as f:
                iters = sum(1 for l in f if l.startswith("(---------iteration"))
        except Exception:
            iters = -1
        print(f"  swipl pid={pid}  RSS={rss_kb // 1024} MB  iter={iters}")
    except Exception as e:
        print(f"(status lookup failed: {e})")


def main():
    ensure_fifo(IN_PATH)
    ensure_fifo(OUT_PATH)

    print("\033[1;36mOma TUI\033[0m — type a message, Enter to send. /quit to exit.")
    print(f"  in:  {IN_PATH}")
    print(f"  out: {OUT_PATH}")
    print()

    stop_event = threading.Event()
    reader = threading.Thread(target=reader_loop, args=(stop_event,), daemon=True)
    reader.start()

    # Open the input fifo for writing in non-blocking append mode so that
    # Oma's read end disconnecting doesn't crash the TUI.
    while True:
        try:
            sys.stdout.write("\033[1;32mYou>\033[0m ")
            sys.stdout.flush()
            line = sys.stdin.readline()
            if not line:
                break
            line = line.rstrip("\n")
            if not line:
                continue
            if line in ("/quit", "/exit"):
                break
            if line == "/clear":
                sys.stdout.write("\033[2J\033[H")
                continue
            if line == "/pid":
                show_pid_status()
                continue
            try:
                # Open per-write so we don't hold the fifo open across user
                # idle time — that would prevent Oma's reader loop from
                # rotating cleanly.
                with open(IN_PATH, "w") as f:
                    f.write(line + "\n")
            except OSError as e:
                if e.errno == errno.ENXIO:
                    print(f"\033[1;31m(Oma not listening on {IN_PATH} — start it first)\033[0m")
                else:
                    print(f"\033[1;31m(write failed: {e})\033[0m")
        except KeyboardInterrupt:
            print()
            break
        except EOFError:
            break

    stop_event.set()
    print("\nTUI exiting. Oma keeps running.")


if __name__ == "__main__":
    main()
