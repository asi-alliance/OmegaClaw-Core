# Reference — Health & Status Endpoint

OmegaClaw exposes its own liveness and high-level state over a small, stable
HTTP interface. This lets anything that orchestrates OmegaClaw (deployment
backends, health monitors, restart supervisors) answer *"is the agent alive,
and what is it doing?"* without SSHing into the container host and scraping
`docker logs`.

The endpoint ships as a plugin under `plugins/health/`, loaded via
`config/plugins.yaml`. `plugins/health/health.py` runs the HTTP server (Python
standard library only); `plugins/health/health.metta` starts it and subscribes
to the loop heartbeat API (`add-heartbeat-listener`), so the reported status is
fed from the agent's actual internal state once per iteration — the core loop
is not modified.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness/readiness probe. |
| `GET` | `/status` | Structured, machine-readable agent state. |

### `GET /health`

Returns `200` while the agent loop is alive (a heartbeat has been recorded
within the staleness window), and `503` when the loop is hung, crashed, or
still starting.

```json
// 200 OK
{ "status": "ok", "agent_status": "thinking", "uptime_seconds": 3600 }

// 503 Service Unavailable
{ "status": "unhealthy", "agent_status": "offline", "uptime_seconds": 3600 }
```

This is suitable as a container/orchestrator health probe: a non-200 response
is a reliable signal to alert or restart.

### `GET /status`

```json
{
  "status": "thinking",
  "current_iteration": 1234,
  "last_activity_at": "2026-06-26T10:30:00Z",
  "uptime_seconds": 3600,
  "version": "v0.1.16"
}
```

| Field | Meaning |
|---|---|
| `status` | High-level state enum (see below). |
| `current_iteration` | The main loop's current iteration counter. |
| `last_activity_at` | UTC ISO-8601 time of the last loop heartbeat, or `null` before the first. |
| `uptime_seconds` | Seconds since the health server started. |
| `version` | Build version (see [Version field](#version-field)). |

---

## Status enum

`status` is a stable string; callers can depend on the exact values.

| Value | Meaning |
|---|---|
| `thinking` | The loop is actively working (`&loops > 0`: processing input or following up). |
| `sleeping` | The loop is idling between wake cycles (`&loops` exhausted), waiting for its next scheduled wake. |
| `idle` | Initial state, before the first heartbeat is recorded. |
| `offline` | No heartbeat within the staleness window — the loop is hung or crashed. Derived by the endpoint, never reported by the loop itself. |

---

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `HEALTH_PORT` | `8081` | TCP port the endpoint binds (`0.0.0.0`). |
| `OMEGACLAW_VERSION` | — | Overrides the `version` field. |

The port is a non-privileged default because the agent runs as the
unprivileged `nobody` user. The container exposes `8081` (`EXPOSE` in the
`Dockerfile`); publish it when running, e.g. `docker run -p 8081:8081 ...`.

Both variables are on the `entrypoint.sh` environment allowlist so they
survive the startup environment scrub.

If the port cannot be bound (e.g. already in use), the failure is logged and
swallowed — the agent keeps running without the endpoint rather than crashing.

### Version field

`version` is resolved in this order, falling back to `"unknown"`:

1. The `OMEGACLAW_VERSION` environment variable.
2. A `VERSION` (or `version.txt`) file at the repository root.

This lets the field return real data once build-time version stamping lands,
without this feature depending on it.

---

## Implementation notes

- The plugin is a MeTTa module (`plugins/health/health.metta`) with a Python
  companion (`plugins/health/health.py`), listed in `config/plugins.yaml` with
  the `metta` loader.
- `loadOmegaClawPlugin` starts the server and registers a heartbeat listener;
  the listener reports the iteration number and status once per loop iteration.
- The server runs in a background daemon thread; it does not block the loop.
- `health.start()` is idempotent, so reloading the plugin will not double-bind.
- A standalone self-test (no docker / MeTTa runtime required) runs with
  `python3 plugins/health/health.py`.
