import hashlib
import logging

logger = logging.getLogger(__name__)

_commChannelRegistry = {}


def _authenticated_export_principal() -> str | None:
    if _commchannel_id == "websocket":
        from config import config_get_by_key

        token = str(config_get_by_key("WS_TOKEN", "")).strip()
        if not token:
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return f"websocket:{digest}"

    from auth import get_channel_authenticated_user_id, is_auth_enabled

    if not is_auth_enabled():
        return None
    return get_channel_authenticated_user_id(_commchannel_id.upper())


def handle_control_message(message: str) -> bool:
    from src.memory_export import handle_export_command, is_export_command

    _, separator, command = message.rpartition(": ")
    if not separator:
        command = message
    if not is_export_command(command):
        return False

    try:
        authenticated_principal = _authenticated_export_principal()
    except Exception as exc:
        logger.exception("Failed to resolve memory-export principal: %s", exc)
        authenticated_principal = None

    reply = handle_export_command(command, authenticated_principal)
    if reply is not None:
        try:
            _commchannel.send(reply)
        except Exception as exc:
            logger.exception("Failed to deliver control-message response: %s", exc)
    return True


class CommChannel:
    """Communication channel implementation"""

    def start(self) -> None:
        """Configure and start communication channel"""
        pass

    def stop(self) -> None:
        """Stop communication channel and free resources"""
        pass

    def receive(self) -> str:
        """Receive message from the communication channel"""
        raise NotImplementedError()

    def send(self, message: str) -> None:
        """Send message via the communication channel"""
        raise NotImplementedError()

def registerCommChannel(id: str, channel: CommChannel) -> None:
    """
    Register communication channel in the registry.

    Arguments:
    id: the identifier of the plugin which is used to load it
    channel: the implementation of the channel
    """
    global _commChannelRegistry
    logger.info(f"registerCommChannel: registering communication channel {id}")
    _commChannelRegistry[id] = channel

_commchannel: CommChannel = None
_commchannel_id = ""

def commChannelStart(commchannel):
    """Select and start one of the communication channels registered by
    plugins"""
    global _commchannel, _commchannel_id
    _commchannel = _commChannelRegistry.get(commchannel, None)
    if _commchannel is None:
        error = f"commChannelStart: Communication channel plugin {commchannel} is not registered"
        logger.error(error)
        raise RuntimeError(error)
    _commchannel_id = str(commchannel).lower()
    _commchannel.start()

def commChannelReceive():
    """Receive message from selected communication channel"""
    global _commchannel
    messages = _commchannel.receive().split(" | ")
    return " | ".join(
        message for message in messages if not handle_control_message(message)
    )

def commChannelSend(message):
    """Send message via selected communication channel"""
    global _commchannel
    _commchannel.send(message)
