# Tutorial 02 — Shell and Files

**Goal:** let OmegaClaw inspect and modify its environment using `shell`, `read-file`, `write-file`, and `append-file`.

## Prerequisites

- A running OmegaClaw (see [Usage](/README.md#usage)).
- Awareness that these skills run with the permissions of the OmegaClaw process.

## The four I/O skills

| Skill | Purpose |
|---|---|
| `(shell "cmd")` | Run a shell command; returns stdout. Apostrophes are not allowed in the argument. |
| `(read-file "path")` | Return the file contents as a string. |
| `(write-file "path" "contents")` | Overwrite the file. |
| `(append-file "path" "line")` | Append a line (with trailing newline) to the file. |

See [reference-skills-io.md](./reference-skills-io.md) for exact signatures.

## 1. Inspect the environment

```
what version of python is available?
```

Expected skill call: `(shell "python3 --version")`.

## 2. Produce a file

```
write a haiku about reasoning under uncertainty to /tmp/haiku.txt
```

Expected: `(write-file "/tmp/haiku.txt" "...")`, then on the next turn `(read-file "/tmp/haiku.txt")` to confirm.

## 3. Keep a running log

```
start a log at /tmp/session.log and append a line summarizing every turn
```

The agent should `(append-file "/tmp/session.log" "...")` on each subsequent turn. Inspect cat `/tmp/session.log`.

## Safety notes

- **Apostrophes in `shell` arguments are rejected** by the Prolog-side `shell` helper. Quote text with double quotes instead, or write it to a file first and operate on the file.
- **There is no sandbox.** If you expose destructive commands (`rm -rf`, etc.) through the shell you will get what you ask for. Run in Docker and treat the container as ephemeral.
- File paths are resolved relative to the OmegaClaw working directory unless absolute.

## Verification

- Log shows a `(shell ...)` call and its captured stdout.
- Files created by `write-file` / `append-file` exist on disk inside the container.

## Next steps

- [tutorial-03-writing-a-custom-skill.md](./tutorial-03-writing-a-custom-skill.md) — extend the surface with your own skill.
- [reference-skills-io.md](./reference-skills-io.md) — full details and edge cases.
