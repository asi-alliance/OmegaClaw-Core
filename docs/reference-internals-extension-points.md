# Internals — Extension Points

Where to plug in new behavior, in order of increasing depth.

## Add a skill

Most common extension. Two edits:

1. A line in `getSkills` (`src/skills.metta`) so the LLM knows the skill exists.
2. A `(= (my-skill $arg) ...)` definition, either pure MeTTa or a `py-call` / `translatePredicate`.

Full walkthrough: [tutorial-03-writing-a-custom-skill.md](./tutorial-03-writing-a-custom-skill.md).

## Add a remote skill

Same as above, but the body delegates to `src/agentverse.py`:

```metta
(= (my-remote-skill $arg)
   (py-call (agentverse.my_remote_skill $arg)))
```

Full walkthrough: [tutorial-06-remote-agentverse-skills.md](./tutorial-06-remote-agentverse-skills.md).

## Add a channel

Three touch points:

1. New Python module `channels/myadapter.py` implementing `start_*`, `getLastMessage`, `send_message`.
2. A new branch in `initChannels`, `(receive)`, and `(send $msg)` in `src/channels.metta`.
3. New parameters declared via `(= (MY_*) (empty))` and bound by `configure`.

Full walkthrough: [tutorial-04-adding-a-channel.md](./tutorial-04-adding-a-channel.md).

## Add an LLM provider

In `src/loop.metta`, the main dispatch is:

```metta
(if (== (provider) OpenAI)
    (useGPT ...)
    (if (== (provider) Anthropic)
        (py-call (lib_llm_ext.useClaude $send))
        (py-call (lib_llm_ext.useMiniMax $send))))
```

To add a provider:

1. Implement a call function in `lib_llm_ext.py` (or a new module).
2. Add a branch to the `if` chain.
3. Use the new provider name in the `configure provider ...` line or via command-line `provider=...`.

## Change the prompt

The agent's identity and values are in `memory/prompt.txt`. The run-time prompt template that sandwiches it is in `getContext` in `src/loop.metta`. Edit carefully — the output-format instruction is what keeps the LLM producing valid skill s-expressions.

## Change the embedding model

In `src/memory.metta`, the `embed` function dispatches on `embeddingprovider`:

```metta
(= (embed $str)
   (if (== (embeddingprovider) Local)
       (py-call (lib_llm_ext.useLocalEmbedding (string-safe $str)))
       (useGPTEmbedding (string-safe $str))))
```

To add a new backend, add a branch and implement the Python function.

## Change the reasoning library

`lib_nal.metta` and `lib_pln.metta` are plain MeTTa files loaded by `lib_omegaclaw.metta`. Add new rule definitions directly, or swap in a different logic library entirely — the only required surface is whatever operator the LLM invokes through `(metta ...)`.

## See also

- [reference-internals-loop.md](./reference-internals-loop.md) — the loop is the host for all of the above.
- [reference-python-bridges.md](./reference-python-bridges.md) — bridge conventions.
