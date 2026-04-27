# Reference — Channels

Channels are the I/O surface the agent uses to talk to the outside world. Adapters live in `channels/`; MeTTa-side dispatch lives in `src/channels.metta`.

## The adapter contract

Each adapter exposes:

| Function | Purpose |
|---|---|
| `start_<name>(...)` | Called once from `initChannels`. Opens sockets / spawns listener threads as needed. |
| `getLastMessage()` | Returns the next unread inbound message as a string. Returns `""` if none. |
| `send_message(str)` | Posts an outbound message. |

The MeTTa side reads `commchannel` and branches:

```metta
(= (receive)
   (if (== (commchannel) irc)
       (py-call (irc.getLastMessage))
       (py-call (mattermost.getLastMessage))))
```

## `channels/irc.py`

IRC adapter with simple one-time-secret authentication.

- `start_irc(channel, server, port, user)` — connect and join.
- Inbound traffic is filtered to the first user who types `auth <one-time-secret>`. All other speakers are ignored.
- Uses QuakeNet (`irc.quakenet.org`) by default.

## `channels/mattermost.py`

Mattermost adapter using a bot token.

- `start_mattermost(url, channel_id, bot_token)` — connect to a Mattermost instance.
- Requires `MM_BOT_TOKEN` configured (empty by default — set via `configure` or command line).

## `channels/websearch.py`

Not a communication channel in the `send`/`receive` sense — this is the backend for the `search` skill. Exposes `search(query)`.

## Adding a new channel

See [tutorial-04-adding-a-channel.md](./tutorial-04-adding-a-channel.md).

## Related reference

- [reference-skills-communication.md](./reference-skills-communication.md) — the MeTTa surface (`send`, `receive`, `search`).
- [reference-configuration.md](./reference-configuration.md) — channel parameters.
