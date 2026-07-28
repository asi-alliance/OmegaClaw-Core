# Reference — I/O Skills

Defined in `src/skills.metta`, with the `shell` primitive backed by `src/skills.pl`.

---

## `shell`

### Signature
```metta
(shell "command")
```

### Purpose
Execute a shell command and return its standard output.

### Parameters
- `command` — a string without apostrophes. Apostrophes are rejected by the Prolog helper.

### Returns
The captured stdout of the command as a string.

### Examples
```metta
(shell "ls -la /app")
(shell "python3 --version")
```

### Notes / Limits
- Runs with the permissions of the OmegaClaw process.
- No sandboxing. Run in a container for anything resembling untrusted use.
- Prefer writing complex commands to a file and invoking the file rather than embedding quotes-within-quotes.

---

## `read-file`

### Signature
```metta
(read-file "path")
```

### Purpose
Read a file into a string.

### Parameters
- `path` — absolute or relative filesystem path. MeTTa library paths of the form `(library OmegaClaw-Core ./memory/prompt.txt)` are also accepted (see `getPrompt`).

### Returns
The file's contents as a single string.

### Examples
```metta
(read-file "/tmp/notes.txt")
```

### Notes / Limits
- Fails if the file does not exist (the call checks `exists_file` first).

---

## `write-file`

### Signature
```metta
(write-file "path" "contents")
```

### Purpose
Create or overwrite a file with the given contents.

### Parameters
- `path` — target filesystem path.
- `contents` — the exact bytes to write.

### Returns
`True` on success.

### Examples
```metta
(write-file "/tmp/note.txt" "hello world")
```

### Notes / Limits
- Overwrites unconditionally — there is no confirm step.
- For incremental writes, use `append-file`.

---

## `append-file`

### Signature
```metta
(append-file "path" "line")
```

### Purpose
Append a line to an existing file, followed by a newline.

### Parameters
- `path` — target filesystem path. File must exist.
- `line` — string to append.

### Returns
`True` on success.

### Examples
```metta
(append-file "/tmp/session.log" "turn 42 summary: ...")
```

### Notes / Limits
- Fails if the file does not exist (the call checks `exists_file` first). Create it with `write-file` first if needed.
- A trailing newline is always added.

---

## `get-io-policy`

### Signature

```metta
(get-io-policy)
```

### Purpose

Return the filesystem paths allowed by OmegaClaw's active security policy.

Agent should use this skill before reading, writing, appending, or otherwise modifying a
file when the target path is not known to be allowed.

### Parameters

This skill does not take any parameters. It reads the policy file configured
by the `securityPolicyPath` runtime option.

### Returns

A JSON-formatted string with two fields:

- `read_only` — paths that may be read;
- `read_write` — paths that may be read and modified.

Example:

```json
{
  "read_only": ["/usr", "/opt", "/var/log"],
  "read_write": ["/tmp", "/var/tmp"]
}
```

If no security policy is configured, the skill returns:

```text
Could not retrieve policy: policy is not set
```

If the policy cannot be loaded, it returns:

```text
Could not retrieve a policy: unexpected exception
```

### Examples

```metta
(get-io-policy)
```

A typical workflow before writing a file is:

1. Call `get-io-policy`.
2. Check whether the target path is covered by a `read_write` path.
3. Call `write-file` or `append-file` only if the path is allowed.

### Notes / Limits

- The skill reports configured policy paths; it does not grant permissions.
- Paths in `read_only` must not be used for writing.
- Paths in `read_write` may be read and modified.
- The skill does not check a particular requested path automatically.
- The result contains policy paths, not the contents of the policy file.
- Does not reveal the complete security-policy configuration to the user.
- If a requested path is denied, suggest using `/tmp` when appropriate.
- If `securityPolicyPath` is empty, the skill reports that the policy is not
  set.
