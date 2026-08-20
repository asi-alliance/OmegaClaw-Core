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
_CHANNEL_AUTH_GROUP_FILE = "authenticated-group.json"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_MEMORY_DIRECTORY = str(_REPO_ROOT / "memory")
_user_ID_processed = False


def get_proxy_url():
    global _proxy_url
    if _proxy_url is None:
        configured_url = config_get_by_key("GATEWAY_URL", "")
        _proxy_url = str(configured_url or "").strip().rstrip("/")
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


# ---------------------------------------------------------------------------
# Single-user (owner) authentication.
#
# UNCHANGED from the original implementation, byte for byte. IRC, Slack and
# Mattermost depend on this exact behavior (including the single-use
# _user_ID_processed guard). Telegram now ALSO calls into this same code
# path (see authenticate_channel_user usage in channels/telegram.py) rather
# than duplicating it -- this is the fix for review point #2: Telegram no
# longer has a parallel "chat-based" identity system, it uses the one owner
# identity every other channel uses.
# ---------------------------------------------------------------------------

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


def get_channel_saved_user_id(channel_identifier, user_id):
    # For any single run of OmegaClaw, allow only a single save of a user-id or verification
    global _user_ID_processed
    if _user_ID_processed:
        logger.warning(f"[{channel_identifier}] Warning: a user was already validated, ignoring")
        return False

    # The first persisted record is the owner.  Do not scan later records
    # looking for another matching user: older installations may contain
    # accidental duplicate records, but they must not create extra owners.
    saved_user_id = get_channel_authenticated_user_id(channel_identifier)
    if saved_user_id != str(user_id or "").strip():
        return False

    _user_ID_processed = True
    return True


def authenticate_channel_user(channel_identifier, user_id, auth_candidate=None):
    channel_identifier = str(channel_identifier or "").strip()
    user_id = str(user_id or "").strip()

    # A persisted owner always wins over a reusable secret. This prevents a
    # restart from allowing someone else who knows the secret to replace the
    # original owner.
    saved_user_id = get_channel_authenticated_user_id(channel_identifier)
    if saved_user_id is not None:
        return "allow" if saved_user_id == user_id else "ignore"

    # The secret can establish an owner only before an owner has been saved.
    if auth_candidate is not None and verify_token(auth_candidate):
        label = channel_identifier.upper()
        if store_channel_authenticated_user_id(channel_identifier, user_id):
            logger.info(f"[{label}] Saved authenticated user ID")
            return "auth_bound"
        logger.error(f"[{label}] ERROR -- Unable to save user ID")

    return "ignore"


def get_channel_authenticated_user_id(channel_identifier):
    """
    Read-only owner lookup. Returns the persisted owner user_id for a
    channel, or None if no owner has authenticated yet.

    This is intentionally separate from get_channel_saved_user_id() above:
    that function is single-use per process (it flips _user_ID_processed
    and refuses to check again), which is fine for its original purpose
    but wrong for Telegram's /bind flow, which needs to ask "who is the
    owner?" repeatedly for the life of the process without ever mutating
    state or tripping that guard. Never writes, never touches
    _user_ID_processed.
    """
    channel_identifier = str(channel_identifier or "").strip()
    if not channel_identifier:
        return None
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


# ---------------------------------------------------------------------------
# Telegram-only group authorization (NEW).
#
# Fixes review point #3: the shared secret is NEVER sent or checked inside
# a group. It is only ever used once, to establish the DM owner (via
# authenticate_channel_user above). Opening a group is purely an identity
# check -- does the /bind sender's user_id match the persisted owner? --
# never a credential check. Stored in its own file so this can never read,
# write, or otherwise influence authenticated-user.json.
# ---------------------------------------------------------------------------

def _channel_auth_group_path():
    return os.path.join(_MEMORY_DIRECTORY, _CHANNEL_DIR_NAME, _CHANNEL_AUTH_GROUP_FILE)


def store_channel_authenticated_group_id(channel_identifier, group_id, authorized_by_user_id):
    """Persist a trusted group. Never touches the single-user auth file."""
    channel_identifier = str(channel_identifier or "").strip()
    group_id = str(group_id or "").strip()
    authorized_by_user_id = str(authorized_by_user_id or "").strip()
    if not channel_identifier:
        raise ValueError("channel_identifier is required")
    if not group_id:
        raise ValueError("group_id is required")

    payload = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "channel_identifier": channel_identifier,
        "group_id": group_id,
        "authorized_by": authorized_by_user_id,
    }
    path = _channel_auth_group_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"))
            f.write("\n")
    except OSError as e:
        raise RuntimeError("Failed to write channel authenticated group record") from e
    return True


def get_channel_saved_group_id(channel_identifier, group_id):
    """Return whether a group has already been authorized for this channel."""
    channel_identifier = str(channel_identifier or "").strip()
    group_id = str(group_id or "").strip()
    if not channel_identifier or not group_id:
        return False
    try:
        with open(_channel_auth_group_path(), "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    saved_channel = str(record.get("channel_identifier", "")).strip()
                    saved_group = str(record.get("group_id", "")).strip()
                except (AttributeError, json.JSONDecodeError) as e:
                    logger.warning(f"Skipping malformed channel authenticated group record: {e}")
                    continue
                if saved_channel == channel_identifier and saved_group == group_id:
                    return True
    except FileNotFoundError:
        return False
    except Exception as e:
        raise RuntimeError("Failed to read channel authenticated group records") from e
    return False


def authorize_channel_group(channel_identifier, group_id, requester_user_id):
    """
    Open a group chat to all its members -- but ONLY when requester_user_id
    matches the persisted owner for this channel (see
    get_channel_authenticated_user_id). The shared secret plays no role
    here at all; this is a pure identity check on the /bind sender.
    """
    if get_channel_saved_group_id(channel_identifier, group_id):
        return "allow"

    owner_id = get_channel_authenticated_user_id(channel_identifier)
    if owner_id is None:
        # No owner has authenticated yet -- nobody can open groups.
        return "ignore"

    if str(requester_user_id or "").strip() != owner_id:
        return "ignore"

    if store_channel_authenticated_group_id(channel_identifier, group_id, owner_id):
        logger.info(f"[{str(channel_identifier).upper()}] Saved authorized group ID")
        return "group_bound"

    logger.error(f"[{str(channel_identifier).upper()}] ERROR -- Unable to save group ID")
    return "ignore"
