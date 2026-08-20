# omegaclaw-telegram

A Telegram communication channel for OmegaClaw with media support: the agent can
read images, PDFs and voice notes that users attach, and can generate images and
send them back.

This is the `telegram` channel. It replaces core's earlier HTTP-polling Telegram
channel and keeps everything that one provided — the gateway proxy path, the
outbound retry queue, and the channel auth handshake.

## Capabilities

| Capability | How the agent sees it |
| --- | --- |
| Inbound photo | Message shows `[image]`; the agent calls `describe-image` on demand |
| Inbound PDF | Extracted text is inlined into the message |
| Inbound voice / audio | Whisper transcript is inlined into the message |
| Outbound image | The agent calls `generate-image`, which generates and sends the photo |
| Admin commands | `/kill`, `/pause [chat_id]`, `/togglesearch`, `/purge` (admin IDs only) |
| Safety | Ethics classification on inbound and outbound text, per-user spam throttling |
| Scope limits | `prompt.txt` is added to the agent's prompt as its own section |
| Authorization | `telegram_profile.yaml` chat/DM rules, plus core's auth handshake when enabled |
| Delivery | Outbound messages queue until the bot connects, and are retried on failure |

## Install

**1. Register the plugin** in core's `config/plugins.yaml`:

```yaml
- name: telegram
  loader: metta
  location: "{REPO}/plugins/telegram"
```

The `metta` loader is what lets `telegram.metta` register the plugin's skills and
its prompt section at load time. Core needs no telegram-specific code: the two
media skills are added with `add-skill`, not written into `src/skills.metta`.

**2. Dependencies** are in `requirements.txt`; core's Dockerfile installs every
`plugins/*/requirements.txt` automatically.

**3. Point at your own config if you want to** — `TG_PROFILE_PATH` and
`TG_POLICY_PATH` override where the plugin reads `telegram_profile.yaml` and
`policy.md`, resolved by core from the command line, an `OMEGACLAW_`-prefixed
environment variable, or `config.yaml`. The files shipped here are the defaults;
mounting over them works too and needs no configuration.

**4. Fill in `telegram_profile.yaml`** — it ships permissive defaults that are
**not safe for production**. Set `admin_controls.admin_ids` to the Telegram user
IDs allowed to run admin commands, and `telegram.allowed_chats` to the chat IDs
the bot may operate in. Both are empty by default.

## Use

```sh
sh run.sh run.metta commchannel=telegram provider=OpenRouter \
    embeddingprovider=Local TG_CHAT_ID="$TG_CHAT_ID"
```

`TG_CHAT_ID` is a run argument; `TG_BOT_TOKEN` is read from the environment. Run
only one instance per bot token — a second makes Telegram reject both.

When `GATEWAY_URL` is set the bot talks to the proxy instead of api.telegram.org
and `TG_BOT_TOKEN` stays in the proxy, out of the agent's environment. Media
downloads use a second route, `/telegram-file/`, because Telegram serves files
from a different path prefix than its API methods.

| Variable | Required | Purpose |
| --- | --- | --- |
| `TG_BOT_TOKEN` | yes | Telegram bot token |
| `ANTHROPIC_API_KEY` | for vision | Used by the default vision provider |
| `OPENROUTER_API_KEY` | for image gen + Whisper | Also the vision key if `VISION_PROVIDER=OpenRouter` |
| `OPENAI_API_KEY` | for safety checks | Moderation API; without it the ethics passes allow content through |
| `VISION_PROVIDER` | no | `Anthropic` (default) or `OpenRouter` |
| `VISION_MODEL` | no | Overrides the provider's default vision model |
| `IMAGE_PROVIDER` | no | `OpenRouter` (default, FLUX) or `OpenAI` |
| `IMAGE_MODEL` | no | Overrides the image provider's default model |
| `TG_PROFILE_PATH` | no | Path to the channel profile, defaults to the shipped one |
| `TG_POLICY_PATH` | no | Path to the user-facing policy text, defaults to the shipped one |
| `TG_PROMPT_PATH` | no | Path to the prompt section, defaults to the shipped one |

Vision defaults to Anthropic because an OpenRouter account whose data policy
excludes vision providers gets a 404 on every vision model while text and image
generation keep working.

## Location

The plugin does not have to live inside the core tree. It finds its own files
relative to its module, and reaches core's Python only through modules core puts
on the path, so `location` in `plugins.yaml` can be any absolute path:

```yaml
- name: telegram
  loader: metta
  location: "/opt/omegaclaw-telegram"
```

Verified by loading it from outside the repository with the in-tree copy removed.

## Tests

```sh
for f in tests/test_*.py; do python3 "$f"; done
```

Plain asserts, no framework. Network and Telegram calls are stubbed, so no
credentials are needed.
