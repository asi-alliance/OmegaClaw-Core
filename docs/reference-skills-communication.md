# Reference — Communication Skills

Defined in `src/channels.metta`. Dispatch depends on the `commchannel` configuration parameter (see [reference-configuration.md](./reference-configuration.md)).

---

## `send`

### Signature
```metta
(send "message")
```

### Purpose
Send a message to the currently active communication channel (IRC or Mattermost by default).

### Parameters
- `message` — the text to send. Newlines are replaced with `\n` before transmission.

### Returns
No meaningful return value. Used for its side effect.

### Examples
```metta
(send "Hello — deployment completed at 10:02.")
```

### Notes / Limits
- **Deduplication:** `send` silently drops the call if `message` is identical to the previous one (`&lastsend` state). Change the text to send a near-duplicate.
- Channel selection is set at `initChannels` time via `commchannel`.

---

## `receive`

### Signature
```metta
(receive)
```

### Purpose
Return the latest message received on the active channel since the previous call. Invoked once per loop iteration by `src/loop.metta`.

### Parameters
None.

### Returns
A string. Empty if nothing new has arrived.

### Examples
The agent does not normally call `receive` itself; the loop wraps it:

```metta
(let $msgrcv (string-safe (repr (receive))) ...)
```

### Notes / Limits
- Delegates to `irc.getLastMessage` or `mattermost.getLastMessage`.
- The loop treats an unchanged message as "no new input" via the `&prevmsg` state.

---

## `search`

### Signature
```metta
(search "query")
```

### Purpose
Perform a web search through the `channels/websearch.py` adapter.

### Parameters
- `query` — the search string.

### Returns
A string of search results suitable for feeding back into the prompt.

### Examples
```metta
(search "MeTTa AtomSpace tutorial")
```

### Notes / Limits
- For research-oriented search through an Agentverse agent, see `tavily-search` in [reference-skills-remote-agents.md](./reference-skills-remote-agents.md).
- Result format depends on the backend used by `websearch.search`.
