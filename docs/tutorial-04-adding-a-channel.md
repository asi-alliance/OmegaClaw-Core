# Tutorial 04 — Adding a Channel

**Goal:** plug OmegaClaw into a new communication surface (Slack, Discord, a REST endpoint, a terminal) by writing a channel adapter.

## Prerequisites

- A local clone.
- Familiarity with the existing adapters in `channels/irc.py` and `channels/mattermost.py`.

## The channel contract

A channel adapter is a Python module that exposes:

- `start_<name>(...)` — called once from `initChannels` in `src/channels.metta`. Opens any background threads/sockets needed.
- `getLastMessage()` — returns the most recent unread inbound message as a string, or an empty string if none.
- `send_message(str)` — posts a string outbound.

The MeTTa side in `src/channels.metta` dispatches on the `commchannel` configuration:

```metta
(= (receive)
   (if (== (commchannel) irc)
       (py-call (irc.getLastMessage))
       (py-call (mattermost.getLastMessage))))
```

Your adapter adds another branch to that dispatch.

## 1. Write the adapter

Create `channels/myadapter.py` exposing `start_myadapter`, `getLastMessage`, and `send_message`. Model the file on `channels/irc.py`:

```python
_inbox = []

def start_myadapter(...):
    # open a socket, spawn a listener thread, etc.
    ...

def getLastMessage():
    if _inbox:
        return _inbox.pop(0)
    return ""

def send_message(msg):
    # publish msg to your surface
    ...
```

## 2. Wire it into MeTTa

In `src/channels.metta`:

- Add a `(= (MY_*) (empty))` entry for each runtime parameter your adapter needs.
- Extend `initChannels` with a new branch that calls `configure` and then `(py-call (myadapter.start_myadapter ...))`.
- Extend `(receive)` and `(send $msg)` with corresponding branches.

## 3. Import the module

Make sure the file can be found. The existing adapters are imported by virtue of being in `channels/` and being called via `py-call`. If you need explicit imports, add them alongside the others.

## 4. Select the channel

Set `commchannel` to your new name — either by editing `initChannels` or through an `argk` override on startup.

## Verification

- On startup, logs show your adapter's initialization line.
- Messages sent through your surface land in `getLastMessage()` and trigger a `HUMAN-LAST-MSG` in the loop.
- `(send ...)` calls reach the surface.

## Next steps

- [reference-channels.md](./reference-channels.md) — the full adapter reference.
- [reference-internals-extension-points.md](./reference-internals-extension-points.md) — other extension seams.
