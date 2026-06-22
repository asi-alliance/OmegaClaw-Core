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
