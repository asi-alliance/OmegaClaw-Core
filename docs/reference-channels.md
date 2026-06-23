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
       (if (== (commchannel) telegram)
           (py-call (telegram.getLastMessage))
           (if (== (commchannel) slack)
               (py-call (slack.getLastMessage))
               (if (== (commchannel) discord)
                   (py-call (discord.getLastMessage))
                   (py-call (mattermost.getLastMessage)))))))
```

## `channels/irc.py`

IRC adapter with simple one-time-secret authentication.

- `start_irc(channel, server, port, user)` — connect and join.
- Inbound traffic is filtered to the first user who types `auth <one-time-secret>`. All other speakers are ignored.
- Uses QuakeNet (`irc.quakenet.org`) by default.

## `channels/mattermost.py`

Mattermost adapter using a bot token.

- `start_mattermost(url, channel_id)` — connect to a Mattermost instance.
- Requires `MM_BOT_TOKEN` environment variable.

## `channels/telegram.py`

Telegram adapter using Bot API long polling.

- `start_telegram(chat_id, poll_timeout)` — starts a poll loop.
- `TG_CHAT_ID` is optional; if empty, the adapter can auto-bind to the first valid inbound chat.
- Outbound messages are chunked to Telegram-safe lengths.

## `channels/slack.py`

Slack adapter using Slack Web API polling.

- `start_slack(channel_id, poll_interval)` — starts a poll loop.
- `SL_CHANNEL_ID` is optional.
- The bot user must already be invited to the target channel.
- If `SL_CHANNEL_ID` is empty, the adapter auto-binds to the first channel where auth succeeds.
- Adapter respects Slack `Retry-After` backoff on HTTP 429 and enforces a minimum 60s poll interval.
- Uses the same one-time `auth <secret>` ownership gate as the other adapters.

## `channels/discord.py`

Discord adapter using the Discord Gateway for inbound messages and the HTTP API for outbound messages.

- `start_discord(channel_id, gateway_intents)` — starts the Gateway listener.
- `DC_CHANNEL_ID` is optional.
- The bot user must be invited to the server/channel or DM where it should receive messages.
- If `DC_CHANNEL_ID` is empty, the adapter auto-binds to the first channel where auth succeeds.
- Requires `DC_BOT_TOKEN`; receiving message text also requires Discord's Message Content privileged intent.
- Outbound messages are chunked below Discord's 2000-character message limit and suppress automatic mentions.
- Create a new Discord application in the developer portal https://discord.com/developers/applications (the Application ID is your bot's Client ID)
- Create a bot token in the bot section for your application by checking "Send messages" and "Read Message History" in the Bot Permissions, enabling "Message Content Intent" and clicking "Reset token" to generate the DC_BOT_TOKEN
- You can use this link to authorize the bot to a Discord server you are allowed to manage: https://discord.com/oauth2/authorize?client_id=<APPLICATION_ID>&scope=bot&permissions=68608
- Adding the bot to private Discord channels requires to go into Edit Channel > Permissions and click "Add Members or Roles" and add the Bot as a member (after authorizing the bot to the Discord server)

## `channels/websearch.py`

Not a communication channel in the `send`/`receive` sense — this is the backend for the `search` skill. Exposes `search(query)`.

## Adding a new channel

See [tutorial-04-adding-a-channel.md](./tutorial-04-adding-a-channel.md).

## Related reference

- [reference-skills-communication.md](./reference-skills-communication.md) — the MeTTa surface (`send`, `receive`, `search`).
- [reference-configuration.md](./reference-configuration.md) — channel parameters.
