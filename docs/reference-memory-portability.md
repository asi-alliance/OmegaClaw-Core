# Reference - Memory Portability

Memory portability lets an operator export persistent user memory from one
deployment and restore it before another agent starts. It is an operator
workflow, not an LLM skill.

## Setup

Choose an absolute host directory for archives. The launcher creates it when
needed and mounts it at the fixed container path `/memory-transfer`; the agent
never accepts arbitrary runtime export paths.

```sh
scripts/omegaclaw start -p OpenAI -t telegram \
  --memory-transfer-dir "$HOME/omegaclaw-transfers" \
  --enable-memory-export
```

`--enable-memory-export` is required because export is disabled by default.
The transfer directory must be writable by the container's agent user.

## Export

In a supported chat, request one component and confirm the returned short-lived
token. When channel authentication is active, only the authenticated owner can
use these commands. When it is disabled, normal channel access rules apply:

```text
/memory-export history
/memory-export ltm
/memory-export both
/memory-export confirm <token>
```

The confirmed export runs immediately in the channel harness. Completion is
delivered to the requester and includes the filename, record count, size, and
SHA-256.

Archives contain selected persistent user memory only:

```text
manifest.json
history/history.metta
vector/collections.json
vector/records.jsonl
```

History is the conversation trace. LTM is logical user-memory records from
ChromaDB. Prompts, credentials, logs, skills, and other operational state are
not exported. SHA-256 detects corruption, not archive authorship.

## Import

Import is an administrative startup operation. The archive argument is a plain
filename in the chosen transfer directory:

```sh
scripts/omegaclaw start -d singularitynet/omegaclaw:<tag> -p OpenAI -t telegram \
  --memory-transfer-dir "$HOME/omegaclaw-transfers" \
  --memory-import omegaclaw-memory-<timestamp>.tar.gz \
  --memory-mode overwrite
```

`overwrite` replaces the selected components after validation and rollback
preparation. `append` preserves existing history and adds imported LTM records
under new IDs. Select components with `--only-history`, `--no-history`, or
`--no-vector`.

The importer validates archive paths, checksums, manifest metadata, record
counts, and embedding compatibility before changing live memory. It runs before
the agent loop starts. A receipt prevents a completed archive import from
running again on container restart.

## Limits

Memory export commands are not supported on the WebSocket chat channel.
Archives are private operator data; keep the host transfer directory protected.
