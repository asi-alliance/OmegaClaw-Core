"""ChatGPT / Codex subscription-auth provider for OmegaClaw (opt-in feature).

Reuses the token from a logged-in Codex CLI (``~/.codex/auth.json``) to drive the
OpenAI **Responses API** on the Codex backend, billed against the ChatGPT
subscription instead of a pay-per-token API key. No API key needed: run
``codex login`` once with a ChatGPT account, then start OmegaClaw with
``provider=Codex``.

Mechanism (verified against the official ``openai/codex`` source):
  * token: ``~/.codex/auth.json`` -> ``tokens.access_token`` (Bearer),
    ``tokens.account_id`` (the required ``chatgpt-account-id`` header),
    ``tokens.refresh_token``; refresh via the public OAuth client at
    ``auth.openai.com/oauth/token`` when the access-token JWT is near expiry.
  * inference: ``POST https://chatgpt.com/backend-api/codex/responses`` with a
    Responses-API body (``input`` is a list, ``stream`` must be true) and the
    headers ``openai-beta: responses=experimental`` + ``originator: codex_cli_rs``.

This file is intentionally dependency-free (stdlib only) so it can be tested on
its own and does not rely on the ``openai`` SDK correctly handling the
undocumented backend.

Note: the backend endpoint is internal, so request details and model slugs may
change over time. Treat ``~/.codex/auth.json`` as a credential (don't commit or share it).
"""
import os, json, time, base64, uuid, urllib.request, urllib.error

CODEX_AUTH_PATH = os.path.expanduser(os.environ.get("CODEX_AUTH_PATH", "~/.codex/auth.json"))
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"          # Codex public OAuth client (no secret)
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
CODEX_DEFAULT_MODEL = os.environ.get("CODEX_MODEL", "gpt-5.4")


def _jwt_exp(token: str) -> int:
    """Read the `exp` claim from a JWT access token (no signature check)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return int(json.loads(base64.urlsafe_b64decode(payload)).get("exp", 0))
    except Exception:
        return 0


def _load_auth() -> dict:
    with open(CODEX_AUTH_PATH) as f:
        return json.load(f)


def _refresh(auth: dict) -> dict:
    """Exchange the refresh token for a fresh access token; write auth.json back."""
    body = json.dumps({
        "client_id": CODEX_CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": auth["tokens"]["refresh_token"],
    }).encode()
    req = urllib.request.Request(CODEX_TOKEN_URL, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    auth["tokens"]["access_token"] = data["access_token"]
    if data.get("refresh_token"):
        auth["tokens"]["refresh_token"] = data["refresh_token"]
    auth["last_refresh"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        with open(CODEX_AUTH_PATH, "w") as f:
            json.dump(auth, f)
    except OSError:
        pass  # read-only fs: token still usable for this process
    return auth


def _access_token():
    """Return (access_token, account_id), refreshing if within 60s of expiry."""
    auth = _load_auth()
    token = auth["tokens"]["access_token"]
    if _jwt_exp(token) <= time.time() + 60:
        auth = _refresh(auth)
        token = auth["tokens"]["access_token"]
    return token, auth["tokens"]["account_id"]


class CodexProvider:
    """Duck-typed OmegaClaw AI provider: exposes ``name`` / ``is_available`` / ``chat``."""

    def __init__(self, name: str = "Codex", model_name: str = None):
        self._name = name
        self._model_name = model_name or CODEX_DEFAULT_MODEL

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_available(self) -> bool:
        return os.path.exists(CODEX_AUTH_PATH)

    def _clean_text(self, text: str) -> str:
        return text.replace("_quote_", '"').replace("_apostrophe_", "'")

    def chat(self, content: str, max_tokens: int = 6000, reasoning: str = "medium", **kwargs) -> str:
        if not self.is_available:
            raise RuntimeError("Codex not logged in (run `codex login`; expected ~/.codex/auth.json)")
        # OmegaClaw packs an optional system prompt before the ":-:-:-:" separator.
        if ":-:-:-:" in content:
            sysmsg, usermsg = content.split(":-:-:-:", 1)
        else:
            sysmsg, usermsg = "", content
        usermsg = usermsg.replace(":-:-:-:", " ")
        try:
            token, account_id = _access_token()
            payload = json.dumps({
                "model": self._model_name,
                "instructions": sysmsg,
                "input": [{"type": "message", "role": "user",
                           "content": [{"type": "input_text", "text": usermsg}]}],
                "reasoning": {"effort": reasoning},
                "stream": True,          # the Codex backend rejects non-streaming requests
                "store": False,
            }).encode()
            req = urllib.request.Request(
                CODEX_RESPONSES_URL, data=payload, method="POST",
                headers={
                    "Authorization": f"Bearer {token}",
                    "chatgpt-account-id": account_id,          # required; drop -> 401/403
                    "openai-beta": "responses=experimental",
                    "originator": "codex_cli_rs",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                    "User-Agent": "codex_cli_rs/0.139.0",
                    "session_id": str(uuid.uuid4()),
                })
            chunks = []
            with urllib.request.urlopen(req, timeout=180) as resp:
                for raw in resp:                                # parse the SSE event stream
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except ValueError:
                        continue
                    if event.get("type") == "response.output_text.delta":
                        chunks.append(event.get("delta", ""))
            return self._clean_text("".join(chunks))
        except urllib.error.HTTPError as e:
            detail = e.read()[:400].decode("utf-8", "replace")
            print(f"[lib_codex_auth.CodexProvider.chat] HTTP {e.code}: {detail}")
            return ""
        except Exception as e:
            print(f"[lib_codex_auth.CodexProvider.chat] Exception: {e}")
            return ""


if __name__ == "__main__":
    # Live self-test: `python3 lib_codex_auth.py` (uses your real Codex login).
    p = CodexProvider()
    print("is_available:", p.is_available, "| model:", p._model_name)
    print("reply:", repr(p.chat("Reply with exactly: codex-provider-works")))
