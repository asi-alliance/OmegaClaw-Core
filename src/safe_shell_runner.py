import argparse
import json
import os
import signal
import subprocess
import time


def kill_group(pgid, sig):
    try:
        os.killpg(pgid, sig)
        return True
    except ProcessLookupError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=float, default=5.0)
    ap.add_argument('cmd')
    args = ap.parse_args()

    started = time.time()
    p = subprocess.Popen(
        ['/bin/sh', '-lc', args.cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=os.setsid
    )
    pgid = os.getpgid(p.pid)

    status = 'ok'
    try:
        out, err = p.communicate(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        status = 'timeout'
        kill_group(pgid, signal.SIGTERM)
        try:
            out, err = p.communicate(timeout=1.0)
        except subprocess.TimeoutExpired:
            kill_group(pgid, signal.SIGKILL)
            out, err = p.communicate()

    ended = time.time()
    result = {
        'status': status,
        'pid': p.pid,
        'pgid': pgid,
        'exit_code': p.returncode,
        'duration_sec': round(ended - started, 3),
        'stdout': out,
        'stderr': err,
        'note': 'runs each command in a fresh process group and kills the whole group on timeout'
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
