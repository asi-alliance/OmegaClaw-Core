import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTH_MODULE_PATH = REPO_ROOT / "channels" / "auth.py"


def load_auth_module(monkeypatch, gateway_url=""):
    monkeypatch.syspath_prepend(str(REPO_ROOT))
    config_module = types.ModuleType("config")
    config_module.config_get_by_key = (
        lambda key, default=None: gateway_url if key == "GATEWAY_URL" else default
    )
    monkeypatch.setitem(sys.modules, "config", config_module)

    spec = importlib.util.spec_from_file_location("channel_auth_under_test", AUTH_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_standalone_auth_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("OMEGACLAW_AUTH_SECRET", "1234")
    auth = load_auth_module(monkeypatch)

    assert auth.is_auth_enabled() is True
    assert auth.verify_token("9999") is False
    assert auth.verify_token("1234") is True


def test_standalone_auth_without_secret_is_disabled_and_denies(monkeypatch):
    monkeypatch.delenv("OMEGACLAW_AUTH_SECRET", raising=False)
    auth = load_auth_module(monkeypatch)

    assert auth.is_auth_enabled() is False
    assert auth.verify_token("anything") is False


def test_standalone_auth_accepts_unicode_secret(monkeypatch):
    monkeypatch.setenv("OMEGACLAW_AUTH_SECRET", "пароль🔒")
    auth = load_auth_module(monkeypatch)

    assert auth.verify_token("пароль🔒") is True
    assert auth.verify_token("пароль") is False


def test_missing_saved_user_file_means_no_saved_user(monkeypatch, tmp_path):
    auth = load_auth_module(monkeypatch)
    monkeypatch.setattr(auth, "_MEMORY_DIRECTORY", str(tmp_path))

    assert auth.get_channel_saved_user_id("IRC", "alice") is False


def test_corrupt_saved_user_file_is_wrapped(monkeypatch, tmp_path):
    auth = load_auth_module(monkeypatch)
    monkeypatch.setattr(auth, "_MEMORY_DIRECTORY", str(tmp_path))
    path = tmp_path / ".channel" / "authenticated-user.json"
    path.parent.mkdir()
    path.write_bytes(b"\xff")

    with pytest.raises(RuntimeError, match="Failed to read channel authenticated user records"):
        auth.get_channel_saved_user_id("IRC", "alice")


def test_plain_message_does_not_verify_a_token(monkeypatch):
    auth = load_auth_module(monkeypatch)
    monkeypatch.setattr(auth, "verify_token", lambda candidate: pytest.fail("unexpected token check"))
    monkeypatch.setattr(auth, "get_channel_saved_user_id", lambda *args: False)

    assert auth.authenticate_channel_user("IRC", "alice") == "ignore"
