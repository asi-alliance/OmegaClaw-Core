import logging

logger = logging.getLogger(__name__)

_commChannelRegistry = {}


def handle_control_message(message: str) -> bool:
    from auth import get_channel_authenticated_user_id, is_auth_enabled
    from memory_export import handle_export_command, is_export_command

    sender, separator, command = message.rpartition(": ")
    if not separator:
        command = message
    if not is_export_command(command):
        return False

    authenticated_user_id = None
    if is_auth_enabled():
        authenticated_user_id = get_channel_authenticated_user_id(
            _commchannel_id.upper()
        )
    owner = authenticated_user_id or sender.strip() or "owner"
    owner_key = f"{_commchannel_id}:{owner}"
    if _commchannel_id == "websocket":
        reply = "Memory export is not supported on the WebSocket channel."
    else:
        reply = handle_export_command(command, owner_key)
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
        raise NotImplementedError()

    def stop(self) -> None:
        """Stop communication channel and free resources"""
        raise NotImplementedError()

    def receive(self) -> str:
        """Receive message from the communication channel"""
        raise NotImplementedError()

    def send(self, message: str) -> None:
        """Send message via the communication channel"""
        raise NotImplementedError()

def registerCommChannel(id: str, channel: CommChannel) -> None:
    """Register communication channel in the registry"""
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
        _error("commChannelStart", f"Communication channel plugin {commchannel} is not registered")
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
