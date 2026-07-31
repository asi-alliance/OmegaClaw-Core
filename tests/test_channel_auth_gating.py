import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CHANNELS_DIRECTORY = REPO_ROOT / "channels"


@pytest.mark.parametrize(
    ("module_name", "arguments"),
    [
        ("irc", ("alice", "hello 🌍")),
        ("telegram", ("chat", "alice", "hello 🌍")),
        ("slack", ("channel", "alice", "hello 🌍")),
        ("mattermost", ("alice", "hello 🌍")),
    ],
)
def test_unbound_plain_message_is_not_used_as_auth_token(monkeypatch, module_name, arguments):
    auth = types.ModuleType("auth")
    auth.is_auth_enabled = lambda: True
    auth.get_channel_saved_user_id = lambda *args: False
    calls = []

    def authenticate_channel_user(*args):
        calls.append(args)
        return "ignore"

    auth.authenticate_channel_user = authenticate_channel_user
    monkeypatch.setitem(sys.modules, "auth", auth)
    config = types.ModuleType("config")
    config.config_get_by_key = lambda key, default=None: default
    monkeypatch.setitem(sys.modules, "config", config)
    monkeypatch.syspath_prepend(str(REPO_ROOT))
    monkeypatch.syspath_prepend(str(CHANNELS_DIRECTORY))
    if module_name == "mattermost":
        monkeypatch.setitem(sys.modules, "requests", types.ModuleType("requests"))
        monkeypatch.setitem(sys.modules, "websocket", types.ModuleType("websocket"))

    path = CHANNELS_DIRECTORY / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"{module_name}_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._is_allowed_message(*arguments) == "ignore"
    assert calls == [(module_name.upper(), "alice", None)]
