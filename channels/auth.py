import hmac
import json
import os
import time
import urllib.request
from pathlib import Path
from config import config_get_by_key

from src.logger import get_logger

logger = get_logger(__name__)

_proxy_url = None
_auth_enabled = None
_CHANNEL_DIR_NAME = ".channel"
_CHANNEL_AUTH_USER_FILE = "authenticated-user.json"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_MEMORY_DIRECTORY = str(_REPO_ROOT / "memory")
_user_ID_processed = False


def get_proxy_url():
    global _proxy_url
    if _proxy_url is None:
        _proxy_url = config_get_by_key("GATEWAY_URL", "").rstrip("/")
    return _proxy_url


def _local_auth_secret():
    return os.environ.get("OMEGACLAW_AUTH_SECRET", "").strip()


def is_auth_enabled():
    global _auth_enabled
    if _auth_enabled is not None:
        return _auth_enabled
    proxy = get_proxy_url()
    if not proxy:
        _auth_enabled = bool(_local_auth_secret())
        return _auth_enabled
    try:
        url = f"{proxy}/auth/status"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            _auth_enabled = data.get("enabled", False)
    except Exception as e:
        logger.warning(f"Could not read auth status from proxy, assuming auth is disabled: {e}")
        _auth_enabled = False
    return _auth_enabled


def verify_token(candidate):
    proxy = get_proxy_url()
    if not proxy:
        secret = _local_auth_secret()
        return bool(secret) and hmac.compare_digest(
            str(candidate).encode("utf-8"), secret.encode("utf-8")
        )
    url = f"{proxy}/auth/verify"
    req = urllib.request.Request(url)
    req.add_header("X-Auth-Token", str(candidate))
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("match", False)
    except Exception as e:
        logger.error(f"Token verification request failed, denying: {e}")
        return False


def _channel_auth_user_path():
    return os.path.join(_MEMORY_DIRECTORY, _CHANNEL_DIR_NAME, _CHANNEL_AUTH_USER_FILE)


def store_channel_authenticated_user_id(channel_identifier, user_id):
    # For any single run of OmegaClaw, allow only a single save of a user-id or verification    
    global _user_ID_processed
    if _user_ID_processed:
        logger.warning(f"[{channel_identifier}] Warning: a user already was validated, ignoring")
        return False    
    channel_identifier = str(channel_identifier or "").strip()
    if not channel_identifier:
        raise ValueError("channel_identifier is required")
    user_id = str(user_id or "").strip()
    if not user_id:
        raise ValueError("user_id is required")
    
    """Record an authenticated channel user ID in the memory directory."""
    payload = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "channel_identifier": channel_identifier,
        "user_id": user_id,
    }
    path = _channel_auth_user_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"))
            f.write("\n")
    except OSError as e:
        raise RuntimeError("Failed to write channel authenticated user record") from e
    _user_ID_processed = True
    return True


def get_channel_authenticated_user_id(channel_identifier):
    """Return the first owner persisted for a channel, if one exists."""
    channel_identifier = str(channel_identifier or "").strip()
    if not channel_identifier:
        raise ValueError("channel_identifier is required")
    try:
        path = _channel_auth_user_path()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    saved_channel_identifier = str(record.get("channel_identifier", "")).strip()
                    saved_user_id = str(record.get("user_id", "")).strip()
                except (AttributeError, json.JSONDecodeError) as e:
                    logger.warning(f"Skipping malformed channel authenticated user record: {e}")
                    continue
                if saved_channel_identifier == channel_identifier and saved_user_id:
                    return saved_user_id
    except FileNotFoundError:
        return None
    except Exception as e:
        raise RuntimeError("Failed to read channel authenticated user records") from e
    return None


def get_channel_saved_user_id(channel_identifier, user_id):
    global _user_ID_processed
    saved_user_id = get_channel_authenticated_user_id(channel_identifier)
    if saved_user_id != str(user_id or "").strip():
        return False
    _user_ID_processed = True
    return True


def authenticate_channel_user(channel_identifier, user_id, auth_candidate=None):
    # A persisted owner takes precedence over the reusable startup secret,
    # including after a process restart.
    saved_user_id = get_channel_authenticated_user_id(channel_identifier)
    if saved_user_id is not None:
        return "allow" if saved_user_id == str(user_id or "").strip() else "ignore"

    # A token is accepted only when it came from an explicit auth command.
    if auth_candidate is not None and verify_token(auth_candidate):
        if store_channel_authenticated_user_id(channel_identifier, user_id):
            label = str(channel_identifier).upper()
            logger.info(f"[{label}] Saved authenticated user ID")
            return "auth_bound"
        else:
            logger.error(f"[{label}] ERROR -- Unable to save user ID")
            return "ignore"
    return "ignore"
