"""Unit tests for channels/discord.py helpers.

These tests avoid Discord network calls and exercise the adapter's local
message filtering and formatting path.
"""
import os
import sys

_PARENT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)
_CHANNELS = os.path.join(_PARENT, "channels")
if _CHANNELS not in sys.path:
    sys.path.insert(0, _CHANNELS)

from channels import discord  # noqa: E402


def _reset_adapter():
    discord._last_message = ""
    discord._channel_id = ""
    discord._bot_user_id = "bot-user"
    discord._authenticated_user_id = None
    discord._message_content_warning_logged = False
    discord._session_id = ""
    discord._resume_gateway_url = ""
    discord._last_sequence = None
    discord._heartbeat_acked = True


def test_message_create_auto_binds_and_formats(monkeypatch):
    _reset_adapter()
    monkeypatch.setattr(discord.auth, "is_auth_enabled", lambda: False)

    discord._handle_message_create(
        {
            "channel_id": "channel-1",
            "content": "hello",
            "author": {"id": "user-1", "username": "alice"},
        }
    )

    assert discord.getLastMessage() == "alice: hello"
    assert discord._channel_id == "channel-1"


def test_message_create_ignores_bot_author(monkeypatch):
    _reset_adapter()
    monkeypatch.setattr(discord.auth, "is_auth_enabled", lambda: False)

    discord._handle_message_create(
        {
            "channel_id": "channel-1",
            "content": "hello",
            "author": {"id": "bot-user", "username": "omegaclaw", "bot": True},
        }
    )

    assert discord.getLastMessage() == ""
    assert discord._channel_id == ""


def test_auth_enabled_requires_auth_command(monkeypatch):
    _reset_adapter()
    monkeypatch.setattr(discord.auth, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(discord.auth, "verify_token", lambda tok: tok == "secret")

    # A plain message before authentication is ignored and not auto-bound.
    assert discord._is_allowed_message("channel-1", "user-1", "hello") == "ignore"
    assert discord._channel_id == ""

    # A wrong token is ignored.
    assert discord._is_allowed_message("channel-1", "user-1", "auth nope") == "ignore"

    # The correct token binds the channel and user.
    assert discord._is_allowed_message("channel-1", "user-1", "auth secret") == "auth_bound"
    assert discord._channel_id == "channel-1"
    assert discord._authenticated_user_id == "user-1"

    # Now only the authenticated user in the bound channel is allowed.
    assert discord._is_allowed_message("channel-1", "user-1", "hi") == "allow"
    assert discord._is_allowed_message("channel-1", "user-2", "hi") == "ignore"
    assert discord._is_allowed_message("channel-2", "user-1", "hi") == "ignore"


def test_display_name_prefers_nick_then_global_then_username():
    author = {"id": "1", "username": "alice", "global_name": "Alice G"}
    assert discord._display_name(author, {"nick": "Ally"}) == "Ally"
    assert discord._display_name(author, {}) == "Alice G"
    assert discord._display_name({"id": "1", "username": "alice"}, {}) == "alice"
    assert discord._display_name({"id": "1"}, {}) == "1"


def test_send_message_chunks_long_text(monkeypatch):
    _reset_adapter()
    discord._channel_id = "channel-1"
    calls = []
    monkeypatch.setattr(
        discord,
        "_api_call",
        lambda method, path, body=None, timeout=30: calls.append(body["content"]),
    )

    text = "x" * (discord._MAX_MESSAGE_LEN + 50)
    discord.send_message(text)

    assert len(calls) == 2
    assert len(calls[0]) == discord._MAX_MESSAGE_LEN
    assert len(calls[1]) == 50
    assert "".join(calls) == text


def test_send_message_noop_without_channel(monkeypatch):
    _reset_adapter()
    monkeypatch.setattr(
        discord,
        "_api_call",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not send")),
    )
    discord.send_message("hello")  # no channel bound -> silently ignored


def test_resume_payload_uses_session_and_sequence(monkeypatch):
    _reset_adapter()
    discord._bot_token = "tok"
    discord._session_id = "sess-123"
    discord._last_sequence = 42
    sent = {}
    monkeypatch.setattr(discord, "_send_gateway_payload", lambda ws, payload: sent.update(payload))

    discord._resume(ws=object())

    assert sent["op"] == 6
    assert sent["d"] == {"token": "tok", "session_id": "sess-123", "seq": 42}


def test_identify_uses_discord_connection_property_keys(monkeypatch):
    _reset_adapter()
    discord._bot_token = "tok"
    discord._gateway_intents = 123
    sent = {}
    monkeypatch.setattr(discord, "_send_gateway_payload", lambda ws, payload: sent.update(payload))

    discord._identify(ws=object())

    assert sent["op"] == 2
    assert sent["d"]["token"] == "tok"
    assert sent["d"]["intents"] == 123
    assert sent["d"]["properties"] == {
        "$os": "linux",
        "$browser": "omegaclaw",
        "$device": "omegaclaw",
    }


def test_decode_close_frame():
    code, reason = discord._decode_close_frame(b"\x0f\xaeintent blocked")

    assert code == 4014
    assert reason == "intent blocked"


def test_gateway_closed_exception_keeps_close_code():
    exc = discord._DiscordGatewayClosed(4014, "code=4014 (disallowed intents)")

    assert exc.code == 4014
    assert str(exc) == "code=4014 (disallowed intents)"


def test_strip_bot_mention_prefix():
    _reset_adapter()
    discord._bot_user_id = "bot-user"

    assert discord._strip_bot_mention("<@bot-user> auth secret") == "auth secret"
    assert discord._strip_bot_mention("<@!bot-user> hello") == "hello"
    assert discord._strip_bot_mention("plain text") == "plain text"


def test_start_discord_requires_websocket(monkeypatch):
    monkeypatch.setattr(discord, "websocket", None)

    try:
        discord.start_discord()
    except RuntimeError as exc:
        assert "websocket-client is required" in str(exc)
    else:
        raise AssertionError("start_discord should fail when websocket-client is missing")
