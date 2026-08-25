import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHANNELS_DIRECTORY = REPO_ROOT / "channels"


def load_telegram(monkeypatch, auth_enabled=True):
    state = {"owner": None, "groups": set()}
    auth = types.ModuleType("auth")
    auth.is_auth_enabled = lambda: auth_enabled
    auth.get_proxy_url = lambda: ""
    auth.get_channel_authenticated_user_id = lambda channel: state["owner"]
    auth.get_channel_saved_group_id = lambda channel, group: (
        channel, str(group)
    ) in state["groups"]

    def authenticate_channel_user(channel, user, candidate=None):
        if candidate != "secret" or state["owner"] is not None:
            return "ignore"
        state["owner"] = str(user)
        return "auth_bound"

    def authorize_channel_group(channel, group, requester):
        if str(requester) != state["owner"]:
            return "ignore"
        state["groups"].add((channel, str(group)))
        return "group_bound"

    def revoke_channel_group(channel, group, requester):
        key = (channel, str(group))
        if str(requester) != state["owner"] or key not in state["groups"]:
            return "ignore"
        state["groups"].remove(key)
        return "group_unbound"

    auth.authenticate_channel_user = authenticate_channel_user
    auth.authorize_channel_group = authorize_channel_group
    auth.revoke_channel_group = revoke_channel_group
    monkeypatch.setitem(sys.modules, "auth", auth)

    config = types.ModuleType("config")
    config.config_get_by_key = lambda _key, default=None: default
    monkeypatch.setitem(sys.modules, "config", config)
    channels = types.ModuleType("channels")
    channels.CommChannel = type("CommChannel", (), {"__init__": lambda self: None})
    channels.registerCommChannel = lambda *_args: None
    monkeypatch.setitem(sys.modules, "channels", channels)
    monkeypatch.syspath_prepend(str(REPO_ROOT))
    monkeypatch.syspath_prepend(str(CHANNELS_DIRECTORY))

    path = CHANNELS_DIRECTORY / "telegram.py"
    spec = importlib.util.spec_from_file_location("telegram_multichat_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reply_uses_the_chat_that_supplied_the_message(monkeypatch):
    telegram = load_telegram(monkeypatch, auth_enabled=False)
    telegram._connected = True
    sent = []
    telegram._api_call = lambda method, params, **_kwargs: sent.append((method, params))

    telegram._enqueue_message("dm message", "dm")
    telegram._enqueue_message("group message", "group")
    assert telegram.getLastMessage() == "dm message"
    assert telegram.getLastMessage() == ""
    telegram.send_message("dm reply")
    assert telegram.getLastMessage() == "group message"
    telegram.send_message("group reply")

    assert [params["chat_id"] for _, params in sent] == ["dm", "group"]


def test_identical_messages_from_different_chats_are_processed(monkeypatch):
    telegram = load_telegram(monkeypatch, auth_enabled=False)
    telegram._connected = True
    sent = []
    telegram._api_call = lambda method, params, **_kwargs: sent.append((method, params))

    telegram._enqueue_message("same message", "dm")
    telegram._enqueue_message("same message", "group")

    assert telegram.getLastMessage() == "same message"
    telegram.send_message("dm reply")
    assert telegram.getLastMessage() == "same message"
    telegram.send_message("group reply")

    assert [params["chat_id"] for _, params in sent] == ["dm", "group"]


def test_failed_delivery_retains_the_original_chat(monkeypatch):
    telegram = load_telegram(monkeypatch, auth_enabled=False)
    telegram._connected = True
    attempts = []

    def flaky_api(method, params, **_kwargs):
        attempts.append((method, params.copy()))
        if len(attempts) == 1:
            raise RuntimeError("temporary failure")

    telegram._api_call = flaky_api
    telegram._enqueue_message("dm message", "dm")
    assert telegram.getLastMessage() == "dm message"

    telegram.send_message("dm reply")
    telegram._enqueue_message("group message", "group")
    assert telegram.getLastMessage() == ""

    telegram._flush_outbox()
    assert telegram.getLastMessage() == "group message"
    assert [params["chat_id"] for _, params in attempts] == ["dm", "dm"]


def test_proactive_message_uses_only_the_configured_default_chat(monkeypatch):
    telegram = load_telegram(monkeypatch, auth_enabled=False)
    telegram._connected = True
    telegram._default_chat_id = "configured-default"
    sent = []
    telegram._api_call = lambda method, params, **_kwargs: sent.append((method, params))

    telegram.send_message("startup message")

    assert sent[0][1]["chat_id"] == "configured-default"


def test_owner_binds_group_without_exposing_secret(monkeypatch):
    telegram = load_telegram(monkeypatch)
    telegram._bot_username = "examplebot"

    # A secret sent in a group cannot establish an owner.
    assert telegram._is_allowed_message("group", "1", "group", "auth secret") == "ignore"
    # The owner authenticates once in a private DM.
    assert telegram._is_allowed_message("dm", "1", "private", "auth secret") == "auth_bound"
    assert telegram._is_allowed_message("dm", "2", "private", "hello") == "ignore"
    # Only that owner can open the group; then every group member is allowed.
    assert telegram._is_allowed_message("group", "2", "group", "/bind") == "ignore"
    assert telegram._is_allowed_message("group", "1", "group", "/bind@ExampleBot") == "group_bound"
    assert telegram._is_allowed_message("group", "2", "group", "hello") == "allow"
    assert telegram._is_allowed_message("other-group", "2", "group", "hello") == "ignore"


def test_bind_command_targets_this_bot_only(monkeypatch):
    telegram = load_telegram(monkeypatch)
    telegram._bot_username = "examplebot"

    assert telegram._is_bind_command("/bind")
    assert telegram._is_bind_command("/authorize_group")

    assert telegram._is_bind_command("/bind@ExampleBot")
    assert telegram._is_bind_command("/BIND@examplebot")
    assert telegram._is_bind_command("/authorize_group@ExampleBot")

    assert not telegram._is_bind_command("/bind@AnotherBot")
    assert not telegram._is_bind_command("/authorize_group@AnotherBot")
    assert not telegram._is_bind_command("/binder@ExampleBot")

    assert telegram._is_unbind_command("/unbind")
    assert telegram._is_unbind_command("/UNBIND@examplebot")
    assert not telegram._is_unbind_command("/unbind@AnotherBot")


def test_only_owner_can_unbind_group(monkeypatch):
    telegram = load_telegram(monkeypatch)
    telegram._bot_username = "examplebot"

    assert telegram._is_allowed_message("dm", "1", "private", "auth secret") == "auth_bound"
    assert telegram._is_allowed_message("group", "1", "group", "/bind") == "group_bound"
    assert telegram._is_allowed_message("group", "2", "group", "/unbind") == "ignore"
    assert telegram._is_allowed_message("group", "2", "group", "hello") == "allow"
    assert telegram._is_allowed_message("group", "1", "group", "/unbind@ExampleBot") == "group_unbound"
    assert telegram._is_allowed_message("group", "2", "group", "hello") == "ignore"


def test_owner_can_unbind_group_from_dm(monkeypatch):
    telegram = load_telegram(monkeypatch)

    assert telegram._is_allowed_message("dm", "1", "private", "auth secret") == "auth_bound"
    assert telegram._is_allowed_message("group", "1", "group", "/bind") == "group_bound"
    assert telegram._is_allowed_message("dm", "1", "private", "/unbind group") == "group_unbound"
    assert telegram._is_allowed_message("group", "2", "group", "hello") == "ignore"


def test_configured_chats_are_a_hard_boundary_when_auth_is_disabled(monkeypatch):
    telegram = load_telegram(monkeypatch, auth_enabled=False)
    telegram._admin_allowed_chats = telegram._parse_admin_allowed_chats(
        "legacy-chat", "group-a, group-b"
    )

    assert telegram._is_allowed_message("legacy-chat", "1", "private", "hello") == "allow"
    assert telegram._is_allowed_message("group-a", "2", "group", "hello") == "allow"
    assert telegram._is_allowed_message("unlisted", "3", "group", "hello") == "ignore"


def test_allowlist_still_permits_owner_dm_bootstrap(monkeypatch):
    telegram = load_telegram(monkeypatch)
    telegram._admin_allowed_chats = {"approved-group"}

    assert telegram._is_allowed_message("owner-dm", "1", "private", "auth secret") == "auth_bound"
    assert telegram._is_allowed_message("owner-dm", "1", "private", "hello") == "allow"
    assert telegram._is_allowed_message("unlisted-group", "2", "group", "hello") == "ignore"
