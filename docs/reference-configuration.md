# Reference — Configuration

Every tunable in OmegaClaw is declared as `(= (name) (empty))` and later bound by a `configure` call inside an `init*` function. The `configure` helper in `src/utils.metta` is:

```metta
(= (configure $name $default)
   (let $value (argk $name $default)
        (add-atom &self (= ($name) $value))))
```

This reads a command-line override via `argk` (`name=value` on the MeTTa command line) if present, otherwise falls back to the default.

## Loop (`src/loop.metta`, `initLoop`)

| Parameter | Default | Meaning |
|---|---|---|
| `maxNewInputLoops` | 50 | How many turns the agent keeps running after a new human message before idling. |
| `maxWakeLoops` | 1 | Extra turns granted on each scheduled wake-up. |
| `sleepInterval` | 1 (seconds) | Delay between loop iterations. |
| `LLM` | `gpt-5.4` | Model identifier passed to the provider. |
| `provider` | `Anthropic` | LLM provider — `Anthropic`, `OpenAI`, `ASICloud`, or `ASIOne`. |
| `maxOutputToken` | 6000 | Output cap passed to the provider. |
| `reasoningMode` | `medium` | Reasoning-effort hint passed to the provider. |
| `wakeupInterval` | 600 (seconds) | How long idle before the next scheduled wake-up. |

## Memory (`src/memory.metta`, `initMemory`)

| Parameter | Default | Meaning |
|---|---|---|
| `maxFeedback` | 50000 (chars) | Ceiling on `LAST_SKILL_USE_RESULTS` text fed back into the prompt. |
| `maxRecallItems` | 20 | Items returned by `query`. |
| `maxEpisodeRecallLines` | 20 | Lines returned by `episodes`. |
| `maxHistory` | 30000 (chars) | Tail of `memory/history.metta` included in the prompt. |
| `embeddingprovider` | `Local` | `Local` (Python-side model) or `OpenAI`. |

## Channels (`src/channels.metta`, `initChannels`)

| Parameter | Default | Meaning |
|---|---|---|
| `commchannel` | `irc` | Active channel — `irc`, `telegram`, `slack`, `discord`, or `mattermost`. |
| `IRC_channel` | `##omegaclaw` | IRC channel to join. |
| `IRC_server` | `irc.quakenet.org` | IRC server hostname. |
| `IRC_port` | 6667 | IRC port. |
| `IRC_user` | `omegaclaw` | IRC nickname. |
| `TG_CHAT_ID` | *(empty — auto-bind supported)* | Optional fixed Telegram chat ID. Leave empty to auto-bind on first valid inbound auth/message. |
| `TG_POLL_TIMEOUT` | 20 | Telegram long-poll timeout in seconds. |
| `SL_CHANNEL_ID` | *(empty — auto-bind supported)* | Optional Slack channel ID where OmegaClaw reads/writes messages. Leave empty to auto-bind on first valid inbound auth/message. |
| `SL_POLL_INTERVAL` | 60 | Slack poll interval in seconds (minimum effective value is 60). |
| `DC_CHANNEL_ID` | *(empty — auto-bind supported)* | Optional Discord channel ID where OmegaClaw reads/writes messages. Leave empty to auto-bind on first valid inbound auth/message. |
| `DC_GATEWAY_INTENTS` | 37377 | Discord Gateway intent bitmask. The default requests guilds, guild messages, direct messages, and message content. |
| `MM_URL` | `https://chat.singularitynet.io` | Mattermost base URL. |
| `MM_CHANNEL_ID` | `8fjrmabjx7gupy7e5kjznpt5qh` | Target channel ID. |

| Environment variable | Meaning |
|---|---|
| `TG_BOT_TOKEN` | Telegram bot token (from BotFather). |
| `MM_BOT_TOKEN` | Bot auth token. |
| `SL_BOT_TOKEN` | Slack bot token (`xoxb-...`). |
| `DC_BOT_TOKEN` | Discord bot token. The bot must have the Message Content privileged intent enabled to receive message text. |

## Command-line overrides

Any `configure`d parameter can be overridden at startup:

```bash
metta run.metta provider=Anthropic LLM=claude-opus-4-6 commchannel=mattermost
```

Slack example:

```bash
SL_BOT_TOKEN=xoxb-... metta run.metta commchannel=slack SL_CHANNEL_ID=C0123456789
```

Discord example:

```bash
DC_BOT_TOKEN=... metta run.metta commchannel=discord DC_CHANNEL_ID=123456789012345678
```

Docker launch wrapper example:

```bash
DC_BOT_TOKEN=... DC_CHANNEL_ID=123456789012345678 scripts/omegaclaw start -t discord
```

The `argk` helper parses `key=value` pairs from `argv`.
