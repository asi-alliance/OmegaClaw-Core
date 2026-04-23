# Tutorial 01 — First Run

**Goal:** bring up OmegaClaw on IRC and hold a short conversation.

## Prerequisites

- Docker installed.
- An OpenAI API key (or another LLM provider key if you plan to change `provider`).
- A web browser for [webchat.quakenet.org](https://webchat.quakenet.org).

## 1. Start the container

```bash
curl -fsSL https://raw.githubusercontent.com/asi-alliance/OmegaClaw-Core/refs/heads/main/scripts/omegaclaw \
  | bash -s -- singularitynet/omegaclaw:latest
```

When prompted, paste your API key and enter a unique IRC channel name (e.g. `##my-omegaclaw-test`).

The script prints a **one-time secret** — copy it.

## 2. Join the channel

Open [webchat.quakenet.org](https://webchat.quakenet.org) and join the channel you named above.

## 3. Authenticate

Send exactly once:

```
auth <one-time-secret>
```

The first user to send the correct secret becomes the authenticated user. All other users are silently ignored from this point on.

## 4. Talk to it

Try a few turns:

```
hello, who are you?
remember that my favorite color is green
what is my favorite color?
```

Behind the scenes the model is emitting skill s-expressions like `(remember "user's favorite color is green")` and `(query "favorite color")`. You can watch them scroll by with:

```bash
docker logs -f omegaclaw
```

## 5. Stop and resume

```bash
docker stop omegaclaw     # stop
docker start omegaclaw    # resume, memory intact
```

## Verification

- `docker logs -f omegaclaw` shows `---------iteration N` lines incrementing.
- After a `remember` turn, a later `query`-style question recalls the fact.

## Next steps

- [tutorial-02-teaching-memories.md](./tutorial-02-teaching-memories.md) — go deeper on memory.
- [tutorial-03-shell-and-files.md](./tutorial-03-shell-and-files.md) — give the agent tools.
